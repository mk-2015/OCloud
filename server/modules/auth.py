from fastapi import Request, WebSocket, HTTPException, status
from datetime import timedelta
from modules.time_utils import now
import asyncio

sessions: dict[str, dict] = {}
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

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

def init_auth_config(config_dict: dict):
    global ADMIN_PASSWORD
    ADMIN_PASSWORD = config_dict.get("admin_password", "admin")
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_cleanup_sessions())
    except RuntimeError:
        pass

def require_session(request: Request | WebSocket, required_role: str | None = None, ormore = False) -> dict:
    is_websocket = isinstance(request, WebSocket)
    token = None
    global privledge_levels

    if is_websocket:
        token = request.query_params.get("token")
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