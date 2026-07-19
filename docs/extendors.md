# Extensors

Extensors are optional modules that add features to OCloud. They are toggled in `server/config.json` under the `extendors` field.

## Enabling an Extensor

```json
{
    "extendors": {
        "fileshare": true
    }
}
```

Set a value to `true` to enable, `false` to disable. Changes take effect on server restart.

## Available Extensors

| Extensor | Description | Docs |
|----------|-------------|------|
| [fileshare](extendors/fileshare.md) | Create time-limited or permanent public links to files | [View](extendors/fileshare.md) |
| [monitord](extendors/monitord.md) | Real-time system monitoring dashboard | [View](extendors/monitord.md) |
| [webshell](extendors/webshell.md) | Browser-based terminal with WebSocket communication | [View](extendors/webshell.md) |

## Creating an Extensor

Extensors live in `server/modules/` and follow this pattern:

1. Create a file `server/modules/myextensor.py`
2. Define an `APIRouter` and an `init` function
3. Import and register the router in `server/server.py` under the `extendors` block
4. Add a config key in `config.json`

### Minimal Example

```python
# server/modules/myextensor.py
from fastapi import APIRouter

router = APIRouter()

def init():
    pass

@router.get("/api/myextensor/test")
def test():
    return {"status": "ok"}
```

```python
# server/server.py (inside the extendors block)
if config["extendors"]["myextensor"]:
    from modules.myextensor import init, router
    init()
    app.include_router(router)
```
