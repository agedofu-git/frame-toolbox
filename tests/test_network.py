# ネットワークの解析、判定、フォールバックを検証する。
# ICMPやWi-Fi機器へ実際の通信は行わない。
import json

import pytest

from frame_toolbox.config import NetworkThresholds
from frame_toolbox.models.status import Health, NetworkStatus, Reachability
from frame_toolbox.services.network_service import (
    NetworkService,
    PingProbe,
    assess_network,
    parse_default_route,
    parse_ip_addresses,
    parse_iw_link,
    parse_nmcli_device,
    parse_nmcli_wifi,
    parse_ping,
    split_nmcli,
    wifi_band,
)
from frame_toolbox.utils.command import CommandResult


def test_ip_output() -> None:
    text = json.dumps([{"ifname": "wlan0", "addr_info": [
        {"local": "192.168.1.50", "scope": "global"}, {"local": "::1", "scope": "host"},
    ]}])
    assert parse_ip_addresses(text, "wlan0") == ["192.168.1.50"]
    assert parse_ip_addresses(text, "eth0") == []
    assert parse_ip_addresses("not-json") == []
    assert parse_ip_addresses("{}") == []


def test_routes_choose_lowest_metric() -> None:
    routes = json.dumps([{"dst": "default", "dev": "eth0", "gateway": "10.0.0.1", "metric": 100},
                         {"dst": "default", "dev": "wlan0", "gateway": "192.168.1.1", "metric": 20}])
    assert parse_default_route(routes) == ("wlan0", "192.168.1.1")
    assert parse_default_route("[]") == (None, None)
    assert parse_default_route("bad") == (None, None)


def test_nmcli_escape_and_wifi_rate() -> None:
    assert split_nmcli(r"*:Room\:A\\B:92:33:1921 Mbit/s") == ["*", "Room:A\\B", "92", "33", "1921 Mbit/s"]
    parsed = parse_nmcli_wifi(r"*:Room\:A:92:33:1921 Mbit/s")
    assert parsed["ssid"] == "Room:A" and parsed["signal_percent"] == 92
    assert parsed["advertised_rate_mbps"] == 1921 and "bitrate_mbps" not in parsed
    assert parse_nmcli_wifi("broken") == {}
    assert parse_nmcli_device(r"IP6.DNS[1]:fe80\:\:1")["IP6.DNS"] == ["fe80::1"]


def test_iw_information() -> None:
    parsed = parse_iw_link("Connected to aa:bb\n\tSSID: Frame Lab\n\tfreq: 6115\n\tsignal: -48 dBm\n\ttx bitrate: 1921.0 MBit/s EHT\n")
    assert parsed["signal_dbm"] == -48 and parsed["frequency_mhz"] == 6115
    assert parsed["bitrate_mbps"] == 1921 and parsed["connected"] is True
    assert wifi_band(6115) == "6 GHz" and wifi_band(2412) == "2.4 GHz"
    assert parse_iw_link("Not connected.")["connected"] is False


@pytest.mark.parametrize("signal,bitrate,gateway,health", [
    (-48, 1921, True, Health.GOOD), (-85, 1921, True, Health.WARNING),
    (-48, 10, True, Health.WARNING), (-48, 1921, False, Health.BAD),
    (None, None, None, Health.UNKNOWN),
])
def test_network_health(signal, bitrate, gateway, health) -> None:
    status = NetworkStatus(connection_type="Wi-Fi", connected=True, signal_dbm=signal,
                           bitrate_mbps=bitrate, gateway_ping=Reachability("192.168.1.1", gateway))
    assess_network(status, NetworkThresholds())
    assert status.health == health


def test_missing_network_commands(fake_runner, tmp_path) -> None:
    status = NetworkService(fake_runner(), sys_net=tmp_path, resolv=tmp_path / "none").collect("", NetworkThresholds())
    assert status.health == Health.UNKNOWN
    assert status.interface is None and status.pc_ping.target is None


def test_network_service_collect(fake_runner, tmp_path) -> None:
    responses = {
        ("ip", "-j", "route", "show", "default"): '[{"dev":"wlan0","gateway":"192.168.1.1","dst":"default"}]',
        ("ip", "-j", "address", "show", "dev", "wlan0"): '[{"ifname":"wlan0","addr_info":[{"local":"192.168.1.50","scope":"global"}]}]',
        ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"): "wlan0:wifi:connected",
        ("iw", "dev", "wlan0", "link"): "Connected to aa:bb\nSSID: Lab\nfreq: 6115\nsignal: -48 dBm\ntx bitrate: 1921 MBit/s",
        ("iw", "dev", "wlan0", "info"): "channel 33 (6115 MHz)",
    }

    class Probe:
        def probe(self, target, interface=None):
            return Reachability(target, True, 1.2, "test reply")

    status = NetworkService(fake_runner(responses), Probe(), tmp_path, tmp_path / "none").collect("192.168.1.20", NetworkThresholds())
    assert status.health == Health.GOOD and status.channel == 33
    assert status.pc_ping.target == "192.168.1.20" and status.pc_ping.latency_ms == 1.2
    assert status.addresses == ["192.168.1.50"]


def test_ping_latency(fake_runner) -> None:
    args = ("ping", "-n", "-c", "1", "-W", "2", "--", "192.168.1.20")
    probe = PingProbe(fake_runner({args: "64 bytes: time=2.1 ms\nrtt min/avg/max/mdev = 2.1/2.1/2.1/0.0 ms"}))
    assert probe.probe("192.168.1.20").latency_ms == 2.1
    assert parse_ping("no reply") is None


def test_ping_failure_and_unavailable_are_distinct(fake_runner) -> None:
    args = ("ping", "-n", "-c", "1", "-W", "2", "--", "192.168.1.20")
    assert PingProbe(fake_runner({args: CommandResult(args, True, 1)})).probe("192.168.1.20").reachable is False
    assert PingProbe(fake_runner()).probe("192.168.1.20").reachable is None
    assert PingProbe(fake_runner()).probe("; sudo bad").detail == "Invalid IP address"
