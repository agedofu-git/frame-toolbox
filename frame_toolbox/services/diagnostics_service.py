# 診断Snapshotを限定された項目のレポートとZIPへ保存する。
# ホーム走査や秘密ファイル収集を行わず、journalは明示選択時のみ追加する。
import json
import logging
import os
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from frame_toolbox import __version__
from frame_toolbox.models.status import Snapshot
from frame_toolbox.utils.command import CommandRunner
from frame_toolbox.utils.files import private_directory

LOG = logging.getLogger("frame_toolbox.diagnostics")
JOURNAL_LINES = 200
LOG_BYTES = 128_000
JOURNAL_PATTERN = "steam|vrserver|vrcompositor|vrmonitor|NetworkManager|wpa_supplicant|iwd"


def redact(text: str) -> str:
    text = re.sub(r"(?is)-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", text)
    text = re.sub(r"(?i)\b(password|passwd|token|secret|authorization|cookie|api[_-]?key)\b\s*[:=]\s*[^\r\n]+",
                  r"\1=[REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+[^\s]+", "Bearer [REDACTED]", text)
    text = re.sub(r"(://)[^\s/@:]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    return text


def redact_values(data: object) -> object:
    # JSON化する前に値を編集し、引用符を壊してsummaryを無効にしない。
    if isinstance(data, str):
        return redact(data)
    if isinstance(data, dict):
        return {key: redact_values(value) for key, value in data.items()}
    if isinstance(data, list):
        return [redact_values(value) for value in data]
    return data


@dataclass(frozen=True)
class DiagnosticReport:
    directory: Path
    archive: Path


class DiagnosticsService:
    def __init__(self, runner: CommandRunner, log_path: Path | None = None) -> None:
        self.runner, self.log_path = runner, log_path

    def collect(self, snapshot: Snapshot, output_root: Path, *, include_journal: bool = False) -> DiagnosticReport:
        private_directory(output_root)
        stem = datetime.now().strftime("frame-toolbox-report-%Y%m%d-%H%M%S")
        directory: Path | None = None
        for index in range(1000):
            candidate = output_root / (stem if index == 0 else f"{stem}-{index}")
            if candidate.with_suffix(".zip").exists():
                continue
            try:
                private_directory(candidate, parents=False, exist_ok=False)
                directory = candidate
                break
            except FileExistsError:
                continue
        if directory is None:
            raise OSError("Could not create a unique diagnostic directory")
        LOG.info("Diagnostic collection started; mock=%s journal=%s", snapshot.mock, include_journal)
        sections = {
            "system.txt": asdict(snapshot.system), "network.txt": asdict(snapshot.network),
            "processes.txt": asdict(snapshot.vr), "audio.txt": asdict(snapshot.audio),
        }
        summary = {
            "schema_version": 1, "toolbox_version": __version__, **asdict(snapshot),
            "privacy": "Includes IP, SSID, hostname and device names. Review before sharing.",
            "journal_requested": include_journal,
        }
        for filename, data in {**sections, "summary.json": summary}.items():
            self._write(directory / filename, json.dumps(redact_values(data), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        self._write(directory / "toolbox.log", redact(self._recent_log()))
        if include_journal:
            if snapshot.mock:
                journal = "Mock Mode: no journal command was executed.\n"
            else:
                result = self.runner.run([
                    "journalctl", "--user", "--boot=0", "--no-pager", "--lines", str(JOURNAL_LINES),
                    "--grep", JOURNAL_PATTERN, "--output=short-iso",
                ], timeout=6.0)
                journal = result.stdout if result.ok else result.failure
            self._write(directory / "related-journal.txt", redact(journal)[-LOG_BYTES:])
        archive = directory.with_suffix(".zip")
        # 排他的に新規作成し、既存ZIPやリンク先を上書きしない。
        fd = os.open(archive, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(directory.iterdir()):
                bundle.write(path, arcname=f"{directory.name}/{path.name}")
        LOG.info("Diagnostic ZIP completed")
        return DiagnosticReport(directory, archive)

    @staticmethod
    def _write(path: Path, text: str) -> None:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
        if os.name != "nt":
            path.chmod(0o600)

    def _recent_log(self) -> str:
        if self.log_path is None or self.log_path.is_symlink():
            return "Toolbox log unavailable\n"
        try:
            with self.log_path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                stream.seek(max(0, stream.tell() - LOG_BYTES))
                return stream.read(LOG_BYTES).decode("utf-8", errors="replace")
        except OSError:
            return "Toolbox log unavailable\n"
