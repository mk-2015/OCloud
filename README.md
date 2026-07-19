# OCloud
Media storage and command execution heaven.

## Configuration
Place runtime and network settings in server/config.json. Example:
```json
{
    "host": "0.0.0.0",
    "port": 443,
    "cube": 
    {
        "use": false,
        "islocal": true,
        "workers": 
        [
            "tcp://localhost:2750"
        ]
    },
    "ssl": 
    {
        "use": true,
        "keyfile": "./key.pem",
        "certfile": "./cert.pem"
    },
    "admin_password": "admin"
}
```

Configure SSL paths, host and port before starting the service.

## Setup
Recommended deployment using Docker Compose:
```bash
docker compose up -d
```
Requirements:
- Docker
- Docker Compose

For a native Python deployment, create a virtual environment, install dependencies (FastAPI, Uvicorn, aiosqlite) and run the ASGI server.

## Components

### OMedia

OMedia is a performant, self-hosted storage component built with Python and FastAPI. It provides per-user file storage, authentication, and an admin interface for user and file management.

Key features
- User registration, login and session management
- Password-protected accounts for regular users
- Admin dashboard for user and file management
- Per-user filesystem storage under server/data
- File operations: create folder, upload, download, list, move, delete
- Minimal web UI for browsing and managing files

Project layout
- server/server.py — FastAPI application and storage logic
- server/root/ — frontend pages and static assets (HTML, CSS, JS, logo)
- server/data/ — per-user directories and SQLite database (database.db)
- server/config.json — runtime configuration (host, port, SSL, admin)

Requirements
- Python 3.10+
- FastAPI
- Uvicorn
- aiosqlite

Storage model
Each user has a directory under server/data. Example:
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

Web interface
- /login.html — user login
- /new_user.html — account creation
- /userdashboard.html — user file manager
- /admin.html — admin dashboard

API highlights
- /api/login
- /api/logout
- /api/me
- /api/create_user
- /api/omedia/lsdir/{username}
- /api/omedia/lsdir/{username}/{path}
- /api/omedia/lsfile/{username}
- /api/omedia/lsfile/{username}/{path}
- /api/omedia/mkdir/{username}
- /api/omedia/rmdir/{username}
- /api/omedia/upload/{username}
- /api/omedia/download/{username}/{path}
- /api/omedia/content/{username}/{path}
- /api/omedia/delete/{username}/{path}
- /api/omedia/move/{username}
- /api/omedia/admin/users
- /api/omedia/admin/files/{username}
- /api/admin/users/{username}

License
This component is licensed under the GNU General Public License v3.0.

Contributing
Contributions are welcome. Please fork the repository, make changes in a branch and submit a pull request.

### Cube

#### What is cube?
* Cube is a lambda like system but there are lambdas (server) and lamblets (commands)

#### Where can it be used?
* It can be used anywhere like-homelabbing, offices (though use in private networks), or just doing lambda-commands through the web.

#### Why is it needed in OCloud?
* A Cloud is storage (OMedia) and lambdas (Cube). to Even compete with google drive we need to, in-some way have a lambda-like system.

#### What are lambdas?
* Lambdas are the servers that run lamblets or commands

#### What are lamblets?
* Lamblets are the commands that run on the servers or Lambdas (also called: lambda-command)