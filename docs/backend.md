# Backend Modules

OCloud includes several core backend modules that handle auditing, events, file system operations, and hooks.

## `audit.py`
Provides system-wide auditing capabilities.

| Function | Description |
|----------|-------------|
| `init_audit()` | Initializes the audit database/tables. |
| `log_audit(...)` | Records an action in the audit log. |
| `get_audit_logs(...)`| Retrieves a paginated list of audit logs. |
| `get_audit_count()` | Returns the total count of audit logs. |

## `events.py`
Manages a per-user event system (e.g., file activity notifications).

| Function | Description |
|----------|-------------|
| `addEvent(event)` | Adds a new event to the user's queue. |
| `waitEvent(...)` | Waits for a new event (used for long-polling). |
| `popEvent(...)` | Removes the latest event from the queue. |
| `getEventsBatch(...)`| Retrieves a batch of pending events. |

## `files.py`
Handles safe file system path resolution and operations.

| Function | Description |
|----------|-------------|
| `ensure_user_dir(...)` | Verifies and creates user-specific storage directories. |
| `resolve_user_path(...)`| Safely resolves a path relative to the user's root directory. |

## `hook.py`
Manages webhook registration and real-time event delivery via WebSockets.

| Function | Description |
|----------|-------------|
| `register_hook(...)` | Registers a new webhook. |
| `websocket_hook(...)` | Handles incoming WebSocket connections for real-time hooks. |

## `time_utils.py`
Provides utility functions for time formatting and manipulation.

| Function | Description |
|----------|-------------|
| `now()` | Returns the current time as a `datetime` object. |
