#!/usr/bin/env python3
"""Verify and smoke-launch a portable Omega Omarchy Linux archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_native import ARTIFACT_FORMAT

MAX_ARCHIVE_MEMBERS = 20_000
MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024


class ArtifactVerificationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _expected_digest(checksum: Path, archive: Path) -> str:
    fields = checksum.read_text(encoding="utf-8").strip().split()
    if (
        len(fields) != 2
        or fields[1] != archive.name
        or len(fields[0]) != 64
        or any(character not in "0123456789abcdef" for character in fields[0])
    ):
        raise ArtifactVerificationError("checksum file does not name the exact archive")
    return fields[0]


def _validate_members(bundle: tarfile.TarFile) -> str:
    roots: set[str] = set()
    members = bundle.getmembers()
    if not members:
        raise ArtifactVerificationError("archive is empty")
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise ArtifactVerificationError("archive member count exceeds safety limit")
    names: set[str] = set()
    files: set[str] = set()
    symlinks: list[tuple[str, str]] = []
    total_bytes = 0
    for member in members:
        path = PurePosixPath(member.name)
        if (
            path.is_absolute()
            or member.name != path.as_posix()
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ArtifactVerificationError(f"unsafe archive member: {member.name}")
        if member.islnk() or not (member.isdir() or member.isfile() or member.issym()):
            raise ArtifactVerificationError(f"unsupported archive member: {member.name}")
        if member.name in names:
            raise ArtifactVerificationError(f"duplicate archive member: {member.name}")
        names.add(member.name)
        total_bytes += member.size
        if total_bytes > MAX_ARCHIVE_BYTES:
            raise ArtifactVerificationError("archive expands beyond safety limit")
        roots.add(path.parts[0])
        if member.isfile():
            files.add(member.name)
        elif member.issym():
            link = PurePosixPath(member.linkname)
            target_name = posixpath.normpath(
                posixpath.join(posixpath.dirname(member.name), member.linkname)
            )
            target = PurePosixPath(target_name)
            if (
                not member.linkname
                or link.is_absolute()
                or target.is_absolute()
                or any(part in {"", ".", ".."} for part in target.parts)
                or target.parts[0] != path.parts[0]
            ):
                raise ArtifactVerificationError(
                    f"symlink escapes archive root: {member.name} -> {member.linkname}"
                )
            symlinks.append((member.name, target.as_posix()))
    if len(roots) != 1:
        raise ArtifactVerificationError(f"archive must have one root directory: {sorted(roots)}")
    for name, target in symlinks:
        if target not in files:
            raise ArtifactVerificationError(f"symlink target is not a bundled file: {name} -> {target}")
    return next(iter(roots))


def _run(command: list[str], *, cwd: Path, profile: Path) -> str:
    env = dict(os.environ)
    profile.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "HOME": str(profile),
            "XDG_CACHE_HOME": str(profile / "cache"),
            "XDG_CONFIG_HOME": str(profile / "config"),
            "XDG_DATA_HOME": str(profile / "data"),
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
        }
    )
    process = subprocess.run(command, cwd=cwd, env=env, check=False, text=True, capture_output=True)
    if process.returncode:
        raise ArtifactVerificationError(
            f"artifact command failed ({process.returncode}): {' '.join(command)}\n"
            f"{process.stdout}{process.stderr}"
        )
    return process.stdout


def _world_identity(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("WORLD_IDENTITY=sha256:"):
            return line.removeprefix("WORLD_IDENTITY=")
    raise ArtifactVerificationError("artifact command did not report a world identity")


def _verify_pack_lifecycle(binary: Path, *, cwd: Path, profile: Path) -> None:
    example = ROOT / "examples" / "content-packs" / "vertical-garden"
    if not example.is_dir():
        raise ArtifactVerificationError("maintained content-pack fixture is missing")
    review = _run([str(binary), "review-pack", str(example)], cwd=cwd, profile=profile)
    required_review = (
        "PACK_REVIEW",
        "id=example.vertical-garden",
        "license=CC0-1.0",
        "capabilities=chapter-profile",
    )
    if not all(marker in review for marker in required_review):
        raise ArtifactVerificationError("artifact content-pack review omitted required metadata")
    installed = _run(
        [str(binary), "install-pack", str(example), "--accept"],
        cwd=cwd,
        profile=profile,
    )
    if (
        "PACK_INSTALLED id=example.vertical-garden" not in installed
        or "enabled=no" not in installed
    ):
        raise ArtifactVerificationError("artifact content-pack install did not remain disabled")
    enabled = _run(
        [str(binary), "enable-pack", "example.vertical-garden"], cwd=cwd, profile=profile
    )
    if "PACK_ENABLED id=example.vertical-garden" not in enabled:
        raise ArtifactVerificationError("artifact content-pack activation failed")
    active_identity = _world_identity(
        _run(
            [str(binary), "dump-identity", "--seed", "artifact-pack-fixture"],
            cwd=cwd,
            profile=profile,
        )
    )
    core_identity = _world_identity(
        _run(
            [
                str(binary),
                "dump-identity",
                "--seed",
                "artifact-pack-fixture",
                "--no-installed-content",
            ],
            cwd=cwd,
            profile=profile,
        )
    )
    if active_identity == core_identity:
        raise ArtifactVerificationError("artifact content-pack activation did not change world identity")
    disabled = _run(
        [str(binary), "disable-pack", "example.vertical-garden"], cwd=cwd, profile=profile
    )
    removed = _run(
        [str(binary), "remove-pack", "example.vertical-garden"], cwd=cwd, profile=profile
    )
    listed = _run([str(binary), "list-packs"], cwd=cwd, profile=profile)
    if (
        "PACK_DISABLED id=example.vertical-garden" not in disabled
        or "PACK_REMOVED id=example.vertical-garden" not in removed
        or listed.strip() != "PACKS_EMPTY"
    ):
        raise ArtifactVerificationError("artifact content-pack cleanup failed")


def verify(archive: Path, checksum: Path, *, require_clean: bool = False) -> dict[str, object]:
    archive = archive.resolve()
    checksum = checksum.resolve()
    expected = _expected_digest(checksum, archive)
    actual = _sha256(archive)
    if actual != expected:
        raise ArtifactVerificationError(f"archive digest mismatch: expected={expected} actual={actual}")
    with tempfile.TemporaryDirectory(prefix="omega-native-verify-") as temporary:
        destination = Path(temporary)
        with tarfile.open(archive, "r:gz") as bundle:
            root_name = _validate_members(bundle)
            bundle.extractall(destination, filter="data")
        root = destination / root_name
        required = (
            "omega-omarchy",
            "BUILD-INFO.json",
            "DEPENDENCIES.json",
            "README.md",
            "LICENSE-CODE.txt",
            "LICENSE-CORE-CONTENT.txt",
            "ASSET-LICENSE.md",
            "CREDITS.md",
            "THIRD_PARTY_NOTICES.md",
            "docs/controls.md",
            "docs/accessibility.md",
            "docs/content-packs.md",
            "_internal/assets/characters/david_ultra_side-idle.png",
            "_internal/assets/character-packs/omarch-king/manifest.json",
            "_internal/assets/character-packs/omarch-queen/manifest.json",
            "_internal/assets/character-creation/agent-kit.zip",
            "_internal/assets/ui/omega-omarchy-icon.png",
            "_internal/omega_omarchy/data/content-packs/omega-core/pack.toml",
        )
        missing = [name for name in required if not (root / name).is_file()]
        if missing:
            raise ArtifactVerificationError(f"artifact is missing required files: {missing}")
        forbidden = [
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if "assets/source" in path.relative_to(root).as_posix()
            or "limitless_library" in path.relative_to(root).as_posix()
            or "cryptography" in path.relative_to(root).as_posix()
            or "jsonschema" in path.relative_to(root).as_posix()
            or path.name in {".git", "OMEGA-OMARCHY-GAME-DESIGN.md", "ONE-SHOT-DEVELOPMENT-GOAL.md"}
        ]
        if forbidden:
            raise ArtifactVerificationError(f"artifact contains private/source-only material: {forbidden}")
        build_info = json.loads((root / "BUILD-INFO.json").read_text(encoding="utf-8"))
        dependencies = json.loads((root / "DEPENDENCIES.json").read_text(encoding="utf-8"))
        if build_info.get("artifactFormat") != ARTIFACT_FORMAT:
            raise ArtifactVerificationError("artifact format is missing or incompatible")
        if require_clean and build_info.get("dirty") is not False:
            raise ArtifactVerificationError("artifact was built from a dirty worktree")
        dependency_names = {item["name"] for item in dependencies.get("runtime") or []}
        required_dependencies = {"pygame-ce", "pillow", "qrcode", "numpy", "pyinstaller"}
        if dependency_names != required_dependencies:
            raise ArtifactVerificationError(f"dependency inventory mismatch: {sorted(dependency_names)}")
        license_files = dependencies.get("licenseFiles") or []
        if not isinstance(license_files, list) or not license_files:
            raise ArtifactVerificationError("dependency license inventory is empty")
        for name in license_files:
            if not isinstance(name, str) or Path(name).name != name or not (root / "licenses" / name).is_file():
                raise ArtifactVerificationError(f"missing or unsafe dependency license file: {name}")
        binary = root / "omega-omarchy"
        if not os.access(binary, os.X_OK):
            raise ArtifactVerificationError("artifact launcher is not executable")
        profile = destination / "profile"
        asset_digest_before = _tree_digest(root / "_internal" / "assets")
        if build_info.get("runtimeAssetsDigest") != f"sha256:{asset_digest_before}":
            raise ArtifactVerificationError("runtime asset digest does not match build receipt")
        version_output = _run([str(binary), "version"], cwd=root, profile=profile).strip()
        if version_output != str(build_info.get("version")):
            raise ArtifactVerificationError(
                f"launcher version mismatch: output={version_output} metadata={build_info.get('version')}"
            )
        smoke = _run(
            [str(binary), "run", "--headless", "--ticks", "2"],
            cwd=root,
            profile=profile,
        )
        if "WORLD_IDENTITY=" not in smoke or "COMPLETION:Play Now" not in smoke:
            raise ArtifactVerificationError("headless artifact smoke did not reach the sealed Play Now world")
        _verify_pack_lifecycle(binary, cwd=root, profile=profile)
        if _tree_digest(root / "_internal" / "assets") != asset_digest_before:
            raise ArtifactVerificationError("artifact launch modified packaged runtime assets")
        unavailable = subprocess.run(
            [str(binary), "assets"],
            cwd=root,
            env={**os.environ, "HOME": str(profile)},
            check=False,
            text=True,
            capture_output=True,
        )
        if unavailable.returncode != 2 or "UNAVAILABLE_IN_PLAYER_BUNDLE" not in unavailable.stderr:
            raise ArtifactVerificationError("player bundle exposes the developer-only asset builder")
        print(f"ARTIFACT_OK archive={archive.name} sha256={actual} version={version_output}")
        return {"archive": archive.name, "digest": actual, "build": build_info}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("checksum", type=Path)
    parser.add_argument("--require-clean", action="store_true")
    args = parser.parse_args(argv)
    try:
        verify(args.archive, args.checksum, require_clean=args.require_clean)
    except (ArtifactVerificationError, OSError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"ARTIFACT_INVALID {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
