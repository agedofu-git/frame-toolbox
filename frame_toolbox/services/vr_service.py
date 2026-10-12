# 設定可能なVRプロセス名とLinux OpenXR設定を観測する。
# プロセス不検出を故障と断定せず、実行引数は収集しない。
import json
import os
import platform
from pathlib import Path

from frame_toolbox.models.status import ProcessStatus, VRStatus
from frame_toolbox.utils.command import CommandRunner
from frame_toolbox.utils.files import read_text


def parse_processes(text: str, names: list[str], available: bool = True) -> list[ProcessStatus]:
    result = [ProcessStatus(name, available=available) for name in names]
    by_name = {p.name: p for p in result}
    for line in text.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2 and fields[0].isdigit() and fields[1] in by_name:
            by_name[fields[1]].pids.append(int(fields[0]))
    return result


def runtime_candidates() -> list[Path]:
    override = os.environ.get("XR_RUNTIME_JSON")
    if override:
        return [Path(override)]
    home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    dirs = [Path(home)] + [Path(p) for p in os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":") if p]
    dirs.append(Path("/etc"))
    arch = platform.machine()
    arch = {"arm64": "aarch64", "AMD64": "x86_64"}.get(arch, arch)
    return [directory / "openxr/1" / name for directory in dirs if directory.is_absolute()
            for name in (f"active_runtime.{arch}.json", "active_runtime.json")]


def detect_openxr(paths: list[Path]) -> tuple[str | None, str | None]:
    for path in paths:
        try:
            if not path.exists():
                continue
            # runtime選択のためのJSONだけを読み、ライブラリはロードしない。
            resolved = path.resolve()
            if path.suffix != ".json" or resolved.suffix != ".json" or ".ssh" in resolved.parts:
                return None, str(path)
            raw = read_text(path)
            data = json.loads(raw) if raw else {}
            runtime = data.get("runtime", {})
            if not isinstance(runtime, dict):
                return None, str(path)
            name = runtime.get("name")
            library = runtime.get("library_path")
            display = name if isinstance(name, str) else Path(library).name if isinstance(library, str) else None
            return display, str(path)
        except (OSError, ValueError, TypeError, AttributeError):
            # 上位設定が壊れていても下位設定が有効と誤認しない。
            return None, str(path)
    return None, None


class VRService:
    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def collect(self, names: list[str]) -> VRStatus:
        result = self.runner.run(["ps", "-eo", "pid=,comm="])
        runtime, manifest = detect_openxr(runtime_candidates())
        return VRStatus(parse_processes(result.stdout if result.ok else "", names, result.ok),
                        runtime, manifest, [] if result.ok else [result.failure])
