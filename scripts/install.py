# Steam Frame向け配布ZIPをユーザー領域へ導入するインストーラー。
# 独立したvenvと起動メニューを作り、システムPythonを変更しない。
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

VERSION = "0.1.0"


def run(arguments: list[str], timeout: int = 300) -> None:
    subprocess.run(arguments, check=True, timeout=timeout)


def verify_bundle(bundle: Path) -> list[Path]:
    manifest = json.loads((bundle / "checksums.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("Invalid checksum manifest")
    wheels: list[Path] = []
    for name, digest in manifest.items():
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle.resolve()) or not path.is_file():
            raise ValueError("Bundle contains an invalid file path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {name}")
        if path.suffix == ".whl":
            wheels.append(path)
    expected = bundle / "wheelhouse" / f"frame_toolbox-{VERSION}-py3-none-any.whl"
    if expected.resolve() not in wheels:
        raise ValueError("Application wheel is missing from the bundle")
    # pipが探索する全wheelを検証し、manifestにない追加ファイルは拒否する。
    if set((bundle / "wheelhouse").glob("*.whl")) != set(wheels):
        raise ValueError("Unexpected wheel in bundle")
    return wheels


def desktop_quote(value: str) -> str:
    if any(character in value for character in "\n\r\x00"):
        raise ValueError("Unsupported newline in installation path")
    value = value.replace("%", "%%")
    for character in ("\\", '"', "`", "$"):
        value = value.replace(character, "\\" + character)
    # Desktop Entry文字列のエスケープとExecのエスケープは別に解釈される。
    return ('"' + value + '"').replace("\\", "\\\\")


def write_atomic(path: Path, contents: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(contents, encoding="utf-8")
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def register_launcher(home: Path, python: Path, desktop: bool) -> Path:
    launcher = home / ".local/bin/frame-toolbox"
    if any(character in str(python) for character in "\n\r\x00"):
        raise ValueError("Unsupported newline in installation path")
    write_atomic(
        launcher,
        "#!/bin/sh\n# Frame Toolboxの専用Pythonを起動する。\n"
        "# アプリメニューと端末から同じユーザー環境を利用する。\n"
        f"exec {shlex.quote(str(python))} -m frame_toolbox \"$@\"\n",
        0o700,
    )
    contents = (
        "# Frame Toolboxをデスクトップのアプリメニューへ登録する。\n"
        "# 専用venvの起動ランチャーをユーザー権限で呼び出す。\n"
        "[Desktop Entry]\nType=Application\nName=Frame Toolbox\n"
        "Comment=SteamOS system, network, VR and audio diagnostics\n"
        f"Exec={desktop_quote(str(launcher))}\nIcon=utilities-system-monitor\n"
        "Terminal=false\nCategories=System;Utility;\nStartupNotify=true\n"
    )
    data_home = Path(os.environ.get("XDG_DATA_HOME", str(home / ".local/share")))
    if not data_home.is_absolute():
        data_home = home / ".local/share"
    write_atomic(data_home / "applications/frame-toolbox.desktop", contents, 0o644)
    if desktop:
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, timeout=5, check=True
            )
            directory = Path(result.stdout.strip())
            if directory.is_absolute() and directory.is_dir() and directory != home:
                write_atomic(directory / "Frame Toolbox.desktop", contents, 0o700)
        except (OSError, subprocess.SubprocessError):
            print("Desktop shortcut unavailable; application menu entry is installed.")
    return launcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Frame Toolbox in your user directory")
    parser.add_argument("--desktop", action="store_true", help="Also create a desktop shortcut")
    options = parser.parse_args(argv)
    try:
        if sys.platform != "linux" or sys.version_info < (3, 10):
            raise ValueError("Linux and Python 3.10 or newer are required")
        if os.geteuid() == 0:
            raise ValueError("Run as your normal desktop user, without sudo")
        if platform.machine() not in ("aarch64", "arm64"):
            raise ValueError("This offline bundle requires ARM64 Linux")
        bundle = Path(__file__).resolve().parent
        verify_bundle(bundle)
        home = Path.home()
        target = home / ".local/share/frame-toolbox/installs" / f"{VERSION}-{uuid.uuid4().hex[:12]}"
        target.mkdir(parents=True, mode=0o700)
        print("Creating isolated user environment...", flush=True)
        # 固定された最終パスでvenvを作り、更新失敗時も前のランチャーを維持する。
        run([sys.executable, "-m", "venv", str(target / "venv")], timeout=60)
        python = target / "venv/bin/python"
        run([
            str(python), "-m", "pip", "--isolated", "install", "--no-index",
            "--only-binary=:all:", "--find-links", str(bundle / "wheelhouse"),
            f"frame-toolbox=={VERSION}",
        ])
        run([str(python), "-m", "pip", "check"], timeout=30)
        run([str(python), "-c", "from PySide6 import QtWidgets; import frame_toolbox"], timeout=30)
        launcher = register_launcher(home, python, options.desktop)
        print(f"Installed. Open Frame Toolbox from the application menu, or run: {launcher}")
        print("Settings and diagnostics remain in your existing user directories.")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Installation failed: {error}", file=sys.stderr)
        print("No system packages were changed. Existing launcher is kept until installation succeeds.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
