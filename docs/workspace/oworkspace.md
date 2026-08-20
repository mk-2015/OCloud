# oworkspace

OWorkspace is the core document and productivity suite for the OCloud ecosystem. It provides a browser-based, secure environment for creating, managing, and collaborating on various types of documents.

---

## 1. System Architecture

OWorkspace follows a modular design pattern grouped by functional concern:

### Backend Services (`modules/oworkspace.py`)
- **API Router:** Exposes a unified set of RESTful endpoints to manage workspace file operations.
- **Persistence Layer:** Manages files within user-specific directories in the server's data storage (`_workfiles/`).
- **File Management:** Implements secure file creation, reading, writing, renaming, and deletion.

### Frontend Interface (`root/workspace/`)
- **Application Suite:** A set of HTML/JS-based productivity tools (`odocs.html`, `oexcel.html`, `ocalc.html`, `opoint.html`, `ovideo.html`, etc.).
- **Shared API Client (`root/static/workspace.js`):** A centralized `WorkspaceAPI` utility that abstracts HTTP requests to the backend, handles CSRF token injection, and provides common error handling.

---

## 2. Backend API Reference

All endpoints are managed within the `Rworkspace` FastAPI router.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/oworkspace/files` | Lists workspace files for the authenticated user. |
| `POST` | `/api/oworkspace/files` | Creates a new file in the user's workspace. |
| `GET` | `/api/oworkspace/files/{filename}` | Reads the content and metadata of a specific file. |
| `PUT` | `/api/oworkspace/files/{filename}` | Updates/saves content to an existing file. |
| `DELETE` | `/api/oworkspace/files/{filename}` | Deletes a file from the user's workspace. |
| `POST` | `/api/oworkspace/files/{filename}/rename`| Renames an existing workspace file. |

---

## 3. Frontend Integration (`WorkspaceAPI`)

The `WorkspaceAPI` object in `root/static/workspace.js` provides a standardized interface for all frontend applications to interact with the workspace backend:

```javascript
// Example Usage
const files = await WorkspaceAPI.listFiles('odoc');
const fileData = await WorkspaceAPI.readFile('my_document.odoc');
await WorkspaceAPI.saveFile('my_document.odoc', { content: "New text" });
```

---

## 4. Security Implementation

OWorkspace enforces several security standards to protect user data:

### CSRF Protection
The backend validates CSRF tokens (`validate_csrf(request)`) on all state-changing operations (POST, PUT, DELETE). The frontend client automatically injects the CSRF token into headers for these operations.

### Data Isolation & Path Sanitization
- **Isolation:** Each user's files are stored in `DATA/_workfiles/<username>/`.
- **Sanitization:** The `_safe_name` utility function enforces strict naming conventions on filenames to prevent directory traversal or file injection attacks:
  ```python
  def _safe_name(name: str) -> str:
      return re.sub(r'[^\w.\-]', '_', name).strip('_') or "untitled"
  ```

# Workspace utils
- [OCalc](./ocalc.md)
- [OConnect](./oconnect.md)
- [ODocs](./odocs.md)
- [OExcel](./oexcel.md)
- [OMail](./omail.md)
- [OPoint](./opoint.md)
- [OVideo](./ovideo.md)
- [.](./oworkspace.md)
