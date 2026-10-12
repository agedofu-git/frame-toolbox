# 標準OS情報と不足したLinux情報の扱いを検証する。
# 一時ディレクトリをproc/sysの代わりに使用する。
from frame_toolbox.services.system_service import SystemService, parse_memory, parse_os_release


def test_os_release_parsing() -> None:
    data = parse_os_release('# comment\nID=steamos\nPRETTY_NAME="SteamOS Test"\nVERSION_ID="3.99"\nBAD="broken\nUNQUOTED=test\n')
    assert data["ID"] == "steamos"
    assert data["PRETTY_NAME"] == "SteamOS Test"
    assert data["VERSION_ID"] == "3.99"
    assert "BAD" not in data


def test_os_release_is_not_executed() -> None:
    assert parse_os_release('NAME="$(touch /tmp/must-not-exist)"')["NAME"] == "$(touch /tmp/must-not-exist)"


def test_memory() -> None:
    assert parse_memory("MemTotal: 1000 kB\nMemAvailable: 300 kB") == (700 * 1024, 1000 * 1024)
    assert parse_memory("") == (None, None)


def test_system_collect(tmp_path) -> None:
    etc, proc, power = (tmp_path / name for name in ("etc", "proc", "power"))
    for path in (etc, proc, power / "BAT0"):
        path.mkdir(parents=True)
    (etc / "os-release").write_text('ID=steamos\nPRETTY_NAME="SteamOS Test"\nVERSION_ID=3.99')
    (proc / "uptime").write_text("9060.5 1000")
    (proc / "meminfo").write_text("MemTotal: 1000 kB\nMemAvailable: 300 kB")
    (power / "BAT0/type").write_text("Battery\n")
    (power / "BAT0/capacity").write_text("72\n")
    (power / "BAT0/status").write_text("Discharging\n")
    status = SystemService(etc, proc, power, tmp_path).collect()
    assert status.steamos_version == "3.99"
    assert status.uptime_seconds == 9060.5
    assert status.battery_percent == 72 and status.charging_state == "Discharging"
    assert status.disk_total_bytes > 0


def test_missing_sources_and_non_steamos(tmp_path) -> None:
    (tmp_path / "os-release").write_text("ID=arch\nVERSION_ID=1\nNAME=Linux")
    status = SystemService(tmp_path, tmp_path / "missing", tmp_path / "missing", tmp_path).collect()
    assert status.os_name == "Linux" and status.steamos_version is None
    assert status.battery_percent is None and status.uptime_seconds is None


def test_multiple_batteries_are_not_guessed(tmp_path) -> None:
    for name in ("BAT0", "controller"):
        path = tmp_path / name
        path.mkdir()
        (path / "type").write_text("Battery")
        (path / "capacity").write_text("72")
    status = SystemService(tmp_path, tmp_path, tmp_path, tmp_path).collect()
    assert status.battery_percent is None
    assert "Multiple batteries" in " ".join(status.notes)
