# oexcel

OExcel is a browser-based spreadsheet application that allows users to create, edit, save, and manage spreadsheet files (`.oexcel`).

---

## Features
- **Spreadsheet Grid:** Interactive grid with cell editing capabilities.
- **Formula Support:** Supports functions like `SUM`, `AVG`, `MIN`, `MAX`, `COUNT` and arithmetic operations (`+`, `-`, `*`, `/`).
- **Sheet Management:** Users can add, rename, and delete sheets within a single spreadsheet file.
- **File Persistence:** Features auto-saving with debounce to ensure data integrity during editing.
- **Data Import/Export:**
    - Imports: Supports importing CSV files from OMedia or local disk.
    - Exports: Supports downloading sheets in `XLSX`, `CSV`, or `JSON` formats.
- **UI Customization:** Toggle between Light and Dark themes.
- **Context Menu:** Provides quick actions for cell, row, and column operations (Cut, Copy, Paste, Insert, Delete, Clear).

---

## Technical Overview

### Frontend
- **Interface:** Located at `root/workspace/oexcel.html`.
- **API Interaction:** Utilizes the shared `WorkspaceAPI` (`root/static/workspace.js`) to perform CRUD operations on spreadsheet files.
- **Styling/Theme:** Managed by `root/static/theme.js`, `root/static/style.css`.
- **External Dependencies:** Uses `xlsx.full.min.js` (via CDN) for XLSX file generation and export.

### Data Storage
- Spreadsheets are saved as JSON files in the user's workspace directory (`_workfiles/<username>/`).
- File structure:
  ```json
  {
    "currentSheet": "Sheet1",
    "sheets": {
      "Sheet1": {
        "cells": { "A1": { "v": "100" }, ... },
        "colWidths": { "A": 120, ... }
      },
      ...
    }
  }
  ```
