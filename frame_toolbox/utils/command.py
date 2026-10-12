# 外部コマンドを引数配列・期限付きで実行する。
# 欠落や失敗をデータへ変換し、UIのクラッシュを防ぐ。
import logging
import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass

LOG = logging.getLogger("frame_toolbox.command")
MAX_OUTPUT_CHARS = 128_000


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    exists: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None
    duration_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.exists and self.exit_code == 0 and not self.timed_out and self.error is None

    @property
    def failure(self) -> str:
        if not self.exists:
            return f"{self.argv[0]}: command not found"
        if self.timed_out:
            return f"{self.argv[0]}: timeout"
        return self.error or f"{self.argv[0]}: exit {self.exit_code}"


class CommandRunner:
    def exists(self, command: str) -> bool:
        return shutil.which(command) is not None

    def run(self, argv: Sequence[str], *, timeout: float = 4.0) -> CommandResult:
        if isinstance(argv, (str, bytes)) or not argv or any(
            not isinstance(arg, str) or "\x00" in arg for arg in argv
        ) or not argv[0] or timeout <= 0:
            raise ValueError("Use a nonempty argument array and a positive timeout")
        args = tuple(argv)
        if not self.exists(args[0]):
            LOG.debug("Command unavailable: %s", args[0])
            return CommandResult(args, exists=False)
        started = time.monotonic()
        env = dict(os.environ, LC_ALL="C", LANG="C")
        # 子プロセスの生出力や環境変数をアプリログへ残さない。
        try:
            process = subprocess.run(
                list(args), shell=False, stdin=subprocess.DEVNULL,
                capture_output=True,
                encoding="utf-8", errors="replace", timeout=timeout, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            result = CommandResult(
                args, True, process.returncode,
                process.stdout[:MAX_OUTPUT_CHARS], process.stderr[:MAX_OUTPUT_CHARS],
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired:
            # 期限を超えた不完全な出力を診断成功として扱わない。
            result = CommandResult(args, True, timed_out=True,
                                   duration_seconds=time.monotonic() - started)
        except FileNotFoundError:
            result = CommandResult(args, False)
        except OSError as exc:
            result = CommandResult(args, True, error=f"Execution unavailable ({type(exc).__name__})")
        LOG.debug("Command %s: exit=%s timeout=%s", args[0], result.exit_code, result.timed_out)
        return result
