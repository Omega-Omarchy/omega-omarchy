#!/usr/bin/env python3
"""Build a portable, receipt-bound Linux player archive."""

from __future__ import annotations

import argparse
import gzip
import hashlib
from importlib.metadata import PackageNotFoundError, distribution, version
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import time
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ASSET_DIRS = ("audio", "bosses", "characters", "fidelity", "items", "tiles", "ui", "character-packs", "character-creation")
RUNTIME_DISTRIBUTIONS = ("pygame-ce", "pillow", "qrcode", "numpy", "pyinstaller")
ARTIFACT_FORMAT = "omega-native-linux-tar/2"


class ArtifactBuildError(RuntimeError):
    pass


def _run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    environ: dict[str, str] | None = None,
) -> str:
    process = subprocess.run(
        command,
        cwd=cwd,
        env=environ,
        check=False,
        text=True,
        capture_output=True,
    )
    if process.returncode:
        raise ArtifactBuildError(
            f"command failed ({process.returncode}): {' '.join(command)}\n{process.stdout}{process.stderr}"
        )
    return process.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_digest(root: Path) -> str:
    if not root.is_dir():
        raise ArtifactBuildError(f"tree digest root is missing: {root}")
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _git(command: str) -> str:
    return _run(["git", *command.split()])


def _source_epoch() -> int:
    configured = os.environ.get("SOURCE_DATE_EPOCH")
    if configured:
        try:
            value = int(configured)
        except ValueError as exc:
            raise ArtifactBuildError("SOURCE_DATE_EPOCH must be an integer") from exc
        if value < 0:
            raise ArtifactBuildError("SOURCE_DATE_EPOCH may not be negative")
        return value
    return int(_git("show -s --format=%ct HEAD"))


def _dependencies() -> list[dict[str, str]]:
    records = []
    for name in RUNTIME_DISTRIBUTIONS:
        try:
            package = distribution(name)
        except PackageNotFoundError as exc:
            raise ArtifactBuildError(f"required release dependency is missing: {name}") from exc
        license_name = package.metadata.get("License-Expression") or package.metadata.get("License") or "unreported"
        records.append(
            {
                "name": name,
                "version": package.version,
                "license": str(license_name).splitlines()[0],
            }
        )
    return records


def _copy_dependency_licenses(destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in RUNTIME_DISTRIBUTIONS:
        package = distribution(name)
        candidates = []
        for item in package.files or ():
            basename = str(item).rsplit("/", 1)[-1].lower()
            if any(marker in basename for marker in ("license", "copying", "notice")):
                candidate = Path(package.locate_file(item))
                if candidate.is_file():
                    candidates.append(candidate)
        if name == "pygame-ce" and not candidates:
            common = Path("/usr/share/common-licenses/LGPL-2.1")
            if common.is_file():
                candidates.append(common)
        if not candidates:
            raise ArtifactBuildError(f"no distributable license text found for {name}")
        for index, source in enumerate(candidates):
            suffix = "" if len(candidates) == 1 else f"-{index + 1}"
            source_name = source.name if "." in source.name else f"{source.name}.txt"
            target = destination / f"{name}{suffix}-{source_name}"
            shutil.copyfile(source, target)
            copied.append(target.name)
    python_license = Path(sysconfig.get_paths()["stdlib"]) / "LICENSE.txt"
    if not python_license.is_file():
        raise ArtifactBuildError(f"Python license text is missing: {python_license}")
    shutil.copyfile(python_license, destination / "python-LICENSE.txt")
    copied.append("python-LICENSE.txt")
    return sorted(copied)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_archive(source: Path, archive: Path, *, epoch: int) -> None:
    source_root = source.resolve()
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=epoch) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as bundle:
                for path in (source, *sorted(source.rglob("*"))):
                    relative = path.relative_to(source.parent).as_posix()
                    info = bundle.gettarinfo(str(path), arcname=relative)
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = epoch
                    if info.isdir():
                        info.mode = 0o755
                        bundle.addfile(info)
                    elif info.issym():
                        target = path.resolve(strict=True)
                        try:
                            target.relative_to(source_root)
                        except ValueError as exc:
                            raise ArtifactBuildError(f"symlink escapes bundle root: {path} -> {target}") from exc
                        if not target.is_file():
                            raise ArtifactBuildError(f"symlink does not resolve to a bundled file: {path}")
                        info.mode = 0o777
                        bundle.addfile(info)
                    elif info.isfile():
                        info.mode = 0o755 if path.name == "omega-omarchy" else 0o644
                        with path.open("rb") as payload:
                            bundle.addfile(info, payload)
                    else:
                        raise ArtifactBuildError(f"unsupported archive member: {path}")


def _required_asset_paths() -> Iterable[Path]:
    for directory in RUNTIME_ASSET_DIRS:
        yield ROOT / "assets" / directory


def build(output: Path, *, require_clean: bool = False) -> tuple[Path, Path]:
    if sys.platform != "linux":
        raise ArtifactBuildError("the current native artifact target is Linux only")
    dirty = bool(_git("status --porcelain"))
    if require_clean and dirty:
        raise ArtifactBuildError("release artifact requires a clean worktree")
    from omega_omarchy.credits_build import build_credits

    for path in _required_asset_paths():
        if not path.is_dir():
            raise ArtifactBuildError(f"runtime assets are missing; run ./scripts/omega assets: {path}")
    sentinel = ROOT / "assets" / "characters" / "david_ultra_side-idle.png"
    if not sentinel.is_file():
        raise ArtifactBuildError("production runtime assets are incomplete; run ./scripts/omega assets")

    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    app_version = version("omega-omarchy")
    architecture = platform.machine().lower().replace("amd64", "x86_64")
    release_name = f"omega-omarchy-{app_version}-linux-{architecture}"
    archive = output / f"{release_name}.tar.gz"
    checksum = output / f"{release_name}.tar.gz.sha256"
    epoch = _source_epoch()
    commit = _git("rev-parse HEAD")

    with tempfile.TemporaryDirectory(prefix="omega-native-") as temporary:
        temp = Path(temporary)
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--console",
            "--noupx",
            "--name",
            "omega-omarchy",
            "--paths",
            str(ROOT / "src"),
            "--collect-data",
            "omega_omarchy",
            "--exclude-module",
            "tkinter",
            "--exclude-module",
            "limitless_library",
            "--distpath",
            str(temp / "frozen"),
            "--workpath",
            str(temp / "work"),
            "--specpath",
            str(temp / "spec"),
        ]
        for asset_path in _required_asset_paths():
            command.extend(("--add-data", f"{asset_path}:assets/{asset_path.name}"))
        command.append(str(ROOT / "packaging" / "native_launcher.py"))
        _run(
            command,
            environ={
                **os.environ,
                "PYTHONHASHSEED": "0",
                "SOURCE_DATE_EPOCH": str(epoch),
            },
        )

        frozen = temp / "frozen" / "omega-omarchy"
        binary = frozen / "omega-omarchy"
        if not binary.is_file():
            raise ArtifactBuildError("PyInstaller did not produce the expected executable")
        # Credits include HEAD and cannot be a fixed-point tracked build output.
        # Refresh the packaged data without dirtying the reviewed checkout.
        build_credits(ROOT, target=frozen / "_internal/omega_omarchy/data/credits.json")
        bundle = temp / release_name
        # PyInstaller 6 uses relative in-tree symlinks for shared libraries.
        # Preserve them so the archive does not duplicate tens of MiB of native
        # payload; both the writer and verifier constrain every link to the
        # single bundle root.
        shutil.copytree(frozen, bundle, symlinks=True)
        shutil.copyfile(ROOT / "packaging" / "PLAYER-README.md", bundle / "README.md")
        shutil.copyfile(ROOT / "LICENSE", bundle / "LICENSE-CODE.txt")
        shutil.copyfile(ROOT / "ASSET-LICENSE.md", bundle / "ASSET-LICENSE.md")
        shutil.copyfile(ROOT / "CREDITS.md", bundle / "CREDITS.md")
        shutil.copyfile(ROOT / "THIRD_PARTY_NOTICES.md", bundle / "THIRD_PARTY_NOTICES.md")
        shutil.copyfile(
            ROOT / "src" / "omega_omarchy" / "data" / "content-packs" / "omega-core" / "LICENSE",
            bundle / "LICENSE-CORE-CONTENT.txt",
        )
        docs = bundle / "docs"
        docs.mkdir()
        for name in ("controls.md", "accessibility.md", "content-packs.md", "character-creation.md"):
            shutil.copyfile(ROOT / "docs" / name, docs / name)
        license_files = _copy_dependency_licenses(bundle / "licenses")
        dependencies = {
            "schemaVersion": "omega-dependencies/1",
            "runtime": _dependencies(),
            "python": platform.python_version(),
            "licenseFiles": license_files,
        }
        _write_json(bundle / "DEPENDENCIES.json", dependencies)
        build_info = {
            "artifactFormat": ARTIFACT_FORMAT,
            "architecture": architecture,
            "builtAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch)),
            "commit": commit,
            "contentsDirectory": "_internal",
            "dirty": dirty,
            "platform": "linux",
            "pyinstaller": version("pyinstaller"),
            "python": platform.python_version(),
            "runtimeAssetsDigest": _tree_digest(bundle / "_internal" / "assets"),
            "version": app_version,
        }
        _write_json(bundle / "BUILD-INFO.json", build_info)
        if archive.exists():
            archive.unlink()
        _write_archive(bundle, archive, epoch=epoch)

    archive_digest = _sha256(archive)
    checksum.write_text(f"{archive_digest}  {archive.name}\n", encoding="utf-8")
    print(f"ARTIFACT={archive}")
    print(f"SHA256={archive_digest}")
    print(f"CHECKSUM={checksum}")
    return archive, checksum


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "native-local")
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args(argv)
    try:
        build(args.output, require_clean=args.require_clean)
    except (ArtifactBuildError, OSError) as exc:
        print(f"PACKAGE_FAILED {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
