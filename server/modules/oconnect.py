import asyncio
import logging
import shutil
from pathlib import Path
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel

from path import DABA, DATA
from modules.auth import require_session

OConnect = APIRouter(tags=["OConnect"])

CONNECTIONS = []


class SendFilePayload(BaseModel):
    to_user: str
    files: list[str]  # e.g. ["docs/important.pdf", "images/photo.png"]


def init_oconnect():
    pass


def _resolve_safe_path(user: str, relative_file_path: str) -> Path | None:
    """
    Resolves DATA/user/relative_file_path safely.
    Prevents directory traversal attacks (e.g. '../../etc/passwd').
    """
    base_dir = (Path(DATA) / user).resolve()
    target_path = (base_dir / relative_file_path).resolve()

    if base_dir in target_path.parents or target_path == base_dir:
        return target_path
    return None


@OConnect.post("/api/konnect/network-connect", status_code=201)
async def network_connect(request: Request):
    session = require_session(request)
    username = session["username"]

    user_entry = next((c for c in CONNECTIONS if c["user"] == username), None)
    if not user_entry:
        CONNECTIONS.append({
            "user": username,
            "connections": {
                "recived": []
            }
        })

    return {"success": True}


@OConnect.get("/api/konnect/list-connected")
async def list_connected(request: Request):
    require_session(request)
    return CONNECTIONS


@OConnect.post("/api/konnect/network-disconnect")
async def network_disconnect(request: Request):
    session = require_session(request)
    username = session["username"]

    CONNECTIONS[:] = [c for c in CONNECTIONS if c["user"] != username]

    return {"success": True}


@OConnect.post("/api/konnect/send-file")
async def send_file(request: Request, payload: SendFilePayload):
    session = require_session(request)
    sender = session["username"]

    recipient = next((c for c in CONNECTIONS if c["user"] == payload.to_user), None)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"User '{payload.to_user}' is not connected."
        )

    formatted_files = [{"file": file_path} for file_path in payload.files]

    recipient["connections"]["recived"].append({
        "from": sender,
        "files": formatted_files
    })

    return {"success": True, "message": f"Files queued for {payload.to_user}"}


@OConnect.websocket("/api/konnect/recieve-file")
async def recieve_file(websock: WebSocket):
    await websock.accept()

    try:
        session = require_session(websock)
        recipient_user = session["username"]
    except Exception:
        await websock.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        while True:
            user_entry = next((c for c in CONNECTIONS if c["user"] == recipient_user), None)

            if user_entry and user_entry["connections"]["recived"]:
                pending_batch = user_entry["connections"]["recived"][:]
                user_entry["connections"]["recived"].clear()

                connection_map = {}
                for idx, transfer in enumerate(pending_batch, start=1):
                    key = f"connection-{idx}"
                    connection_map[key] = {
                        "user": transfer["from"],
                        "file": transfer["files"]
                    }

                await websock.send_json(connection_map)

                try:
                    response_text = await asyncio.wait_for(websock.receive_text(), timeout=10.0)
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    raise
                except Exception as e:
                    logging.warning(f"Error receiving response for {recipient_user}: {e}")
                    continue

                logging.info(f"Received WebSocket response from {recipient_user}: {response_text}")

                decisions = {}
                for line in response_text.strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        action, conn_key = parts[0].upper(), parts[1]
                        dest_path = parts[2] if len(parts) >= 3 else ""
                        decisions[conn_key] = {"action": action, "dest": dest_path}
                        logging.info(f"Decision for {conn_key}: {action}, Dest: {dest_path}")

                results = []
                for key, connection_info in connection_map.items():
                    decision = decisions.get(key, {})
                    if decision.get("action") == "OK":
                        sender_user = connection_info["user"]
                        dest_subdir = decision.get("dest", "")

                        for item in connection_info["file"]:
                            rel_file = item["file"]
                            filename = Path(rel_file).name
                            
                            dest_rel = Path(dest_subdir) / filename if dest_subdir else filename

                            logging.info(f"Attempting to copy: {rel_file} from {sender_user} to {recipient_user} at {dest_rel}")

                            src_path = _resolve_safe_path(sender_user, rel_file)
                            dest_path = _resolve_safe_path(recipient_user, str(dest_rel))

                            if not src_path or not dest_path:
                                logging.warning(f"Unsafe path attempt blocked: {rel_file}")
                                continue

                            if not src_path.is_file():
                                logging.error(f"Source file missing: {src_path}")
                                continue

                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src_path, dest_path)
                            results.append(f"Copied {rel_file} to {dest_rel}")
                            logging.info(f"Successfully copied: {rel_file}")

                await websock.send_json({"status": "processed", "copied": results})

            else:
                await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logging.info(f"WebSocket disconnected for user: {recipient_user}")
    except Exception as e:
        logging.error(f"WebSocket error for {recipient_user}: {e}")
        await websock.close()