import asyncio
import os
import platform

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from modules.auth import require_session, WebSocketAuthException

_IS_WINDOWS = platform.system() == "Windows"

if not _IS_WINDOWS:
    import pty
    import fcntl
    import struct
    import termios

webshell_router = APIRouter()


def _detect_shell() -> list[str]:
    system = platform.system()
    if system == "Windows":
        powershell = "powershell.exe"
        if os.path.exists(powershell):
            return [powershell, "-NoLogo", "-NoProfile", "-NoExit"]
        return ["cmd.exe"]
    elif system == "Darwin":
        for shell in ["/bin/zsh", "/bin/bash", "/bin/sh"]:
            if os.path.exists(shell):
                return [shell]
    else:
        for shell in ["/bin/bash", "/bin/sh"]:
            if os.path.exists(shell):
                return [shell]
    return ["/bin/sh"]


@webshell_router.websocket("/api/webshell/ws")
async def shell_ws(websocket: WebSocket):
    try:
        session = require_session(websocket, required_role="admin")
    except WebSocketAuthException as ae:
        await websocket.accept()
        await websocket.close(code=ae.code, reason=ae.reason)
        return
    except Exception:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Auth failure")
        return

    await websocket.accept()

    try:
        if _IS_WINDOWS:
            await _handle_windows(websocket)
        else:
            await _handle_unix(websocket)
    except Exception:
        pass


async def _handle_windows(websocket: WebSocket):
    cmd = _detect_shell()

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception:
        await websocket.send_text("Failed to start shell")
        await websocket.close(code=1011, reason="Shell spawn failed")
        return

    async def read_stdout():
        try:
            while True:
                data = await proc.stdout.read(4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            pass

    async def read_stderr():
        try:
            while True:
                data = await proc.stderr.read(4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            pass

    stdout_task = asyncio.create_task(read_stdout())
    stderr_task = asyncio.create_task(read_stderr())

    try:
        while True:
            msg = await websocket.receive(max_size=1048576)
            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    try:
                        proc.stdin.write(msg["bytes"])
                        await proc.stdin.drain()
                    except Exception:
                        break
                elif "text" in msg:
                    data = msg["text"]
                    if data.startswith("\x04"):
                        await websocket.close(code=1000, reason="Shell exited")
                        break
                    if data.startswith("\x1b["):
                        continue
                    try:
                        proc.stdin.write(data.encode())
                        await proc.stdin.drain()
                    except Exception:
                        break
            elif msg["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        stdout_task.cancel()
        stderr_task.cancel()
        if proc.returncode is None:
            proc.terminate()


async def _handle_unix(websocket: WebSocket):
    cmd = _detect_shell()

    master_fd, slave_fd = pty.openpty()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
    )
    os.close(slave_fd)

    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    async def read_pty():
        try:
            while True:
                await asyncio.sleep(0.02)
                try:
                    data = os.read(master_fd, 4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
                except (BlockingIOError, OSError):
                    pass
        except asyncio.CancelledError:
            pass

    pty_task = asyncio.create_task(read_pty())

    try:
        while True:
            msg = await websocket.receive(max_size=1048576)
            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    try:
                        os.write(master_fd, msg["bytes"])
                    except Exception:
                        break
                elif "text" in msg:
                    data = msg["text"]
                    if data.startswith("\x04"):
                        await websocket.close(code=1000, reason="Shell exited")
                        break
                    if data.startswith("\x1b["):
                        try:
                            parts = data[2:].rstrip("R").split(";")
                            rows = int(parts[0])
                            cols = int(parts[1])
                            winsize = struct.pack("HHHH", rows, cols, 0, 0)
                            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                        except (ValueError, IndexError):
                            pass
                    else:
                        try:
                            os.write(master_fd, data.encode())
                        except Exception:
                            break
            elif msg["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        pty_task.cancel()
        try:
            os.close(master_fd)
        except OSError:
            pass
        if proc.returncode is None:
            proc.terminate()
