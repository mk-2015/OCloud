# Implementation

API Endpoint: /api/hook/ws
What it does:
    - This is the main endpoint that the hooker uses
Note: if i write http for the request blocks remember its ws
Note: # are comments, omit in the request/response

## Handshake

### Init
client:
```http
SYNC
CODE: <CODE>
```

server:
```http
SYNC ACK
```

- Client hooker wants synchronous events
client (sync):
```http
MODE
USE SYNC
CODE: <CODE>
```

server (sync):
```http
MODE ACK
USE SYNC
```
- Client hooker wants asynchronous events
client (async):
```http
MODE
USE ASYNC
CODE: <CODE>
```

server:
```http
MODE ACK
USE ASYNC
```

## Event-Out (Server to Hooker)

### SYNC Mode (Reliable Delivery)
1. Server pushes event.
2. Client MUST process and send:
```http
Processing done
```
3. Server only removes the event from the queue upon receiving this confirmation.

### ASYNC Mode (Reliable Batch Delivery)
1. Server pushes batch with a `BatchID`:
```http
BatchID: <id>
Event 1:
...
```
2. Client MUST acknowledge receipt to clear server's pending buffer:
```http
ACK: <id>
```

## Event-In (Hooker to Server)
- The hooker can inject events into the system

client:
```http
REQ: EVENT
TYPE: <event_type>
PATH: <path>
TAGS: <json_data>
```
