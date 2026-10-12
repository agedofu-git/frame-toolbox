# 実機I/Oを使用しないデモ用バックエンド。
# Windowsや通常Linuxでも全画面と設定、レポートを検証できる。
from datetime import datetime, timezone

from frame_toolbox.config import AppConfig
from frame_toolbox.models.status import (
    AudioStatus,
    Health,
    NetworkStatus,
    ProcessStatus,
    Reachability,
    Snapshot,
    SystemStatus,
    VRStatus,
)
from frame_toolbox.services.network_service import assess_network
from frame_toolbox.services.restart_service import MockRestartBackend


class MockBackend:
    def __init__(self) -> None:
        self.restart_backend = MockRestartBackend()

    def collect(self, config: AppConfig) -> Snapshot:
        config.validate()
        pc = Reachability(config.pc_ip, True, 2.3, "Mock ICMP reply") if config.pc_ip else Reachability(detail="PC IP not configured")
        snapshot = Snapshot(
            system=SystemStatus(
                hostname="steam-frame-mock", os_name="SteamOS (mock)",
                steamos_version="Unknown (mock)", kernel="7.x.x (mock)", architecture="aarch64 (mock)",
                uptime_seconds=9060, memory_used_bytes=5 * 1024**3, memory_total_bytes=16 * 1024**3,
                disk_used_bytes=80 * 1024**3, disk_total_bytes=256 * 1024**3,
                battery_percent=72, charging_state="Discharging", notes=["All values are simulated"],
            ),
            network=NetworkStatus(
                interface="wlan0", connection_type="Wi-Fi", connected=True,
                addresses=["192.168.1.50"], gateway="192.168.1.1", dns=["192.168.1.1"],
                ssid="Frame Lab (mock)", signal_dbm=-48, signal_percent=92,
                frequency_mhz=6115, channel=33, bitrate_mbps=1921,
                gateway_ping=Reachability("192.168.1.1", True, 1.1, "Mock ICMP reply"),
                pc_ping=pc, health=Health.GOOD, notes=["All values are simulated"],
            ),
            vr=VRStatus([ProcessStatus(name, [1000 + i]) for i, name in enumerate(config.vr_process_names)],
                        "SteamVR (mock)", "Mock manifest; no file read"),
            audio=AudioStatus("PipeWire (mock)", "Steam Frame Audio (mock)", "Steam Frame Mic (mock)",
                              False, 80.0, "Unavailable (no microphone capture)"),
            collected_at=datetime.now(timezone.utc).isoformat(), mock=True,
        )
        assess_network(snapshot.network, config.thresholds)
        return snapshot
