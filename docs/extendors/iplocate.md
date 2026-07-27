# Iplocate

Get your ip address in seconds.

## Overview

Iplocate provides a service for you to get your ip address (And conneting port, if specified.) without signing in!

## Enabling

```json
{
    "extendors": {
        "iplocate": true
    }
}
```

- **Note:** Turned off by default

## API Endpoints
- Endpoint 1: POST /api/iplocate/myip
```json
POST /api/iplocate/myip

// Body
{
    // "needport": true // if you want port too.
}
```

- Endpoint 2: GET /myip
* Frontend for the user.