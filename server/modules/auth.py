from fastapi import Request, WebSocket, HTTPException, status
from datetime import timedelta
from modules.time_utils import now
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
import asyncio
import time

_ph = PasswordHasher()

def hash_password(password: str) -> str:
    return _ph.hash(password)

def verify_password(stored: str, password: str) -> bool:
    try:
        return _ph.verify(stored, password)
    except (VerifyMismatchError, VerificationError):
        return False

def needs_rehash(stored: str) -> bool:
    return _ph.check_needs_rehash(stored)

sessions: dict[str, dict] = {}
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = hash_password("admin")

login_attempts: dict[str, list[float]] = {}
LOCKOUT_THRESHOLD = 3
LOCKOUT_BASE = 150

privledge_levels = [
    ["user", 1],
    ["admin", 2]
]

class WebSocketAuthException(Exception):
    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason

async def _cleanup_sessions():
    while True:
        await asyncio.sleep(300)
        now_ts = now()
        expired = [token for token, sess in sessions.items() if sess["expires_at"] < now_ts]
        for token in expired:
            sessions.pop(token, None)

def _get_client_ip(request: Request | WebSocket) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if hasattr(request, "client") and request.client:
        return request.client.host
    return "unknown"

def check_login_rate_limit(ip: str) -> dict | None:
    attempts = login_attempts.get(ip, [])
    now_ts = time.time()
    attempts = [t for t in attempts if now_ts - t < 3600]
    login_attempts[ip] = attempts
    count = len(attempts)
    if count >= LOCKOUT_THRESHOLD:
        lockout_number = (count - LOCKOUT_THRESHOLD) // LOCKOUT_THRESHOLD + 1
        lockout_duration = LOCKOUT_BASE * lockout_number
        last_attempt = attempts[-1]
        remaining = lockout_duration - (now_ts - last_attempt)
        if remaining > 0:
            return {"locked": True, "retry_after": int(remaining) + 1, "lockout_level": lockout_number}
    return None

def record_failed_login(ip: str):
    login_attempts.setdefault(ip, []).append(time.time())

def clear_login_attempts(ip: str):
    login_attempts.pop(ip, None)

def init_auth_config(config_dict: dict):
    global ADMIN_PASSWORD
    plain = config_dict.get("admin_password", "admin")
    ADMIN_PASSWORD = hash_password(plain)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_cleanup_sessions())
    except RuntimeError:
        pass

def require_session(request: Request | WebSocket, debug=False, required_role: str | None = None, ormore = False) -> dict:
    is_websocket = isinstance(request, WebSocket)
    token = None
    global privledge_levels

    if is_websocket:
        token = request.query_params.get("token")
        if debug:
            print(f"[WS AUTH] query_token={token!r}, cookies={dict(request.scope.get('cookies', {}))!r}")
        if not token:
            cookies = request.scope.get("cookies", {})
            token = cookies.get("omedia_session")
        if not token:
            token = request.headers.get("x-session-token")
    else:
        token = request.cookies.get("omedia_session")
        if not token:
            token = request.headers.get("x-session-token")

    def handle_auth_failure(http_status: int, detail: str, ws_close_code: int):
        if is_websocket:
            raise WebSocketAuthException(code=ws_close_code, reason=detail)
        else:
            raise HTTPException(status_code=http_status, detail=detail)

    if not token:
        handle_auth_failure(status.HTTP_401_UNAUTHORIZED, "Missing session token", 4401)

    session = sessions.get(token)
    if not session:
        handle_auth_failure(status.HTTP_401_UNAUTHORIZED, "Invalid session token", 4401)

    if session["expires_at"] < now():
        sessions.pop(token, None)
        handle_auth_failure(status.HTTP_401_UNAUTHORIZED, "Session expired", 4401)

    if required_role:
        user_role = session.get("role")

        if not ormore:
            if user_role != required_role:
                handle_auth_failure(status.HTTP_403_FORBIDDEN, "Forbidden", 403)
        else:
            level_map = dict(privledge_levels)
            user_level = level_map.get(user_role, 0)
            required_level = level_map.get(required_role, 0)

            if user_level < required_level:
                handle_auth_failure(status.HTTP_403_FORBIDDEN, "Forbidden", 403)

    return session
