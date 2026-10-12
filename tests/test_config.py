# 設定の永続化と入力検証をテストする。
# 不正設定を上書きせず、安全なデフォルトへ戻すことを確認する。
import json

import pytest

from frame_toolbox.config import AppConfig, ConfigStore, validate_pc_ip


def test_config_load_save(tmp_path) -> None:
    store = ConfigStore(tmp_path / "config" / "config.json")
    config = AppConfig(pc_ip="192.168.1.20", auto_refresh_seconds=15, debug_logging=True,
                       vr_process_names=["vrserver", "custom_vr"])
    store.save(config)
    assert store.load() == config
    assert json.loads(store.path.read_text())["pc_ip"] == "192.168.1.20"
    assert not list(store.path.parent.glob(".config-*"))


def test_missing_config(tmp_path) -> None:
    store = ConfigStore(tmp_path / "absent.json")
    assert store.load() == AppConfig() and store.last_error is None
    assert not store.path.exists()


def test_bad_config_is_preserved(tmp_path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"pc_ip":"; reboot"}')
    store = ConfigStore(path)
    assert store.load() == AppConfig() and store.last_error
    assert path.read_text() == '{"pc_ip":"; reboot"}'


@pytest.mark.parametrize("data", ["[]", "{", '{"debug_logging":"yes"}', '{"auto_refresh_seconds":1}', '{"thresholds":{"weak_signal_dbm":"weak"}}'])
def test_malformed_settings(tmp_path, data) -> None:
    path = tmp_path / "config.json"
    path.write_text(data)
    store = ConfigStore(path)
    assert store.load() == AppConfig() and store.last_error


@pytest.mark.parametrize("address", ["192.168.1.20", "2001:db8::1", "", "127.0.0.1"])
def test_valid_pc_address(address) -> None:
    assert validate_pc_ip(address) == address


@pytest.mark.parametrize("address", ["-c 999", "pc.example.com", "; reboot", "0.0.0.0", "224.0.0.1", "fe80::1%eth0"])
def test_invalid_pc_address(address) -> None:
    with pytest.raises(ValueError):
        validate_pc_ip(address)
