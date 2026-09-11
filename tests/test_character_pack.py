from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from zipfile import ZipFile

from PIL import Image
import pygame
import pytest

from omega_omarchy.canonical import sha256_json
from omega_omarchy.character import DAVID, parse_character
from omega_omarchy.character_build import build_pack, export_kit, validate_source, zip_pack
from omega_omarchy.character_pack import POSES, available_characters, decode_png, install_pack, install_zip, pose_size, resolve_pack, validate_pack
from omega_omarchy.installer import InstallerSession, PARODY_STEPS
from omega_omarchy.physics import InputState
from omega_omarchy.presentation import FIDELITIES
from omega_omarchy.render import Renderer
from omega_omarchy.runtime_assets import asset_dir
from omega_omarchy.sim import GameSim


def royal(kind="omarch-king"):
    return next(c for c in available_characters()[0] if c.kind == kind)


def custom_source(tmp_path):
    source = export_kit(tmp_path / "source", asset_dir())
    manifest_path = source / "character.json"
    record = json.loads(manifest_path.read_text())
    record.update(id="test-royal", name="Test Royal", author="Test fixture", license="Local test fixture only")
    manifest_path.write_text(json.dumps(record))
    for pose in POSES:
        shutil.copyfile(asset_dir() / "character-packs/omarch-king/ultra" / f"{pose}.png", source / "frames" / f"{pose}.png")
    return source


def test_builtins_have_complete_distinct_art_and_preserve_david_identity():
    roster, errors = available_characters(storage=Path("/nonexistent-character-fixture"))
    assert not errors
    assert [c.kind for c in roster] == ["david", "omarch-king", "omarch-queen"]
    assert "assetPack" not in DAVID.to_record()
    assert parse_character(DAVID.to_record()) == DAVID
    for fid in FIDELITIES:
        existing_poses = {path.stem.removeprefix("david_") for path in (asset_dir() / "fidelity" / fid / "characters").glob("david_*.png")}
        assert existing_poses == set(POSES), "the custom contract must cover every current David view"
    for character in roster[1:]:
        assert parse_character(character.to_record()) == character
        assert character.ability_bias() == DAVID.ability_bias()
        root = resolve_pack(character.to_record())
        assert len(validate_pack(root)["files"]) == 78
        for fidelity in FIDELITIES:
            for pose in POSES:
                with Image.open(root / fidelity / f"{pose}.png") as image:
                    assert image.size == pose_size(pose, fidelity)
                    assert image.getchannel("A").getextrema() == (0, 255)
                    with Image.open(asset_dir() / "fidelity" / fidelity / "characters" / f"david_{pose}.png") as david:
                        assert image.tobytes() != david.convert("RGBA").tobytes()


def test_installer_selects_and_renames_without_changing_appearance():
    sim = GameSim.new()
    for _ in range(60):
        sim.step(InputState())
    assert sim.installer.characters_ready
    sim.installer.step_index = PARODY_STEPS.index("character")
    sim.step(InputState(down_pressed=True))
    assert sim.installer.choices.character.kind == "omarch-king"
    sim.step(InputState(right_pressed=True))
    assert sim.installer.choices.character.kind == "omarch-queen"
    sim.installer.edit_character_name("Ada")
    selected = sim.installer.choices.character
    assert selected.name == "Ada" and selected.asset_pack == "omarch-queen"
    assert parse_character(selected.to_record()) == selected
    sim.step(InputState(interact=True))
    assert sim.installer.step == "seed"


def test_agent_option_does_not_silently_start_a_david_world(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    session = InstallerSession(step_index=PARODY_STEPS.index("character"))
    session.cycle(-1)
    assert session.character_agent_selected
    session.next_step()
    assert session.step == "character" and session.character_help_open
    assert (tmp_path / "omega-omarchy/character-agent-kit.zip").is_file()
    session.cycle(-1)
    assert not session.character_help_open and session.choices.character.kind == "omarch-queen"


def test_agent_kit_and_pack_round_trip_with_exact_version_and_all_tiers(tmp_path):
    source = custom_source(tmp_path)
    _, images = validate_source(source)
    assert set(images) == set(POSES)
    pack = build_pack(source, tmp_path / "compiled")
    archive = zip_pack(pack, tmp_path / "character.zip")
    installed = install_zip(archive.read_bytes(), storage=tmp_path / "installed")
    assert install_pack(pack, storage=tmp_path / "installed") == installed
    roster, errors = available_characters(storage=tmp_path / "installed")
    assert not errors
    custom = next(c for c in roster if c.asset_pack == "test-royal")
    assert custom.kind == "custom"
    assert resolve_pack(custom.to_record(), storage=tmp_path / "installed") == installed
    assert "digest" in validate_pack(installed)
    with pytest.raises(ValueError, match="unavailable"):
        resolve_pack(replace(custom, asset_digest="sha256:" + "0" * 64).to_record(), storage=tmp_path / "installed")
    (installed / "high/side-bomb.png").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="PNG"):
        validate_pack(installed)


def test_source_rejects_missing_poses_opaque_backdrops_and_escaping_paths(tmp_path):
    source = custom_source(tmp_path)
    path = source / "frames/ots.png"
    path.unlink()
    with pytest.raises(OSError):
        validate_source(source)
    Image.new("RGBA", pose_size("ots", "ultra"), "white").save(path)
    with pytest.raises(ValueError, match="transparent"):
        validate_source(source)
    manifest_path = source / "character.json"
    record = json.loads(manifest_path.read_text())
    record["frames"]["side-idle"] = "../outside.png"
    manifest_path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="Invalid source"):
        validate_source(source)


def test_archive_rejects_unexpected_paths_before_writing(tmp_path):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("../outside.py", "raise RuntimeError('must never run')")
    with pytest.raises(ValueError, match="root"):
        install_zip(buffer.getvalue(), storage=tmp_path / "installed")
    assert not (tmp_path / "installed").exists()


def test_browser_png_decoder_matches_source_pixels_and_rejects_corruption():
    for pose in POSES:
        path = asset_dir() / "character-packs/omarch-queen/ultra" / f"{pose}.png"
        data = path.read_bytes()
        with Image.open(path) as source:
            assert decode_png(data) == source.convert("RGBA").tobytes()
        with pytest.raises(ValueError, match="checksum"):
            decode_png(data[:-5] + bytes([data[-5] ^ 1]) + data[-4:])


def test_browser_import_bridge_persists_and_restores_a_custom_pack(tmp_path, monkeypatch):
    import base64
    import platform
    from omega_omarchy import character_pack

    pack = build_pack(custom_source(tmp_path), tmp_path / "compiled")
    archive = zip_pack(pack, tmp_path / "character.zip")
    saved = {}

    class BrowserStorage:
        @property
        def length(self):
            return len(saved)

        def key(self, index):
            return list(saved)[index]

        def getItem(self, key):
            return saved.get(key)

        def setItem(self, key, value):
            saved[key] = value

    window = SimpleNamespace(localStorage=BrowserStorage(), omegaCharacterImport=base64.b64encode(archive.read_bytes()).decode())
    monkeypatch.setattr(platform, "window", window, raising=False)
    monkeypatch.setattr(character_pack, "sys", SimpleNamespace(platform="emscripten"))
    monkeypatch.setattr(character_pack, "user_data_dir", lambda: tmp_path / "data")
    assert character_pack.poll_browser_import().startswith("Installed Test Royal")
    assert window.omegaCharacterImport == ""
    assert len(saved) == 1
    shutil.rmtree(tmp_path / "data/characters")
    character_pack.restore_browser_characters()
    roster, errors = available_characters(storage=tmp_path / "data/characters")
    assert not errors and any(c.asset_pack == "test-royal" for c in roster)


def test_cli_reports_invalid_character_without_a_traceback(tmp_path, capsys):
    from omega_omarchy.cli import main

    assert main(["validate-character", str(tmp_path)]) == 2
    assert "CHARACTER_INVALID" in capsys.readouterr().err


def test_all_runtime_views_resolve_the_selected_pack_and_missing_art_falls_back_once():
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    sim = GameSim.new()
    sim.installer.step_index = PARODY_STEPS.index("character")
    for character in (royal(), royal("omarch-queen")):
        sim.installer.choices.character = character
        for fidelity in FIDELITIES:
            sim.installer.choices.fidelity = fidelity
            for pose in POSES:
                sprite = renderer._character_sprite(sim, pose)
                assert sprite.get_size() == pose_size(pose, fidelity)
            renderer.frame(sim)
    sim.installer.choices.character = replace(royal(), kind="custom", asset_digest="sha256:" + "0" * 64)
    for pose in POSES:
        renderer._character_sprite(sim, pose)
    warnings = [m for m in sim.messages if "Using David art" in m]
    assert len(warnings) == 1


def test_selected_character_and_art_digest_survive_world_save_and_reload(tmp_path):
    sim = GameSim.new()
    sim.installer.choices.character = replace(royal("omarch-queen"), name="Ada")
    sim.confirm_play_now(skip_prologue=True)
    original = dict(sim.world.character)
    sim.save_path = tmp_path / "world.json"
    sim.save_to_disk()
    sim.load_from_disk()
    assert sim.world.character == original
    assert sim.character_name == "Ada"
    assert sim.world.character["assetPack"] == "omarch-queen"
    assert resolve_pack(sim.world.character)
