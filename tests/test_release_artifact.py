from __future__ import annotations

import hashlib
import io
from pathlib import Path
import sys
import tarfile

import pytest

from omega_omarchy.assets import asset_dir
from omega_omarchy.save import user_data_dir
from tools.build_native import ARTIFACT_FORMAT, ArtifactBuildError, _write_archive
from tools.verify_native import ArtifactVerificationError, _expected_digest, _validate_members


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_asset_root_uses_meipass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert asset_dir() == tmp_path / "assets"


def test_user_data_dir_honors_only_absolute_xdg_paths(tmp_path: Path) -> None:
    assert user_data_dir({"XDG_DATA_HOME": str(tmp_path)}) == tmp_path / "omega-omarchy"
    fallback = tmp_path / "home" / ".local" / "share" / "omega-omarchy"
    assert user_data_dir({}, home=tmp_path / "home") == fallback
    assert user_data_dir({"XDG_DATA_HOME": "relative"}, home=tmp_path / "home") == fallback


def test_normalized_archive_wrapper_is_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "omega-bundle"
    source.mkdir()
    (source / "omega-omarchy").write_bytes(b"binary")
    (source / "BUILD-INFO.json").write_text(ARTIFACT_FORMAT)
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"
    _write_archive(source, first, epoch=1_700_000_000)
    _write_archive(source, second, epoch=1_700_000_000)
    assert first.read_bytes() == second.read_bytes()


def test_normalized_archive_preserves_safe_internal_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "omega-bundle"
    internal = source / "_internal"
    libraries = internal / "libraries"
    libraries.mkdir(parents=True)
    (libraries / "libomega.so").write_bytes(b"library")
    (internal / "libomega.so").symlink_to("libraries/libomega.so")
    archive_path = tmp_path / "bundle.tar.gz"
    _write_archive(source, archive_path, epoch=1_700_000_000)
    with tarfile.open(archive_path, "r:gz") as archive:
        link = archive.getmember("omega-bundle/_internal/libomega.so")
        assert link.issym()
        assert link.linkname == "libraries/libomega.so"
        assert _validate_members(archive) == "omega-bundle"


def test_normalized_archive_rejects_symlink_outside_bundle(tmp_path: Path) -> None:
    source = tmp_path / "omega-bundle"
    source.mkdir()
    outside = tmp_path / "outside.so"
    outside.write_bytes(b"outside")
    (source / "libomega.so").symlink_to(outside)
    with pytest.raises(ArtifactBuildError, match="symlink escapes bundle root"):
        _write_archive(source, tmp_path / "bundle.tar.gz", epoch=1_700_000_000)


def test_checksum_must_name_exact_archive(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.tar.gz"
    archive.write_bytes(b"artifact")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = tmp_path / "bundle.tar.gz.sha256"
    checksum.write_text(f"{digest}  {archive.name}\n")
    assert _expected_digest(checksum, archive) == digest
    checksum.write_text(f"{digest}  other.tar.gz\n")
    with pytest.raises(ArtifactVerificationError, match="exact archive"):
        _expected_digest(checksum, archive)
    checksum.write_text(f"{'z' * 64}  {archive.name}\n")
    with pytest.raises(ArtifactVerificationError, match="exact archive"):
        _expected_digest(checksum, archive)


def test_archive_verifier_rejects_traversal() -> None:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("../escape")
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))
    payload.seek(0)
    with tarfile.open(fileobj=payload, mode="r") as archive:
        with pytest.raises(ArtifactVerificationError, match="unsafe archive member"):
            _validate_members(archive)


def test_archive_verifier_rejects_duplicate_members() -> None:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        for value in (b"a", b"b"):
            info = tarfile.TarInfo("bundle/file")
            info.size = 1
            archive.addfile(info, io.BytesIO(value))
    payload.seek(0)
    with tarfile.open(fileobj=payload, mode="r") as archive:
        with pytest.raises(ArtifactVerificationError, match="duplicate archive member"):
            _validate_members(archive)


def test_archive_verifier_rejects_noncanonical_aliases() -> None:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        info = tarfile.TarInfo("bundle//file")
        info.size = 1
        archive.addfile(info, io.BytesIO(b"x"))
    payload.seek(0)
    with tarfile.open(fileobj=payload, mode="r") as archive:
        with pytest.raises(ArtifactVerificationError, match="unsafe archive member"):
            _validate_members(archive)


def test_archive_verifier_rejects_escaping_symlink() -> None:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w") as archive:
        root = tarfile.TarInfo("bundle")
        root.type = tarfile.DIRTYPE
        archive.addfile(root)
        link = tarfile.TarInfo("bundle/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../escape"
        archive.addfile(link)
    payload.seek(0)
    with tarfile.open(fileobj=payload, mode="r") as archive:
        with pytest.raises(ArtifactVerificationError, match="symlink escapes"):
            _validate_members(archive)


def test_ci_and_public_contribution_surfaces_are_tracked() -> None:
    required = (
        ".github/workflows/ci.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CREDITS.md",
        "GOVERNANCE.md",
        "ROADMAP.md",
        "DCO.md",
        "ASSET-LICENSE.md",
        "THIRD_PARTY_NOTICES.md",
        "docs/release-artifact.md",
    )
    assert all((ROOT / name).is_file() for name in required)
    assert not (ROOT / "CODE_OF_CONDUCT.md").exists()
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "permissions:\n  contents: read" in workflow
    assert "pull_request_target" not in workflow
    assert "package --require-clean" in workflow
    assert "verify-package" in workflow
    assert "./scripts/omega release-check" in workflow
    script = (ROOT / "scripts" / "omega").read_text()
    assert 'cmd="${1:-help}"' in script
    assert "Specify issue-relevant test paths/selectors" in script
