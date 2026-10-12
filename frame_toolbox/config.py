# ユーザー領域の設定を検証し、原子的に保存する。
# 診断閾値とプロセス名を機種固有の推測から切り離す。
import ipaddress
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from frame_toolbox.utils.files import private_directory, read_text


def user_directory(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable)
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


def config_directory() -> Path:
    return user_directory("XDG_CONFIG_HOME", ".config") / "frame-toolbox"


def state_directory() -> Path:
    return user_directory("XDG_STATE_HOME", ".local/state") / "frame-toolbox"


def validate_pc_ip(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if "%" in value:
        raise ValueError("PC IP: scoped addresses are not supported in v0.1")
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("PC IP: enter an IPv4 or IPv6 address") from exc
    if address.is_unspecified or address.is_multicast:
        raise ValueError("PC IP: enter a unicast address")
    return str(address)


@dataclass
class NetworkThresholds:
    weak_signal_dbm: float = -75.0
    weak_signal_percent: int = 30
    low_bitrate_mbps: float = 50.0


@dataclass
class AppConfig:
    pc_ip: str = ""
    auto_refresh_seconds: int = 30
    debug_logging: bool = False
    vr_process_names: list[str] = field(default_factory=lambda: [
        "vrserver", "vrcompositor", "vrmonitor", "steam",
    ])
    thresholds: NetworkThresholds = field(default_factory=NetworkThresholds)

    def validate(self) -> None:
        self.pc_ip = validate_pc_ip(self.pc_ip)
        if type(self.auto_refresh_seconds) is not int or not (
            self.auto_refresh_seconds == 0 or 5 <= self.auto_refresh_seconds <= 3600
        ):
            raise ValueError("Auto refresh: use 0 (off) or 5–3600 seconds")
        if type(self.debug_logging) is not bool:
            raise ValueError("Debug logging must be true or false")
        if not isinstance(self.vr_process_names, list) or not 1 <= len(self.vr_process_names) <= 16:
            raise ValueError("Provide 1–16 process names")
        if any(not isinstance(n, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", n)
               for n in self.vr_process_names):
            raise ValueError("Process names must contain only letters, digits, _, . or -")
        self.vr_process_names = list(dict.fromkeys(self.vr_process_names))
        t = self.thresholds
        if not isinstance(t, NetworkThresholds) or any(
            type(v) not in (int, float) for v in asdict(t).values()
        ):
            raise ValueError("Network thresholds must be numeric")
        if not -120 <= t.weak_signal_dbm <= -10 or not 0 <= t.weak_signal_percent <= 100 \
                or not 0 < t.low_bitrate_mbps <= 100_000:
            raise ValueError("Network thresholds are outside the supported range")


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else config_directory() / "config.json"
        self.last_error: str | None = None

    def load(self) -> AppConfig:
        self.last_error = None
        try:
            if not self.path.exists():
                return AppConfig()
            if self.path.is_symlink():
                raise ValueError("Settings symlink")
            raw = read_text(self.path)
            if raw is None:
                raise ValueError("Unreadable settings")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Settings must be an object")
            allowed = {"pc_ip", "auto_refresh_seconds", "debug_logging", "vr_process_names"}
            config = AppConfig(**{k: v for k, v in data.items() if k in allowed})
            config.thresholds = NetworkThresholds(**data.get("thresholds", {}))
            config.validate()
            return config
        except (OSError, ValueError, TypeError, AttributeError):
            self.last_error = "Settings could not be loaded; defaults are active. The file was preserved."
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        config.validate()
        if self.path.is_symlink():
            raise OSError("Refusing to replace a settings symlink")
        private_directory(self.path.parent)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=".config-", delete=False) as stream:
                temporary = Path(stream.name)
                if os.name != "nt":
                    temporary.chmod(0o600)
                json.dump(asdict(config), stream, indent=2, ensure_ascii=False, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.last_error = None
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
