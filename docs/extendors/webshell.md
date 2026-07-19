# Webshell

Browser-based terminal with real-time WebSocket communication.

## Overview

Webshell provides a full terminal emulator in the browser using xterm.js. It spawns a native shell process on the server and bridges stdin/stdout over WebSockets. Admin-only access.

## Enabling

```json
{
    "extendors": {
        "webshell": true
    }
}
```

## Shell Detection

The shell is selected automatically based on the server OS:

| OS | Primary | Fallback |
|----|---------|----------|
| Windows | PowerShell | cmd.exe |
| macOS | /bin/zsh | /bin/bash, /bin/sh |
| Linux | /bin/bash | /bin/sh |

## Terminal

Access at `/webshell/index.html`. **Admin only** — non-admin users are redirected.

Features:
- Full xterm.js terminal emulation
- Real-time WebSocket I/O
- Automatic terminal resize
- Auto-reconnect on disconnect (3 second delay)
- Dark theme matching OCloud UI
- Status indicator (green = connected, red = disconnected)

## How It Works

1. Browser opens WebSocket to `/api/webshell/ws`
2. Server authenticates via session cookie (admin required)
3. Server spawns a PTY (Unix) or subprocess (Windows)
4. Keystrokes are sent from browser to shell via WebSocket
5. Shell output is sent from server to browser via WebSocket
6. Terminal resize events are forwarded to the PTY

## Technical Details

### Unix (Linux/macOS)

- Uses `pty.openpty()` to create a pseudo-terminal
- Shell runs with its stdin/stdout/stderr connected to the slave end
- Master end is set to non-blocking and polled asynchronously
- Resize events use `TIOCSWINSZ` ioctl

### Windows

- Uses `asyncio.create_subprocess_exec` with PowerShell or cmd
- Separate tasks read stdout and stderr
- Input is sent directly to stdin

## API Endpoints

### WebSocket Terminal

```
WS /api/webshell/ws
```

**Auth**: Session cookie or `x-session-token` header (admin required)

**Protocol**:
- **Text messages**: Keystrokes sent to the shell. Special: `\x04` closes the connection.
- **Binary messages**: Raw terminal output from the shell.
- **Resize**: Send `\x1b[rows;colsR` to resize the terminal.

**Close codes**:
- `1000`: Normal close (shell exit)
- `4401`: Authentication failure
- `403`: Forbidden (non-admin)

## File Location

`server/modules/extend/webshell.py`
