# テスト用のコマンド応答とQt実行環境を提供する。
# 実機のネットワークや設定を変更せず診断を検証する。
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from frame_toolbox.utils.command import CommandResult

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], str | CommandResult] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, ...]] = []

    def exists(self, command: str) -> bool:
        return any(args[0] == command for args in self.responses)

    def run(self, argv: list[str], *, timeout: float = 4.0) -> CommandResult:
        args = tuple(argv)
        self.calls.append(args)
        result = self.responses.get(args)
        if isinstance(result, CommandResult):
            return result
        if result is None:
            return CommandResult(args, self.exists(args[0]), exit_code=2 if self.exists(args[0]) else None)
        return CommandResult(args, True, 0, result)


@pytest.fixture
def fake_runner() -> Callable[..., FakeRunner]:
    return FakeRunner


@pytest.fixture(scope="session")
def qt_app():
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from PySide6.QtGui import QFontDatabase

    if os.name == "nt" and not QFontDatabase.families():
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/segoeui.ttf"))
    assert QFontDatabase.families(), "A font is required to verify readable UI rendering"
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    return app
