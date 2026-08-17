import base64
import json
import logging
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from modules.auth import require_session
from modules.omedia import DABA, log_audit, validate_csrf

Mailer = APIRouter(tags=["OMail Gmail Engine"])

ATTACHMENT_STORAGE = Path("workspace/mail_storage/attachments")
ATTACHMENT_STORAGE.mkdir(parents=True, exist_ok=True)
MAX_STORAGE_PER_USER_BYTES = 10 * 1024 * 1024 * 1024

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

DOMAIN = "opencloud.local"


def init_omail(maildomain: str = "opencloud.local"):
    DOMAIN = maildomain


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
                message_id_header TEXT NOT NULL,
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


def generate_rfc822_message_id() -> str:
    return f"<{uuid.uuid4().hex}.{int(time.time() * 1000)}.moha@{DOMAIN}>"


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


@Mailer.post("/api/mail/messages/send")
async def send_message(request: Request, background_tasks: BackgroundTasks):
    session = require_session(request)
    username = session.get("username")
    sender_email = f"{username}@{DOMAIN}"
    logging.info(f"Send message request from {sender_email}")

    validate_csrf(request)
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

    async with aiosqlite.connect(DABA) as db:
        await ensure_system_labels(db, sender_email)
        await ensure_system_labels(db, recipient)

        while True:
            header_msg_id = generate_rfc822_message_id()
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

            msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            total_size = len(body_plain.encode("utf-8")) + len(
                body_html.encode("utf-8")
            )

            try:
                await db.execute(
                    """
                    INSERT INTO moha_messages (
                        id, thread_id, message_id_header, in_reply_to, sender, recipient, cc, bcc,
                        subject, body_plain, body_html, timestamp, is_draft, size_bytes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        msg_id,
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
                break
            except sqlite3.IntegrityError as e:
                logging.error(f"IntegrityError during message send: {e}")
                continue

        # Attach labels
        await db.execute(
            "INSERT INTO moha_message_labels VALUES (?, ?)",
            (msg_id, f"sys_{sender_email}_sent"),
        )
        await db.execute(
            "INSERT INTO moha_message_labels VALUES (?, ?)",
            (msg_id, f"sys_{recipient}_inbox"),
        )
        await db.execute(
            "INSERT INTO moha_message_labels VALUES (?, ?)",
            (msg_id, f"sys_{recipient}_unread"),
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

            await db.execute(
                """
                INSERT INTO moha_attachments (id, message_id, filename, mime_type, file_path, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (att_id, msg_id, fname, mtype, str(file_disk_path), size),
            )

        await index_message_fts(
            db, msg_id, sender_email, recipient, subject, f"{body_plain} {body_html}"
        )
        await db.commit()

    background_tasks.add_task(
        log_audit,
        action="moha_send_message",
        detail=f"From: {sender_email} | To: {recipient} | HeaderID: {header_msg_id}",
        ip=request.client.host if request.client else "127.0.0.1",
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message_id": msg_id,
            "thread_id": thread_id,
            "header_message_id": header_msg_id,
        },
    )


def parse_search_query(q):
    target_label = "INBOX"
    fts_terms = []
    from_filter, to_filter, subject_filter = None, None, None
    has_attachment = False
    before_timestamp = None

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
            elif token.lower() == "has:attachment":
                has_attachment = True
            elif token.lower().startswith("before:"):
                try:
                    before_date_str = token.split(":")[1]
                    before_timestamp = datetime.strptime(
                        before_date_str, "%Y-%m-%d"
                    ).timestamp()
                except ValueError:
                    pass
            else:
                fts_terms.append(token)
    return (
        target_label,
        fts_terms,
        from_filter,
        to_filter,
        subject_filter,
        has_attachment,
        before_timestamp,
    )


@Mailer.get("/api/mail/threads")
async def list_threads(
    request: Request,
    q: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    session = require_session(request)
    username = session.get("username")
    user_email = f"{username}@{DOMAIN}"
    await init_moha_engine_db()

    (
        target_label,
        fts_terms,
        from_filter,
        to_filter,
        subject_filter,
        has_attachment,
        before_timestamp,
    ) = parse_search_query(q)

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
        if has_attachment:
            sql += " AND m.id IN (SELECT message_id FROM moha_attachments)"
        if before_timestamp:
            sql += " AND m.timestamp < ?"
            params.append(before_timestamp)

        if fts_terms:
            raw_fts = " ".join(fts_terms)
            sql += (
                " AND m.id IN (SELECT message_id FROM moha_fts WHERE moha_fts MATCH ?)"
            )
            params.append(raw_fts)

        sql += " ORDER BY t.last_message_timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()

        threads = []
        for r in rows:
            thread_id = r[0]
            async with db.execute(
                """
                SELECT DISTINCT l.name
                FROM moha_labels l
                JOIN moha_message_labels ml ON l.id = ml.label_id
                JOIN moha_messages m ON ml.message_id = m.id
                WHERE m.thread_id = ? AND l.user_email = ?
                """,
                (thread_id, user_email),
            ) as l_cursor:
                labels = [l_row[0] for l_row in await l_cursor.fetchall()]

            threads.append(
                {
                    "id": thread_id,
                    "subject": r[1],
                    "last_message_timestamp": r[2],
                    "snippet": r[3],
                    "message_count": r[4],
                    "labels": labels,
                }
            )

    return {
        "query": q or f"label:{target_label}",
        "count": len(threads),
        "threads": threads,
    }


@Mailer.get("/api/mail/threads/{thread_id}")
async def get_thread_details(thread_id: str, request: Request):
    session = require_session(request)
    username = session.get("username")
    user_email = f"{username}@{DOMAIN}"
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
                }
                for a in att_rows
            ]

            messages.append(
                {
                    "id": msg_id,
                    "message_id_header": r[1],
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

    return {
        "id": t_row[0],
        "subject": t_row[1],
        "last_message_timestamp": t_row[2],
        "messages": messages,
    }


@Mailer.get("/api/mail/attachments/{attachment_id}")
async def download_attachment(attachment_id: str, request: Request):
    session = require_session(request)
    username = session.get("username")
    user_email = f"{username}@{DOMAIN}"

    await init_moha_engine_db()

    async with aiosqlite.connect(DABA) as db:
        async with db.execute(
            """
            SELECT a.filename, a.file_path, a.mime_type
            FROM moha_attachments a
            JOIN moha_messages m ON m.id = a.message_id
            WHERE a.id = ? AND (m.sender = ? OR m.recipient = ?)
            """,
            (attachment_id, user_email, user_email),
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Attachment not found")

        filename, file_path, mime_type = row
        return FileResponse(file_path, media_type=mime_type, filename=filename)


@Mailer.get("/api/mail/labels")
async def list_labels(request: Request):
    session = require_session(request)
    username = session.get("username")
    user_email = f"{username}@{DOMAIN}"

    async with aiosqlite.connect(DABA) as db:
        async with db.execute(
            "SELECT id, name FROM moha_labels WHERE user_email = ? AND type = 'user'",
            (user_email,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1]} for r in rows]


@Mailer.post("/api/mail/labels")
async def create_label(request: Request):
    session = require_session(request)
    username = session.get("username")
    user_email = f"{username}@{DOMAIN}"

    validate_csrf(request)
    payload = await request.json()
    name = payload.get("name")

    if not name:
        raise HTTPException(status_code=400, detail="Label name is required")

    label_id = f"usr_{user_email}_{name.lower()}"

    async with aiosqlite.connect(DABA) as db:
        await db.execute(
            "INSERT OR IGNORE INTO moha_labels (id, user_email, name, type) VALUES (?, ?, ?, 'user')",
            (label_id, user_email, name),
        )
        await db.commit()

    return {"status": "success", "label_id": label_id}


@Mailer.delete("/api/mail/labels/{label_id}")
async def delete_label(label_id: str, request: Request):
    session = require_session(request)
    username = session.get("username")
    user_email = f"{username}@{DOMAIN}"

    validate_csrf(request)

    async with aiosqlite.connect(DABA) as db:
        await db.execute(
            "DELETE FROM moha_labels WHERE id = ? AND user_email = ? AND type = 'user'",
            (label_id, user_email),
        )
        await db.commit()

    return {"status": "success"}


@Mailer.post("/api/mail/batch")
async def batch_update_labels(request: Request):
    session = require_session(request)
    username = session.get("username")
    user_email = f"{username}@{DOMAIN}"

    validate_csrf(request)
    payload = await request.json()
    message_ids = payload.get("message_ids", [])
    add_labels = payload.get("add_labels", [])
    remove_labels = payload.get("remove_labels", [])

    async with aiosqlite.connect(DABA) as db:
        for msg_id in message_ids:
            for lbl in add_labels:
                lbl_id = f"sys_{user_email}_{lbl.lower()}"
                await db.execute(
                    "INSERT OR IGNORE INTO moha_message_labels VALUES (?, ?)",
                    (msg_id, lbl_id),
                )
            for lbl in remove_labels:
                lbl_id = f"sys_{user_email}_{lbl.lower()}"
                await db.execute(
                    "DELETE FROM moha_message_labels WHERE message_id = ? AND label_id = ?",
                    (msg_id, lbl_id),
                )
        await db.commit()

    return {"status": "success"}
