# 各Linuxサービスをまとめて部分的な失敗を隔離する。
# 独立した診断を並行取得し、表示層へ単一のSnapshotを返す。
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from frame_toolbox.config import AppConfig
from frame_toolbox.models.status import Snapshot
from frame_toolbox.services.audio_service import AudioService
from frame_toolbox.services.network_service import NetworkService
from frame_toolbox.services.restart_service import UnavailableRestartBackend
from frame_toolbox.services.system_service import SystemService
from frame_toolbox.services.vr_service import VRService
from frame_toolbox.utils.command import CommandRunner

LOG = logging.getLogger("frame_toolbox.backend")


class LinuxBackend:
    def __init__(self, runner: CommandRunner | None = None) -> None:
        runner = runner or CommandRunner()
        self.system = SystemService()
        self.network = NetworkService(runner)
        self.vr = VRService(runner)
        self.audio = AudioService(runner)
        self.restart_backend = UnavailableRestartBackend()

    def collect(self, config: AppConfig) -> Snapshot:
        config.validate()
        snapshot = Snapshot(collected_at=datetime.now(timezone.utc).isoformat())
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="frame-diagnostic") as pool:
            jobs = {
                "system": pool.submit(self.system.collect),
                "network": pool.submit(self.network.collect, config.pc_ip, config.thresholds),
                "vr": pool.submit(self.vr.collect, config.vr_process_names),
                "audio": pool.submit(self.audio.collect),
            }
            for name, job in jobs.items():
                try:
                    setattr(snapshot, name, job.result())
                except Exception as exc:
                    # 1サービスの想定外の失敗でも残りの診断結果は利用可能。
                    message = f"{name}: collection failed ({type(exc).__name__})"
                    snapshot.errors.append(message)
                    LOG.warning(message)
        LOG.info("Status refresh completed; failed services=%s", len(snapshot.errors))
        return snapshot
