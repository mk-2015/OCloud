import time
import platform
import psutil
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from modules.auth import require_session, Request, WebSocketAuthException

monitord = APIRouter()


def _bytes_fmt(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _get_stats_data():
    cpu_percent = psutil.cpu_percent(interval=None)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else None

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    disk = psutil.disk_usage("/")

    boot = psutil.boot_time()
    uptime_secs = int(time.time() - boot)

    net = psutil.net_io_counters()
    interfaces = psutil.net_if_addrs()

    return {
        "cpu": {
            "percent": cpu_percent,
            "count": cpu_count,
            "freq_current": round(cpu_freq.current, 0) if cpu_freq else None,
            "freq_max": round(cpu_freq.max, 0) if cpu_freq else None,
            "load_avg": {
                "1m": round(load_avg[0], 2),
                "5m": round(load_avg[1], 2),
                "15m": round(load_avg[2], 2),
            } if load_avg else None,
        },
        "memory": {
            "total": mem.total,
            "used": mem.used,
            "available": mem.available,
            "percent": mem.percent,
            "total_fmt": _bytes_fmt(mem.total),
            "used_fmt": _bytes_fmt(mem.used),
            "available_fmt": _bytes_fmt(mem.available),
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "percent": swap.percent,
            "total_fmt": _bytes_fmt(swap.total),
            "used_fmt": _bytes_fmt(swap.used),
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
            "total_fmt": _bytes_fmt(disk.total),
            "used_fmt": _bytes_fmt(disk.used),
            "free_fmt": _bytes_fmt(disk.free),
        },
        "uptime": {
            "seconds": uptime_secs,
            "days": uptime_secs // 86400,
            "hours": (uptime_secs % 86400) // 3600,
            "minutes": (uptime_secs % 3600) // 60,
            "boot_time": int(boot),
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "bytes_sent_fmt": _bytes_fmt(net.bytes_sent),
            "bytes_recv_fmt": _bytes_fmt(net.bytes_recv),
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "interface_count": len(interfaces),
        },
        "system": {
            "os": platform.system(),
            "os_release": platform.release(),
            "hostname": platform.node(),
            "python": platform.python_version(),
            "arch": platform.machine(),
        },
    }


def init_monitord():
    # Initial call to initialize psutil sensors
    psutil.cpu_percent(interval=None)


@monitord.get("/api/monitord/test")
def test():
    return {"Test": "Ok"}


@monitord.get("/api/monitord/stats")
def get_stats(request: Request):
    require_session(request, required_role="admin")
    return _get_stats_data()


@monitord.websocket("/ws/monitor")
async def monitor_websocket(websocket: WebSocket):
    try:
        require_session(websocket, required_role="admin")
    except WebSocketAuthException as e:
        await websocket.close(code=e.code)
        return

    await websocket.accept()
    try:
        while True:
            stats = _get_stats_data()
            await websocket.send_json(stats)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()


@monitord.get("/api/monitord/processes")
def get_processes(request: Request):
    require_session(request, required_role="admin")

    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "user": info.get("username") or "-",
                "cpu": round(info.get("cpu_percent") or 0, 1),
                "mem": round(info.get("memory_percent") or 0, 1),
                "status": info.get("status") or "-",
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: x["cpu"], reverse=True)

    return {"processes": procs[:50]}


@monitord.get("/api/monitord/disks")
def get_disks(request: Request):
    require_session(request, required_role="admin")

    disks = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
                "total_fmt": _bytes_fmt(usage.total),
                "used_fmt": _bytes_fmt(usage.used),
                "free_fmt": _bytes_fmt(usage.free),
            })
        except (PermissionError, OSError):
            continue

    return {"disks": disks}


@monitord.get("/api/monitord/network")
def get_network(request: Request):
    require_session(request, required_role="admin")

    interfaces = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for name, addr_list in addrs.items():
        stat = stats.get(name)
        ips = []
        for addr in addr_list:
            if addr.family.name in ("AF_INET", "AF_INET6"):
                ips.append({
                    "family": addr.family.name,
                    "address": addr.address,
                    "netmask": addr.netmask,
                })
        interfaces.append({
            "name": name,
            "ips": ips,
            "is_up": stat.isup if stat else False,
            "speed": stat.speed if stat else 0,
        })

    counters = psutil.net_io_counters(pernic=True)
    for iface in interfaces:
        c = counters.get(iface["name"])
        if c:
            iface["bytes_sent"] = c.bytes_sent
            iface["bytes_recv"] = c.bytes_recv
            iface["bytes_sent_fmt"] = _bytes_fmt(c.bytes_sent)
            iface["bytes_recv_fmt"] = _bytes_fmt(c.bytes_recv)

    return {"interfaces": interfaces}
