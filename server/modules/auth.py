from fastapi import Request, WebSocket, HTTPException, status
from datetime import timedelta
from modules.time_utils import now

sessions: dict[str, dict] = {}
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

class WebSocketAuthException(Exception):
    def __init__(self, code: int, reason: str):
        self.code = code
        self.reason = reason

def init_auth_config(config_dict: dict):
    global ADMIN_PASSWORD
    ADMIN_PASSWORD = config_dict.get("admin_password", "admin")

def require_session(request: Request | WebSocket, required_role: str | None = None) -> dict:
    is_websocket = isinstance(request, WebSocket)
    token = None

    if is_websocket:
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
        
    if required_role and session.get("role") != required_role:
        handle_auth_failure(status.HTTP_403_FORBIDDEN, "Forbidden", 4403)
        
    return session