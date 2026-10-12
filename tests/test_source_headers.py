# プログラムファイル先頭の責務コメントを検証する。
# 新しいモジュールでもプロジェクトの説明ルールを維持する。
from pathlib import Path


def test_program_files_begin_with_role_comments() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [path for folder in ("frame_toolbox", "scripts", "tests")
             for path in (root / folder).rglob("*.py")]
    assert files
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 2 and all(line.startswith("# ") and len(line) > 10 for line in lines[:2]), path
