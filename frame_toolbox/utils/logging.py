# アプリ専用の回転ログをユーザー領域へ保存する。
# 外部コマンドの出力や秘密情報をログに残さない。
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from frame_toolbox.utils.files import private_directory


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _open(self):
        # ローテーション後にも新規ファイルの0600を維持する。
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.baseFilename, flags, 0o600)
        try:
            if os.name != "nt":
                os.fchmod(fd, 0o600)
            return os.fdopen(fd, self.mode, encoding=self.encoding, errors=self.errors)
        except Exception:
            os.close(fd)
            raise


def configure_logging(directory: Path, debug: bool = False) -> Path:
    private_directory(directory)
    log_path = directory / "toolbox.log"
    if log_path.is_symlink():
        raise OSError("Refusing a log symlink")
    logger = logging.getLogger("frame_toolbox")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    handler = PrivateRotatingFileHandler(log_path, maxBytes=256_000, backupCount=2, encoding="utf-8")
    if os.name != "nt":
        log_path.chmod(0o600)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.info("Frame Toolbox started; debug=%s", debug)
    return log_path


def set_debug_logging(enabled: bool) -> None:
    logging.getLogger("frame_toolbox").setLevel(logging.DEBUG if enabled else logging.INFO)
