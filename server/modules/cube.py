import http.client
from fastapi import APIRouter, status, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import secrets

from modules.auth import require_session

cube_router = APIRouter()

vmrunn: List[Dict[str, Any]] = []

@cube_router.post("/api/cube/spin-up")
def spinup(request: Request):
    session = require_session(request, required_role="user")

    vm_name = request.headers.get("X-Session-VM-Name")
    if not vm_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No VM Session name provided"
        )
    
    spinid = {
        "pid": "Not implemented",
        "ip": "Not implemented",
        "role": session["role"],
        "session_vm_id": secrets.token_hex(32),
        "session_vm_name": vm_name,
    }

    vmrunn.append(spinid)

    return spinid