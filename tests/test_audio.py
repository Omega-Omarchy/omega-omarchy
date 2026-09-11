import hashlib
import json
from pathlib import Path
import wave

import pygame
import pytest

from omega_omarchy.audio import (
    AUDIO_FIDELITIES,
    AUDIO_SETTING_ROWS,
    AudioManager,
    normalize_audio_settings,
)
from omega_omarchy.audio_build import _emit_sfx_masters
from omega_omarchy.campaign import chapter_by_id
from omega_omarchy.physics import InputState
from omega_omarchy.runtime_assets import asset_dir
from omega_omarchy.sim import GameSim


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runtime_manifest_resolves_every_semantic_cue_at_every_tier():
    root = asset_dir() / "audio"
    manifest = json.loads((root / "audio-manifest.json").read_text(encoding="utf-8"))
    assert tuple(manifest["tiers"]) == AUDIO_FIDELITIES
    assert {"ui", "logo", "jump", "collect", "convert", "hit", "bomb"} <= set(manifest["cues"])
    assert "credits-theme" in manifest["cues"]
    assert not {"installation-signal", "chapter-one", "boss-pressure"} & set(manifest["cues"])
    assert manifest["cues"]["credits-theme"]["loop"] is False
    assert manifest["sceneMusic"] == {
        "chapter-credits": "credits-roll",
        "credits": "credits-roll",
        "ending": "credits-theme",
    }
    for cue in manifest["cues"].values():
        assert set(cue["files"]) == set(AUDIO_FIDELITIES)
        assert set(cue["levels"]) == set(AUDIO_FIDELITIES)
        files = [root / cue["files"][tier] for tier in AUDIO_FIDELITIES]
        assert all(path.is_file() and path.read_bytes().startswith(b"OggS") for path in files)
        assert len({_digest(path) for path in files}) == 3


def test_source_sfx_masters_are_deterministic_and_stereo(tmp_path):
    _emit_sfx_masters(tmp_path)
    first = {path.relative_to(tmp_path): _digest(path) for path in tmp_path.rglob("*.wav")}
    _emit_sfx_masters(tmp_path)
    second = {path.relative_to(tmp_path): _digest(path) for path in tmp_path.rglob("*.wav")}
    assert first == second
    assert set(path.parts[-2] for path in first) == {"ui", "logo", "jump", "collect", "convert", "hit", "bomb"}
    with wave.open(str(tmp_path / "sfx" / "convert" / "master.wav"), "rb") as source:
        assert source.getframerate() == 48_000
        assert source.getnchannels() == 2


def test_visual_and_audio_fidelity_are_independent_across_all_nine_combinations():
    sim = GameSim.from_play_now()
    identity = sim.identity_digest
    for visual in AUDIO_FIDELITIES:
        for sound in AUDIO_FIDELITIES:
            sim.set_presentation(fidelity=visual)
            sim.set_audio_fidelity(sound)
            assert sim.fidelity == visual
            assert sim.audio_fidelity == sound
            assert sim.settings["fidelity"] == visual
            assert sim.settings["audioFidelity"] == sound
            assert sim.identity_digest == identity


def test_old_settings_inherit_visual_fidelity_once_then_diverge():
    migrated = normalize_audio_settings({"fidelity": "high"}, legacy_fidelity="high")
    assert migrated["audioFidelity"] == "high"
    migrated["fidelity"] = "ultra"
    migrated = normalize_audio_settings(migrated, legacy_fidelity="ultra")
    assert migrated["audioFidelity"] == "high"


def test_audio_settings_menu_changes_quality_buses_mute_and_captions():
    sim = GameSim.from_play_now()
    sim.scene = "audio-settings"
    assert sim.audio_settings_rows == AUDIO_SETTING_ROWS
    sim.audio_cursor = AUDIO_SETTING_ROWS.index("quality")
    sim.step(InputState(left_pressed=True))
    assert sim.audio_fidelity == "high"
    sim.audio_cursor = AUDIO_SETTING_ROWS.index("music")
    before = sim.settings["audio"]["musicVolume"]
    sim.step(InputState(left_pressed=True))
    assert sim.settings["audio"]["musicVolume"] == pytest.approx(before - 0.05)
    sim.audio_cursor = AUDIO_SETTING_ROWS.index("mute")
    sim.step(InputState(jump_pressed=True))
    assert sim.audio_muted and sim.settings["audio"]["muted"]
    sim.audio_cursor = AUDIO_SETTING_ROWS.index("captions")
    sim.step(InputState(jump_pressed=True))
    assert sim.audio_captions and sim.settings["audio"]["captions"]
    sim.note("collect")
    assert sim.audio_caption == "Item collected"


def test_audio_settings_save_and_restore(tmp_path):
    sim = GameSim.from_play_now()
    sim.set_audio_fidelity("sixteen-bit")
    sim.settings["audio"]["masterVolume"] = 0.35
    sim.audio_captions = True
    sim._sync_audio()
    path = tmp_path / "audio-save.json"
    sim.save_path = path
    sim.save_to_disk()

    restored = GameSim.from_play_now()
    restored.save_path = path
    restored.load_from_disk()
    assert restored.audio_fidelity == "sixteen-bit"
    assert restored.settings["audio"]["masterVolume"] == 0.35
    assert restored.audio_captions is True


def test_manager_resolves_tiers_when_playback_is_disabled():
    manager = AudioManager(enabled=False)
    assert manager.available is False
    for fidelity in AUDIO_FIDELITIES:
        manager.apply_settings({"audioFidelity": fidelity})
        assert manager.cue_path("credits-theme") == asset_dir() / "audio" / fidelity / "music" / "credits-theme.ogg"
    manager.update(scene="action", in_combat=False, settings={}, cues=("jump", "missing"))


def test_make_it_come_alive_is_reserved_for_credits():
    manager = AudioManager(enabled=False)
    assert manager._desired_music("action", in_combat=False) is None
    assert manager._desired_music("installer", in_combat=False) is None
    assert manager._desired_music("turn", in_combat=True) is None
    assert manager._desired_music("ending", in_combat=False) == "credits-theme"
    assert manager._desired_music("chapter-credits", in_combat=False) == "credits-roll"
    assert manager._desired_music("credits", in_combat=False) == "credits-roll"


def test_omarchy_oligarchy_reference_is_not_a_runtime_cue():
    # The optional reference master stays local pending redistribution rights;
    # public checkouts must build and test without it.
    assert "omarchy-oligarchy" not in json.loads(
        (asset_dir() / "audio" / "audio-manifest.json").read_text(encoding="utf-8")
    )["cues"]
    assert "oligarchy" in chapter_by_id("walled-garden").events


def test_missing_selected_tier_falls_back_without_stopping_play(tmp_path):
    ultra = tmp_path / "ultra.ogg"
    ultra.write_bytes(b"OggS fallback")
    (tmp_path / "audio-manifest.json").write_text(
        json.dumps(
            {
                "cues": {
                    "jump": {
                        "kind": "sfx",
                        "files": {"sixteen-bit": "missing.ogg", "ultra": "ultra.ogg"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    manager = AudioManager(tmp_path, enabled=False)
    manager.apply_settings({"audioFidelity": "sixteen-bit"})
    assert manager.cue_path("jump") == ultra


def test_no_audio_device_fails_silently(monkeypatch):
    pygame.mixer.quit()

    def unavailable(*args, **kwargs):
        raise pygame.error("no device")

    monkeypatch.setattr(pygame.mixer, "init", unavailable)
    manager = AudioManager()
    assert manager.available is False
    manager.update(scene="action", in_combat=False, settings={}, cues=("jump",))
