# 標準Linux情報源からOS、使用量、電源状態を取得する。
# Steam Frame固有のパスを仮定せず、欠落はNoneで返す。
import platform
import re
import shlex
import shutil
import socket
from pathlib import Path

from frame_toolbox.models.status import SystemStatus
from frame_toolbox.utils.files import number, read_text


def parse_os_release(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            continue
        try:
            tokens = shlex.split(value, comments=True, posix=True)
            result[key] = " ".join(tokens)
        except ValueError:
            continue
    return result


def parse_memory(text: str) -> tuple[int | None, int | None]:
    entries: dict[str, int] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"(\w+):\s+(\d+)\s+kB", line.strip())
        if match:
            entries[match[1]] = int(match[2]) * 1024
    total = entries.get("MemTotal")
    available = entries.get("MemAvailable")
    return (max(0, total - available) if total is not None and available is not None else None, total)


class SystemService:
    def __init__(self, etc: Path = Path("/etc"), proc: Path = Path("/proc"),
                 power: Path = Path("/sys/class/power_supply"), disk: Path = Path("/")) -> None:
        self.etc, self.proc, self.power, self.disk = etc, proc, power, disk

    def collect(self) -> SystemStatus:
        status = SystemStatus(disk_path=str(self.disk))
        try:
            status.hostname = socket.gethostname()
            status.kernel = platform.release()
            status.architecture = platform.machine()
        except OSError:
            status.notes.append("Platform information unavailable")
        os_release = read_text(self.etc / "os-release")
        if os_release is None:
            os_release = read_text(Path("/usr/lib/os-release"))
        os_info = parse_os_release(os_release or "")
        status.os_name = os_info.get("PRETTY_NAME") or os_info.get("NAME")
        # VERSION_IDだけでSteamOSと断定しない。
        if os_info.get("ID", "").lower() == "steamos":
            status.steamos_version = os_info.get("VERSION_ID") or os_info.get("VERSION")
        raw_uptime = (read_text(self.proc / "uptime") or "").split()
        status.uptime_seconds = number(raw_uptime[0]) if raw_uptime else None
        status.memory_used_bytes, status.memory_total_bytes = parse_memory(
            read_text(self.proc / "meminfo") or ""
        )
        try:
            disk = shutil.disk_usage(self.disk)
            status.disk_used_bytes, status.disk_total_bytes = disk.used, disk.total
        except OSError:
            status.notes.append("Disk usage unavailable")
        batteries: list[tuple[float | None, str | None]] = []
        try:
            for supply in sorted(self.power.iterdir())[:64]:
                if (read_text(supply / "type") or "").strip() != "Battery":
                    continue
                present = (read_text(supply / "present") or "1").strip()
                if present == "0":
                    continue
                capacity = number(read_text(supply / "capacity"))
                batteries.append((capacity if capacity is not None and 0 <= capacity <= 100 else None,
                                  (read_text(supply / "status") or "").strip() or None))
            if len(batteries) == 1:
                status.battery_percent, status.charging_state = batteries[0]
            elif len(batteries) > 1:
                status.notes.append("Multiple batteries detected; no device-specific selection configured")
        except OSError:
            status.notes.append("Battery information unavailable")
        return status
