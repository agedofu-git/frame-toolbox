# Mock UIの操作とGUI応答性をQtのイベントループで検証する。
# 遅いバックエンド中もタイマーが動き、終了時にWorkerを安全に保持する。
import time

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from frame_toolbox.backends.mock import MockBackend
from frame_toolbox.config import AppConfig, ConfigStore
from frame_toolbox.services.diagnostics_service import DiagnosticsService
from frame_toolbox.ui.main_window import MainWindow


def wait_until(app, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    assert predicate(), "Background operation did not complete"


def make_window(tmp_path, fake_runner, backend=None):
    return MainWindow(backend or MockBackend(), AppConfig(auto_refresh_seconds=0),
                      ConfigStore(tmp_path / "config.json"), DiagnosticsService(fake_runner()),
                      tmp_path / "reports", mock=True)


def test_all_ui_tabs_settings_refresh_and_report(qt_app, fake_runner, tmp_path) -> None:
    window = make_window(tmp_path, fake_runner)
    window.show()
    try:
        wait_until(qt_app, lambda: window.snapshot is not None and window.worker is None)
        assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == ["Overview", "Network", "VR", "Audio", "Diagnostics", "Settings"]
        assert "72%" in window.overview_panels["System"].values["Battery"].text()
        assert "6 GHz" in window.panels["Network"].values["Band"].text()
        assert "Memory" in window.overview_panels["System"].values
        window.pc_ip.setText("192.168.1.20")
        window.save_button.click()
        wait_until(qt_app, lambda: window.worker is None)
        assert window.store.load().pc_ip == "192.168.1.20"
        assert window.snapshot.network.pc_ping.target == "192.168.1.20"
        window.collect_button.click()
        wait_until(qt_app, lambda: window.worker is None)
        assert list((tmp_path / "reports").glob("*.zip"))
        assert "Diagnostics ZIP created" in window.report_result.toPlainText()
        for index in range(window.tabs.count()):
            window.tabs.setCurrentIndex(index)
            qt_app.processEvents()
            assert not window.grab().isNull()
    finally:
        wait_until(qt_app, lambda: window.worker is None)
        window.close()


def test_refresh_does_not_block_event_loop(qt_app, fake_runner, tmp_path) -> None:
    class SlowBackend(MockBackend):
        def collect(self, config):
            time.sleep(0.35)
            return super().collect(config)

    ticks = []
    heartbeat = QTimer()
    heartbeat.setInterval(10)
    heartbeat.timeout.connect(lambda: ticks.append(time.monotonic()))
    window = make_window(tmp_path, fake_runner, SlowBackend())
    window.show()
    heartbeat.start()
    try:
        wait_until(qt_app, lambda: window.worker is not None)
        assert not window.refresh_button.isEnabled()
        window.refresh()
        wait_until(qt_app, lambda: window.snapshot is not None and window.worker is None)
        assert len(ticks) >= 10
        assert window.refresh_button.isEnabled()
        window.refresh_button.click()
        wait_until(qt_app, lambda: window.worker is not None)
        window.close()
        assert window.close_pending and window.isVisible()
        wait_until(qt_app, lambda: not window.isVisible())
    finally:
        heartbeat.stop()
        wait_until(qt_app, lambda: window.worker is None)
        window.close()


def test_restart_confirmation(qt_app, fake_runner, tmp_path, monkeypatch) -> None:
    window = make_window(tmp_path, fake_runner)
    try:
        wait_until(qt_app, lambda: window.snapshot is not None and window.worker is None)
        confirmations = []

        def confirm(*args):
            confirmations.append(args[2])
            return QMessageBox.StandardButton.Yes

        monkeypatch.setattr(QMessageBox, "question", confirm)
        window.restart_button.click()
        wait_until(qt_app, lambda: window.worker is None)
        assert "No process is changed" in confirmations[0]
        assert "Mock restart completed" in window.statusBar().currentMessage()
    finally:
        wait_until(qt_app, lambda: window.worker is None)
        window.close()
