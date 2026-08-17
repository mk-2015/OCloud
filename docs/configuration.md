# Configuration

All runtime settings live in `server/config.json`.

## Example

```json
{
    "host": "0.0.0.0",
    "port": 443,
    "cube": {
        "use": false,
        "islocal": true,
        "workers": ["tcp://localhost:2350"]
    },
    "ssl": {
        "use": true,
        "keyfile": "./key.pem",
        "certfile": "./cert.pem"
    },
    "extendors": {
        "fileshare": true,
        "monitord": true,
        "webshell": true,
        "iplocate": true
    },
    "oworkspace": {
        "use": true,
        "omail": {
            "domain": "opencloud.local"
        }
    },
    "max_upload_mb": 1024
}
```

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `host` | string | Bind address. Use `0.0.0.0` for all interfaces. |
| `port` | int | Listening port. |
| `max_upload_mb` | int | Maximum upload size in megabytes. |
| `admin_password` | string | Password for the built-in admin account. |

### `ssl`

| Field | Type | Description |
|-------|------|-------------|
| `use` | bool | Enable HTTPS. |
| `keyfile` | string | Path to the private key file. |
| `certfile` | string | Path to the certificate file. |

### `cube`

| Field | Type | Description |
|-------|------|-------------|
| `use` | bool | Enable the Cube component at startup. |
| `islocal` | bool | Run lambdas locally (ignores `workers`). |
| `workers` | string[] | Remote worker addresses (e.g. `tcp://host:port`). |

### `oworkspace`

| Field | Type | Description |
|-------|------|-------------|
| `use` | bool | Enable OWorkspace. |
| `omail.domain` | string | Domain name for OMail. Defaults to `opencloud.local`. |

### `extendors`

| Field | Type | Description |
|-------|------|-------------|
| `fileshare` | bool | Enable the file sharing extendor. |
| `monitord` | bool | Enable the monitor dashboard. |
| `webshell` | bool | Enable the web terminal. |
| `iplocate` | bool | Enable IP location service. |

## Firewall

If running on Windows and other devices can't connect, add firewall rules:

```
netsh advfirewall firewall add rule name="OCloud" dir=in action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="OCloud (Outbound)" dir=out action=allow protocol=TCP localport=80
netsh advfirewall firewall add rule name="OCloud SSL" dir=in action=allow protocol=TCP localport=443
netsh advfirewall firewall add rule name="OCloud SSL (Outbound)" dir=out action=allow protocol=TCP localport=443
```

Run in an elevated Command Prompt (Run as administrator).
