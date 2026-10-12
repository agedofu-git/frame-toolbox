# オフライン導入の整合性確認と起動ファイルを検証する。
# 実機のインストール先やシステム環境を変更せず安全性を確かめる。
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("installer", Path(__file__).resolve().parents[1] / "scripts/install.py")
assert spec and spec.loader
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def make_bundle(root: Path) -> Path:
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    wheel = wheelhouse / "frame_toolbox-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"fake wheel")
    (root / "checksums.json").write_text(json.dumps({"wheelhouse/" + wheel.name: hashlib.sha256(wheel.read_bytes()).hexdigest()}))
    return wheel


def test_verified_bundle_rejects_tampering_and_extra_wheels(tmp_path: Path) -> None:
    wheel = make_bundle(tmp_path)
    assert installer.verify_bundle(tmp_path) == [wheel]
    wheel.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        installer.verify_bundle(tmp_path)
    wheel.write_bytes(b"fake wheel")
    (wheel.parent / "unexpected.whl").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="Unexpected wheel"):
        installer.verify_bundle(tmp_path)


def test_manifest_rejects_outside_paths(tmp_path: Path) -> None:
    (tmp_path / "checksums.json").write_text(json.dumps({"../outside": "0"}))
    with pytest.raises(ValueError, match="invalid file path"):
        installer.verify_bundle(tmp_path)


def test_launcher_handles_home_spaces_and_arguments(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / 'user space%name'
    home.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(home / "data"))
    python = home / "installs/venv/bin/python"
    launcher = installer.register_launcher(home, python, False)
    assert '"$@"' in launcher.read_text(encoding="utf-8")
    assert "user space%name" in launcher.read_text(encoding="utf-8")
    menu = (home / "data/applications/frame-toolbox.desktop").read_text(encoding="utf-8")
    assert 'Exec="' in menu and "space%%name" in menu and "Terminal=false" in menu
    with pytest.raises(ValueError):
        installer.desktop_quote("invalid\npath")


def test_failed_install_does_not_register_launcher(tmp_path: Path, monkeypatch) -> None:
    make_bundle(tmp_path)
    monkeypatch.setattr(installer, "__file__", str(tmp_path / "install.py"))
    monkeypatch.setattr(installer.sys, "platform", "linux")
    monkeypatch.setattr(installer.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(installer.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(installer.Path, "home", lambda: tmp_path)
    def failure(*args, **kwargs):
        raise OSError("venv unavailable")
    monkeypatch.setattr(installer, "run", failure)
    assert installer.main([]) == 1
    assert not (tmp_path / ".local/bin/frame-toolbox").exists()
