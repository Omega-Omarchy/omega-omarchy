"""Ordinary-input first-chapter playthrough. No private skips."""

import pytest

from omega_omarchy.physics import TILE, InputState
from omega_omarchy.sim import (
    LEVEL_INTRO_TICKS,
    PROLOGUE_SKIP_HOLD_TICKS,
    STAGE_MAP_INPUT_LOCK_TICKS,
    GameSim,
)


def _confirm(sim: GameSim) -> None:
    sim.step(InputState(jump_pressed=True))


def _gap_ahead(sim: GameSim) -> bool:
    if sim.body is None or not sim.tiles:
        return False
    tx = int((sim.body.x + sim.body.width / 2) // TILE)
    feet = int((sim.body.y + sim.body.height + 1) // TILE)
    height = len(sim.tiles)
    width = len(sim.tiles[0])
    for dx in (1, 2, 3):
        col = tx + dx
        if col >= width:
            return False
        support = False
        for row in (feet, feet - 1, min(height - 1, feet + 1)):
            if 0 <= row < height and sim.tiles[row][col] in {"#", "=", "B"}:
                support = True
                break
        if not support:
            return True
    return False


@pytest.mark.parametrize("seed", ["omega-fixture-1", "chapter-design-a", "chapter-design-b"])
def test_ordinary_keys_from_greeter_to_chapter_one_completion(seed):
    sim = GameSim.new(seed)
    assert sim.scene == "installer"
    assert sim.installer.step == "greeter"
    _confirm(sim)

    visited = []
    guard = 0
    while sim.scene == "installer" and sim.installer.step != "complete" and guard < 32:
        guard += 1
        visited.append(sim.installer.step)
        if sim.installer.step == "quality":
            sim.step(InputState(down_pressed=True))
        if sim.installer.step == "limitless":
            sim.step(InputState(down_pressed=True))
        _confirm(sim)
    assert sim.installer.step == "complete"
    assert sim.scene == "installer"
    assert sim.installer.choices.limitless_enabled is True
    sim.step(InputState())
    _confirm(sim)

    assert sim.scene == "prologue"
    for _ in range(PROLOGUE_SKIP_HOLD_TICKS):
        sim.step(InputState(turn=True))
    assert sim.scene == "stage-map"
    for _ in range(STAGE_MAP_INPUT_LOCK_TICKS):
        sim.step(InputState())
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "level-intro"
    for _ in range(LEVEL_INTRO_TICKS):
        sim.step(InputState())
    assert sim.scene == "action"
    assert sim.world is not None
    assert sim.settings.get("limitlessEnabled") is True
    assert sim.quality == sim.installer.choices.quality
    assert "quality" in visited and "character" in visited and "sharing" in visited
    assert sim.messages[0] == "The installer finished. The world did not."
    assert all("Play Now" not in message for message in sim.messages)

    sim.step(InputState(customize=True))
    assert sim.scene == "customize"
    sim.step(InputState(jump_pressed=True))
    assert sim.limitless_receipt is not None
    assert sim.limitless_receipt.get("treatment") in {"exact-adoption", "method-guided", "abstain", "offline-fresh"}
    sim.step(InputState(interact=True))
    assert sim.scene == "action"

    for tick in range(20000):
        if sim.scene == "chapter-complete" or sim.chapter_index > 0:
            break
        if sim.scene == "flight":
            sim.step(InputState())
            continue
        if sim.scene == "edit":
            sim.step(InputState(interact=True))
            continue
        if sim.combat is not None and sim.scene == "action":
            if sim.combat.foe_ready_to_recruit:
                sim.step(InputState(turn_pressed=True))
            else:
                sim.step(InputState(action_pressed=True))
            continue
        if sim.scene == "turn":
            if sim.combat is None:
                continue
            if sim.battle_queue or sim.battle_delay_ticks:
                sim.step(InputState())
                continue
            if sim.combat.foe_ready_to_recruit:
                sim.step(InputState(interact=True))
            else:
                sim.step(InputState(jump_pressed=True))
            continue
        hop = bool(sim.body and (not sim.body.on_ground or _gap_ahead(sim) or tick % 18 == 0))
        sim.step(InputState(right=True, jump=hop, jump_pressed=hop))

    assert sim.scene == "chapter-complete", "first boss must end the release-qualified chapter"
    assert sim.chapter_index == 0, "Chapter 2 must require an explicit development-build opt-in"
    assert sim.pending_chapter == 1
    assert "package-bureaucrat" in sim.converted or "provenance-pass" in sim.converted
    assert all("Play Now" not in message for message in sim.messages)
