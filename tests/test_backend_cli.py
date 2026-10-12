# バックエンドの障害分離とQtなしCLIを検証する。
# Mock Modeで実機コマンドが実行されないことを確認する。
import json
import os
import subprocess
import sys
from pathlib import Path

from frame_toolbox.backends.linux import LinuxBackend
from frame_toolbox.backends.mock import MockBackend
from frame_toolbox.config import AppConfig
from frame_toolbox.main import main
from frame_toolbox.models.status import Health


def test_mock_snapshot() -> None:
    snapshot = MockBackend().collect(AppConfig(pc_ip="192.168.1.20"))
    assert snapshot.mock and snapshot.system.battery_percent == 72
    assert snapshot.network.frequency_mhz == 6115 and snapshot.network.bitrate_mbps == 1921
    assert snapshot.network.pc_ping.reachable is True
    assert "Running" in snapshot.vr.steamvr_label


def test_mock_uses_configured_thresholds() -> None:
    config = AppConfig()
    config.thresholds.weak_signal_dbm = -40
    assert MockBackend().collect(config).network.health == Health.WARNING


def test_service_failure_is_isolated(fake_runner, monkeypatch) -> None:
    backend = LinuxBackend(fake_runner())

    def unavailable():
        raise PermissionError("private detail")

    monkeypatch.setattr(backend.system, "collect", unavailable)
    snapshot = backend.collect(AppConfig())
    assert "system: collection failed (PermissionError)" in snapshot.errors
    assert "private detail" not in " ".join(snapshot.errors)
    assert snapshot.audio.server is None
    assert len(snapshot.vr.processes) == 4


def test_headless_cli(tmp_path, capsys) -> None:
    code = main(["--mock", "--headless", "--config-dir", str(tmp_path / "config"),
                 "--state-dir", str(tmp_path / "state")])
    assert code == 0
    assert json.loads(capsys.readouterr().out)["mock"] is True
    assert (tmp_path / "state/toolbox.log").exists()


def test_collect_cli(tmp_path, capsys) -> None:
    code = main(["--mock", "--collect", "--config-dir", str(tmp_path / "config"),
                 "--state-dir", str(tmp_path / "state"), "--output-dir", str(tmp_path / "reports")])
    assert code == 0 and ".zip" in capsys.readouterr().out
    assert len(list((tmp_path / "reports").glob("*.zip"))) == 1


def test_cli_help_legacy_console_encoding() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "frame_toolbox", "--help"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=5,
        env=dict(os.environ, PYTHONIOENCODING="cp932"), shell=False,
    )
    assert result.returncode == 0, result.stderr
    assert b"Frame Toolbox" in result.stdout
