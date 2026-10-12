# CLIからGUIを組み立てる起動経路を別プロセスで検証する。
# Mockの初回取得後に正常終了させ、Qtアプリの多重生成を避ける。
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def test_gui_entrypoint(tmp_path) -> None:
    script = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from frame_toolbox.ui.main_window import MainWindow
from frame_toolbox.main import main

original_show = MainWindow.show
def show_and_check(window):
    original_show(window)
    timer = QTimer(window)
    def finish():
        if window.snapshot is not None and window.worker is None:
            print('GUI_READY_WITH_MOCK_SNAPSHOT')
            timer.stop()
            window.close()
    timer.timeout.connect(finish)
    timer.start(10)
    QTimer.singleShot(3000, lambda: QApplication.instance().exit(2))
MainWindow.show = show_and_check
raise SystemExit(main(sys.argv[1:]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, "--mock", "--config-dir", str(tmp_path / "config"),
         "--state-dir", str(tmp_path / "state")],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True,
        timeout=8.0, shell=False, env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
    )
    assert result.returncode == 0, result.stderr
    assert "GUI_READY_WITH_MOCK_SNAPSHOT" in result.stdout
