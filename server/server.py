from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from path import ROOT, DATA, CFIG, LOGF, DABA
import uvicorn
import json
import aiosqlite
import sys
import asyncio
import os
import atexit
from modules.omedia import omedia_router
from modules.admin import admin_backdoor
from modules.auth import init_auth_config, _cleanup_sessions

if len(sys.argv) >= 2 and sys.argv[1] == "init":
    async def init_db():
        async with aiosqlite.connect(DABA) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    email    TEXT NOT NULL UNIQUE
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    username TEXT,
                    action TEXT NOT NULL,
                    detail TEXT,
                    ip TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key_hash TEXT NOT NULL UNIQUE,
                    username TEXT NOT NULL,
                    label TEXT,
                    created_at TEXT NOT NULL,
                    last_used TEXT
                )
            """)
            await db.commit()
        os.makedirs(DATA, exist_ok=True)
        for user_dir in [DATA / "demo", DATA / "guest"]:
            user_dir.mkdir(exist_ok=True)
            (user_dir / "docs").mkdir(exist_ok=True)
            (user_dir / "docs" / "welcome.html").write_text("<h1>Welcome</h1>", encoding="utf-8")
    asyncio.run(init_db())
    print("Database initialized.")
    sys.exit(0)

logfile = open(LOGF, "a")
atexit.register(lambda: logfile.close())
config: dict = {}

with open(CFIG) as f:
    config = json.load(f)
    print("Loaded configuration: config.json")
    logfile.write(f"Loaded configuration: config.json\n")

init_auth_config(config)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(_cleanup_sessions())
    if config.get("cube", {}).get("use"):
        asyncio.create_task(_cleanup_expired_containers())
    if config.get("extendors", {}).get("fileshare"):
        from modules.extend.fileshare import task_expiry
        asyncio.create_task(task_expiry())
    yield

app = FastAPI(lifespan=lifespan)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/static/") or request.url.path.endswith(".html"):
            response.headers["Cache-Control"] = "no-store"
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(NoCacheMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES = config.get("max_upload_mb", 1024) * 1024 * 1024

class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/omedia/upload"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_UPLOAD_BYTES:
                return Response(
                    status_code=413,
                    content=f"File too large. Max upload size: {config.get('max_upload_mb', 1024)} MB",
                )
        return await call_next(request)

app.add_middleware(UploadSizeLimitMiddleware)
app.include_router(omedia_router)
app.include_router(admin_backdoor)
if config["cube"]["use"] or (len(sys.argv) >= 2 and sys.argv[1] == "--with-cube"):
    from modules.cube import cube_router, init_cube, _cleanup_expired_containers
    if config["cube"]["islocal"]:
        init_cube([])
    else:
        init_cube(config["cube"].get("workers", []), local=False)
    app.include_router(cube_router)

if config.get("oworkspace", {}).get("use"):
    print("[WARNING] oworkspace is experimental.")
    from modules.oworkspace import Rworkspace, init_oworkspace
    init_oworkspace()
    app.include_router(Rworkspace)

if config["extendors"]["iplocate"]:
    print("[Extendor] extendor \"iplocate\" is on.")
    
    from modules.extend.iplocate import init_iplocate, iplocate_router
    init_iplocate()
    
    app.include_router(iplocate_router)

if config["extendors"]["fileshare"]:
    print("[Extendor] extendor \"fileshare\" is on.")
    
    from modules.extend.fileshare import init_fileshare, Rfileshare
    init_fileshare()
    
    app.include_router(Rfileshare)
    
if config["extendors"]["monitord"]:
    print("[Extendor] extendor \"monitord\" is on.")
    
    from modules.extend.monitord import init_monitord, monitord
    init_monitord()
    
    app.include_router(monitord)

if config["extendors"]["webshell"]:
    print("[Extendor] extendor \"webshell\" is on.")
    
    from modules.extend.webshell import webshell_router
    app.include_router(webshell_router)

app.mount("/", StaticFiles(directory=ROOT, html=True), name="static")

if __name__ == "__main__":
    try:
        host = config["host"] if "host" in config else "0.0.0.0"
        display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        port = config["port"] if "port" in config else 443

        if "ssl" in config and config["ssl"].get("use", False):
            print(f"SSL: Yes. visit: https://{display_host}:{port}")
            uvicorn.run(
                "server:app",
                host=host,
                port=port,
                ssl_certfile=config["ssl"].get("certfile", "./cert.pem"),
                ssl_keyfile=config["ssl"].get("keyfile", "./key.pem"),
                reload=True
            )
        else:
            print(f"SSL: None. visit: http://{display_host}:{port}")
            uvicorn.run(
                "server:app",
                host=host,
                port=port,
                reload=True
            )

    except KeyboardInterrupt:
        print("Server stopped by user")
