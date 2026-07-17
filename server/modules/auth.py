from fastapi import Request, HTTPException
from datetime import timedelta
from modules.time_utils import now

sessions: dict[str, dict] = {}
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

def init_auth_config(config_dict: dict):
    global ADMIN_PASSWORD
    ADMIN_PASSWORD = config_dict.get("admin_password", "admin")

def require_session(request: Request, required_role: str | None = None) -> dict:
    token = request.cookies.get("omedia_session")
    if not token:
        token = request.headers.get("x-session-token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing session token")
    session = sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session token")
    if session["expires_at"] < now():
        sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Session expired")
    if required_role and session.get("role") != required_role:
        raise HTTPException(status_code=403, detail="Forbidden")
    return session