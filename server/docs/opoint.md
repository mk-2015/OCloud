# opoint

OPoint is a browser-based presentation editor and viewer.

## Features
- **Slide Editor:** Edit slides with HTML/rich text content.
- **Presentation Mode:** Integrated viewer using [reveal.js](https://revealjs.com/) for full-screen presentations.
- **Slide Management:** Add, delete, duplicate, and reorder slides with drag-and-drop-like ease.
- **Import:** Supports importing presentation outlines from text/markdown/html files from OMedia or disk.
- **Persistence:** Auto-saving functionality ensures progress is maintained.

## Technical Details
- **Frontend:** `root/workspace/opoint.html`.
- **Rendering:** Presentation mode uses `reveal.js` for transitions and slide management.
- **File Storage:** Saves presentations as `.opoint` JSON files containing the slide structure and content.
