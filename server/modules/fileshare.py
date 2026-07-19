import asyncio
import json
import mimetypes
import secrets
from typing import List, Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, HTMLResponse
from modules.auth import require_session
from path import DATA
from pathlib import Path
from datetime import datetime, timezone

Rfileshare = APIRouter()
copen_fsr: List[Dict[str, Any]] = []

def is_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except Exception:
        return False
#
# [
#  { "owner": "username", "filepath": "document.docx", "lastfor": 86400000, "createdat": unixtime, "token": "token" }
# ]
#

async def task_expiry():
    while True:
        await asyncio.sleep(60)
        now = int(datetime.now(timezone.utc).timestamp())
        for cfsr in copen_fsr[:]:
            lastfor = cfsr["lastfor"]
            if lastfor == 0:
                continue
            createdat = cfsr["createdat"]
            if now > createdat + (lastfor // 1000):
                copen_fsr.remove(cfsr)

def init_fileshare():
    @Rfileshare.on_event("startup")
    async def start_expiry_task():
        asyncio.create_task(task_expiry())

@Rfileshare.get("/api/fileshare/test")
def testfileshare(request: Request):
    return { "Test": "Ok" }

@Rfileshare.post("/api/fileshare/upload")
async def generate_fileshare_token(request: Request):
    session = require_session(request, required_role="user", ormore=True)
    body = await request.json()
    token = secrets.token_hex(32)

    if not body:
        return JSONResponse(
            status_code=400,
            content={ "success": False, "Reason": "No Body in request" }
        )

    filepath = body.get("filepath")
    if not filepath:
        return JSONResponse(
            status_code=400,
            content={ "success": False, "Reason": "No filepath provided" }
        )

    filetopen = (DATA / session["username"] / filepath).resolve()

    try:
        with open(filetopen):
            pass
    except FileNotFoundError:
        return JSONResponse(
            status_code=404,
            content={ "success": False, "Reason": "File not found" }
        )
    lastfor = 86400000
    if body.get("isforever", False):
        lastfor = 0
        
    copen_fsr.append({
        "owner": session["username"],
        "filepath": filepath,
        "lastfor": lastfor,
        "createdat": int(datetime.now(timezone.utc).timestamp()),
        "token": token
    })

    return JSONResponse(
        status_code=201,
        content={
            "URL": f"/fileshare/{token}",
            "filepath": filepath,
            "rawtoken": token
        }
    )

@Rfileshare.get("/api/fileshare/pure/{token}")
async def get_file_pure(request: Request, token: str):
    owner: str = ""
    filepath: str = ""

    for cfsr in copen_fsr:
        if cfsr["token"] == token:
            owner = cfsr["owner"]
            filepath = cfsr["filepath"]
            break
    else:
        return Response(
            status_code=404,
            content="Doesn't exist or has expired"
        )

    filetopen = (DATA / owner / filepath).resolve()

    try:
        if is_binary(filetopen):
            mime, _ = mimetypes.guess_type(filepath)
            return Response(
                content=filetopen.read_bytes(),
                media_type=mime or "application/octet-stream"
            )
        content = filetopen.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return Response(
            status_code=404,
            content="Owner has deleted the file"
        )

    return Response(
        content=content,
        media_type="text/plain"
    )

@Rfileshare.get("/fileshare/{token}")
async def get_file(request: Request, token: str):
    owner: str = ""
    filepath: str = ""
    filename: str = ""

    for cfsr in copen_fsr:
        if cfsr["token"] == token:
            owner = cfsr["owner"]
            filepath = cfsr["filepath"]
            filename = Path(cfsr["filepath"]).name
            break
    else:
        return HTMLResponse(
            status_code=404,
            content=f"<h1>File token: {token} doesn't exist.</h1>\n"
                    f"<p>Either the file doesn't exist or it has expired.</p>"
        )

    filetopen = (DATA / owner / filepath).resolve()

    try:
        if is_binary(filetopen):
            mime, _ = mimetypes.guess_type(filepath)
            return Response(
                content=filetopen.read_bytes(),
                media_type=mime or "application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )
        content = filetopen.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        return HTMLResponse(
            status_code=404,
            content=f"<h1>File token: {token} doesn't exist.</h1>\n"
                    f"<p>The owner has deleted this file before you could access it.</p>"
        )

    return HTMLResponse(
        content=f"<h1>File Contents</h1><br>\n"
               f"<p>\n"
               f"Filename: {filename}<br>\n"
               f"Owner: {owner}<br>\n"
               f"</p><br>\n"
               f"<br>\n"
               f"<a href=\"/api/fileshare/pure/{token}\" download><button>Download {filename}</button></a>\n"
               f"<br><br><pre>{content}</pre>"
    )
