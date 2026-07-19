# Fileshare

Public file sharing with time-limited or permanent links.

## Overview

Fileshare lets authenticated users generate share tokens for their files. Anyone with the token can access the file without logging in. Tokens are stored in memory and expire automatically.

## Enabling

```json
{
    "extendors": {
        "fileshare": true
    }
}
```

## How It Works

1. User sends a file path and options to the upload endpoint
2. Server generates a 64-character hex token
3. Token is stored in memory with the file path, owner, and expiry
4. Public URL is returned to the user
5. A background task removes expired tokens every 60 seconds

## Token Storage

Tokens are held in an in-memory list (`copen_fsr`). Each entry:

```json
{
    "owner": "username",
    "filepath": "docs/note.html",
    "lastfor": 86400000,
    "createdat": 1700000000,
    "token": "a1b2c3..."
}
```

| Field | Description |
|-------|-------------|
| `owner` | Username who created the share |
| `filepath` | Relative path to the file |
| `lastfor` | Duration in milliseconds. `0` = never expires |
| `createdat` | Unix timestamp when the token was created |
| `token` | 64-character hex token |

## Expiry

- Default: 24 hours (86400000 ms)
- Forever: set `isforever: true` in the request (`lastfor = 0`)
- A background task checks every 60 seconds and removes expired tokens

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
    "filepath": "docs/note.html",
    "isforever": false
}
```

**Response** (201):
```json
{
    "URL": "/fileshare/a1b2c3...",
    "filepath": "docs/note.html",
    "rawtoken": "a1b2c3..."
}
```

**Errors**:
- 400: No body or missing `filepath`
- 404: File not found

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

`server/modules/fileshare.py`
