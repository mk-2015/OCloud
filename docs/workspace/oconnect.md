# oconnect

OConnect is a peer-to-peer file transfer service designed to facilitate secure file sharing between authenticated users within the OCloud ecosystem.

## Overview
The module architecture consists of two primary components:
1.  **Backend (`modules/oconnect.py`):** A FastAPI-based service that manages user connection states and processes file transfer operations using a WebSocket-based protocol.
2.  **Frontend (`root/static/oconnect.js`):** A JavaScript interface providing network connectivity management, file selection, and an interactive UI for accepting or rejecting incoming file transfers.

---

## Backend API Reference

The backend uses a combination of REST endpoints for control flow and a WebSocket for asynchronous file transfer orchestration.

### REST API

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/konnect/network-connect` | Announces the current user as an active peer. |
| `GET` | `/api/konnect/list-connected` | Returns a list of all currently connected users. |
| `POST` | `/api/konnect/network-disconnect` | Removes the current user from the network. |
| `POST` | `/api/konnect/send-file` | Queues files for transfer to a specified recipient. |

### WebSocket API

| Endpoint | Protocol | Description |
| :--- | :--- | :--- |
| `/api/konnect/recieve-file` | `WS` | Primary channel for receiving file transfer offers and confirming/rejecting them. |

#### Transfer Protocol Detail
The WebSocket operates on an offer/response pattern:
1.  **Offers:** The server pushes JSON payloads containing a dictionary of pending transfers (`connection-N` keys).
2.  **Responses:** The client must send a newline-separated string response for each offer:
    `{ACTION} {CONNECTION_KEY} {DESTINATION_PATH}`
    *   **ACTION:** `OK` or `NO`
    *   **DESTINATION_PATH:** Optional subdir within the user's storage.

---

## Security

### Path Traversal Protection
The backend implements strict path sanitization to prevent unauthorized file access. The helper function `_resolve_safe_path` ensures that all file operations are restricted to the user's designated root data directory:

```python
def _resolve_safe_path(user: str, relative_file_path: str) -> Path | None:
    base_dir = (Path(DATA) / user).resolve()
    target_path = (base_dir / relative_file_path).resolve()
    
    # Ensures target_path is within base_dir
    if base_dir in target_path.parents or target_path == base_dir:
        return target_path
    return None
```

---

## Frontend Integration

The frontend (`oconnect.js`) manages the client-side lifecycle:

*   **Peer Discovery:** Automatically fetches the updated user list upon connection.
*   **File Selection:** Uses the OMedia API (`/api/omedia/list/...`) to browse user files for selection.
*   **Transfer Handling:** Dynamically generates a `transferModal` to allow users to review incoming files and choose specific destination folders before confirming the transfer.
*   **Connection Lifecycle:** Properly closes WebSocket connections on page unload.
