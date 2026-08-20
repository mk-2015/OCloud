# odocs

ODocs is a rich-text document editor designed for collaborative and personal document management.

## Features
- **Rich Editing:** Built on top of [Quill.js](https://quilljs.com/), supporting bold, italic, underline, lists, headers, images, video, and more.
- **Persistence:** Features real-time auto-saving with a 5-second debounce to ensure no data loss.
- **File Management:** Create, open, rename, and delete documents (`.odoc` files).
- **Import Support:** Import text files from OMedia or the local disk.

## Technical Details
- **Frontend:** Located at `root/workspace/odocs.html`.
- **API Interaction:** Uses the `WorkspaceAPI` utility to interface with the backend OWorkspace service.
- **Storage:** Documents are stored in the user's workspace directory (`_workfiles/<username>/`) in a JSON-based format compatible with Quill's Delta representation.
