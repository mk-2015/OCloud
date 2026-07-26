import asyncio
import os
import platform
import shutil
import signal
import subprocess
import sys

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from modules.auth import require_session, WebSocketAuthException

_winpty = None
if platform.system() == "Windows":
    try:
        import winpty as _winpty
    except ImportError:
        pass

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
        for name, args in [
            ("powershell.exe", ["-NoLogo", "-NoProfile", "-NoExit"]),
            ("pwsh.exe", ["-NoLogo", "-NoProfile", "-NoExit"]),
        ]:
            path = shutil.which(name)
            if path:
                return [path, *args]
        cmd = shutil.which("cmd.exe")
        if cmd:
            return [cmd]
        raise FileNotFoundError("No suitable shell found on PATH")
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
    loop = asyncio.get_running_loop()
    cols, rows = 80, 24

    pty = None
    proc = None

    if _winpty is not None:
        try:
            pty = _winpty.PTY(cols, rows)
            pty.spawn(cmd[0], " ".join(cmd[1:]) if len(cmd) > 1 else None)
        except Exception:
            pty = None

    if pty is None:
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                bufsize=0,
            )
        except Exception as e:
            await websocket.send_text(f"Failed to start shell: {type(e).__name__}: {e}")
            await websocket.close(code=1011, reason="Shell spawn failed")
            return

    async def read_output():
        try:
            while True:
                if pty:
                    data = await loop.run_in_executor(None, pty.read, True)
                    if not data:
                        break
                    await websocket.send_bytes(data.encode("utf-8", errors="replace"))
                else:
                    data = await loop.run_in_executor(None, proc.stdout.read, 4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
        except Exception:
            pass

    async def read_stderr():
        if proc is None:
            return
        try:
            while True:
                data = await loop.run_in_executor(None, proc.stderr.read, 4096)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            pass

    output_task = asyncio.create_task(read_output())
    stderr_task = asyncio.create_task(read_stderr())

    try:
        while True:
            msg = await websocket.receive(max_size=1048576)
            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    try:
                        if pty:
                            await loop.run_in_executor(None, pty.write, msg["bytes"].decode("utf-8", errors="replace"))
                        else:
                            await loop.run_in_executor(None, proc.stdin.write, msg["bytes"])
                            await loop.run_in_executor(None, proc.stdin.flush)
                    except Exception:
                        break
                elif "text" in msg:
                    data = msg["text"]
                    if data.startswith("\x04"):
                        await websocket.close(code=1000, reason="Shell exited")
                        break
                    if data.startswith("\x1b["):
                        if pty:
                            try:
                                parts = data[2:].rstrip("R").split(";")
                                r = int(parts[0])
                                c = int(parts[1])
                                cols, rows = c, r
                                await loop.run_in_executor(None, pty.set_size, c, r)
                            except (ValueError, IndexError):
                                pass
                        continue
                    try:
                        if pty:
                            await loop.run_in_executor(None, pty.write, data)
                        else:
                            await loop.run_in_executor(None, proc.stdin.write, data.encode())
                            await loop.run_in_executor(None, proc.stdin.flush)
                    except Exception:
                        break
            elif msg["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        output_task.cancel()
        stderr_task.cancel()
        if pty and pty.isalive():
            try:
                os.kill(pty.pid, signal.SIGTERM)
            except OSError:
                pass
        elif proc and proc.poll() is None:
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
