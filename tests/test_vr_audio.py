# プロセス検出、OpenXR選択、音声の代替取得を検証する。
# プロセスの停止や音声設定の変更は行わない。
import json

from frame_toolbox.services.audio_service import AudioService, parse_wpctl_volume
from frame_toolbox.services.restart_service import UnavailableRestartBackend
from frame_toolbox.services.vr_service import (
    VRService,
    detect_openxr,
    parse_processes,
    runtime_candidates,
)


def test_process_detection_exact_match() -> None:
    processes = parse_processes(" 42 vrserver\n43 vrserver-helper\n44 vrcompositor\n45 steam", ["vrserver", "vrmonitor", "steam"])
    assert processes[0].pids == [42] and processes[0].label == "Running"
    assert processes[1].label == "Not detected"
    assert processes[2].pids == [45]


def test_missing_ps(fake_runner) -> None:
    status = VRService(fake_runner()).collect(["vrserver"])
    assert status.processes[0].label == "Unavailable"


def test_restart_is_unavailable() -> None:
    backend = UnavailableRestartBackend()
    assert not backend.plan().available
    assert not backend.restart().success


def test_openxr_detection(tmp_path) -> None:
    manifest = tmp_path / "runtime.json"
    manifest.write_text(json.dumps({"runtime": {"name": "Test Runtime", "library_path": "/opt/runtime.so"}}))
    assert detect_openxr([manifest]) == ("Test Runtime", str(manifest))
    manifest.write_text("invalid")
    lower = tmp_path / "lower.json"
    lower.write_text(json.dumps({"runtime": {"name": "Must not be selected"}}))
    assert detect_openxr([manifest, lower]) == (None, str(manifest))


def test_runtime_override(monkeypatch, tmp_path) -> None:
    manifest = tmp_path / "test.json"
    monkeypatch.setenv("XR_RUNTIME_JSON", str(manifest))
    assert runtime_candidates() == [manifest]


def test_audio_pactl(fake_runner) -> None:
    runner = fake_runner({
        ("pactl", "info"): "Server Name: PulseAudio (on PipeWire)\nDefault Sink: sink0\nDefault Source: source0",
        ("pactl", "--format=json", "list", "sinks"): '[{"name":"sink0","description":"Frame Output"}]',
        ("pactl", "--format=json", "list", "sources"): '[{"name":"source0","description":"Frame Mic"}]',
        ("pactl", "get-source-mute", "@DEFAULT_SOURCE@"): "Mute: no",
        ("pactl", "get-source-volume", "@DEFAULT_SOURCE@"): "Volume: front-left: 52428 / 80% / -5.81 dB",
    })
    status = AudioService(runner).collect()
    assert status.default_output == "Frame Output" and status.default_input == "Frame Mic"
    assert status.microphone_muted is False and status.microphone_volume_percent == 80
    assert status.microphone_level.startswith("Unavailable")
    assert all(call[0] == "pactl" for call in runner.calls)


def test_wpctl_only_fallback(fake_runner) -> None:
    runner = fake_runner({
        ("wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"): 'node.description = "Output"',
        ("wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"): 'node.description = "Mic"',
        ("wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"): "Volume: 0.80 [MUTED]",
    })
    status = AudioService(runner).collect()
    assert status.default_input == "Mic" and status.default_output == "Output"
    assert status.microphone_muted is True and status.microphone_volume_percent == 80
    assert "PipeWire" in status.server


def test_missing_audio_tools(fake_runner) -> None:
    status = AudioService(fake_runner()).collect()
    assert status.default_input is None and status.server is None
    assert parse_wpctl_volume("Unavailable") == (None, None)
