# Monitord

Real-time system monitoring dashboard.

## Overview

Monitord provides a live dashboard showing CPU, memory, disk, swap usage, system info, uptime, network stats, and top processes. Data refreshes every 3 seconds.

## Enabling

```json
{
    "extendors": {
        "monitord": true
    }
}
```

Requires `psutil` (already in `requirements.txt`).

## Dashboard

Access at `/monitor/index.html`. **Admin only** — non-admin users are redirected to the dashboard.

Features:

- **Gauge cards** — CPU, memory, disk, swap with color-coded rings (green < 70%, yellow < 90%, red >= 90%)
- **System info** — hostname, OS, architecture, Python version
- **Uptime** — days/hours/minutes since last boot
- **Network** — total bytes sent/received, interface count
- **Disks** — per-partition usage
- **Top processes** — top 50 by CPU usage with PID, name, user, CPU%, MEM%, status

## API Endpoints

All endpoints require admin session auth.

### System Stats

```
GET /api/monitord/stats
```

Returns:

```json
{
    "cpu": {
        "percent": 12.5,
        "count": 8,
        "freq_current": 3200,
        "freq_max": 4500,
        "load_avg": { "1m": 0.5, "5m": 0.3, "15m": 0.2 }
    },
    "memory": {
        "total": 17179869184,
        "used": 8589934592,
        "available": 8589934592,
        "percent": 50.0,
        "total_fmt": "16.0 GB",
        "used_fmt": "8.0 GB",
        "available_fmt": "8.0 GB"
    },
    "swap": { "...": "same structure" },
    "disk": { "...": "same structure" },
    "uptime": {
        "seconds": 123456,
        "days": 1,
        "hours": 10,
        "minutes": 17,
        "boot_time": 1700000000
    },
    "network": {
        "bytes_sent": 1234567,
        "bytes_recv": 9876543,
        "bytes_sent_fmt": "1.2 MB",
        "bytes_recv_fmt": "9.9 MB",
        "packets_sent": 12345,
        "packets_recv": 98765
    },
    "system": {
        "os": "Windows",
        "os_release": "10",
        "hostname": "my-pc",
        "python": "3.13.3",
        "arch": "AMD64"
    }
}
```

### Top Processes

```
GET /api/monitord/processes
```

Returns top 50 processes sorted by CPU usage:

```json
{
    "processes": [
        {
            "pid": 1234,
            "name": "python.exe",
            "user": "WTS",
            "cpu": 12.5,
            "mem": 3.2,
            "status": "running"
        }
    ]
}
```

### Disk Partitions

```
GET /api/monitord/disks
```

Returns all mounted partitions:

```json
{
    "disks": [
        {
            "device": "/dev/sda1",
            "mountpoint": "/",
            "fstype": "ext4",
            "total": 500000000000,
            "used": 200000000000,
            "free": 300000000000,
            "percent": 40.0,
            "total_fmt": "500.0 GB",
            "used_fmt": "200.0 GB",
            "free_fmt": "300.0 GB"
        }
    ]
}
```

### Network Interfaces

```
GET /api/monitord/network
```

Returns all network interfaces:

```json
{
    "interfaces": [
        {
            "name": "eth0",
            "ips": [
                { "family": "AF_INET", "address": "192.168.1.100", "netmask": "255.255.255.0" }
            ],
            "is_up": true,
            "speed": 1000,
            "bytes_sent": 1234567,
            "bytes_recv": 9876543,
            "bytes_sent_fmt": "1.2 MB",
            "bytes_recv_fmt": "9.9 MB"
        }
    ]
}
```

### Health Check

```
GET /api/monitord/test
```

**Response**: `{"Test": "Ok"}`

## File Location

`server/modules/extend/monitord.py`
