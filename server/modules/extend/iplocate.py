from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Request
from fastapi.responses import JSONResponse, HTMLResponse
from modules.auth import require_session, WebSocketAuthException

iplocate_router = APIRouter()

@iplocate_router.post("/api/locate/myip")
async def getmyip(request: Request):    
    json = await request.json()

    portopt = json.get("needport", False)

    ip: str = request.client.host
    if portopt:
        port: int = request.client.port
    port: int = 0

    return JSONResponse(
        status_code=200,
        content={
            "ip": ip,
            "port": port,
            "options": {
                "isneed_port": portopt
            }
        }
    )

@iplocate_router.get("/myip")
async def getmyip_fancy(request: Request):
    return HTMLResponse(
        status_code=200,
        content="<h1>MY IP ADDRESS</h1>" \
                f"Your ip address is: {request.client.host}" \
                f"Your port is: {request.client.port}"    
    )