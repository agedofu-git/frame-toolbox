# 遅い診断操作をQtのワーカースレッドへ移す。
# 結果とエラーだけをシグナルでGUIスレッドへ戻す。
import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

LOG = logging.getLogger("frame_toolbox.worker")


class TaskWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], object], parent: object = None) -> None:
        super().__init__(parent)
        self.operation = operation

    def run(self) -> None:
        try:
            self.succeeded.emit(self.operation())
        except Exception as exc:
            # 外部文字列を無制限にログへ流さず、失敗の種類は残す。
            message = f"Operation failed ({type(exc).__name__}). Check available tools and user directory permissions."
            LOG.error(message)
            self.failed.emit(message)
