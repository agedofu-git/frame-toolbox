# Linuxの標準ネットワーク情報を収集・評価する。
# NetworkManagerやiwがなくても部分的な診断をUIへ提供する。
import ipaddress
import json
import re
from pathlib import Path
from typing import Protocol

from frame_toolbox.config import NetworkThresholds, validate_pc_ip
from frame_toolbox.models.status import Health, NetworkStatus, Reachability
from frame_toolbox.utils.command import CommandRunner
from frame_toolbox.utils.files import read_text


def parse_ip_addresses(text: str, interface: str | None = None) -> list[str]:
    try:
        rows = json.loads(text)
        if not isinstance(rows, list):
            return []
        addresses = []
        for row in rows:
            if not isinstance(row, dict) or interface and row.get("ifname") != interface:
                continue
            for entry in row.get("addr_info", []):
                if isinstance(entry, dict) and entry.get("scope") != "host" and entry.get("local"):
                    address = ipaddress.ip_address(entry["local"])
                    addresses.append(str(address))
        return list(dict.fromkeys(addresses))
    except (ValueError, TypeError, AttributeError):
        return []


def parse_default_route(text: str) -> tuple[str | None, str | None]:
    try:
        rows = json.loads(text)
        if not isinstance(rows, list):
            return None, None
        routes = [r for r in rows if isinstance(r, dict) and r.get("dev")
                  and r.get("dst", "default") == "default" and r.get("type") not in
                  {"unreachable", "blackhole", "prohibit"}]
        route = min(routes, key=lambda r: int(r.get("metric", 0))) if routes else {}
        return route.get("dev"), route.get("gateway")
    except (ValueError, TypeError):
        return None, None


def split_nmcli(line: str) -> list[str]:
    fields: list[str] = []
    value = ""
    escaped = False
    for char in line:
        if escaped:
            value += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append(value)
            value = ""
        else:
            value += char
    fields.append(value + ("\\" if escaped else ""))
    return fields


def parse_nmcli_device(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for line in text.splitlines():
        fields = split_nmcli(line)
        if len(fields) >= 2:
            key = fields[0].split("[", 1)[0]
            value = ":".join(fields[1:])
            if value and value != "--":
                result.setdefault(key, []).append(value)
    return result


def parse_nmcli_wifi(text: str) -> dict[str, object]:
    for line in text.splitlines():
        fields = split_nmcli(line)
        if len(fields) != 5 or fields[0] not in {"*", "yes"}:
            continue
        rate = re.search(r"([\d.]+)\s*Mbit/s", fields[4])
        return {
            "ssid": fields[1] or None,
            "signal_percent": int(fields[2]) if fields[2].isdigit() and 0 <= int(fields[2]) <= 100 else None,
            "channel": int(fields[3]) if fields[3].isdigit() else None,
            # APの広告レートは実リンク速度ではないため別フィールドで保持。
            "advertised_rate_mbps": float(rate[1]) if rate else None,
        }
    return {}


def parse_iw_link(text: str) -> dict[str, object]:
    result: dict[str, object] = {}
    patterns = {
        "ssid": (r"^\s*SSID: (.+)$", str),
        "signal_dbm": (r"^\s*signal:\s*(-?[\d.]+)(?:\s+\[[^\]]*\])?\s+dBm", float),
        "frequency_mhz": (r"^\s*freq:\s*(\d+)", int),
        "bitrate_mbps": (r"^\s*tx bitrate:\s*([\d.]+)\s*MBit/s", float),
    }
    for key, (pattern, convert) in patterns.items():
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            result[key] = convert(match[1])
    if "Not connected" in text:
        result["connected"] = False
    elif "Connected to " in text:
        result["connected"] = True
    return result


def parse_ping(text: str) -> float | None:
    summary = re.search(r"(?:rtt|round-trip)[^=]*=\s*[\d.]+/([\d.]+)/", text)
    reply = re.search(r"time[=<]\s*([\d.]+)\s*ms", text)
    return float(summary[1]) if summary else float(reply[1]) if reply else None


def wifi_band(frequency_mhz: int | None) -> str:
    if frequency_mhz is None:
        return "Unknown"
    if 2400 <= frequency_mhz <= 2500:
        return "2.4 GHz"
    if 4900 <= frequency_mhz < 5925:
        return "5 GHz"
    if 5925 <= frequency_mhz <= 7125:
        return "6 GHz"
    return f"{frequency_mhz} MHz"


class ReachabilityProbe(Protocol):
    # PC Agentの接続方式を将来差し替えられる境界。
    def probe(self, target: str, interface: str | None = None) -> Reachability: ...


class PingProbe:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def probe(self, target: str, interface: str | None = None) -> Reachability:
        try:
            address = ipaddress.ip_address(target)
        except ValueError:
            return Reachability(target, detail="Invalid IP address")
        args = ["ping", "-n", "-c", "1", "-W", "2"]
        if address.version == 6:
            args.append("-6")
            if address.is_link_local and interface and re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", interface):
                args.extend(["-I", interface])
        args.extend(["--", str(address)])
        result = self.runner.run(args, timeout=3.5)
        if not result.exists or result.timed_out or result.error or result.exit_code not in (0, 1):
            return Reachability(target, detail=result.failure)
        return Reachability(target, result.ok, parse_ping(result.stdout) if result.ok else None,
                            "reachable" if result.ok else "No ICMP reply (may be filtered)")


def assess_network(status: NetworkStatus, thresholds: NetworkThresholds) -> None:
    status.warnings = []
    if status.gateway_ping.reachable is False:
        status.warnings.append("Gateway did not respond to ICMP; firewall filtering is also possible")
        status.health = Health.BAD
        return
    if status.signal_dbm is not None and status.signal_dbm < thresholds.weak_signal_dbm:
        status.warnings.append("Wi-Fi signal degraded (generic dBm threshold)")
    elif status.signal_dbm is None and status.signal_percent is not None \
            and status.signal_percent < thresholds.weak_signal_percent:
        status.warnings.append("Wi-Fi signal degraded (NetworkManager percentage)")
    if status.connection_type == "Wi-Fi" and status.bitrate_mbps is not None \
            and status.bitrate_mbps < thresholds.low_bitrate_mbps:
        status.warnings.append("Wi-Fi transmit bitrate below generic threshold")
    if status.pc_ping.reachable is False:
        status.warnings.append("PC did not respond to ICMP; check the PC firewall")
    if status.warnings:
        status.health = Health.WARNING
    elif status.gateway_ping.reachable is not True or status.connected is not True:
        status.health = Health.UNKNOWN
    elif status.pc_ping.target and status.pc_ping.reachable is None:
        status.health = Health.UNKNOWN
    elif status.connection_type == "Wi-Fi" and (
        status.signal_dbm is None and status.signal_percent is None or status.bitrate_mbps is None
    ):
        status.health = Health.UNKNOWN
    elif status.connection_type not in {"Wi-Fi", "Ethernet"}:
        status.health = Health.UNKNOWN
    else:
        status.health = Health.GOOD


class NetworkService:
    def __init__(self, runner: CommandRunner, probe: ReachabilityProbe | None = None,
                 sys_net: Path = Path("/sys/class/net"), resolv: Path = Path("/etc/resolv.conf")) -> None:
        self.runner = runner
        self.probe = probe or PingProbe(runner)
        self.sys_net, self.resolv = sys_net, resolv

    def collect(self, pc_ip: str, thresholds: NetworkThresholds) -> NetworkStatus:
        status = NetworkStatus()
        route = self.runner.run(["ip", "-j", "route", "show", "default"])
        if route.ok:
            status.interface, status.gateway = parse_default_route(route.stdout)
        if status.interface is None and route.exists:
            route6 = self.runner.run(["ip", "-6", "-j", "route", "show", "default"])
            if route6.ok:
                status.interface, status.gateway = parse_default_route(route6.stdout)
        if not route.ok:
            status.notes.append(route.failure)
        nm = self.runner.run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
        if nm.ok:
            for line in nm.stdout.splitlines():
                fields = split_nmcli(line)
                if len(fields) != 3:
                    continue
                name, kind, state = fields
                if not status.interface and state.startswith("connected") and kind in {"wifi", "ethernet"}:
                    status.interface = name
                if name == status.interface:
                    status.connection_type = {"wifi": "Wi-Fi", "ethernet": "Ethernet"}.get(kind, kind)
                    status.connected = state.startswith("connected")
        else:
            status.notes.append(nm.failure)
        interface = status.interface
        if interface and not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", interface):
            status.notes.append("Unsupported interface name")
            status.interface = interface = None
        if interface:
            addr = self.runner.run(["ip", "-j", "address", "show", "dev", interface])
            if addr.ok:
                status.addresses = parse_ip_addresses(addr.stdout, interface)
            elif addr.exists:
                status.notes.append(addr.failure)
            if status.connection_type is None:
                if (self.sys_net / interface / "wireless").exists() or (self.sys_net / interface / "phy80211").exists():
                    status.connection_type = "Wi-Fi"
                elif (read_text(self.sys_net / interface / "type") or "").strip() == "1":
                    status.connection_type = "Ethernet"
            if status.connected is None:
                carrier = (read_text(self.sys_net / interface / "carrier") or "").strip()
                status.connected = carrier == "1" if carrier in {"0", "1"} else None
            if status.connection_type == "Ethernet":
                speed = (read_text(self.sys_net / interface / "speed") or "").strip()
                status.ethernet_link_mbps = float(speed) if speed.isdigit() and int(speed) > 0 else None
            if nm.exists:
                details = self.runner.run([
                    "nmcli", "-t", "-f", "GENERAL.TYPE,GENERAL.STATE,IP4.ADDRESS,IP4.GATEWAY,IP4.DNS,IP6.ADDRESS,IP6.GATEWAY,IP6.DNS",
                    "device", "show", interface,
                ])
                if details.ok:
                    data = parse_nmcli_device(details.stdout)
                    if not status.addresses:
                        status.addresses = [v.split("/", 1)[0] for key in ("IP4.ADDRESS", "IP6.ADDRESS") for v in data.get(key, [])]
                    if not status.gateway:
                        status.gateway = next(iter(data.get("IP4.GATEWAY", []) + data.get("IP6.GATEWAY", [])), None)
                    status.dns = data.get("IP4.DNS", []) + data.get("IP6.DNS", [])
            if status.connection_type in {"Wi-Fi", None}:
                link = self.runner.run(["iw", "dev", interface, "link"])
                if link.ok:
                    for key, value in parse_iw_link(link.stdout).items():
                        setattr(status, key, value)
                    if status.ssid or status.frequency_mhz:
                        status.connection_type = "Wi-Fi"
                else:
                    status.notes.append(link.failure)
                if status.connection_type == "Wi-Fi":
                    self._wifi_details(status, interface, nm.exists)
        if not status.dns:
            status.dns = [line.split()[1] for line in (read_text(self.resolv) or "").splitlines()
                          if line.strip().startswith("nameserver ") and len(line.split()) >= 2]
            if status.dns:
                status.notes.append("DNS fallback: resolv.conf may list a local stub resolver")
        if status.gateway:
            status.gateway_ping = self.probe.probe(status.gateway, interface)
        if pc_ip:
            status.pc_ping = self.probe.probe(validate_pc_ip(pc_ip))
        assess_network(status, thresholds)
        return status

    def _wifi_details(self, status: NetworkStatus, interface: str, nm_available: bool) -> None:
        if status.bitrate_mbps is None:
            station = self.runner.run(["iw", "dev", interface, "station", "dump"])
            if station.ok:
                for key, value in parse_iw_link(station.stdout).items():
                    if getattr(status, key) is None:
                        setattr(status, key, value)
        info = self.runner.run(["iw", "dev", interface, "info"])
        if info.ok:
            channel = re.search(r"channel (\d+) \((\d+) MHz\)", info.stdout)
            if channel:
                status.channel = int(channel[1])
                if status.frequency_mhz is None:
                    status.frequency_mhz = int(channel[2])
        if nm_available:
            wifi = self.runner.run([
                "nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,CHAN,RATE", "device", "wifi", "list",
                "ifname", interface, "--rescan", "no",
            ])
            if wifi.ok:
                for key, value in parse_nmcli_wifi(wifi.stdout).items():
                    if getattr(status, key) is None:
                        setattr(status, key, value)
