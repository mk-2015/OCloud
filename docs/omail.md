# OMail

OMail is a self-hosted email engine providing core mail functionality.

## Overview

OMail allows users to send and receive emails, manage threads, use labels, and handle attachments within the OCloud workspace.

## API Endpoints

All endpoints are prefixed with `/api/mail`.

### Send Message

```
POST /api/mail/messages/send
```

**Auth**: Session

**Request Body**:
```json
{
    "to": "recipient@company.org",
    "cc": "cc@company.org",
    "bcc": "bcc@company.org",
    "subject": "Email Subject",
    "body_plain": "Plain text content",
    "body_html": "HTML content",
    "in_reply_to": "header_message_id_to_reply_to",
    "attachments": [
        {
            "filename": "file.txt",
            "mime_type": "text/plain",
            "data": "base64_encoded_data"
        }
    ]
}
```

### List Threads

```
GET /api/mail/threads
```

**Auth**: Session

**Query Parameters**:
- `q`: Search query (e.g., "label:INBOX", "from:user@company.org")
- `limit`: Number of threads to return (default 20, max 100)
- `offset`: Offset for pagination

### Get Thread Details

```
GET /api/mail/threads/{thread_id}
```

**Auth**: Session

Returns messages within the thread.

### Batch Modify Labels

```
POST /api/mail/batch
```

**Auth**: Session

**Request Body**:
```json
{
    "message_ids": ["msg_id1", "msg_id2"],
    "add_labels": ["IMPORTANT"],
    "remove_labels": ["UNREAD"]
}
```

### Download Attachment

```
GET /api/mail/attachments/{attachment_id}
```

**Auth**: Session

Returns attachment details and base64 encoded data.

## File Location

`server/modules/omail.py`
