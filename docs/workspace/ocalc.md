# ocalc

OCalc is a functional, browser-based calculator integrated into the OWorkspace suite.

## Features
- **Expression Evaluation:** Supports basic and advanced mathematical expressions, including parenthetical grouping.
- **History:** Maintains a local history of recent calculations, which can be cleared.
- **Data Import:** Supports importing expressions from local text or CSV files.
- **Theme Support:** Toggles between light and dark themes.
- **UI:** Includes a clear display area for expressions and results, with responsive design.

## Technical Details
- **Frontend:** Located at `root/workspace/ocalc.html`.
- **Logic:** Implemented in vanilla JS with a safe evaluation pattern using `new Function()`.
- **Storage:** Calculations are transient (stored in-memory during the session), though history can be imported/exported.
