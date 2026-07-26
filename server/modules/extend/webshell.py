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


def _detect_shell(use_winpty: bool = False) -> list[str]:
    system = platform.system()
    if system == "Windows":
        cmd = shutil.which("cmd.exe")
        if use_winpty and cmd:
            return [cmd]
        for name, args in [
            ("powershell.exe", ["-NoLogo", "-NoProfile", "-NoExit"]),
            ("pwsh.exe", ["-NoLogo", "-NoProfile", "-NoExit"]),
        ]:
            path = shutil.which(name)
            if path:
                return [path, *args]
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
    except Exception as e:
        await websocket.accept()
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Auth failure")
        return

    await websocket.accept()

    try:
        if _IS_WINDOWS:
            await _handle_windows(websocket)
        else:
            await _handle_unix(websocket)
    except Exception as e:
        print(f"[WEBSHELL] handler error: {type(e).__name__}: {e}")
        try:
            await websocket.close(code=1011, reason=str(e)[:120])
        except Exception:
            pass


async def _handle_windows(websocket: WebSocket):
    loop = asyncio.get_running_loop()
    cols, rows = 80, 24

    pty_obj = None
    proc = None

    if _winpty is not None:
        try:
            cmd = _detect_shell(use_winpty=True)
            pty_obj = _winpty.PTY(cols, rows)
            pty_obj.spawn(cmd[0], " ".join(cmd[1:]) if len(cmd) > 1 else None)
        except Exception as e:
            print(f"[WEBSHELL] winpty spawn failed: {e}")
            pty_obj = None

    if pty_obj is None:
        try:
            cmd = _detect_shell(use_winpty=False)
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
                if pty_obj:
                    data = await loop.run_in_executor(None, pty_obj.read, True)
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

    print(f"[WEBSHELL] shell started, winpty={pty_obj is not None}, proc={proc is not None}")

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    try:
                        if pty_obj:
                            await loop.run_in_executor(None, pty_obj.write, msg["bytes"].decode("utf-8", errors="replace"))
                        else:
                            await loop.run_in_executor(None, proc.stdin.write, msg["bytes"])
                            await loop.run_in_executor(None, proc.stdin.flush)
                    except Exception as e:
                        print(f"[WEBSHELL] write error: {e}")
                        break
                elif "text" in msg:
                    data = msg["text"]
                    if data.startswith("\x04"):
                        await websocket.close(code=1000, reason="Shell exited")
                        break
                    if data.startswith("\x1b["):
                        if pty_obj:
                            try:
                                parts = data[2:].rstrip("R").split(";")
                                r = int(parts[0])
                                c = int(parts[1])
                                if r > 0 and c > 0:
                                    cols, rows = c, r
                                    await loop.run_in_executor(None, pty_obj.set_size, c, r)
                            except Exception:
                                pass
                        continue
                    try:
                        if pty_obj:
                            await loop.run_in_executor(None, pty_obj.write, data)
                        else:
                            await loop.run_in_executor(None, proc.stdin.write, data.encode())
                            await loop.run_in_executor(None, proc.stdin.flush)
                    except Exception as e:
                        print(f"[WEBSHELL] write error: {e}")
                        break
            elif msg["type"] == "websocket.disconnect":
                print("[WEBSHELL] client disconnected")
                break
    except WebSocketDisconnect:
        print("[WEBSHELL] WebSocketDisconnect")
        pass
    except Exception as e:
        print(f"[WEBSHELL] main loop error: {type(e).__name__}: {e}")
        pass
    finally:
        print("[WEBSHELL] cleaning up")
        output_task.cancel()
        stderr_task.cancel()
        if pty_obj and pty_obj.isalive():
            try:
                os.kill(pty_obj.pid, signal.SIGTERM)
            except OSError:
                pass
        elif proc and proc.poll() is None:
            proc.terminate()
        try:
            await websocket.close(code=1000)
        except Exception:
            pass


async def _handle_unix(websocket: WebSocket):
    try:
        cmd = _detect_shell()
    except FileNotFoundError as e:
        await websocket.close(code=1011, reason=str(e)[:120])
        return

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
            msg = await websocket.receive()
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
        try:
            await websocket.close(code=1000)
        except Exception:
            pass
