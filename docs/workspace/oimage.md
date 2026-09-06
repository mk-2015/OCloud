# oimage

OImage is a lightweight, browser-based image viewing and manipulation tool integrated into the OWorkspace suite.

## Features
- **View:** Display images opened from the local disk or imported via OMedia.
- **Manipulate:** Perform basic transformations on images:
  - Rotate left/right (90-degree increments)
  - Zoom in/out (multiplicative scaling)
  - Reset to original view (fit-to-window)
- **Paint:** Draw on the image with adjustable brush size and color.
- **Import:** Open files directly from the browser or browse/import images stored in OMedia.
- **Export:** Download the manipulated image as a PNG.

## Technical Details

### Frontend Architecture
- **Location:** `server/root/workspace/oimage.html`
- **Logic:** `server/static/oimage.js`
- **Rendering:** Implemented using the **HTML5 Canvas API**. It manages image state (rotation, zoom level, base scaling) and re-renders the canvas context dynamically upon user interaction.
- **State Management:** 
  - Maintains a local state (via `img`, `rotation`, `userZoom`, `baseScale` variables).
  - Implements a **History Stack** using `ctx.getImageData` to capture canvas states for Undo (`Ctrl+Z`) and Redo (`Ctrl+Y`) functionality.

### Integration Patterns
- **OMedia Import:** 
  - The script fetches the current user's file list from `/api/omedia/lsfile/{username}`.
  - Images are filtered client-side by common extensions (`jpg|png|gif|webp|svg|bmp|tiff`).
  - Upon selection, the application performs a background fetch to `/api/omedia/download/...`, converts the response to a `Blob`, and loads it into an `Image` object.
- **Backend Communication:**
  - Uses standard `fetch` API calls for interacting with `OMedia` endpoints.
  - Operates in a transient session; manipulations are not automatically persisted to the OMedia server, but can be downloaded by the user.

### Key Functions
- `draw()`: The core rendering function. Clears the canvas, applies translations/rotations via `ctx.translate`/`ctx.rotate`, and draws the image at the calculated scale.
- `saveState()`: Captures current canvas state using `getImageData` into the history stack.
- `undo()` / `redo()`: Manipulates history index to restore previous `ImageData` via `putImageData`.
- `computeBaseScale(w, h)`: Calculates an initial scaling factor to ensure the image fits within the viewport upon load.
- `loadFile(file)`: Creates an `ObjectUrl`, loads the image into memory, and resets view state.

### Keyboard Shortcuts
- `+` / `-`: Zoom in/out
- `Ctrl+ArrowLeft` / `Ctrl+ArrowRight`: Rotate image by 90 degrees
- `Ctrl+Z`: Undo last drawing action
- `Ctrl+Y`: Redo last undone action
