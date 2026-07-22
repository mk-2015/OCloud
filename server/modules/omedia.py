from fastapi import APIRouter, Response, UploadFile, File, Form, status, Request, HTTPException
from path import DATA, DABA
from datetime import timedelta
import aiosqlite
import shutil
import secrets
import re
import time

from modules.time_utils import now
from modules.files import ensure_user_dir, resolve_user_path
from modules.auth import sessions, ADMIN_USERNAME, ADMIN_PASSWORD, require_session

omedia_router = APIRouter()

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

_login_attempts: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 900


def _check_rate_limit(ip: str):
    attempts = _login_attempts.get(ip, [])
    cutoff = time.time() - _WINDOW_SECONDS
    attempts = [t for t in attempts if t > cutoff]
    _login_attempts[ip] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")


def _record_failed_attempt(ip: str):
    _login_attempts.setdefault(ip, []).append(time.time())


def _clear_attempts(ip: str):
    _login_attempts.pop(ip, None)


_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_registration(payload: dict):
    username = payload.get("username", "")
    password = payload.get("password", "")
    email = payload.get("email", "")
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="Username must be 3-32 characters, alphanumeric, underscore, or hyphen")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")


def _generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _set_csrf_cookie(response: Response, token: str):
    response.set_cookie(CSRF_COOKIE, token, httponly=False, samesite="lax", max_age=60 * 60 * 8)


def validate_csrf(request: Request):
    cookie_val = request.cookies.get(CSRF_COOKIE)
    header_val = request.headers.get(CSRF_HEADER)
    if not cookie_val or not header_val or cookie_val != header_val:
        raise HTTPException(status_code=403, detail="CSRF validation failed")


@omedia_router.get("/api/csrf-token")
async def csrf_token(response: Response):
    token = _generate_csrf_token()
    _set_csrf_cookie(response, token)
    return {"csrf_token": token}


@omedia_router.get("/api/test")
def test(response: Response):
    token = _generate_csrf_token()
    _set_csrf_cookie(response, token)
    return {"Test": "OK"}

@omedia_router.post("/api/create_user", status_code=status.HTTP_201_CREATED)
async def create_user(payload: dict, response: Response):
    if not all(k in payload for k in ("username", "password", "email")):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Missing required fields"}

    _validate_registration(payload)

    async with aiosqlite.connect(DABA) as db:
        cursor = await db.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (payload["username"],)
        )
        existing = await cursor.fetchone()
        if existing:
            response.status_code = status.HTTP_409_CONFLICT
            return {"error": "User already exists"}

        await db.execute(
            "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
            (payload["username"], payload["password"], payload["email"])
        )
        await db.commit()

    user_dir = ensure_user_dir(payload["username"])
    (user_dir / "docs").mkdir(exist_ok=True)
    csrf_token = _generate_csrf_token()
    _set_csrf_cookie(response, csrf_token)
    return {"status": "User created"}

@omedia_router.post("/api/login")
async def login(request: Request, payload: dict, response: Response):
    if not all(k in payload for k in ("username", "password")):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": "Missing required fields"}

    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    if payload["username"] == ADMIN_USERNAME and payload["password"] == ADMIN_PASSWORD:
        _clear_attempts(client_ip)
        token = secrets.token_urlsafe(32)
        sessions[token] = {
            "username": ADMIN_USERNAME,
            "role": "admin",
            "expires_at": now() + timedelta(hours=8),
        }
        response.set_cookie("omedia_session", token, httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 8)
        csrf_token = _generate_csrf_token()
        _set_csrf_cookie(response, csrf_token)
        return {"status": "Logged in", "username": ADMIN_USERNAME, "role": "admin"}

    async with aiosqlite.connect(DABA) as db:
        cursor = await db.execute(
            "SELECT username FROM users WHERE username = ? AND password = ?",
            (payload["username"], payload["password"])
        )
        user = await cursor.fetchone()

    if not user:
        _record_failed_attempt(client_ip)
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return {"error": "Invalid username or password"}

    _clear_attempts(client_ip)
    token = secrets.token_urlsafe(32)
    sessions[token] = {
        "username": payload["username"],
        "role": "user",
        "expires_at": now() + timedelta(hours=8),
    }
    response.set_cookie("omedia_session", token, httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 8)
    csrf_token = _generate_csrf_token()
    _set_csrf_cookie(response, csrf_token)
    return {"status": "Logged in", "username": payload["username"], "role": "user"}

@omedia_router.post("/api/logout")
async def logout(request: Request, response: Response):
    validate_csrf(request)
    token = request.cookies.get("omedia_session")
    if token:
        sessions.pop(token, None)
    response.delete_cookie("omedia_session")
    response.delete_cookie(CSRF_COOKIE)
    return {"status": "Logged out"}

@omedia_router.get("/api/me")
async def me(request: Request):
    session = require_session(request)
    return {"username": session["username"], "role": session.get("role", "user")}

@omedia_router.get("/api/omedia/admin/users")
async def admin_list_users(request: Request):
    require_session(request, required_role="admin")
    async with aiosqlite.connect(DABA) as db:
        cursor = await db.execute("SELECT username, email FROM users ORDER BY username")
        rows = await cursor.fetchall()
    return {"users": [{"username": row[0], "email": row[1]} for row in rows]}

@omedia_router.get("/api/omedia/admin/files/{username}")
@omedia_router.get("/api/omedia/admin/files/{username}/{path:path}")
async def admin_list_user_files(request: Request, username: str, path: str = ""):
    require_session(request, required_role="admin")
    target_dir = resolve_user_path(username, path)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    entries = []
    for child in sorted(target_dir.iterdir()):
        entries.append({
            "name": child.name,
            "type": "dir" if child.is_dir() else "file",
            "size": child.stat().st_size if child.is_file() else None,
            "path": child.relative_to(ensure_user_dir(username)).as_posix(),
        })
    return {"username": username, "path": path or ".", "entries": entries}

@omedia_router.delete("/api/admin/users/{username}")
async def admin_delete_user(request: Request, username: str):
    validate_csrf(request)
    session = require_session(request, required_role="admin")
    if session["username"] == username:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    async with aiosqlite.connect(DABA) as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")
        await db.execute("DELETE FROM users WHERE username = ?", (username,))
        await db.commit()

    user_dir = DATA / username
    if user_dir.exists():
        shutil.rmtree(user_dir)
    return {"status": "Deleted"}

@omedia_router.get("/api/omedia/list/{username}")
@omedia_router.get("/api/omedia/lsdir/{username}")
async def list_user_files(request: Request, username: str, path: str = ""):
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    target_dir = resolve_user_path(username, path)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    entries = []
    for child in sorted(target_dir.iterdir()):
        entries.append({
            "name": child.name,
            "type": "dir" if child.is_dir() else "file",
            "size": child.stat().st_size if child.is_file() else None,
            "path": child.relative_to(ensure_user_dir(username)).as_posix(),
        })
    return {
        "username": username,
        "path": path or ".",
        "entries": entries,
        "parent": ".." if path else None,
    }

@omedia_router.get("/api/omedia/lsdir/{username}/{path:path}")
async def list_user_files_nested(request: Request, username: str, path: str):
    return await list_user_files(request, username, path)

@omedia_router.get("/api/omedia/lsfile/{username}")
@omedia_router.get("/api/omedia/lsfile/{username}/{path:path}")
async def list_user_files_flat(request: Request, username: str, path: str = ""):
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    target_dir = resolve_user_path(username, path)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")

    files = []
    for child in sorted(target_dir.rglob("*")):
        if child.is_file():
            files.append({
                "name": child.name,
                "path": child.relative_to(ensure_user_dir(username)).as_posix(),
                "size": child.stat().st_size,
            })
    return {"username": username, "path": path or ".", "files": files}

@omedia_router.post("/api/omedia/mkdir/{username}")
async def make_dir(request: Request, username: str, payload: dict | None = None):
    validate_csrf(request)
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    data = payload or {}
    folder = data.get("path") or data.get("folder") or ""
    if not folder:
        raise HTTPException(status_code=400, detail="Path required")
    target_dir = resolve_user_path(username, folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    return {"status": "Created", "path": str(target_dir.relative_to(ensure_user_dir(username)).as_posix())}

@omedia_router.delete("/api/omedia/rmdir/{username}")
async def remove_dir(request: Request, username: str, payload: dict | None = None):
    validate_csrf(request)
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    data = payload or {}
    folder = data.get("path") or data.get("folder") or ""
    if not folder:
        raise HTTPException(status_code=400, detail="Path required")
    target_dir = resolve_user_path(username, folder)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    if any(target_dir.iterdir()):
        raise HTTPException(status_code=409, detail="Directory not empty")
    target_dir.rmdir()
    return {"status": "Removed"}

@omedia_router.post("/api/omedia/upload/{username}")
async def upload_file(request: Request, username: str, file: UploadFile = File(...), folder: str = Form("")):
    validate_csrf(request)
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")

    user_dir = ensure_user_dir(username)
    target_dir = resolve_user_path(username, folder) if folder else user_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / file.filename
    with target_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"status": "Uploaded", "path": target_path.relative_to(user_dir).as_posix()}

@omedia_router.post("/api/omedia/move/{username}")
async def move_path(request: Request, username: str, payload: dict | None = None):
    validate_csrf(request)
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    data = payload or {}
    src = data.get("from")
    dst = data.get("to")
    if not src or not dst:
        raise HTTPException(status_code=400, detail="from and to are required")

    src_path = resolve_user_path(username, src)
    dst_path = resolve_user_path(username, dst)
    if not src_path.exists():
        raise HTTPException(status_code=404, detail="Source not found")
    if dst_path.exists():
        raise HTTPException(status_code=409, detail="Destination already exists")

    shutil.move(str(src_path), str(dst_path))
    return {"status": "Moved", "from": src, "to": dst}

@omedia_router.get("/api/omedia/download/{username}/{path:path}")
async def download_file(request: Request, username: str, path: str):
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    target_path = resolve_user_path(username, path)
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return Response(content=target_path.read_bytes(), media_type="application/octet-stream")

@omedia_router.get("/api/omedia/content/{username}/{path:path}")
async def read_content(request: Request, username: str, path: str):
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    target_path = resolve_user_path(username, path)
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content = target_path.read_text(encoding="utf-8", errors="ignore")
    return {"path": target_path.relative_to(ensure_user_dir(username)).as_posix(), "content": content}

@omedia_router.delete("/api/omedia/delete/{username}/{path:path}")
async def delete_file(request: Request, username: str, path: str):
    validate_csrf(request)
    session = require_session(request)
    if session["username"] != username:
        raise HTTPException(status_code=403, detail="Forbidden")
    target_path = resolve_user_path(username, path)
    if target_path.exists():
        if target_path.is_file():
            target_path.unlink()
        else:
            shutil.rmtree(target_path)
        return {"status": "Deleted"}
    raise HTTPException(status_code=404, detail="Not found")
