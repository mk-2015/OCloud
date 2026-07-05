from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from path import ROOT, LOGS, DATA, CFIG, LOGF, DABA
from datetime import datetime
import uvicorn
import json
import aiosqlite
import sys

if len(sys.argv) >= 2 and sys.argv[1] == "init":
    # Initialize database
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
            await db.commit()
    init_db()
    print("Database initialized.")
    sys.exit(0)

# variables for runtime
logfile = open(LOGF, "a")
config: dict = {}

## Load configuration
with open(CFIG) as f:
    config = json.load(f)
    print("Loaded configuration: config.json")
    logfile.write(f"Loaded configuration: config.json\n")


# APP
app = FastAPI()
app.mount("/", StaticFiles(directory=ROOT, html=True), name="static")

@app.get("/api/test")
def test():
    return { "Test": "OK" }

if __name__ == "__main__":
    try:
        host = config.get("host", "0.0.0.0")
        display_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
        port = config.get("port", 443)

        if config.get("ssl", {}).get("use", False):
            print(f"SSL: Yes. visit: https://{display_host}:{port}")
            uvicorn.run(
                "server:app",
                host=host,
                port=port,
                ssl_certfile=config.get("ssl", {}).get("certfile", "./cert.pem"),
                ssl_keyfile=config.get("ssl", {}).get("keyfile", "./key.pem"),
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
        logfile.write("Server stopped by user\n")
        logfile.close()
        print("Server stopped by user")
