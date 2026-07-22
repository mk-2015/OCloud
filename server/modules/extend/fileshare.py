import asyncio
import html
import mimetypes
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from modules.auth import require_session
from modules.files import resolve_user_path
from modules.omedia import validate_csrf

Rfileshare = APIRouter()
copen_fsr: List[Dict[str, Any]] = []


def is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except Exception:
        return False


async def task_expiry():
    while True:
        await asyncio.sleep(60)
        now = int(datetime.now(timezone.utc).timestamp())
        for cfsr in copen_fsr[:]:
            lastfor = cfsr["lastfor"]
            if lastfor != 0 and now > cfsr["createdat"] + (lastfor // 1000):
                copen_fsr.remove(cfsr)
                continue
            try:
                file_path = resolve_user_path(cfsr["owner"], cfsr["filepath"])
                if not file_path.exists() or not file_path.is_file():
                    copen_fsr.remove(cfsr)
            except Exception:
                copen_fsr.remove(cfsr)


def init_fileshare():
    @Rfileshare.on_event("startup")
    async def start_expiry_task():
        asyncio.create_task(task_expiry())


@Rfileshare.get("/api/fileshare/test")
def testfileshare(request: Request):
    return {"Test": "Ok"}


@Rfileshare.post("/api/fileshare/upload")
async def generate_fileshare_token(request: Request):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    body = await request.json()

    if not body or "filepath" not in body:
        return JSONResponse(
            status_code=400,
            content={"success": False, "Reason": "No filepath provided"},
        )

    filepath = body["filepath"]
    username = session["username"]

    try:
        filetopen = resolve_user_path(username, filepath)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code, content={"success": False, "Reason": e.detail}
        )

    if not filetopen.exists() or not filetopen.is_file():
        return JSONResponse(
            status_code=404,
            content={"success": False, "Reason": "File not found"},
        )

    token = secrets.token_hex(32)
    lastfor = 0 if body.get("isforever", False) else 86400000

    copen_fsr.append(
        {
            "owner": username,
            "filepath": filepath,
            "lastfor": lastfor,
            "createdat": int(datetime.now(timezone.utc).timestamp()),
            "token": token,
        }
    )

    return JSONResponse(
        status_code=201,
        content={
            "URL": f"/fileshare/{token}",
            "filepath": filepath,
            "rawtoken": token,
        },
    )


@Rfileshare.get("/api/fileshare/pure/{token}")
async def get_file_pure(request: Request, token: str):
    cfsr = next((item for item in copen_fsr if item["token"] == token), None)

    if not cfsr:
        return Response(status_code=404, content="Doesn't exist or has expired")

    owner = cfsr["owner"]
    filepath = cfsr["filepath"]

    try:
        filetopen = resolve_user_path(owner, filepath)
    except HTTPException as e:
        return Response(status_code=e.status_code, content=e.detail)

    if not filetopen.exists() or not filetopen.is_file():
        return Response(status_code=404, content="Owner has deleted the file")

    if is_binary(filetopen):
        mime, _ = mimetypes.guess_type(filepath)
        return Response(
            content=filetopen.read_bytes(),
            media_type=mime or "application/octet-stream",
        )

    content = filetopen.read_text(encoding="utf-8", errors="ignore")
    return Response(content=content, media_type="text/plain")


@Rfileshare.get("/fileshare/{token}")
async def get_file(request: Request, token: str):
    cfsr = next((item for item in copen_fsr if item["token"] == token), None)

    if not cfsr:
        return HTMLResponse(
            status_code=404,
            content=f"<h1>File token: {html.escape(token)} doesn't exist.</h1>\n"
            f"<p>Either the file doesn't exist or it has expired.</p>",
        )

    owner = cfsr["owner"]
    filepath = cfsr["filepath"]
    filename = Path(filepath).name

    try:
        filetopen = resolve_user_path(owner, filepath)
    except HTTPException:
        return HTMLResponse(status_code=403, content="<h1>Access Denied</h1>")

    if not filetopen.exists() or not filetopen.is_file():
        return HTMLResponse(
            status_code=404,
            content=f"<h1>File token: {html.escape(token)} doesn't exist.</h1>\n"
            f"<p>The owner has deleted this file before you could access it.</p>",
        )

    if is_binary(filetopen):
        mime, _ = mimetypes.guess_type(filepath)
        return Response(
            content=filetopen.read_bytes(),
            media_type=mime or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{html.escape(filename)}"'
            },
        )

    content = filetopen.read_text(encoding="utf-8", errors="ignore")

    safe_filename = html.escape(filename)
    safe_owner = html.escape(owner)
    safe_content = html.escape(content)

    return HTMLResponse(
        content=f"<h1>File Contents</h1><br>\n"
        f"<p>\n"
        f"Filename: {safe_filename}<br>\n"
        f"Owner: {safe_owner}<br>\n"
        f"</p><br>\n"
        f'<a href="/api/fileshare/pure/{token}" download><button>Download {safe_filename}</button></a>\n'
        f"<br><br><pre>{safe_content}</pre>"
    )
