import base64
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from modules.auth import require_session
from modules.omedia import DABA, log_audit, validate_csrf

Mailer = APIRouter(prefix="/api/v1/mail", tags=["MOHA Gmail Engine"])

ATTACHMENT_STORAGE = Path("workspace/mail_storage/attachments")
ATTACHMENT_STORAGE.mkdir(parents=True, exist_ok=True)
MAX_STORAGE_PER_USER_BYTES = 10 * 1024 * 1024 * 1024

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


async def init_moha_engine_db():
    async with aiosqlite.connect(DABA) as db:
        await db.execute("PRAGMA foreign_keys = ON;")

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS moha_threads (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                subject TEXT DEFAULT '',
                last_message_timestamp REAL NOT NULL,
                snippet TEXT DEFAULT '',
                message_count INTEGER DEFAULT 1
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS moha_messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                message_id_header TEXT UNIQUE NOT NULL,
                in_reply_to TEXT,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                cc TEXT DEFAULT '',
                bcc TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                body_plain TEXT DEFAULT '',
                body_html TEXT DEFAULT '',
                timestamp REAL NOT NULL,
                is_draft INTEGER DEFAULT 0,
                size_bytes INTEGER DEFAULT 0,
                FOREIGN KEY(thread_id) REFERENCES moha_threads(id) ON DELETE CASCADE
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS moha_labels (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'user'
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS moha_message_labels (
                message_id TEXT NOT NULL,
                label_id TEXT NOT NULL,
                PRIMARY KEY (message_id, label_id),
                FOREIGN KEY(message_id) REFERENCES moha_messages(id) ON DELETE CASCADE,
                FOREIGN KEY(label_id) REFERENCES moha_labels(id) ON DELETE CASCADE
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS moha_attachments (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                checksum_sha256 TEXT,
                FOREIGN KEY(message_id) REFERENCES moha_messages(id) ON DELETE CASCADE
            )
            """
        )

        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS moha_fts USING fts5(
                message_id UNINDEXED,
                sender,
                recipient,
                subject,
                body
            );
            """
        )

        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_thread ON moha_messages(thread_id);"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON moha_messages(timestamp);"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_sender ON moha_messages(sender);"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_recipient ON moha_messages(recipient);"
        )

        await db.commit()


def generate_rfc822_message_id(domain: str = "company.org") -> str:
    return f"<{uuid.uuid4().hex}.moha@{domain}>"


async def ensure_system_labels(db: aiosqlite.Connection, user_email: str):
    system_labels = [
        "INBOX",
        "SENT",
        "DRAFT",
        "SPAM",
        "TRASH",
        "STARRED",
        "UNREAD",
        "IMPORTANT",
    ]
    for label in system_labels:
        label_id = f"sys_{user_email}_{label.lower()}"
        await db.execute(
            """
            INSERT OR IGNORE INTO moha_labels (id, user_email, name, type)
            VALUES (?, ?, ?, 'system')
            """,
            (label_id, user_email, label),
        )


async def index_message_fts(
    db: aiosqlite.Connection,
    msg_id: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
):
    await db.execute(
        "INSERT INTO moha_fts (message_id, sender, recipient, subject, body) VALUES (?, ?, ?, ?, ?)",
        (msg_id, sender, recipient, subject, body),
    )


@Mailer.post("/messages/send")
async def send_message(request: Request, background_tasks: BackgroundTasks):
    session = await require_session(request)
    username = session.get("username")
    sender_email = f"{username}@company.org"

    await validate_csrf(request)
    await init_moha_engine_db()

    payload = await request.json()
    recipient = payload.get("to", "").strip()
    cc = payload.get("cc", "").strip()
    bcc = payload.get("bcc", "").strip()
    subject = payload.get("subject", "").strip() or "(No Subject)"
    body_plain = payload.get("body_plain", "")
    body_html = payload.get("body_html", "")
    in_reply_to = payload.get("in_reply_to")
    attachments = payload.get("attachments", [])

    if not recipient or not EMAIL_REGEX.match(recipient):
        raise HTTPException(status_code=400, detail="Invalid primary recipient")

    now = time.time()
    header_msg_id = generate_rfc822_message_id()

    async with aiosqlite.connect(DABA) as db:
        await ensure_system_labels(db, sender_email)
        await ensure_system_labels(db, recipient)

        thread_id = None
        if in_reply_to:
            async with db.execute(
                "SELECT thread_id FROM moha_messages WHERE message_id_header = ?",
                (in_reply_to,),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    thread_id = row[0]

        if not thread_id:
            thread_id = f"thr_{uuid.uuid4().hex[:12]}"
            snippet = body_plain[:100] if body_plain else "HTML Content"
            await db.execute(
                """
                INSERT INTO moha_threads (id, user_email, subject, last_message_timestamp, snippet, message_count)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (thread_id, sender_email, subject, now, snippet),
            )
        else:
            snippet = body_plain[:100] if body_plain else "HTML Content"
            await db.execute(
                """
                UPDATE moha_threads 
                SET last_message_timestamp = ?, snippet = ?, message_count = message_count + 1
                WHERE id = ?
                """,
                (now, snippet, thread_id),
            )

        msg_id_sender = f"msg_{uuid.uuid4().hex[:12]}"
        msg_id_recipient = f"msg_{uuid.uuid4().hex[:12]}"

        total_size = len(body_plain.encode("utf-8")) + len(
            body_html.encode("utf-8")
        )

        await db.execute(
            """
            INSERT INTO moha_messages (
                id, thread_id, message_id_header, in_reply_to, sender, recipient, cc, bcc,
                subject, body_plain, body_html, timestamp, is_draft, size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                msg_id_sender,
                thread_id,
                header_msg_id,
                in_reply_to,
                sender_email,
                recipient,
                cc,
                bcc,
                subject,
                body_plain,
                body_html,
                now,
                total_size,
            ),
        )

        await db.execute(
            """
            INSERT INTO moha_messages (
                id, thread_id, message_id_header, in_reply_to, sender, recipient, cc, bcc,
                subject, body_plain, body_html, timestamp, is_draft, size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                msg_id_recipient,
                thread_id,
                header_msg_id,
                in_reply_to,
                sender_email,
                recipient,
                cc,
                bcc,
                subject,
                body_plain,
                body_html,
                now,
                total_size,
            ),
        )

        await db.execute(
            "INSERT INTO moha_message_labels VALUES (?, ?)",
            (msg_id_sender, f"sys_{sender_email}_sent"),
        )
        await db.execute(
            "INSERT INTO moha_message_labels VALUES (?, ?)",
            (msg_id_recipient, f"sys_{recipient}_inbox"),
        )
        await db.execute(
            "INSERT INTO moha_message_labels VALUES (?, ?)",
            (msg_id_recipient, f"sys_{recipient}_unread"),
        )

        for att in attachments:
            fname = att.get("filename", "file.bin")
            mtype = att.get("mime_type", "application/octet-stream")
            b64_raw = att.get("data", "")

            try:
                content_bytes = base64.b64decode(b64_raw)
            except Exception:
                continue

            att_id = f"att_{uuid.uuid4().hex[:10]}"
            file_disk_path = ATTACHMENT_STORAGE / f"{att_id}_{fname}"

            with open(file_disk_path, "wb") as f:
                f.write(content_bytes)

            size = len(content_bytes)

            for target_msg_id in [msg_id_sender, msg_id_recipient]:
                await db.execute(
                    """
                    INSERT INTO moha_attachments (id, message_id, filename, mime_type, file_path, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"att_{uuid.uuid4().hex[:10]}",
                        target_msg_id,
                        fname,
                        mtype,
                        str(file_disk_path),
                        size,
                    ),
                )

        await index_message_fts(
            db,
            msg_id_sender,
            sender_email,
            recipient,
            subject,
            f"{body_plain} {body_html}",
        )
        await index_message_fts(
            db,
            msg_id_recipient,
            sender_email,
            recipient,
            subject,
            f"{body_plain} {body_html}",
        )

        await db.commit()

    background_tasks.add_task(
        log_audit,
        action="moha_send_message",
        details=f"From: {sender_email} | To: {recipient} | HeaderID: {header_msg_id}",
        ip=request.client.host if request.client else "127.0.0.1",
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message_id": msg_id_sender,
            "thread_id": thread_id,
            "header_message_id": header_msg_id,
        },
    )


@Mailer.get("/threads")
async def list_threads(
    request: Request,
    q: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    session = await require_session(request)
    username = session.get("username")
    user_email = f"{username}@company.org"
    await init_moha_engine_db()

    target_label = "INBOX"
    fts_terms = []
    from_filter = None
    to_filter = None
    subject_filter = None

    if q:
        tokens = q.split()
        for token in tokens:
            if token.lower().startswith("label:"):
                target_label = token.split(":")[1].upper()
            elif token.lower().startswith("from:"):
                from_filter = token.split(":")[1]
            elif token.lower().startswith("to:"):
                to_filter = token.split(":")[1]
            elif token.lower().startswith("subject:"):
                subject_filter = token.split(":")[1]
            else:
                fts_terms.append(token)

    async with aiosqlite.connect(DABA) as db:
        await ensure_system_labels(db, user_email)

        sql = """
            SELECT DISTINCT t.id, t.subject, t.last_message_timestamp, t.snippet, t.message_count
            FROM moha_threads t
            JOIN moha_messages m ON m.thread_id = t.id
            JOIN moha_message_labels ml ON ml.message_id = m.id
            JOIN moha_labels l ON l.id = ml.label_id
            WHERE l.user_email = ? AND l.name = ?
        """
        params: List[Any] = [user_email, target_label]

        if from_filter:
            sql += " AND m.sender LIKE ?"
            params.append(f"%{from_filter}%")
        if to_filter:
            sql += " AND m.recipient LIKE ?"
            params.append(f"%{to_filter}%")
        if subject_filter:
            sql += " AND m.subject LIKE ?"
            params.append(f"%{subject_filter}%")

        if fts_terms:
            raw_fts = " ".join(fts_terms)
            sql += " AND m.id IN (SELECT message_id FROM moha_fts WHERE moha_fts MATCH ?)"
            params.append(raw_fts)

        sql += " ORDER BY t.last_message_timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()

        threads = [
            {
                "id": r[0],
                "subject": r[1],
                "last_message_timestamp": r[2],
                "snippet": r[3],
                "message_count": r[4],
            }
            for r in rows
        ]

    return {"query": q or f"label:{target_label}", "count": len(threads), "threads": threads}


@Mailer.get("/threads/{thread_id}")
async def get_thread_details(thread_id: str, request: Request):
    session = await require_session(request)
    username = session.get("username")
    user_email = f"{username}@company.org"
    await init_moha_engine_db()

    async with aiosqlite.connect(DABA) as db:
        async with db.execute(
            "SELECT id, subject, last_message_timestamp FROM moha_threads WHERE id = ?",
            (thread_id,),
        ) as cursor:
            t_row = await cursor.fetchone()
            if not t_row:
                raise HTTPException(status_code=404, detail="Thread not found")

        async with db.execute(
            """
            SELECT m.id, m.message_id_header, m.in_reply_to, m.sender, m.recipient, m.cc, 
                   m.subject, m.body_plain, m.body_html, m.timestamp, m.is_draft
            FROM moha_messages m
            WHERE m.thread_id = ? AND (m.sender = ? OR m.recipient = ?)
            ORDER BY m.timestamp ASC
            """,
            (thread_id, user_email, user_email),
        ) as cursor:
            m_rows = await cursor.fetchall()

        messages = []
        for r in m_rows:
            msg_id = r[0]

            async with db.execute(
                """
                SELECT l.name FROM moha_labels l
                JOIN moha_message_labels ml ON l.id = ml.label_id
                WHERE ml.message_id = ? AND l.user_email = ?
                """,
                (msg_id, user_email),
            ) as l_cursor:
                labels = [l_row[0] for l_row in await l_cursor.fetchall()]

            async with db.execute(
                "SELECT id, filename, mime_type, size_bytes FROM moha_attachments WHERE message_id = ?",
                (msg_id,),
            ) as att_cursor:
                att_rows = await att_cursor.fetchall()

            attachments = [
                {
                    "id": a[0],
                    "filename": a[1],
                    "mime_type": a[2],
                    "size_bytes": a[3],
                    "download_url": f"/api/v1/mail/attachments/{a[0]}",
                }
                for a in att_rows
            ]

            unread_label_id = f"sys_{user_email}_unread"
            await db.execute(
                "DELETE FROM moha_message_labels WHERE message_id = ? AND label_id = ?",
                (msg_id, unread_label_id),
            )

            messages.append(
                {
                    "id": msg_id,
                    "header_message_id": r[1],
                    "in_reply_to": r[2],
                    "sender": r[3],
                    "recipient": r[4],
                    "cc": r[5],
                    "subject": r[6],
                    "body_plain": r[7],
                    "body_html": r[8],
                    "timestamp": r[9],
                    "is_draft": bool(r[10]),
                    "labels": labels,
                    "attachments": attachments,
                }
            )

        await db.commit()

    return {
        "thread_id": t_row[0],
        "subject": t_row[1],
        "message_count": len(messages),
        "messages": messages,
    }


@Mailer.post("/batch")
async def batch_modify_messages(request: Request):
    session = await require_session(request)
    username = session.get("username")
    user_email = f"{username}@company.org"

    await validate_csrf(request)
    await init_moha_engine_db()

    payload = await request.json()
    msg_ids = payload.get("message_ids", [])
    add_labels = payload.get("add_labels", [])
    remove_labels = payload.get("remove_labels", [])

    if not msg_ids:
        raise HTTPException(status_code=400, detail="No message_ids provided")

    async with aiosqlite.connect(DABA) as db:
        await ensure_system_labels(db, user_email)

        for msg_id in msg_ids:
            for label_name in add_labels:
                lbl_id = f"sys_{user_email}_{label_name.lower()}"
                await db.execute(
                    "INSERT OR IGNORE INTO moha_message_labels (message_id, label_id) VALUES (?, ?)",
                    (msg_id, lbl_id),
                )

            for label_name in remove_labels:
                lbl_id = f"sys_{user_email}_{label_name.lower()}"
                await db.execute(
                    "DELETE FROM moha_message_labels WHERE message_id = ? AND label_id = ?",
                    (msg_id, lbl_id),
                )

        await db.commit()

    return {
        "status": "success",
        "processed_count": len(msg_ids),
        "added": add_labels,
        "removed": remove_labels,
    }


@Mailer.get("/attachments/{attachment_id}")
async def download_attachment_payload(attachment_id: str, request: Request):
    session = await require_session(request)
    username = session.get("username")
    user_email = f"{username}@company.org"

    await init_moha_engine_db()

    async with aiosqlite.connect(DABA) as db:
        async with db.execute(
            """
            SELECT a.filename, a.mime_type, a.file_path, a.size_bytes
            FROM moha_attachments a
            JOIN moha_messages m ON m.id = a.message_id
            WHERE a.id = ? AND (m.sender = ? OR m.recipient = ?)
            """,
            (attachment_id, user_email, user_email),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404, detail="Attachment missing or restricted"
            )

        filename, mime_type, file_path, size_bytes = row

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Disk asset not found")

        with open(file_path, "rb") as f:
            base64_encoded = base64.b64encode(f.read()).decode("utf-8")

    return {
        "id": attachment_id,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "base64_data": base64_encoded,
    }   