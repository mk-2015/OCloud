# omail

OMail is a secure, web-based mail client for the OCloud ecosystem.

## Features
- **Threaded Views:** Emails are grouped into conversations for easier reading.
- **Labeling System:** Organize emails using custom and system labels (INBOX, SENT, TRASH, STARRED, etc.).
- **Search:** Supports full-text search using SQLite FTS5 (from/to/subject filters, attachment search).
- **Compose:** Supports rich-text composing, attachments, and managing drafts.
- **Batch Actions:** Perform batch operations on threads (starring, moving to trash, toggling read status).

## Technical Details
- **Backend:** `modules/omail.py` leverages `aiosqlite` for email data, thread management, and full-text search.
- **Frontend:** Located at `root/workspace/omail.html`.
- **Data Storage:** Emails, threads, and metadata are stored in the primary OCloud database; attachments are stored on disk in `workspace/mail_storage/attachments/`.
