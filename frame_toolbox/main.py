# CLI設定、バックエンド選択、GUI起動を組み立てる。
# headless診断はQt不要で実行でき、実機調査にも利用できる。
import argparse
import json
import logging
import platform
import sys
from dataclasses import asdict
from pathlib import Path

from frame_toolbox.backends.linux import LinuxBackend
from frame_toolbox.backends.mock import MockBackend
from frame_toolbox.config import ConfigStore, state_directory
from frame_toolbox.services.diagnostics_service import DiagnosticsService
from frame_toolbox.utils.command import CommandRunner
from frame_toolbox.utils.logging import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Frame Toolbox - SteamOS desktop diagnostics")
    parser.add_argument("--mock", action="store_true", help="Use simulated data; no system commands")
    parser.add_argument("--headless", action="store_true", help="Print one JSON snapshot without Qt")
    parser.add_argument("--collect", action="store_true", help="Generate a ZIP without starting the GUI")
    parser.add_argument("--include-journal", action="store_true", help="Opt in to bounded related user journal")
    parser.add_argument("--config-dir", type=Path, help="Override user config location")
    parser.add_argument("--state-dir", type=Path, help="Override user log location")
    parser.add_argument("--output-dir", type=Path, help="Override report directory")
    args = parser.parse_args(argv)
    if not args.mock and platform.system() != "Linux":
        parser.error("Live diagnostics require Linux. Use --mock on Windows or macOS.")
    if args.include_journal and not args.collect:
        parser.error("--include-journal is for --collect; use the Diagnostics checkbox in GUI mode")
    store = ConfigStore(args.config_dir / "config.json" if args.config_dir else None)
    config = store.load()
    state = args.state_dir if args.state_dir else state_directory()
    try:
        log_path = configure_logging(state, config.debug_logging)
    except OSError:
        log_path = None
        logging.getLogger("frame_toolbox").addHandler(logging.NullHandler())
        print("Warning: application log directory unavailable.", file=sys.stderr)
    if store.last_error:
        print(store.last_error, file=sys.stderr)
    backend = MockBackend() if args.mock else LinuxBackend()
    diagnostics = DiagnosticsService(CommandRunner(), log_path)
    reports = args.output_dir if args.output_dir else state / "reports"
    if args.headless or args.collect:
        try:
            snapshot = backend.collect(config)
            if args.collect:
                print(diagnostics.collect(snapshot, reports, include_journal=args.include_journal).archive)
            else:
                # JSONはASCII escapeを使い、古いWindows端末の文字コードでも出力できる。
                print(json.dumps(asdict(snapshot), indent=2, ensure_ascii=True, allow_nan=False))
            return 0
        except (OSError, ValueError) as exc:
            print(f"Diagnostics unavailable ({type(exc).__name__}). Check user directory permissions.", file=sys.stderr)
            return 1
    try:
        from PySide6.QtWidgets import QApplication

        from frame_toolbox.ui.main_window import MainWindow
    except ImportError:
        print('GUI dependency unavailable. Install with: python -m pip install -e ".[dev]"', file=sys.stderr)
        return 2
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Frame Toolbox")
    app.setOrganizationName("Frame Toolbox")
    app.setStyle("Fusion")
    window = MainWindow(backend, config, store, diagnostics, reports, mock=args.mock)
    window.show()
    return app.exec()
