# 少量の標準システム情報を読み取る共通関数。
# 読み取り失敗や巨大ファイルを通常の取得不能として処理する。
import os
from pathlib import Path


def private_directory(path: Path, *, parents: bool = True, exist_ok: bool = True) -> None:
    # Windowsの0o700は特殊なACLを設定するため、ユーザーディレクトリのACLを継承する。
    path.mkdir(parents=parents, exist_ok=exist_ok, mode=0o700 if os.name != "nt" else 0o777)


def read_text(path: Path, limit: int = 65_536) -> str | None:
    try:
        if not path.is_file():
            return None
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            return None
        return raw.decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return None


def number(text: str | None) -> float | None:
    try:
        value = float(text) if text is not None else None
        return value if value is not None and abs(value) < float("inf") else None
    except ValueError:
        return None
