import json
import re
import time
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, File, UploadFile, Form, Query
from fastapi.responses import JSONResponse, FileResponse

from modules.auth import require_session
from modules.omedia import log_audit, validate_csrf
from path import DATA
import shutil


Rworkspace = APIRouter()

WORKSPACE_DIR = (DATA / "_workfiles").resolve()

MAX_NAME_LEN = 120
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB cap on serialized document payloads
ALLOWED_KINDS = {"odoc", "oexcel", "opoint"}


def _user_ws_dir(username: str) -> Path:
    d = WORKSPACE_DIR / username
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    name = re.sub(r'[^\w.\-]', '_', str(name)).strip('_ ').strip('.')
    return name[:MAX_NAME_LEN] or "untitled"


def _kind_ext(kind: str) -> str:
    k = (kind or "").lower().lstrip(".")
    if k not in ALLOWED_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{k}'. Allowed: {', '.join(sorted(ALLOWED_KINDS))}",
        )
    return f".{k}"


def _file_meta(fpath: Path) -> dict:
    try:
        stat = fpath.stat()
        mtime = stat.st_mtime
        size = stat.st_size
    except OSError:
        mtime = time.time()
        size = 0
    return {
        "name": fpath.stem,
        "filename": fpath.name,
        "ext": fpath.suffix,
        "size": size,
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
        "mtime_epoch": mtime,
    }


def _write_atomic(fpath: Path, text: str) -> None:
    tmp = fpath.with_name(fpath.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, fpath)


async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object expected")
    return body


def init_oworkspace():
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


@Rworkspace.get("/api/oworkspace/test")
def test():
    return {"Test": "Ok"}


@Rworkspace.get("/api/oworkspace/files")
async def list_files(
    request: Request,
    kind: str = "",
    q: str = Query("", description="Search substring for filename"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("name", pattern="^(name|modified|size)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    modified_since: float = Query(0.0, ge=0.0),
):
    session = require_session(request, required_role="user", ormore=True)
    ws_dir = _user_ws_dir(session["username"])
    kind_norm = kind.lower().lstrip(".") if kind else ""
    files = []
    for f in ws_dir.iterdir():
        try:
            if not f.is_file() or f.name.startswith("."):
                continue
            if kind_norm and f.suffix != f".{kind_norm}":
                continue
            meta = _file_meta(f)
            if q and q.lower() not in meta["name"].lower():
                continue
            if modified_since and meta.get("mtime_epoch", 0) <= float(modified_since):
                continue
            files.append(meta)
        except OSError:
            continue

    reverse = order == "desc"
    if sort_by == "name":
        files.sort(key=lambda x: x["name"].lower(), reverse=reverse)
    elif sort_by == "modified":
        files.sort(key=lambda x: x.get("mtime_epoch", 0), reverse=reverse)
    elif sort_by == "size":
        files.sort(key=lambda x: x.get("size", 0), reverse=reverse)

    sliced = files[offset : offset + limit]
    return {"files": sliced, "total": len(files), "limit": limit, "offset": offset}


@Rworkspace.post("/api/oworkspace/files")
async def create_file(request: Request):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    body = await _json_body(request)
    name = _safe_name(body.get("name") or "untitled")
    ext = _kind_ext(body.get("kind", "odoc"))
    ws_dir = _user_ws_dir(session["username"])
    fpath = ws_dir / f"{name}{ext}"
    if fpath.exists():
        return JSONResponse(status_code=409, content={"detail": "File already exists"})
    try:
        with open(fpath, "x", encoding="utf-8") as fh:
            fh.write(json.dumps({"content": "", "created": time.time()}))
    except FileExistsError:
        return JSONResponse(status_code=409, content={"detail": "File already exists"})
    await log_audit("workspace_create", session["username"], fpath.name)
    return {"file": _file_meta(fpath)}


@Rworkspace.post("/api/oworkspace/upload")
async def upload_file(request: Request, file: UploadFile = File(...), kind: str = Form(None)):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)

    # Determine filename and extension
    orig_name = file.filename or "upload"
    safe_name = _safe_name(Path(orig_name).stem)
    ext = Path(orig_name).suffix
    if kind:
        # override/validate by provided kind
        ext = _kind_ext(kind)
    else:
        if not ext:
            ext = ".odoc"
        else:
            # validate existing extension
            if ext.lstrip(".").lower() not in ALLOWED_KINDS:
                raise HTTPException(status_code=400, detail="Unsupported file type")

    filename = f"{safe_name}{ext}"
    ws_dir = _user_ws_dir(session["username"])
    fpath = ws_dir / filename
    if fpath.exists():
        return JSONResponse(status_code=409, content={"detail": "File already exists"})

    tmp = fpath.with_name(fpath.name + ".uploadtmp")
    total = 0
    try:
        with tmp.open("wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    fh.close()
                    try:
                        tmp.unlink()
                    except Exception:
                        pass
                    raise HTTPException(status_code=413, detail="File too large (10 MB limit)")
                fh.write(chunk)
        os.replace(tmp, fpath)
    finally:
        try:
            await file.close()
        except Exception:
            pass

    await log_audit("workspace_upload", session["username"], fpath.name)
    return {"file": _file_meta(fpath)}


@Rworkspace.get("/api/oworkspace/files/{filename}/download")
def download_file(request: Request, filename: str):
    session = require_session(request, required_role="user", ormore=True)
    ws_dir = _user_ws_dir(session["username"])
    fpath = ws_dir / _safe_name(filename)
    if not fpath.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(fpath), media_type="application/octet-stream", filename=fpath.name)


@Rworkspace.get("/api/oworkspace/files/{filename}")
async def read_file(request: Request, filename: str):
    session = require_session(request, required_role="user", ormore=True)
    ws_dir = _user_ws_dir(session["username"])
    fpath = ws_dir / _safe_name(filename)
    if not fpath.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    raw = fpath.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"content": raw}
    return {"file": _file_meta(fpath), "data": data}


@Rworkspace.put("/api/oworkspace/files/{filename}")
async def save_file(request: Request, filename: str):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (10 MB limit)")
    body = await _json_body(request)
    payload = json.dumps(body.get("data", {}))
    if len(payload.encode("utf-8")) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large (10 MB limit)")
    ws_dir = _user_ws_dir(session["username"])
    fpath = ws_dir / _safe_name(filename)
    if not fpath.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # create simple timestamped backup before overwriting
    try:
        backups_dir = ws_dir / ".backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        backup_name = f"{fpath.name}.{int(time.time())}.bak"
        backup_path = backups_dir / backup_name
        shutil.copy2(fpath, backup_path)
    except Exception:
        # non-fatal: continue saving even if backup fails
        pass

    _write_atomic(fpath, payload)
    await log_audit("workspace_save", session["username"], fpath.name)
    return {"status": "saved", "file": _file_meta(fpath)}


@Rworkspace.delete("/api/oworkspace/files/{filename}")
async def delete_file(request: Request, filename: str):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    ws_dir = _user_ws_dir(session["username"])
    fpath = ws_dir / _safe_name(filename)
    if not fpath.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    fpath.unlink()
    await log_audit("workspace_delete", session["username"], fpath.name)
    return {"status": "deleted"}


@Rworkspace.post("/api/oworkspace/files/{filename}/rename")
async def rename_file(request: Request, filename: str):
    validate_csrf(request)
    session = require_session(request, required_role="user", ormore=True)
    body = await _json_body(request)
    raw_name = str(body.get("name", "")).strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="Invalid name")
    new_name = _safe_name(raw_name)
    ws_dir = _user_ws_dir(session["username"])
    old_path = ws_dir / _safe_name(filename)
    if not old_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    new_path = ws_dir / f"{new_name}{old_path.suffix}"
    if new_path.exists():
        return JSONResponse(status_code=409, content={"detail": "File already exists"})
    old_path.rename(new_path)
    await log_audit("workspace_rename", session["username"], f"{old_path.name} -> {new_path.name}")
    return {"file": _file_meta(new_path)}

