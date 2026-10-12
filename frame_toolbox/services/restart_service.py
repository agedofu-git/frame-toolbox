# SteamVR再起動の安全なバックエンド境界を定義する。
# 正式な実機手順が未確認の間は本体へ何も実行しない。
from dataclasses import dataclass
from typing import Protocol

from frame_toolbox.models.status import ActionResult


@dataclass(frozen=True)
class RestartPlan:
    available: bool
    description: str
    reason: str = ""
    timeout_seconds: float = 10.0


class RestartBackend(Protocol):
    # 実装追加時は同一の計画と操作、期限付きCommandRunnerを使用する。
    def plan(self) -> RestartPlan: ...
    def restart(self) -> ActionResult: ...


class UnavailableRestartBackend:
    def plan(self) -> RestartPlan:
        return RestartPlan(False, "No system command will be executed.",
                           "Steam Frame's supported SteamVR restart method is unverified. Disabled in v0.1.")

    def restart(self) -> ActionResult:
        return ActionResult(False, self.plan().reason)


class MockRestartBackend:
    def plan(self) -> RestartPlan:
        return RestartPlan(True, "Simulate SteamVR restart in Mock Mode. No process is changed.")

    def restart(self) -> ActionResult:
        return ActionResult(True, "Mock restart completed. No system command was executed.")
