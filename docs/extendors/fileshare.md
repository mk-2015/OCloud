# Fileshare

Public file sharing with time-limited or permanent links.

## Overview

Fileshare lets authenticated users generate share tokens for their files with custom share names, view all their active shared links, and manually revoke access. Tokens are stored in memory and expire automatically.

## Enabling

```json
{
    "extendors": {
        "fileshare": true
    }
}
```

## How It Works

1. User sends a file path, optional share name, and options to the upload endpoint
2. Server generates a 64-character hex token
3. Token is stored in memory with the share name, file path, owner, and expiry
4. Public URL is returned to the user
5. Users can view their active shared links or delete specific share tokens at any time
6. A background task removes expired tokens or missing file references every 60 seconds

## Token Storage

Tokens are held in an in-memory list (`copen_fsr`). Each entry:

```json
{
    "name": "My Document",
    "owner": "username",
    "filepath": "docs/note.html",
    "lastfor": 86400000,
    "createdat": 1700000000,
    "token": "a1b2c3..."
}
```

| Field | Description |
|-------|-------------|
| `name` | Custom name tag for the share (defaults to `"share1"`) |
| `owner` | Username who created the share |
| `filepath` | Relative path to the file |
| `lastfor` | Duration in milliseconds. `0` = never expires |
| `createdat` | Unix timestamp when the token was created |
| `token` | 64-character hex token |

## Expiry

- Default: 24 hours (86400000 ms)
- Forever: set `isforever: true` in the request (`lastfor = 0`)
- A background task checks every 60 seconds and removes expired tokens
- Manual Revocation: Users can delete active shares immediately via `POST /api/fileshare/delete/{token}`

## Binary Support

Binary files (images, PDFs, archives, etc.) are detected automatically by checking for null bytes in the first 8KB.

- **Pure endpoint**: serves with correct MIME type (e.g. `image/jpeg`)
- **HTML endpoint**: triggers a download with `Content-Disposition: attachment`
- **Text files**: rendered as plain text or HTML preview

## API Endpoints

### Create Share Token

```
POST /api/fileshare/upload
```

**Auth**: Session (user or admin)

**Request body**:
```json
{
    "name": "My Document",
    "filepath": "docs/note.html",
    "isforever": false
}
```

**Response** (201):
```json
{
    "name": "My Document",
    "URL": "/fileshare/a1b2c3...",
    "filepath": "docs/note.html",
    "rawtoken": "a1b2c3..."
}
```

**Errors**:
- 400: No body or missing `filepath`
- 404: File not found

### List User Shares

```
GET /api/fileshare/list
```

**Auth**: Session (user or admin)

Returns all active shares belonging to the authenticated user.

**Response** (200):
```json
{
    "shares": [
        {
            "name": "My Document",
            "filepath": "docs/note.html",
            "createdat": 1700000000,
            "lastfor": 86400000,
            "token": "a1b2c3...",
            "URL": "/fileshare/a1b2c3..."
        }
    ]
}
```

### Delete Share Token

```
POST /api/fileshare/delete/{token}
```

**Auth**: Session (owner of the share)

Revokes an active share token immediately.

**Response** (200):
```json
{
    "success": true,
    "message": "Share deleted successfully"
}
```

**Errors**:
- 403: Permission denied (user does not own the share token)
- 404: Share token not found

### Raw File Access

```
GET /api/fileshare/pure/{token}
```

**Auth**: None

Returns the file content directly. Binary files are served with their detected MIME type. Text files are returned as `text/plain`.

### HTML Preview

```
GET /fileshare/{token}
```

**Auth**: None

Renders an HTML page with:
- Share name heading
- Filename and owner info
- Download button
- File content in a `<pre>` block (text files) or binary download (binary files)

### Health Check

```
GET /api/fileshare/test
```

**Auth**: None

**Response**: `{"Test": "Ok"}`

## File Location

`server/modules/extend/fileshare.py`