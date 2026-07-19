import secrets
import threading
import asyncio

from typing import List, Dict, Any
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from modules.auth import require_session, WebSocketAuthException
import docker

cube_router = APIRouter()
lmbservers: List[Dict[str, Any]] = []
_lmb_lock = threading.Lock()
_node_lock = threading.Lock()

clientnodes: List[docker.DockerClient] = []
clientidx: int = 0
islocal: bool = True

def init_cube(workerarray: List, local = True):
    global clientnodes, clientidx, islocal
    with _node_lock:
        if local:
            islocal = True
            clientidx = 0
            try:
                clientnodes = [docker.from_env()]
            except Exception:
                clientnodes = [docker.DockerClient(base_url="tcp://localhost:2375")]
        else:
            islocal = False
            clientidx = 0
            clientnodes = [docker.DockerClient(base_url=url) for url in workerarray]

def _find_lambda(lambda_id: str, session: dict):
    for server in lmbservers:
        if server["lambda_id"] == lambda_id:
            if server["createdby"].get("username") != session.get("username"):
                return "forbidden"
            return server
    return None


@cube_router.post("/api/cube")
def cubemsg(request: Request):
    return "Under Construction"


@cube_router.post("/api/cube/lambda/launch")
async def launchlambda(request: Request):
    global clientidx
    session = require_session(request, required_role="user")
    json = await request.json()

    dockertag = json.get("os", "fedora:44")

    if not clientnodes:
        return JSONResponse(
            content={"success": False, "reason": "Cube runtime not initialized"},
            status_code=503
        )
        
    lambdaid = secrets.token_hex(32)

    with _node_lock:
        target_client = clientnodes[clientidx]
        clientidx = (clientidx + 1) % len(clientnodes)

    container = target_client.containers.run(
        dockertag,
        command="sleep infinity",
        name=f"cube-lambda-{lambdaid}",
        detach=True,
        tty=True,
    )

    with _lmb_lock:
        lmbservers.append({
            "lambda_id": lambdaid,
            "createdby": session,
            "container": container,
            "node_client": target_client
        })

    return {"lambda_id": lambdaid, "createdby": session.get("username")}


@cube_router.delete("/api/cube/lambda/shutdown/{lmdid}")
def shutdownlambda(request: Request, lmdid: str):
    session = require_session(request, required_role="user")

    with _lmb_lock:
        result = _find_lambda(lmdid, session)
        if result is None:
            return JSONResponse(content={"success": False, "reason": "Server id not found"}, status_code=404)
        if result == "forbidden":
            return JSONResponse(content={"success": False, "reason": "Not your lambda"}, status_code=403)
        
        lmbservers.remove(result)

    try:
        container = result["container"]
        container.stop(timeout=5)
        container.remove()
    except Exception as e:
        pass

    return {"success": True}


@cube_router.post("/api/cube/lamblets/exec")
async def execlamblet(request: Request):
    session = require_session(request, required_role="user")
    body = await request.json()

    lambda_id = body.get("lambda_id")
    command = body.get("command")
    if not lambda_id or not command:
        return JSONResponse(content={"success": False, "reason": "lambda_id or command missing"}, status_code=400)

    with _lmb_lock:
        result = _find_lambda(lambda_id, session)

    if result is None:
        return JSONResponse(content={"success": False, "reason": "Server id not found"}, status_code=404)
    if result == "forbidden":
        return JSONResponse(content={"success": False, "reason": "Not your lambda"}, status_code=403)

    loop = asyncio.get_event_loop()
    exit_code, output = await loop.run_in_executor(
        None, lambda: result["container"].exec_run(command, demux=True)
    )
    
    stdout = output[0] if output and output[0] else b""
    stderr = output[1] if output and output[1] else b""

    return {
        "success": True,
        "exit": exit_code,
        "terminal": {
            "stdout": stdout.decode(errors="replace"),
            "err": stderr.decode(errors="replace"),
        },
    }


@cube_router.websocket("/api/cube/lamblets/{lambda_id}/shell")
async def lambda_shell(websocket: WebSocket, lambda_id: str):
    try:
        session = require_session(websocket, required_role="user")
    except WebSocketAuthException as ae:
        await websocket.accept()
        await websocket.close(code=ae.code, reason=ae.reason)
        return
    except Exception:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Auth failure")
        return

    await websocket.accept()

    with _lmb_lock:
        result = _find_lambda(lambda_id, session)
        
    if result is None or result == "forbidden":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized workspace access")
        return

    container = result["container"]
    node_client = result["node_client"]

    try:
        exec_inst = node_client.api.exec_create(
            container.id,
            cmd="/bin/bash", 
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True
        )
        docker_sock = node_client.api.exec_start(exec_inst["Id"], socket=True, tty=True)
        raw_sock = docker_sock._sock
        raw_sock.setblocking(False) 
    except Exception as err:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Container attach error")
        return

    reader, writer = await asyncio.open_connection(sock=raw_sock)

    async def pump_docker_to_ws():
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            pass
        finally:
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)

    async def pump_ws_to_docker():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
                await writer.drain()
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            writer.close()

    await asyncio.gather(pump_docker_to_ws(), pump_ws_to_docker(), return_exceptions=True)
