from __future__ import annotations

import json
from pathlib import Path
import shutil
import stat
import zipfile

import pytest

from omega_omarchy.cli import main
from omega_omarchy.content import load_content
from omega_omarchy.content_pack import PackValidationError, seal_pack, validate_pack
from omega_omarchy.generation import generate_world
from omega_omarchy.pack_store import PackConsentRequired, PackStore, PackStoreError


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PACK = ROOT / "examples" / "content-packs" / "vertical-garden"


def _zip_pack(destination: Path, *, prefix: str = "vertical-garden") -> Path:
    archive = destination / "vertical-garden.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for source in sorted(EXAMPLE_PACK.rglob("*")):
            if source.is_file():
                relative = source.relative_to(EXAMPLE_PACK).as_posix()
                output.write(source, f"{prefix}/{relative}" if prefix else relative)
    return archive


def _install(store: PackStore, source: Path = EXAMPLE_PACK):
    review = store.review(source)
    return store.install(source, accept=True, accepted_digest=review.content_digest)


def test_review_is_read_only_and_install_requires_explicit_acceptance(tmp_path: Path) -> None:
    store_root = tmp_path / "player-data" / "content-packs"
    store = PackStore(store_root)

    review = store.review(EXAMPLE_PACK)
    assert review.pack_id == "example.vertical-garden"
    assert review.version == "1.0.0"
    assert review.license == "CC0-1.0"
    assert review.capabilities == ("chapter-profile",)
    assert review.dependencies == ("omega-core-1",)
    assert review.files == 3
    assert not store_root.exists()

    with pytest.raises(PackConsentRequired, match="explicit --accept"):
        store.install(EXAMPLE_PACK)
    assert not store_root.exists()


def test_directory_install_enable_disable_remove_lifecycle_is_deterministic(tmp_path: Path) -> None:
    store = PackStore(tmp_path / "content-packs")
    expected = validate_pack(EXAMPLE_PACK)

    installed = _install(store)
    assert installed.identity() == expected.identity()
    assert installed.enabled is False
    assert _install(store) == installed

    core_world = generate_world("installed-pack", content=load_content(), force_logo=True)
    enabled = store.enable(expected.pack_id)
    paths = store.enabled_paths()
    first = generate_world("installed-pack", content=load_content(paths), force_logo=True)
    repeat = generate_world("installed-pack", content=load_content(paths), force_logo=True)
    assert enabled.enabled is True
    assert first.to_record() == repeat.to_record()
    assert first.identity.digest() != core_world.identity.digest()

    with pytest.raises(PackStoreError, match="disable .* before removing"):
        store.remove(expected.pack_id)
    assert store.disable(expected.pack_id).enabled is False
    removed = store.remove(expected.pack_id)
    assert removed.identity() == expected.identity()
    assert store.list() == ()
    assert not (store.root / removed.relative_path).exists()


def test_zip_install_accepts_one_flat_or_wrapped_pack_root(tmp_path: Path) -> None:
    for index, prefix in enumerate(("vertical-garden", "")):
        archive_dir = tmp_path / f"archive-{index}"
        archive_dir.mkdir()
        archive = _zip_pack(archive_dir, prefix=prefix)
        store = PackStore(tmp_path / f"store-{index}")
        review = store.review(archive)
        installed = store.install(
            archive, accept=True, accepted_digest=review.content_digest
        )
        assert review.pack_id == installed.pack_id == "example.vertical-garden"
        assert installed.source_label == "vertical-garden.zip"
        assert validate_pack(store.root / installed.relative_path).identity() == installed.identity()


@pytest.mark.parametrize(
    "attack", ("traversal", "duplicate", "symlink", "extra-root", "file-directory")
)
def test_zip_review_rejects_ambiguous_or_unsafe_members(tmp_path: Path, attack: str) -> None:
    archive = _zip_pack(tmp_path)
    with zipfile.ZipFile(archive, "a") as output:
        if attack == "traversal":
            output.writestr("vertical-garden/../outside.txt", "outside")
        elif attack == "duplicate":
            output.writestr("VERTICAL-GARDEN/LICENSE", "duplicate")
        elif attack == "extra-root":
            output.writestr("unrelated/readme.txt", "unrelated")
        elif attack == "file-directory":
            output.writestr("vertical-garden/collision", "file")
            output.writestr("vertical-garden/collision/child.txt", "child")
        else:
            link = zipfile.ZipInfo("vertical-garden/linked.txt")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            output.writestr(link, "LICENSE")

    with pytest.raises(PackValidationError):
        PackStore(tmp_path / "store").review(archive)


def test_same_id_and_version_cannot_be_replaced_by_a_different_digest(tmp_path: Path) -> None:
    store = PackStore(tmp_path / "store")
    _install(store)
    changed = tmp_path / "changed"
    shutil.copytree(EXAMPLE_PACK, changed)
    attribution = changed / "ATTRIBUTION.md"
    attribution.write_text(attribution.read_text(encoding="utf-8") + "\nAdditional attribution.\n", encoding="utf-8")
    seal_pack(changed)

    with pytest.raises(PackStoreError, match="different digest"):
        review = store.review(changed)
        store.install(changed, accept=True, accepted_digest=review.content_digest)


def test_multiple_installed_versions_require_an_explicit_selection(tmp_path: Path) -> None:
    store = PackStore(tmp_path / "store")
    first = _install(store)
    newer_source = tmp_path / "newer"
    shutil.copytree(EXAMPLE_PACK, newer_source)
    manifest = newer_source / "pack.toml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace('version = "1.0.0"', 'version = "1.1.0"', 1),
        encoding="utf-8",
    )
    seal_pack(newer_source)
    newer = _install(store, newer_source)

    assert first.version == "1.0.0"
    assert newer.version == "1.1.0"
    with pytest.raises(PackStoreError, match="multiple versions installed"):
        store.enable(first.pack_id)
    assert store.enable(first.pack_id, newer.version).version == newer.version
    states = {item.version: item.enabled for item in store.list()}
    assert states == {"1.0.0": False, "1.1.0": True}


def test_installation_is_bound_to_the_exact_reviewed_digest(tmp_path: Path) -> None:
    store = PackStore(tmp_path / "store")
    source = tmp_path / "source"
    shutil.copytree(EXAMPLE_PACK, source)
    reviewed = store.review(source)
    attribution = source / "ATTRIBUTION.md"
    attribution.write_text(attribution.read_text(encoding="utf-8") + "\nChanged after review.\n")
    seal_pack(source)

    with pytest.raises(PackStoreError, match="changed after review"):
        store.install(source, accept=True, accepted_digest=reviewed.content_digest)
    assert not store.root.exists()


def test_registry_and_installed_content_corruption_fail_closed(tmp_path: Path) -> None:
    store = PackStore(tmp_path / "store")
    installed = _install(store)
    state = json.loads(store.state_path.read_text(encoding="utf-8"))
    state["installed"][0]["source"] = "tampered"
    store.state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(PackStoreError, match="registry digest mismatch"):
        store.list()

    clean_store = PackStore(tmp_path / "clean-store")
    clean = _install(clean_store)
    chapter = clean_store.root / clean.relative_path / "chapters" / "vertical-garden-addon.json"
    chapter.write_text(chapter.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(PackValidationError, match="mismatch"):
        clean_store.enable(installed.pack_id)


def test_registry_duplicate_keys_fail_closed(tmp_path: Path) -> None:
    store = PackStore(tmp_path / "store")
    _install(store)
    raw = store.state_path.read_text(encoding="utf-8")
    store.state_path.write_text(raw.replace('"schemaVersion":', '"schemaVersion": "1.0.0",\n  "schemaVersion":', 1))

    with pytest.raises(PackStoreError, match="duplicate JSON key"):
        store.list()


def test_cli_pack_lifecycle_and_default_activation(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    pack_id = "example.vertical-garden"

    assert main(["install-pack", str(EXAMPLE_PACK)]) == 2
    captured = capsys.readouterr()
    assert "PACK_REVIEW" in captured.out
    assert "PACK_CONFIRM_REQUIRED" in captured.err

    assert main(["install-pack", str(EXAMPLE_PACK), "--accept"]) == 0
    assert "enabled=no" in capsys.readouterr().out
    assert main(["enable-pack", pack_id]) == 0
    capsys.readouterr()

    assert main(["dump-identity", "--seed", "pack-cli"]) == 0
    active = capsys.readouterr().out
    assert main(["dump-identity", "--seed", "pack-cli", "--no-installed-content"]) == 0
    core_only = capsys.readouterr().out
    assert active.splitlines()[0] != core_only.splitlines()[0]

    assert main(["disable-pack", pack_id]) == 0
    assert main(["remove-pack", pack_id]) == 0
    assert main(["list-packs"]) == 0
    assert "PACKS_EMPTY" in capsys.readouterr().out
