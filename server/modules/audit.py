import aiosqlite
from path import DABA

AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    username TEXT,
    action TEXT NOT NULL,
    detail TEXT,
    ip TEXT
)
"""

async def init_audit():
    async with aiosqlite.connect(DABA) as db:
        await db.execute(AUDIT_TABLE)
        await db.commit()


async def log_audit(action: str, username: str = None, detail: str = None, ip: str = None):
    from modules.time_utils import now
    async with aiosqlite.connect(DABA) as db:
        await db.execute(
            "INSERT INTO audit_log (timestamp, username, action, detail, ip) VALUES (?, ?, ?, ?, ?)",
            (now().isoformat(), username, action, detail, ip)
        )
        await db.commit()


async def get_audit_logs(limit: int = 100, offset: int = 0):
    async with aiosqlite.connect(DABA) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_audit_count():
    async with aiosqlite.connect(DABA) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM audit_log")
        row = await cursor.fetchone()
        return row[0]
