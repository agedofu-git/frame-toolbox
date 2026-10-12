# 回転ログの動作と通常ログレベルを検証する。
# 再オープンしたログにもユーザー用の権限を適用する。
import logging
import os
import stat

from frame_toolbox.utils.logging import PrivateRotatingFileHandler, configure_logging


def test_default_log_level_and_rotation(tmp_path) -> None:
    path = configure_logging(tmp_path)
    logger = logging.getLogger("frame_toolbox")
    assert logger.level == logging.INFO
    handler = next(h for h in logger.handlers if isinstance(h, PrivateRotatingFileHandler))
    handler.maxBytes = 180
    for _ in range(8):
        logger.info("bounded test message " + "x" * 40)
    handler.flush()
    assert path.exists() and path.with_name("toolbox.log.1").exists()
    assert len(list(tmp_path.glob("toolbox.log*"))) <= 3
    if os.name != "nt":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.with_name("toolbox.log.1").stat().st_mode) == 0o600
