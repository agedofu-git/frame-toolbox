# 公開用のソースZIPとARM64オフライン導入ZIPを構築する。
# 診断ログや秘密情報を除外し、許可したファイルだけを配布する。
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

VERSION = "0.1.0"


def source_paths(root: Path) -> list[Path]:
    text = (root / "docs/FILES.md").read_text(encoding="utf-8")
    entries = text.split("```text\n", 1)[1].split("```", 1)[0].splitlines()
    paths = [(root / entry).resolve() for entry in entries if entry.strip()]
    if any(not path.is_relative_to(root.resolve()) or not path.is_file() for path in paths):
        raise ValueError("Invalid source manifest")
    return paths


def archive_files(output: Path, files: list[tuple[Path, str]]) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            archive.write(path, name)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(files):
            raise ValueError("Archive verification failed")


def build(root: Path) -> list[Path]:
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    source = dist / f"frame-toolbox-{VERSION}-source.zip"
    archive_files(source, [(path, "frame-toolbox/" + path.relative_to(root).as_posix())
                           for path in source_paths(root)])
    bundle = root / "artifacts/release-bundle" / f"frame-toolbox-{VERSION}"
    wheelhouse = bundle / "wheelhouse"
    wheelhouse.mkdir(parents=True, exist_ok=True)
    wheels = sorted((root / "artifacts/wheelhouse-arm64").glob("*.whl"))
    if len(wheels) != 2:
        raise ValueError("Expected the tested PySide6-Essentials and Shiboken ARM64 wheels")
    wheels.append(dist / f"frame_toolbox-{VERSION}-py3-none-any.whl")
    for wheel in wheels:
        if not wheel.is_file():
            raise ValueError(f"Missing wheel: {wheel.name}")
        shutil.copyfile(wheel, wheelhouse / wheel.name)
    shutil.copyfile(root / "scripts/install.py", bundle / "install.py")
    shutil.copyfile(root / "LICENSE", bundle / "LICENSE")
    shutil.copyfile(root / "docs/INSTALL_STEAM_FRAME.md", bundle / "README.md")
    shutil.copyfile(root / "docs/THIRD_PARTY_NOTICES.md", bundle / "THIRD_PARTY_NOTICES.md")
    files = [bundle / name for name in ("install.py", "LICENSE", "README.md", "THIRD_PARTY_NOTICES.md")]
    files.extend(sorted(wheelhouse.glob("*.whl")))
    checksums = {path.relative_to(bundle).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in files}
    manifest = bundle / "checksums.json"
    manifest.write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    files.append(manifest)
    offline = dist / f"frame-toolbox-{VERSION}-steamos-arm64.zip"
    archive_files(offline, [(path, bundle.name + "/" + path.relative_to(bundle).as_posix())
                            for path in files])
    outputs = [source, offline, dist / f"frame_toolbox-{VERSION}-py3-none-any.whl",
               dist / f"frame_toolbox-{VERSION}.tar.gz"]
    (dist / "SHA256SUMS").write_text(
        "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in outputs),
        encoding="utf-8",
    )
    return outputs


if __name__ == "__main__":
    for artifact in build(Path(__file__).resolve().parents[1]):
        print(f"Created: {artifact.name} ({artifact.stat().st_size} bytes)")
