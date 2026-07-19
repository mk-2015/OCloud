# API Reference

All endpoints are prefixed with `/api/`. Authentication is session-based via cookies.

## Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/create_user` | None | Register new user |
| POST | `/api/login` | None | Login, returns session token |
| POST | `/api/logout` | Session | Clear session |
| GET | `/api/me` | Session | Current user info |
| POST | `/api/del_user` | None | Self-service account deletion |

## OMedia — File Operations

All file endpoints require session auth. Users can only access their own files.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/omedia/lsdir/{username}` | List root directory |
| GET | `/api/omedia/lsdir/{username}/{path}` | List subdirectory |
| GET | `/api/omedia/lsfile/{username}` | Flat recursive file list |
| GET | `/api/omedia/lsfile/{username}/{path}` | Flat list from subdirectory |
| POST | `/api/omedia/mkdir/{username}` | Create directory |
| DELETE | `/api/omedia/rmdir/{username}` | Remove empty directory |
| POST | `/api/omedia/upload/{username}` | Upload file (multipart form) |
| GET | `/api/omedia/download/{username}/{path}` | Download file (binary) |
| GET | `/api/omedia/content/{username}/{path}` | Read file content (text) |
| DELETE | `/api/omedia/delete/{username}/{path}` | Delete file or directory |
| POST | `/api/omedia/move/{username}` | Move file or directory |

## OMedia — Admin

Requires admin role.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/omedia/admin/users` | List all users |
| GET | `/api/omedia/admin/files/{username}` | Browse any user's files |
| DELETE | `/api/admin/users/{username}` | Delete a user account |

## File Sharing

When the `fileshare` extendor is enabled.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/fileshare/upload` | User | Create a share token |
| GET | `/api/fileshare/pure/{token}` | None | Raw file content |
| GET | `/fileshare/{token}` | None | HTML preview page |

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

## Cube

Requires Cube to be enabled in config.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/cube/lambda/launch` | User | Launch a lambda |
| DELETE | `/api/cube/lambda/shutdown/{lmdid}` | User | Shutdown a lambda |
| POST | `/api/cube/lamblets/exec` | User | Execute a command |
| WS | `/api/cube/lamblets/{lambda_id}/shell` | User | Interactive shell |
