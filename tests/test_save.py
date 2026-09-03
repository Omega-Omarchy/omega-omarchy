import json
from pathlib import Path

import pytest

from omega_omarchy.generation import generate_world
from omega_omarchy.physics import InputState
from omega_omarchy.save import SaveError, make_save, read_save, reroll_progress, validate_save, write_save
from omega_omarchy.sim import BOSS_FIELD_HEALTH, STARTING_INVENTORY, GameSim


class BrowserStorage:
    def __init__(self):
        self.values: dict[str, str] = {}

    def setItem(self, key: str, value: str) -> None:
        self.values[key] = value

    def getItem(self, key: str) -> str | None:
        return self.values.get(key)


def test_save_load_round_trip(tmp_path: Path):
    sim = GameSim.from_play_now("omega-fixture-1")
    sim.player_bs = 42
    record = sim.save_record()
    path = tmp_path / "slot.json"
    write_save(path, record)
    loaded = read_save(path)
    assert loaded["worldDigest"] == sim.identity_digest
    assert loaded["progress"]["penguins"] == sim.penguins
    assert loaded["progress"]["playerBS"] == 42


def test_browser_save_round_trip_uses_namespaced_local_storage(tmp_path: Path, monkeypatch):
    import omega_omarchy.save as save_module

    storage = BrowserStorage()
    monkeypatch.setattr(save_module, "_browser_storage", lambda: storage)
    sim = GameSim.from_play_now("omega-fixture-1")
    path = tmp_path / "slot.json"
    write_save(path, sim.save_record())

    assert list(storage.values) == ["omega-omarchy.file.v1.slot.json"]
    assert not path.exists()
    assert read_save(path)["worldDigest"] == sim.identity_digest


def test_tampered_save_is_rejected(tmp_path: Path):
    world = generate_world("omega-fixture-1", force_logo=True)
    record = make_save(world.to_record(), {"penguins": 3})
    record["progress"]["penguins"] = 99
    with pytest.raises(SaveError):
        validate_save(record)


def test_goliath_phase_and_remaining_proxy_survive_save_restore(tmp_path: Path):
    sim = GameSim.from_play_now("omega-fixture-1")
    sim.dev_warp("goliath-amalgam:boss-15")
    boss = next(entity for entity in sim.entities if entity.kind == "boss")
    sim._damage_side_enemy(boss, BOSS_FIELD_HEALTH)
    sim._damage_side_enemy(boss, BOSS_FIELD_HEALTH)
    first_proxy = next(entity for entity in sim.entities if entity.extra.get("goliath_minion"))
    sim._damage_side_enemy(first_proxy, 5)
    assert sim.goliath_stage == "minions"
    assert sim.goliath_minions_defeated == 1

    sim.save_path = tmp_path / "goliath.json"
    sim.save_to_disk()
    restored = GameSim.from_play_now("temporary-loader-world")
    restored.save_path = sim.save_path
    restored.load_from_disk()

    assert restored.goliath_stage == "minions"
    assert restored.goliath_minions_defeated == 1
    assert len(
        [entity for entity in restored.entities if entity.extra.get("goliath_minion")]
    ) == 1


def test_reroll_archives_world_and_keeps_character():
    previous = {
        "character": {"name": "Ada"},
        "settings": {"quality": "crt"},
        "identity": {"seed": "old"},
        "chapters": [1],
        "penguins": 4,
        "sharePolicy": "local-only",
        "convertedCapabilities": ["gate-key"],
    }
    retain, archive = reroll_progress(previous)
    assert retain["character"]["name"] == "Ada"
    assert retain["convertedCapabilities"] == ["gate-key"]
    assert retain["currentChapter"] == "corrupted-install"
    assert "chapters" in archive
    assert "chapters" not in retain or retain.get("chapters") is None


def test_pause_reroll_requires_confirmation_archives_old_world_and_resets_progress(tmp_path: Path):
    sim = GameSim.from_play_now("omega-fixture-1")
    sim.save_path = tmp_path / "slot.json"
    assert sim.world is not None
    old_digest = sim.identity_digest
    old_tiles = sim.world.chapters[0]["tiles"]
    old_character = dict(sim.world.character)
    sim.set_presentation(fidelity="high", display="crt")
    sim.accessibility.remap("jump", "Q")
    sim.accessibility.remap("item", "Button 10", device="gamepad")
    sim._sync_accessibility()
    sim.converted = ["provenance-pass", "package-bureaucrat"]
    sim.inventory.append("checksum-key")
    sim.score = 900
    sim.player_bs = 73
    sim.penguins = 4
    sim.scene = "pause"
    sim.pause_cursor = sim.pause_rows().index("reroll")

    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "reroll-confirm"
    assert not sim.reroll_confirm_yes
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "pause"
    assert sim.identity_digest == old_digest

    sim.step(InputState(jump_pressed=True))
    sim.step(InputState(right_pressed=True))
    assert sim.reroll_confirm_yes
    sim.step(InputState(jump_pressed=True))

    assert sim.scene == "action"
    assert sim.world is not None
    assert sim.world.identity.seed == "omega-fixture-1-reroll-1"
    assert sim.identity_digest != old_digest
    assert sim.world.chapters[0]["tiles"] != old_tiles
    assert sim.world.character == old_character
    assert sim.fidelity == "high" and sim.display == "crt"
    assert sim.accessibility.keyboard["jump"] == "Q"
    assert sim.accessibility.gamepad["item"] == "Button 10"
    assert sim.converted == ["provenance-pass"]
    assert sim.inventory == list(STARTING_INVENTORY)
    assert sim.score == 0 and sim.player_bs == 0 and sim.penguins == 0
    assert sim.rerolls == 1 and sim.reroll_root_seed == "omega-fixture-1"
    assert sim.last_archive_path is not None and sim.last_archive_path.is_file()
    archived = read_save(sim.last_archive_path)
    assert archived["worldDigest"] == old_digest
    assert archived["progress"]["nextSeed"] == "omega-fixture-1-reroll-1"

    sim.save_to_disk()
    restored = GameSim.from_play_now("temporary-loader-world")
    restored.save_path = sim.save_path
    restored.load_from_disk()
    assert restored.world is not None
    assert restored.world.identity.seed == "omega-fixture-1-reroll-1"
    assert restored.rerolls == 1
    assert restored.reroll_root_seed == "omega-fixture-1"
    assert restored.fidelity == "high" and restored.display == "crt"
    assert restored.accessibility.keyboard["jump"] == "Q"
    assert restored.accessibility.gamepad["item"] == "Button 10"
    restored.scene = "pause"
    restored.pause_cursor = restored.pause_rows().index("reroll")
    restored.step(InputState(jump_pressed=True))
    restored.step(InputState(right_pressed=True))
    restored.step(InputState(jump_pressed=True))
    assert restored.world.identity.seed == "omega-fixture-1-reroll-2"
    assert restored.rerolls == 2


def test_reroll_archive_failure_leaves_current_world_untouched(tmp_path: Path, monkeypatch):
    import omega_omarchy.sim as sim_module

    sim = GameSim.from_play_now("omega-fixture-1")
    sim.save_path = tmp_path / "slot.json"
    old_world = sim.world
    old_digest = sim.identity_digest
    sim.scene = "reroll-confirm"
    sim.reroll_confirm_yes = True

    def fail_write(path, record):
        raise OSError("read-only test archive")

    monkeypatch.setattr(sim_module, "write_save", fail_write)
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "reroll-confirm"
    assert sim.world is old_world
    assert sim.identity_digest == old_digest
    assert "failed closed" in sim.messages[-1].lower()
