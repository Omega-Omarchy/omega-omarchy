from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from omega_omarchy.cli import main
from omega_omarchy.content import BUILTIN_PACK, load_content
from omega_omarchy.content_pack import PackValidationError, order_packs, seal_pack, validate_pack
from omega_omarchy.generation import generate_world
from omega_omarchy.sim import GameSim


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PACK = ROOT / "examples" / "content-packs" / "vertical-garden"


def _copy_core(tmp_path: Path) -> Path:
    target = tmp_path / "pack"
    shutil.copytree(BUILTIN_PACK, target)
    return target


def test_built_in_and_example_pack_validate_and_compose() -> None:
    core = validate_pack(BUILTIN_PACK)
    example = validate_pack(EXAMPLE_PACK)
    assert core.pack_id == "omega-core-1"
    assert example.dependencies == (core.pack_id,)

    content = load_content((EXAMPLE_PACK,))
    profile = content.chapter_profile("corrupted-install")
    assert content.pack_ids == ("omega-core-1", "example.vertical-garden")
    assert profile is not None
    assert profile["generation"]["recipes"][-1] == "broken-bridge"
    assert profile["generation"]["sectorMotifs"][-1] == "garden"
    assert profile["enemyMotifs"][-1] == "garden-glitch"
    assert profile["itemPool"][-1] == "mirror-cache"


def test_enabled_pack_changes_deterministic_world_and_receipt() -> None:
    core_world = generate_world("pack-fixture", content=load_content(), force_logo=True)
    content = load_content((EXAMPLE_PACK,))
    first = generate_world("pack-fixture", content=content, force_logo=True)
    repeat = generate_world("pack-fixture", content=content, force_logo=True)

    assert first.to_record() == repeat.to_record()
    assert first.identity.digest() != core_world.identity.digest()
    assert first.chapters[0]["placements"] != core_world.chapters[0]["placements"]
    assert first.identity.content_pack_ids == ("omega-core-1", "example.vertical-garden")
    assert first.receipt["contentPackIdentities"] == content.pack_identities()
    assert first.chapters[0]["contentAddons"][0]["sourcePack"] == "example.vertical-garden"


def test_cli_validates_pack(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate-pack", str(EXAMPLE_PACK)]) == 0
    assert "PACK_OK id=example.vertical-garden" in capsys.readouterr().out


def test_cli_rejects_invalid_pack_before_world_activation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _copy_core(tmp_path)
    manifest = root / "pack.toml"
    manifest.write_text(manifest.read_text().replace('schemaVersion = "1.0.0"', 'schemaVersion = "9.0.0"'))
    assert main(["dump-identity", "--content-pack", str(root)]) == 2
    assert "PACK_INVALID unsupported pack schema 9.0.0" in capsys.readouterr().err


def test_seal_pack_refreshes_file_and_content_digests(tmp_path: Path) -> None:
    root = _copy_core(tmp_path)
    chapter = root / "chapters" / "corrupted-install.json"
    chapter.write_text(chapter.read_text().replace("The world did not.", "The world did not. Again."))
    before = validate_pack(BUILTIN_PACK).content_digest
    sealed = seal_pack(root)
    assert sealed.content_digest != before
    assert validate_pack(root).content_digest == sealed.content_digest


def test_failed_seal_does_not_replace_source_manifest(tmp_path: Path) -> None:
    root = _copy_core(tmp_path)
    manifest = root / "pack.toml"
    before = manifest.read_text()
    chapter = root / "chapters" / "corrupted-install.json"
    entry = json.loads(chapter.read_text())
    entry["ignoredByEngine"] = True
    chapter.write_text(json.dumps(entry))

    with pytest.raises(PackValidationError, match="unsupported fields"):
        seal_pack(root)
    assert manifest.read_text() == before


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda root: (root / "pack.toml").write_text((root / "pack.toml").read_text().replace('schemaVersion = "1.0.0"', 'schemaVersion = "9.0.0"')), "unsupported pack schema"),
        (lambda root: (root / "pack.toml").write_text((root / "pack.toml").read_text().replace('path = "ATTRIBUTION.md"', 'path = "../ATTRIBUTION.md"')), "unsafe pack path"),
        (lambda root: (root / "chapters" / "corrupted-install.json").write_text((root / "chapters" / "corrupted-install.json").read_text() + "\n"), "mismatch"),
        (lambda root: (root / "surprise.json").write_text("{}"), "undeclared"),
        (lambda root: (root / "pack.toml").write_text("mystery = true\n" + (root / "pack.toml").read_text()), "unsupported manifest fields"),
        (lambda root: (root / "pack.toml").write_text((root / "pack.toml").read_text().replace("bytes = 236", "bytes = true")), "bytes must be an integer"),
    ),
)
def test_pack_validator_rejects_corrupt_or_unsafe_inputs(tmp_path: Path, mutation, message: str) -> None:
    root = _copy_core(tmp_path)
    mutation(root)
    with pytest.raises(PackValidationError, match=message):
        validate_pack(root)


def test_pack_validator_rejects_symlinks(tmp_path: Path) -> None:
    root = _copy_core(tmp_path)
    license_path = root / "LICENSE"
    license_path.unlink()
    license_path.symlink_to("ATTRIBUTION.md")
    with pytest.raises(PackValidationError, match="symlink"):
        validate_pack(root)


def test_pack_validator_rejects_executable_payload(tmp_path: Path) -> None:
    root = _copy_core(tmp_path)
    payload = root / "payload.py"
    payload.write_text("raise SystemExit\n")
    manifest = root / "pack.toml"
    manifest.write_text(
        manifest.read_text()
        + "\n[[files]]\n"
        + 'path = "payload.py"\n'
        + 'digest = "sha256:dac72909b22cced85a1274177d820a73f9f391f0e6eea2c4db3f0d0d093edc58"\n'
        + "bytes = 17\n"
        + 'mediaType = "text/x-python"\n'
    )
    with pytest.raises(PackValidationError, match="executable file type"):
        validate_pack(root)


def test_pack_ordering_rejects_missing_dependencies_cycles_and_conflicts() -> None:
    core = validate_pack(BUILTIN_PACK)
    example = validate_pack(EXAMPLE_PACK)
    with pytest.raises(PackValidationError, match="missing dependency"):
        order_packs((example,))
    with pytest.raises(PackValidationError, match="cycle"):
        order_packs((replace(core, load_after=(example.pack_id,)), example))
    with pytest.raises(PackValidationError, match="duplicate pack id"):
        order_packs((core, replace(example, pack_id=core.pack_id, dependencies=(), load_after=())))
    conflicting = replace(example, entries=(dict(core.entries[0]),))
    with pytest.raises(PackValidationError, match="content id conflict"):
        order_packs((core, conflicting))


def test_save_load_requires_exact_enabled_pack_set(tmp_path: Path) -> None:
    save_path = tmp_path / "pack-save.json"
    source = GameSim.from_play_now("pack-save", (EXAMPLE_PACK,))
    source.save_path = save_path
    source.save_to_disk()

    missing = GameSim.from_play_now("different-world")
    missing.save_path = save_path
    before = missing.world.identity.digest() if missing.world else ""
    missing.load_from_disk()
    assert missing.world is not None and missing.world.identity.digest() == before
    assert "missing=['example.vertical-garden']" in missing.messages[-1]

    restored = GameSim.from_play_now("different-world", (EXAMPLE_PACK,))
    restored.save_path = save_path
    restored.load_from_disk()
    assert restored.world is not None
    assert restored.world.identity.seed == "pack-save"
    assert restored.messages[-1] == "Save restored."
