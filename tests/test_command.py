# コマンドラッパーの成功・欠落・期限・安全性を検証する。
# 実機コマンドを使わずPythonの子プロセスだけを実行する。
import subprocess
import sys

import pytest

from frame_toolbox.utils.command import MAX_OUTPUT_CHARS, CommandRunner


def test_execution_wrapper() -> None:
    result = CommandRunner().run([sys.executable, "-c", "import sys; print('hello'); print('err', file=sys.stderr); sys.exit(3)"])
    assert result.exists and not result.ok
    assert result.exit_code == 3
    assert result.stdout.strip() == "hello"
    assert result.stderr.strip() == "err"
    assert result.duration_seconds >= 0


def test_command_not_found() -> None:
    result = CommandRunner().run(["frame-toolbox-nonexistent-test-command"])
    assert not result.exists and not result.ok
    assert "command not found" in result.failure


def test_timeout() -> None:
    result = CommandRunner().run([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.08)
    assert result.timed_out and not result.ok and result.exit_code is None


def test_shell_metacharacters_are_literal() -> None:
    literal = "; echo unsafe && $(whoami)"
    result = CommandRunner().run([sys.executable, "-c", "import sys; print(sys.argv[1])", literal])
    assert result.ok and result.stdout.strip() == literal


def test_execution_os_error(monkeypatch) -> None:
    runner = CommandRunner()
    monkeypatch.setattr(runner, "exists", lambda _: True)

    def fail(*args, **kwargs):
        raise PermissionError("private detail")

    monkeypatch.setattr(subprocess, "run", fail)
    result = runner.run(["restricted"])
    assert not result.ok and "PermissionError" in result.failure
    assert "private detail" not in result.failure


def test_output_cap() -> None:
    result = CommandRunner().run([sys.executable, "-c", f"print('x' * {MAX_OUTPUT_CHARS + 100})"])
    assert result.ok and len(result.stdout) == MAX_OUTPUT_CHARS


@pytest.mark.parametrize("argv,timeout", [("uname -a", 4), ([], 4), (["uname"], 0), (["uname", "\x00"], 4)])
def test_invalid_command_arguments(argv, timeout) -> None:
    with pytest.raises(ValueError):
        CommandRunner().run(argv, timeout=timeout)
