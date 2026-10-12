# Mockまたは実機UIの起動と全タブの画像保存を行う検証スクリプト。
# LinuxのヘッドレスCIでも表示崩れを確認できる成果物を作る。
import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from frame_toolbox.backends.linux import LinuxBackend
from frame_toolbox.backends.mock import MockBackend
from frame_toolbox.config import AppConfig, ConfigStore
from frame_toolbox.services.diagnostics_service import DiagnosticsService
from frame_toolbox.ui.main_window import MainWindow
from frame_toolbox.utils.command import CommandRunner
from frame_toolbox.utils.logging import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify desktop UI and save screenshots")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ui"))
    parser.add_argument("--live", action="store_true", help="Read real Linux status instead of mock data")
    parser.add_argument("--pc-ip", default="", help="Optional PC IP for the live ping check")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    log_path = configure_logging(args.output_dir / "state")
    app = QApplication([])
    if os.name == "nt" and not QFontDatabase.families():
        # Windowsのoffscreen pluginにはフォント探索がないため、既存フォントを検証時だけ読む。
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"
        QFontDatabase.addApplicationFont(str(font))
    if not QFontDatabase.families():
        print("UI verification needs an installed font", file=sys.stderr)
        return 1
    app.setStyle("Fusion")
    config = AppConfig(pc_ip=args.pc_ip if args.live else "192.168.1.20", auto_refresh_seconds=0)
    config.validate()
    backend = LinuxBackend() if args.live else MockBackend()
    window = MainWindow(backend, config, ConfigStore(args.output_dir / "config.json"),
                        DiagnosticsService(CommandRunner(), log_path), args.output_dir / "reports", mock=not args.live)
    window.show()
    timer = QTimer()
    state = {"index": 0, "attempts": 0, "failed": False}

    def capture() -> None:
        state["attempts"] += 1
        if state["attempts"] > 600:
            state["failed"] = True
            window.close()
            timer.stop()
            return
        if window.worker is not None or window.snapshot is None:
            return
        index = state["index"]
        window.tabs.setCurrentIndex(index)
        app.processEvents()
        target = args.output_dir / (window.tabs.tabText(index).lower() + ".png")
        if not window.grab().save(str(target)):
            state["failed"] = True
        state["index"] += 1
        if state["index"] == window.tabs.count():
            timer.stop()
            window.close()

    timer.timeout.connect(capture)
    timer.start(100)
    app.exec()
    if state["failed"] or state["index"] != 6:
        print("UI verification failed", file=sys.stderr)
        return 1
    print(f"Verified 6 tabs; mock={not args.live}; screenshots: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
