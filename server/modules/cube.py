import secrets
import threading
import asyncio
import time
import re

from typing import List, Dict, Any
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse, Response
from modules.auth import require_session, WebSocketAuthException
import docker
import requests

cube_router = APIRouter()
lmbservers: List[Dict[str, Any]] = []
_lmb_lock = threading.Lock()
_node_lock = threading.Lock()

clientnodes: List[docker.DockerClient] = []
clientidx: int = 0
islocal: bool = True

_CONTAINER_TTL = 7200
_LAMBDA_MEM_LIMIT = "512m"
_LAMBDA_NANOCPUS = 1_000_000_000
_LAMBDA_PIDS_LIMIT = 256
_NETWORK_NAME = "cube-lambdas"
_CAP_DROP = ["ALL"]
_CAP_ADD = ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID", "KILL", "NET_BIND_SERVICE"]
_SECURITY_OPT = ["no-new-privileges:true"]
_IMAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-/]*(?::[A-Za-z0-9_.\-]+)?$")
_DEFAULT_IMAGE = "fedora:latest"
_PREVIEW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
_HOP_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailer", "trailers", "transfer-encoding", "upgrade",
    "host", "content-length", "cookie", "authorization",
}

def init_cube(workerarray: List, local = True):
    global clientnodes, clientidx, islocal
    with _node_lock:
        if local:
            islocal = True
            clientidx = 0
            try:
                clientnodes = [docker.from_env()]
            except Exception:
                print("[CUBE ERROR] Docker socket unavailable. Cube stays disabled (insecure tcp fallback removed). Configure DOCKER_HOST or mount the docker socket.")
                clientnodes = []
        else:
            islocal = False
            clientidx = 0
            clientnodes = []
            for url in workerarray:
                if isinstance(url, str) and url.startswith("tcp://"):
                    print(f"[CUBE WARNING] Worker '{url}' uses unauthenticated TCP. Prefer unix:// or tls:// endpoints.")
                try:
                    clientnodes.append(docker.DockerClient(base_url=url))
                except Exception as e:
                    print(f"[CUBE ERROR] Failed to attach worker '{url}': {e}")
            if not clientnodes:
                print("[CUBE ERROR] No reachable workers. Cube stays disabled.")


def _find_lambda(lambda_id: str, session: dict):
    for server in lmbservers:
        if server["lambda_id"] == lambda_id:
            if server["createdby"].get("username") != session.get("username"):
                return "forbidden"
            return server
    return None


async def _cleanup_expired_containers():
    while True:
        await asyncio.sleep(300)
        now = time.time()
        with _lmb_lock:
            expired = [s for s in lmbservers if now - s.get("created_at", now) > _CONTAINER_TTL]
            for s in expired:
                lmbservers.remove(s)
        for s in expired:
            try:
                s["container"].stop(timeout=5)
                s["container"].remove()
            except Exception:
                pass


@cube_router.post("/api/cube")
def cubemsg(request: Request):
    require_session(request, required_role="user")
    return "Under Construction"


def _ensure_network(client: docker.DockerClient):
    try:
        return client.networks.get(_NETWORK_NAME)
    except Exception:
        try:
            return client.networks.create(_NETWORK_NAME, driver="bridge", labels={"managed_by": "ocloud-cube"})
        except Exception:
            print(f"[CUBE WARNING] Could not create '{_NETWORK_NAME}' on node; falling back to default bridge.")
            return None


@cube_router.post("/api/cube/lambda/launch")
async def launchlambda(request: Request):
    global clientidx
    session = require_session(request, required_role="user")
    json = await request.json()

    dockertag = json.get("os", _DEFAULT_IMAGE)

    if not isinstance(dockertag, str) or len(dockertag) > 200 or not _IMAGE_RE.match(dockertag):
        return JSONResponse(
            content={"success": False, "reason": "Invalid image reference"},
            status_code=400
        )

    if not clientnodes:
        return JSONResponse(
            content={"success": False, "reason": "Cube runtime not initialized"},
            status_code=503
        )

    lambdaid = secrets.token_hex(32)

    with _node_lock:
        target_client = clientnodes[clientidx]
        clientidx = (clientidx + 1) % len(clientnodes)

    network = _ensure_network(target_client)

    try:
        container = target_client.containers.run(
            dockertag,
            command="sleep infinity",
            name=f"cube-lambda-{lambdaid}",
            detach=True,
            tty=True,
            mem_limit=_LAMBDA_MEM_LIMIT,
            nano_cpus=_LAMBDA_NANOCPUS,
            pids_limit=_LAMBDA_PIDS_LIMIT,
            cap_drop=_CAP_DROP,
            cap_add=_CAP_ADD,
            security_opt=_SECURITY_OPT,
            network=network.name if network else "bridge",
        )
    except Exception as e:
        return JSONResponse(
            content={"success": False, "reason": f"Failed to launch lambda: {e}"},
            status_code=502
        )

    with _lmb_lock:
        lmbservers.append({
            "lambda_id": lambdaid,
            "createdby": session,
            "container": container,
            "node_client": target_client,
            "created_at": time.time(),
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
    except Exception:
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


def _lambda_ip(container) -> str | None:
    try:
        container.reload()
        networks = (container.attrs.get("NetworkSettings") or {}).get("Networks") or {}
        for net in networks.values():
            ip = net.get("IPAddress")
            if ip:
                return ip
    except Exception:
        pass
    return None


@cube_router.api_route("/cube/preview/{lambda_id}/{port}", methods=_PREVIEW_METHODS)
@cube_router.api_route("/cube/preview/{lambda_id}/{port}/{rest_path:path}", methods=_PREVIEW_METHODS)
async def preview_lambda(request: Request, lambda_id: str, port: str, rest_path: str = ""):
    session = require_session(request, required_role="user")

    try:
        portnum = int(port)
        if not 1 <= portnum <= 65535:
            raise ValueError
    except ValueError:
        return JSONResponse(content={"success": False, "reason": "Invalid port"}, status_code=400)

    with _lmb_lock:
        result = _find_lambda(lambda_id, session)

    if result is None:
        return JSONResponse(content={"success": False, "reason": "Server id not found"}, status_code=404)
    if result == "forbidden":
        return JSONResponse(content={"success": False, "reason": "Not your lambda"}, status_code=403)

    ip = _lambda_ip(result["container"])
    if not ip:
        return JSONResponse(content={"success": False, "reason": "Lambda is not running"}, status_code=502)

    target = f"http://{ip}:{portnum}"
    url = f"{target}/{rest_path}"
    if request.url.query:
        url += "?" + request.url.query

    fwd_headers = {}
    for k, v in request.headers.items():
        if k.lower() not in _HOP_HEADERS:
            fwd_headers[k] = v
    body = await request.body()

    def _do_request():
        return requests.request(
            request.method,
            url,
            data=body or None,
            headers=fwd_headers,
            allow_redirects=False,
            timeout=(5, 60),
        )

    loop = asyncio.get_event_loop()
    try:
        upstream = await loop.run_in_executor(None, _do_request)
    except Exception:
        return JSONResponse(
            content={"success": False, "reason": f"No service reachable on port {portnum}"},
            status_code=502
        )

    resp_headers = {}
    for k, v in upstream.headers.items():
        lk = k.lower()
        if lk in _HOP_HEADERS or lk == "content-type" or lk == "content-encoding":
            continue
        resp_headers[k] = v

    loc = upstream.headers.get("location")
    if loc and loc.startswith(target):
        resp_headers["location"] = f"/cube/preview/{lambda_id}/{portnum}" + loc[len(target):]

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )


@cube_router.websocket("/api/cube/lamblets/{lambda_id}/shell")
async def lambda_shell(websocket: WebSocket, lambda_id: str):
    try:
        session = require_session(websocket, required_role="user")
        print(f"[CUBE TTY] auth ok user={session.get('username')}")
    except WebSocketAuthException as ae:
        print(f"[CUBE TTY] auth FAILED code={ae.code} reason={ae.reason}")
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
        raw_sock = getattr(docker_sock, "_sock", docker_sock)
        print(f"[CUBE TTY] attached lambda={lambda_id[:8]} sock_type={type(raw_sock).__name__} has_recv={hasattr(raw_sock, 'recv')} has_read={hasattr(raw_sock, 'read')}")
    except Exception as err:
        print(f"[CUBE TTY] attach FAILED lambda={lambda_id[:8]}: {type(err).__name__}: {err}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Container attach error")
        return

    loop = asyncio.get_running_loop()
    out_q: asyncio.Queue = asyncio.Queue(maxsize=256)

    def _read_chunk():
        try:
            return raw_sock.recv(4096)
        except AttributeError:
            return docker_sock.read(4096)

    def _reader_thread():
        try:
            while True:
                try:
                    data = _read_chunk()
                except Exception as e:
                    print(f"[CUBE TTY] reader error: {type(e).__name__}: {e}")
                    return
                if not data:
                    print("[CUBE TTY] reader EOF")
                    return
                fut = asyncio.run_coroutine_threadsafe(out_q.put(data), loop)
                try:
                    fut.result(timeout=30)
                except Exception as e:
                    print(f"[CUBE TTY] queue handoff failed: {type(e).__name__}: {e}")
                    return
        finally:
            asyncio.run_coroutine_threadsafe(out_q.put(b""), loop)

    async def _pump_out():
        while True:
            data = await out_q.get()
            if not data:
                return
            await websocket.send_bytes(data)

    reader_thread = threading.Thread(target=_reader_thread, daemon=True)
    sender_task = asyncio.create_task(_pump_out())
    reader_thread.start()

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                print(f"[CUBE TTY] client disconnected lambda={lambda_id[:8]}")
                break
            if msg["type"] != "websocket.receive":
                continue
            if "bytes" in msg and msg["bytes"]:
                await loop.run_in_executor(None, raw_sock.sendall, msg["bytes"])
            elif "text" in msg and msg["text"]:
                text = msg["text"]
                if text.startswith("\x1b["):
                    try:
                        parts = text[2:].rstrip("R").split(";")
                        rows, cols = int(parts[0]), int(parts[1])
                        node_client.api.exec_resize(exec_inst["Id"], height=rows, width=cols)
                    except Exception:
                        pass
                else:
                    await loop.run_in_executor(None, raw_sock.sendall, text.encode())
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[CUBE TTY] ws loop error: {type(e).__name__}: {e}")
    finally:
        sender_task.cancel()
        try:
            raw_sock.close()
        except Exception:
            pass
        try:
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
        except Exception:
            pass
