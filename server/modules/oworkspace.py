import json
import os
import re
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from modules.auth import require_session
from modules.omedia import DABA, log_audit, validate_csrf

import aiosqlite

Rworkspace = APIRouter()

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "_workspace"


def _user_ws_dir(username: str) -> Path:
    d = WORKSPACE_DIR / username
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    return re.sub(r'[^\w.\-]', '_', name).strip('_') or "untitled"


def _file_meta(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.stem,
        "filename": path.name,
        "ext": path.suffix,
        "size": stat.st_size,
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
    }


def init_oworkspace():
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


@Rworkspace.get("/api/oworkspace/test")
def test():
    return {"Test": "Ok"}


@Rworkspace.get("/api/oworkspace/files")
async def list_files(request: Request, kind: str = ""):
    session = require_session(request, required_role="user", ormore=True)
    ws_dir = _user_ws_dir(session["username"])
    files = []
    for f in sorted(ws_dir.iterdir()):
        if f.is_file():
            if kind and f.suffix != f".{kind.lstrip('.')}":
                continue
            files.append(_file_meta(f))
    return {"files": files}


@Rworkspace.post("/api/oworkspace/files")
async def create_file(request: Request):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    body = await request.json()
    name = _safe_name(body.get("name", "untitled"))
    kind = body.get("kind", "odoc")
    ext = f".{kind.lstrip('.')}"
    ws_dir = _user_ws_dir(session["username"])
    path = ws_dir / f"{name}{ext}"
    if path.exists():
        return JSONResponse(status_code=409, content={"detail": "File already exists"})
    path.write_text(json.dumps({"content": "", "created": time.time()}), encoding="utf-8")
    await log_audit("workspace_create", session["username"], f"{name}{ext}")
    return {"file": _file_meta(path)}


@Rworkspace.get("/api/oworkspace/files/{filename}")
async def read_file(request: Request, filename: str):
    session = require_session(request, required_role="user", ormore=True)
    ws_dir = _user_ws_dir(session["username"])
    path = ws_dir / _safe_name(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"content": path.read_text(encoding="utf-8")}
    return {"file": _file_meta(path), "data": data}


@Rworkspace.put("/api/oworkspace/files/{filename}")
async def save_file(request: Request, filename: str):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    body = await request.json()
    ws_dir = _user_ws_dir(session["username"])
    path = ws_dir / _safe_name(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    path.write_text(json.dumps(body.get("data", {})), encoding="utf-8")
    return {"status": "saved", "file": _file_meta(path)}


@Rworkspace.delete("/api/oworkspace/files/{filename}")
async def delete_file(request: Request, filename: str):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    ws_dir = _user_ws_dir(session["username"])
    path = ws_dir / _safe_name(filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    path.unlink()
    await log_audit("workspace_delete", session["username"], filename)
    return {"status": "deleted"}


@Rworkspace.post("/api/oworkspace/files/{filename}/rename")
async def rename_file(request: Request, filename: str):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    body = await request.json()
    new_name = _safe_name(body.get("name", ""))
    if not new_name:
        raise HTTPException(status_code=400, detail="Invalid name")
    ws_dir = _user_ws_dir(session["username"])
    old_path = ws_dir / _safe_name(filename)
    if not old_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    new_path = ws_dir / f"{new_name}{old_path.suffix}"
    if new_path.exists():
        return JSONResponse(status_code=409, content={"detail": "File already exists"})
    old_path.rename(new_path)
    return {"file": _file_meta(new_path)}
