# Snapshotの値を利用者向けのテキストへ整形する。
# QtとI/Oに依存しないため表示規則を単体検証できる。
from frame_toolbox.models.status import Health, Reachability, Snapshot
from frame_toolbox.services.network_service import wifi_band


def value(item: object, unit: str = "") -> str:
    return "Unavailable" if item is None else f"{item:g}{unit}" if isinstance(item, (int, float)) else f"{item}{unit}"


def usage(used: int | None, total: int | None) -> str:
    if total is None or used is None:
        return "Unavailable"
    return f"{used / 1024**3:.1f} / {total / 1024**3:.1f} GiB"


def uptime(seconds: float | None) -> str:
    if seconds is None:
        return "Unavailable"
    hours, rest = divmod(int(seconds), 3600)
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h {rest // 60}m" if days else f"{hours}h {rest // 60}m"


def reachability(ping: Reachability) -> str:
    if ping.target is None:
        return "UNKNOWN · Not configured / no gateway detected"
    state = "OK · reachable" if ping.reachable is True else "WARNING · no ICMP reply" if ping.reachable is False else "UNKNOWN · unavailable"
    latency = f" · {ping.latency_ms:.2f} ms" if ping.latency_ms is not None else ""
    return f"{state}{latency}\n{ping.target} · {ping.detail}"


def health_label(health: Health) -> str:
    return {Health.GOOD: "OK (GOOD)", Health.WARNING: "WARNING", Health.BAD: "ERROR (BAD)",
            Health.UNKNOWN: "UNKNOWN"}[health]


def status_rows(snapshot: Snapshot) -> dict[str, dict[str, str]]:
    s, n, a, vr = snapshot.system, snapshot.network, snapshot.audio, snapshot.vr
    system = {
        "Hostname": value(s.hostname), "OS": value(s.os_name),
        "SteamOS": s.steamos_version or "Unknown / not detected", "Kernel": value(s.kernel),
        "Architecture": value(s.architecture), "Uptime": uptime(s.uptime_seconds),
        "Memory": usage(s.memory_used_bytes, s.memory_total_bytes),
        f"Disk ({s.disk_path})": usage(s.disk_used_bytes, s.disk_total_bytes),
        "Battery": value(s.battery_percent, "%"), "Charging state": value(s.charging_state),
        "Notes": "\n".join(s.notes) or "—",
    }
    connection = "Connected" if n.connected is True else "Disconnected" if n.connected is False else "Unknown"
    network = {
        "Assessment": health_label(n.health), "Interface": value(n.interface),
        "Connection": f"{value(n.connection_type)} · {connection}", "IP addresses": ", ".join(n.addresses) or "Unavailable",
        "Gateway": value(n.gateway), "DNS": ", ".join(n.dns) or "Unavailable", "SSID": value(n.ssid),
        "Band": wifi_band(n.frequency_mhz), "Frequency": value(n.frequency_mhz, " MHz"),
        "Channel": value(n.channel), "Signal": value(n.signal_dbm, " dBm"),
        "NM signal": value(n.signal_percent, "% (not dBm)"),
        "TX link bitrate": value(n.bitrate_mbps, " Mbps"),
        "Ethernet link speed": value(n.ethernet_link_mbps, " Mbps"),
        "AP advertised rate": value(n.advertised_rate_mbps, " Mbps (not link speed)"),
        "Gateway ping": reachability(n.gateway_ping), "PC ping": reachability(n.pc_ping),
        "Warnings": "\n".join(n.warnings) or "None detected / incomplete information may remain",
        "Notes": "\n".join(n.notes) or "—",
    }
    audio = {
        "Audio server": value(a.server), "Output": value(a.default_output), "Input": value(a.default_input),
        "Microphone mute": "Muted" if a.microphone_muted is True else "Not muted" if a.microphone_muted is False else "Unavailable",
        "Microphone volume": value(a.microphone_volume_percent, "% (configured gain)"),
        "Mic level": a.microphone_level, "Notes": "\n".join(a.notes) or "—",
    }
    vr_rows = {"SteamVR": vr.steamvr_label,
               **{p.name: p.label + (" · PID " + ", ".join(map(str, p.pids)) if p.pids else "") for p in vr.processes},
               "OpenXR": vr.openxr_runtime or "Unknown", "Runtime manifest": value(vr.openxr_manifest),
               "Notes": "\n".join(vr.notes) or "Process presence does not prove runtime health"}
    return {"System": system, "Network": network, "VR": vr_rows, "Audio": audio}
