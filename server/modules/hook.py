from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from modules.auth import require_auth
import uuid
import secrets
import string
import logging
import datetime
import json
import asyncio
from modules.events import waitEvent, getEventsBatch, popEvent, addEvent, Event, _user_queues

HookRouter = APIRouter(tags=["Hook"])

registered_hooks = {}
registry_lock = asyncio.Lock()

def generate_code():
    digits = ''.join(secrets.choice(string.digits) for _ in range(32))
    letters = ''.join(secrets.choice(string.ascii_letters) for _ in range(8))
    return f"{digits}{letters}"

async def safe_send(websocket: WebSocket, data: str):
    if websocket.client_state == WebSocketState.CONNECTED:
        try:
            await websocket.send_text(data)
        except Exception as e:
            logging.error(f"Failed to send data: {e}")
    else:
        logging.warning("Attempted to send data to a closed or connecting socket.")

@HookRouter.post("/api/hook/register")
async def register_hook(request: Request):
    session = await require_auth(request)
    username = session["username"]
    
    async with registry_lock:
        if username in registered_hooks:
            raise HTTPException(status_code=400, detail="Hook already registered for this user")
        
        code = generate_code()
        registered_hooks[username] = {"code": code}
    
    logging.info(f"Hook registered for user: {username}")
    return {"success": True, "code": code}

@HookRouter.post("/api/hook/unregister")
async def unregister_hook(request: Request):
    session = await require_auth(request)
    username = session["username"]
    
    async with registry_lock:
        if username not in registered_hooks:
            raise HTTPException(status_code=404, detail="Hook not found for this user")
            
        del registered_hooks[username]
    logging.info(f"Hook unregistered for user: {username}")
    return {"success": True}

@HookRouter.websocket("/api/hook/ws")
async def websocket_hook(websocket: WebSocket):
    await websocket.accept()
    
    user = None
    mode = None
    
    try:
        data = await websocket.receive_text()
        lines = data.splitlines()
        
        if not lines:
            await websocket.close(code=1003)
            return

        cmd = lines[0].strip()
        code = None
        if len(lines) > 1 and lines[1].startswith("CODE:"):
            code = lines[1].split("CODE:")[1].strip()
            
        if cmd == "SYNC":
            async with registry_lock:
                for username, hook_data in registered_hooks.items():
                    if hook_data["code"] == code:
                        user = username
                        break
            
            if not user:
                await websocket.close(code=1008)
                return
            
            await safe_send(websocket, "SYNC ACK")
            
            data = await websocket.receive_text()
            lines = data.splitlines()
            if len(lines) >= 2 and lines[0] == "MODE":
                if "USE SYNC" in lines[1]:
                    mode = "SYNC"
                    await safe_send(websocket, "MODE ACK\nUSE SYNC")
                elif "USE ASYNC" in lines[1]:
                    mode = "ASYNC"
                    await safe_send(websocket, "MODE ACK\nUSE ASYNC")
                else:
                    await websocket.close(code=1003)
                    return
            else:
                await websocket.close(code=1003)
                return
            
            if mode == "SYNC":
                while True:
                    event = await waitEvent(user, removeEventfromQueue=False)
                    
                    event_data = f"Emit: {event.event}\n"
                    event_data += f"Path: {event.path}\n"
                    event_data += f"Time (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
                    event_data += f"Tags: {json.dumps(event.event_tag)}"
                    
                    await safe_send(websocket, event_data)
                    
                    resp = await websocket.receive_text()
                    if "Processing done" in resp:
                        await popEvent(user)
                        continue
            elif mode == "ASYNC":
                pending_acks = {} 

                async def ack_listener():
                    try:
                        while True:
                            msg = await websocket.receive_text()
                            if msg.startswith("ACK:"):
                                msg_id = msg.split(":")[1].strip()
                                if msg_id in pending_acks:
                                    del pending_acks[msg_id]
                                    logging.info(f"ACK received for batch {msg_id}")
                            elif msg.startswith("REQ: EVENT"):
                                lines = msg.splitlines()
                                event_type = "custom.event"
                                event_path = "hook-in"
                                event_tags = {}
                                for line in lines:
                                    key, _, value = line.partition(":")
                                    key, value = key.strip(), value.strip()
                                    if key == "TYPE":
                                        event_type = value
                                    elif key == "PATH":
                                        event_path = value
                                    elif key == "TAGS":
                                        try:
                                            event_tags = json.loads(value)
                                        except:
                                            pass

                                new_event = Event(user=user, path=event_path, event=event_type, event_tag=event_tags)
                                await addEvent(new_event)
                                logging.info(f"Event injected by hooker: {event_type} for user: {user} at path: {event_path}")
                    except WebSocketDisconnect:
                        pass

                ack_task = asyncio.create_task(ack_listener())
                
                async def ack_cleanup():
                    try:
                        while True:
                            await asyncio.sleep(60)
                            now = datetime.datetime.now(datetime.timezone.utc)
                            expired = [
                                mid for mid, (events, ts) in pending_acks.items()
                                if (now - ts).total_seconds() > 300
                            ]
                            for mid in expired:
                                del pending_acks[mid]
                                logging.warning(f"Batch {mid} ACK timed out and removed.")
                    except asyncio.CancelledError:
                        pass

                cleanup_task = asyncio.create_task(ack_cleanup())
                
                try:
                    batch_counter = 0
                    while True:
                        events = await getEventsBatch(user)
                        batch_counter += 1
                        msg_id = str(batch_counter)
                        
                        pending_acks[msg_id] = (events, datetime.datetime.now(datetime.timezone.utc))
                        
                        batch_data = f"BatchID: {msg_id}\n"
                        for i, event in enumerate(events):
                            event_data = f"Event {i+1}:\n"
                            event_data += f"Emit: {event.event}\n"
                            event_data += f"Path: {event.path}\n"
                            event_data += f"Time (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
                            event_data += f"Tags: {json.dumps(event.event_tag)}\n\n"
                            batch_data += event_data
                        
                        await safe_send(websocket, batch_data.strip())
                        await asyncio.sleep(0.1) # Brief yield
                        
                finally:
                    for msg_id, (events, ts) in pending_acks.items():
                        for event in reversed(events):
                            await _user_queues[user].put(event)
                    ack_task.cancel()
                    cleanup_task.cancel()
                
    except WebSocketDisconnect:
        logging.info(f"Hook disconnected for user: {user}")
    except Exception as e:
        logging.error(f"Error in hook websocket: {e}")
        try:
            await websocket.close()
        except:
            pass
