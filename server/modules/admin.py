import secrets
from typing import Any, Dict

import aiosqlite
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from path import DABA
from modules.events import addEvent, Event

admin_backdoor = APIRouter()

ADMIN_BK_USER = "admin"
ADMIN_BK_PASSWORD = "MYADMIN"

SESSION_TOKENS: Dict[str, Dict[str, Any]] = {}


def init_adminbackdoor(config: dict):
    global ADMIN_BK_USER, ADMIN_BK_PASSWORD
    ADMIN_BK_USER = config.get("admin_backdoor_user", "admin")
    ADMIN_BK_PASSWORD = config.get("admin_backdoor_password", "MYADMIN")


def isauthed(request: Request) -> dict:
    global SESSION_TOKENS
    token = request.headers.get("SToken")
    if not token:
        raise HTTPException(status_code=401, detail="SToken header missing")

    session = SESSION_TOKENS.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    client_ip = request.client.host if request.client else "unknown"
    if session.get("ip") != client_ip:
        raise HTTPException(status_code=403, detail="IP address mismatch")

    return session


@admin_backdoor.get("/admin/api/test")
def testfunction_admin(request: Request):
    return {"Test": "OK"}


@admin_backdoor.post("/admin/api/login")
async def login(request: Request):
    global SESSION_TOKENS
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON body"})

    username = data.get("User")
    password = data.get("Password")

    if not username or not password:
        return JSONResponse(status_code=400, content={"error": "Invalid request"})

    valid_user = secrets.compare_digest(username, ADMIN_BK_USER)
    valid_pass = secrets.compare_digest(password, ADMIN_BK_PASSWORD)

    if valid_user and valid_pass:
        token = secrets.token_urlsafe(32)
        client_ip = request.client.host if request.client else "unknown"

        SESSION_TOKENS[token] = {
            "ip": client_ip,
            "username": username
        }

        await addEvent(Event(user=username, path="admin", event="admin.login", event_tag={"ip": client_ip}))
        return JSONResponse(status_code=201, content={"token": token})

    return JSONResponse(
        status_code=401, content={"error": "Incorrect password or user name."}
    )   


@admin_backdoor.post("/admin/api/logout")
async def logout(request: Request):
    global SESSION_TOKENS
    session = isauthed(request)
    token = request.headers.get("SToken")

    if token in SESSION_TOKENS:
        del SESSION_TOKENS[token]
        await addEvent(Event(user=session.get("username", "admin"), path="admin", event="admin.logout"))
        return JSONResponse(
            status_code=200, content={"message": "Logged out successfully"}
        )

    return JSONResponse(status_code=401, content={"error": "Invalid token"})


@admin_backdoor.get("/admin/api/list-all-users")
async def listallusers(request: Request):
    session = isauthed(request)

    async with aiosqlite.connect(DABA) as db:
        cursor = await db.execute(
            "SELECT username, email FROM users ORDER BY username"
        )
        rows = await cursor.fetchall()

    return {"users": [{"username": row[0], "email": row[1]} for row in rows]}


@admin_backdoor.delete("/admin/api/users/{username}")
async def delete_user(request: Request, username: str):
    session = isauthed(request)

    async with aiosqlite.connect(DABA) as db:
        cursor = await db.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="User not found")

        await db.execute("DELETE FROM users WHERE username = ?", (username,))
        await db.commit()

    await addEvent(Event(user=session.get("username", "admin"), path="admin", event="admin.user_deleted", event_tag={"target": username}))
    return {"message": f"User {username} deleted successfully"}


@admin_backdoor.get("/admin/api/audit")
async def get_audit(request: Request, limit: int = 100):
    session = isauthed(request)

    async with aiosqlite.connect(DABA) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()

    return {"logs": [dict(row) for row in rows]}
