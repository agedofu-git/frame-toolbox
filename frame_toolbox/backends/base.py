# バックエンドの最小契約を定義する。
# Desktop UIと将来のOverlayが同じステータスを利用する。
from typing import Protocol

from frame_toolbox.config import AppConfig
from frame_toolbox.models.status import Snapshot
from frame_toolbox.services.restart_service import RestartBackend


class StatusBackend(Protocol):
    restart_backend: RestartBackend

    def collect(self, config: AppConfig) -> Snapshot: ...
