# API Reference

All endpoints are prefixed with `/api/`. Authentication is session-based via cookies.

## CSRF Protection

State-changing endpoints (POST, DELETE) require a CSRF token. The token is obtained from the `/api/csrf-token` endpoint and sent in both a cookie (`csrf_token`) and a header (`X-CSRF-Token`). The cookie and header values must match.

```
GET /api/csrf-token
```

Returns a JSON response and sets the `csrf_token` cookie. Call this before any state-changing request.

## Authentication

| Method | Endpoint | Auth | CSRF | Description |
|--------|----------|------|------|-------------|
| POST | `/api/create_user` | None | No | Register new user |
| POST | `/api/login` | None | No | Login, returns session token |
| POST | `/api/logout` | Session | Yes | Clear session |
| GET | `/api/me` | Session | No | Current user info |
| POST | `/api/del_user` | None | Yes | Self-service account deletion |

### Rate Limiting

Login attempts are rate-limited per IP. After 3 failed attempts, the IP is locked out for 150 seconds. Each additional 3 failures increases the lockout by 150 seconds. The `retry_after` field in the error response indicates seconds remaining.

## OMedia — File Operations

All file endpoints require session auth. Users can only access their own files.

| Method | Endpoint | CSRF | Description |
|--------|----------|------|-------------|
| GET | `/api/omedia/lsdir/{username}` | No | List root directory |
| GET | `/api/omedia/lsdir/{username}/{path}` | No | List subdirectory |
| GET | `/api/omedia/lsfile/{username}` | No | Flat recursive file list |
| GET | `/api/omedia/lsfile/{username}/{path}` | No | Flat list from subdirectory |
| POST | `/api/omedia/mkdir/{username}` | Yes | Create directory |
| DELETE | `/api/omedia/rmdir/{username}` | Yes | Remove empty directory |
| POST | `/api/omedia/upload/{username}` | Yes | Upload file (multipart form) |
| GET | `/api/omedia/download/{username}/{path}` | No | Download file (binary) |
| GET | `/api/omedia/content/{username}/{path}` | No | Read file content (text) |
| DELETE | `/api/omedia/delete/{username}/{path}` | Yes | Delete file or directory |
| POST | `/api/omedia/move/{username}` | Yes | Move file or directory |

### Upload Size Limit

File uploads are limited by the `max_upload_mb` setting in `config.json` (default: 1024 MB). Requests exceeding this return 413.

## OMedia — Admin

Requires admin role.

| Method | Endpoint | CSRF | Description |
|--------|----------|------|-------------|
| GET | `/api/omedia/admin/users` | No | List all users |
| GET | `/api/omedia/admin/files/{username}` | No | Browse any user's files |
| DELETE | `/api/admin/users/{username}` | Yes | Delete a user account |

## File Sharing

When the `fileshare` extendor is enabled.

| Method | Endpoint | Auth | CSRF | Description |
|--------|----------|------|------|-------------|
| POST | `/api/fileshare/upload` | User | Yes | Create a share token |
| GET | `/api/fileshare/pure/{token}` | None | No | Raw file content |
| GET | `/fileshare/{token}` | None | No | HTML preview page |

### Share Token Request

```json
POST /api/fileshare/upload
{
    "filepath": "docs/note.html",
    "isforever": false
}
```

Response:
```json
{
    "URL": "/fileshare/abc123...",
    "filepath": "docs/note.html",
    "rawtoken": "abc123..."
}
```

## Monitord

When the `monitord` extendor is enabled. All endpoints require admin session auth.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/monitord/stats` | CPU, memory, disk, swap, uptime, network, system info |
| GET | `/api/monitord/processes` | Top 50 processes by CPU usage |
| GET | `/api/monitord/disks` | All mounted disk partitions |
| GET | `/api/monitord/network` | All network interfaces |
| GET | `/api/monitord/test` | Health check |

See [Monitord Docs](extendors/monitord.md) for full response schemas.

## Webshell

When the `webshell` extendor is enabled. Admin only.

| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/api/webshell/ws` | Interactive terminal WebSocket |

**Auth**: Session cookie or `x-session-token` query param (admin required).

**Protocol**:
- Text messages: keystrokes sent to shell. `\x04` closes connection.
- Binary messages: raw terminal output.
- Resize: send `\x1b[rows;colsR`.

See [Webshell Docs](extendors/webshell.md) for details.

## Cube

Requires Cube to be enabled in config.

| Method | Endpoint | Auth | CSRF | Description |
|--------|----------|------|------|-------------|
| POST | `/api/cube/lambda/launch` | User | Yes | Launch a lambda |
| DELETE | `/api/cube/lambda/shutdown/{lmdid}` | User | Yes | Shutdown a lambda |
| POST | `/api/cube/lamblets/exec` | User | Yes | Execute a command |
| WS | `/api/cube/lamblets/{lambda_id}/shell` | User | No | Interactive shell |
