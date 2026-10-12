# PulseAudio互換またはWirePlumberからデバイス状態を取得する。
# 音量の読み取りを実際のマイク入力レベルと混同しない。
import json
import re

from frame_toolbox.models.status import AudioStatus
from frame_toolbox.utils.command import CommandRunner


def parse_pactl_info(text: str) -> dict[str, str]:
    return {key.strip(): value.strip() for line in text.splitlines() if ":" in line
            for key, value in [line.split(":", 1)]}


def parse_wpctl_inspect(text: str) -> str | None:
    values = {match[1]: match[2] for match in re.finditer(r'([\w.]+)\s*=\s*"([^"\n]*)"', text)}
    return values.get("node.description") or values.get("node.nick") or values.get("node.name")


def parse_wpctl_volume(text: str) -> tuple[float | None, bool | None]:
    match = re.search(r"Volume:\s*([\d.]+)", text)
    if not match:
        return None, None
    return float(match[1]) * 100, "[MUTED]" in text


def device_description(text: str, name: str | None) -> str | None:
    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return name
        for row in data:
            if isinstance(row, dict) and row.get("name") == name:
                description = row.get("description")
                return description if isinstance(description, str) else name
    except (ValueError, TypeError):
        pass
    return name


class AudioService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def collect(self) -> AudioStatus:
        status = AudioStatus()
        info = self.runner.run(["pactl", "info"])
        if info.ok:
            values = parse_pactl_info(info.stdout)
            status.server = values.get("Server Name")
            status.default_output = values.get("Default Sink")
            status.default_input = values.get("Default Source")
            for kind, attr in [("sinks", "default_output"), ("sources", "default_input")]:
                devices = self.runner.run(["pactl", "--format=json", "list", kind])
                if devices.ok:
                    setattr(status, attr, device_description(devices.stdout, getattr(status, attr)))
            mute = self.runner.run(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"])
            volume = self.runner.run(["pactl", "get-source-volume", "@DEFAULT_SOURCE@"])
            if mute.ok:
                match = re.search(r"Mute:\s*(yes|no)", mute.stdout)
                status.microphone_muted = match[1] == "yes" if match else None
            if volume.ok:
                percentages = re.findall(r"(\d+)%", volume.stdout)
                status.microphone_volume_percent = max(map(float, percentages)) if percentages else None
        else:
            status.notes.append(info.failure)
        if any(value is None for value in (status.server, status.default_output, status.default_input,
                                           status.microphone_muted, status.microphone_volume_percent)):
            self._wpctl_fallback(status)
        return status

    def _wpctl_fallback(self, status: AudioStatus) -> None:
        if not self.runner.exists("wpctl"):
            status.notes.append("wpctl: command not found")
            return
        success = False
        for target, attr in [("@DEFAULT_AUDIO_SINK@", "default_output"),
                             ("@DEFAULT_AUDIO_SOURCE@", "default_input")]:
            if getattr(status, attr) is not None:
                continue
            result = self.runner.run(["wpctl", "inspect", target])
            if result.ok:
                setattr(status, attr, parse_wpctl_inspect(result.stdout))
                success = True
            else:
                status.notes.append(result.failure)
        if status.microphone_muted is None or status.microphone_volume_percent is None:
            result = self.runner.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"])
            if result.ok:
                volume, muted = parse_wpctl_volume(result.stdout)
                if status.microphone_volume_percent is None:
                    status.microphone_volume_percent = volume
                if status.microphone_muted is None:
                    status.microphone_muted = muted
                success = True
        if success and status.server is None:
            status.server = "PipeWire / WirePlumber (wpctl available; version unknown)"
