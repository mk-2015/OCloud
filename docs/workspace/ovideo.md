# ovideo

OVideo is a robust browser-based video player with advanced control features.

## Features
- **Playback Control:** Play, pause, skip forward/back 10 seconds, speed control (0.5x - 2x).
- **Volume & Mute:** Adjustable volume with keyboard shortcuts.
- **Trim:** Define trim start and end points for video playback.
- **Screenshot:** Capture and download screenshots from the current frame.
- **Advanced UI:** Supports Picture-in-Picture (PiP), fullscreen mode, and keyboard shortcuts for quick control.
- **Responsive:** Optimized for mobile and desktop screens.

## Technical Details
- **Frontend:** `root/workspace/ovideo.html`.
- **Technology:** Uses standard HTML5 `<video>` element with custom CSS/JS for control overlay.
- **Video Source:** Streams video content via OMedia API (`/api/omedia/download/...`).
