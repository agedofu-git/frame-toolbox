# 診断結果を型付きデータとして定義する。
# UI、レポート、将来のOverlayの共通契約になる。
from dataclasses import dataclass, field
from enum import Enum


class Health(str, Enum):
    GOOD = "GOOD"
    WARNING = "WARNING"
    BAD = "BAD"
    UNKNOWN = "UNKNOWN"


@dataclass
class SystemStatus:
    hostname: str | None = None
    os_name: str | None = None
    steamos_version: str | None = None
    kernel: str | None = None
    architecture: str | None = None
    uptime_seconds: float | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    disk_used_bytes: int | None = None
    disk_total_bytes: int | None = None
    disk_path: str = "/"
    battery_percent: float | None = None
    charging_state: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class Reachability:
    target: str | None = None
    reachable: bool | None = None
    latency_ms: float | None = None
    detail: str = "Unavailable"


@dataclass
class NetworkStatus:
    interface: str | None = None
    connection_type: str | None = None
    connected: bool | None = None
    addresses: list[str] = field(default_factory=list)
    gateway: str | None = None
    dns: list[str] = field(default_factory=list)
    ssid: str | None = None
    signal_dbm: float | None = None
    signal_percent: int | None = None
    frequency_mhz: int | None = None
    channel: int | None = None
    bitrate_mbps: float | None = None
    ethernet_link_mbps: float | None = None
    advertised_rate_mbps: float | None = None
    gateway_ping: Reachability = field(default_factory=Reachability)
    pc_ping: Reachability = field(default_factory=Reachability)
    health: Health = Health.UNKNOWN
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class ProcessStatus:
    name: str
    pids: list[int] = field(default_factory=list)
    available: bool = True

    @property
    def label(self) -> str:
        return "Running" if self.pids else "Not detected" if self.available else "Unavailable"


@dataclass
class VRStatus:
    processes: list[ProcessStatus] = field(default_factory=list)
    openxr_runtime: str | None = None
    openxr_manifest: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def steamvr_label(self) -> str:
        # SteamVR固有の状態APIではなく、設定されたプロセスの観測結果。
        vr = [p for p in self.processes if p.name != "steam"]
        if any(p.pids for p in vr):
            return "Running (process detected)"
        return "Not detected" if vr and all(p.available for p in vr) else "Unavailable"


@dataclass
class AudioStatus:
    server: str | None = None
    default_output: str | None = None
    default_input: str | None = None
    microphone_muted: bool | None = None
    microphone_volume_percent: float | None = None
    microphone_level: str = "Unavailable (live capture is not enabled)"
    notes: list[str] = field(default_factory=list)


@dataclass
class Snapshot:
    system: SystemStatus = field(default_factory=SystemStatus)
    network: NetworkStatus = field(default_factory=NetworkStatus)
    vr: VRStatus = field(default_factory=VRStatus)
    audio: AudioStatus = field(default_factory=AudioStatus)
    collected_at: str = ""
    mock: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ActionResult:
    success: bool
    message: str
