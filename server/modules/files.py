from fastapi import HTTPException
from pathlib import Path
from path import DATA

TEXT_EXTENSIONS = {".txt", ".md", ".html", ".css", ".js", ".json", ".xml", ".csv", ".py", ".yml", ".yaml"}

def ensure_user_dir(username: str):
    user_dir = DATA / username
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir

def resolve_user_path(username: str, raw_path: str):
    user_dir = ensure_user_dir(username)
    if not raw_path or raw_path in {".", "/"}:
        return user_dir
    clean_path = raw_path.replace("\\", "/").strip().strip("/")
    if not clean_path:
        return user_dir
    parts = Path(clean_path).parts
    if any(part in {"..", ""} for part in parts):
        raise HTTPException(status_code=400, detail="Invalid path")
    target_path = (user_dir / Path(clean_path)).resolve()
    if not str(target_path).startswith(str(user_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    return target_path