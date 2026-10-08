# OMedia

Self-hosted file storage component built with Python and FastAPI.

## Features

- User registration, login, and session management
- Role-based access (user, admin)
- Per-user filesystem storage under `server/data/`
- Admin dashboard for user and file management
- File sharing with time-limited or permanent public links
- File operations: create folder, upload, download, list, move, delete

## Project Layout

```
server/
  server.py              # FastAPI app entry point
  path.py                # Path constants
  config.json            # Runtime configuration
  modules/
    omedia.py            # Core file/user API endpoints
    auth.py              # Session management and access control
    fileshare.py         # File sharing extendor
    cube.py              # Lambda management (if enabled)
    files.py             # Filesystem helpers
    time_utils.py        # UTC datetime helper
  root/                  # Frontend (served as static files)
  data/                  # Per-user storage + SQLite database
```

## Storage Model

Each user gets a directory under `server/data/`:

```
server/data/
  user1/
    docs/
      note.html
    file.bin
  user2/
    report.docx
  database.db
```

## Web Interface

| Page | Path | Description |
|------|------|-------------|
| Landing | `/` | Links to login and registration |
| Login | `/login.html` | User login |
| Register | `/new_user.html` | Account creation |
| Dashboard | `/omedia/userdashboard.html` | File manager |
| Admin | `/omedia/admin.html` | User and file management |
| Cube IDE | `/cube/index.html` | Lambda management terminal |

## File Sharing

When the `fileshare` extendor is enabled, users can create public links to their files.

- Links expire after 24 hours by default
- Users can choose "forever" links that never expire
- Binary files (images, PDFs, etc.) are served with correct MIME types
- Text files are rendered in an HTML preview page

Share links are accessible at `/fileshare/{token}` without authentication.
