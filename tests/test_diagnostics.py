# ZIPの内容、秘匿化、限定journal収集を検証する。
# 収集対象が固定され、実機ホームや秘密ファイルへ触れないことを確認する。
import json
import zipfile

from frame_toolbox.backends.mock import MockBackend
from frame_toolbox.config import AppConfig
from frame_toolbox.services.diagnostics_service import JOURNAL_PATTERN, DiagnosticsService, redact


def test_report_generation(fake_runner, tmp_path) -> None:
    runner = fake_runner()
    log = tmp_path / "toolbox.log"
    log.write_text("INFO refresh complete\npassword=must-not-be-shared\n")
    snapshot = MockBackend().collect(AppConfig(pc_ip="192.168.1.20"))
    snapshot.network.ssid = "token=must-not-be-shared"
    service = DiagnosticsService(runner, log)
    report = service.collect(snapshot, tmp_path / "reports")
    assert report.directory.name.startswith("frame-toolbox-report-") and report.archive.exists()
    expected = {"system.txt", "network.txt", "processes.txt", "audio.txt", "toolbox.log", "summary.json"}
    assert {p.name for p in report.directory.iterdir()} == expected
    with zipfile.ZipFile(report.archive) as bundle:
        assert {name.rsplit("/", 1)[-1] for name in bundle.namelist()} == expected
        summary = json.loads(bundle.read(f"{report.directory.name}/summary.json"))
        assert summary["mock"] is True and summary["network"]["pc_ping"]["target"] == "192.168.1.20"
        assert "must-not-be-shared" not in bundle.read(f"{report.directory.name}/toolbox.log").decode()
        assert summary["network"]["ssid"] == "token=[REDACTED]"
    assert runner.calls == []
    second = service.collect(snapshot, tmp_path / "reports")
    assert second.archive != report.archive


def test_journal_is_bounded_and_opt_in(fake_runner, tmp_path) -> None:
    command = ("journalctl", "--user", "--boot=0", "--no-pager", "--lines", "200", "--grep", JOURNAL_PATTERN, "--output=short-iso")
    runner = fake_runner({command: "steam: token=secret\nsteam: ready"})
    snapshot = MockBackend().collect(AppConfig())
    snapshot.mock = False
    report = DiagnosticsService(runner).collect(snapshot, tmp_path, include_journal=True)
    assert runner.calls == [command]
    assert "secret" not in (report.directory / "related-journal.txt").read_text()


def test_mock_never_calls_journal(fake_runner, tmp_path) -> None:
    runner = fake_runner()
    report = DiagnosticsService(runner).collect(MockBackend().collect(AppConfig()), tmp_path, include_journal=True)
    assert runner.calls == []
    assert "Mock Mode" in (report.directory / "related-journal.txt").read_text()


def test_redaction() -> None:
    text = "Bearer abcdef\n-----BEGIN OPENSSH PRIVATE KEY-----\nsecret\n-----END OPENSSH PRIVATE KEY-----\nhttps://user:pass@example.org"
    result = redact(text)
    assert "abcdef" not in result and "secret" not in result and "user:pass" not in result
