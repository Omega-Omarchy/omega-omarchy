from __future__ import annotations

from dataclasses import replace

from omega_omarchy.physics import InputState, TILE, spawn_body
from omega_omarchy.sim import GameSim


def workshop() -> GameSim:
    sim = GameSim.from_play_now()
    tiles = ["." * 30 for _ in range(12)] + ["....S....................X....", "#" * 30]
    sim.tiles = tiles
    sim.original_tiles = list(tiles)
    sim.chapter_map_tiles = [tiles]
    sim.chapter_map_originals = [list(tiles)]
    sim.chapter_map_upper = [{}]
    sim.entities = []
    sim.map_index = 0
    sim.world.chapters[0] = {**sim.chapter, "tiles": tiles, "width": 30, "height": 14}
    sim.body = spawn_body(tiles)
    sim.cam_x, sim.cam_y = 0, 48
    sim._begin_flight()
    sim._enter_edit()
    return sim


def connect_goal(sim: GameSim) -> None:
    gx, gy = sim.edit_reward
    sim.edit_ops = [{"op": "place", "x": gx, "y": y, "tile": "L"} for y in range(gy, 13)]
    assert sim._refresh_edit_preview()


def test_enter_and_cancel_do_not_change_terrain_or_leave_a_free_cache():
    sim = workshop()
    assert sim.edit_reward is not None
    assert sim.tiles == sim.original_tiles
    assert not sim.edit_goal_ready
    original = list(sim.tiles)
    sim._step_edit(InputState(interact=True))
    assert sim.tiles == original
    assert not any(e.alive and e.extra.get("edit_reward") for e in sim.entities)
    assert sim.scene == "flight" and sim.flight_direction == "in"


def test_route_forecast_updates_after_edits_and_reset_without_awarding_points():
    sim = workshop()
    before = sim.score
    connect_goal(sim)
    assert sim.edit_goal_ready and sim.edit_reward in sim.edit_new_reachable
    assert sim.score == before
    sim._step_edit(InputState(customize=True))
    assert not sim.edit_goal_ready and not sim.edit_new_reachable
    assert sim.score == before


def test_empty_seal_cannot_farm_points_or_stage_rewards():
    sim = workshop()
    before = sim.score
    sim._seal_edit()
    assert sim.score == before
    assert not any(e.alive and e.extra.get("edit_reward") for e in sim.entities)


def test_free_build_fallback_recognizes_a_new_connected_landing():
    sim = workshop()
    sim._finish_edit_reward(sealed=False)
    sim._refresh_edit_routes()
    assert not sim.edit_goal_ready
    sim.edit_ops = [{"op": "place", "x": 9, "y": 10, "tile": "="}]
    assert sim._refresh_edit_preview() and sim.edit_goal_ready
    sim._step_edit(InputState(interact=True))
    assert not sim.edit_goal_ready


def test_sealed_cache_pays_out_only_when_collected_and_only_once():
    sim = workshop()
    connect_goal(sim)
    before = sim.score
    sim._seal_edit()
    assert sim.scene == "flight", sim.messages[-1]
    assert sim.score == before + 500
    reward = next(e for e in sim.entities if e.alive and e.extra.get("edit_reward"))
    assert reward.extra.get("edit_route_bonus") and not reward.extra.get("edit_pending")
    sim.scene = "action"
    sim.flight_ticks = 0
    sim.body = replace(sim.body, x=reward.x * TILE, y=reward.y * TILE, vx=0, vy=0)
    sim.step(InputState())
    assert not reward.alive
    assert sim.score >= before + 850
    assert any("Your route paid off" in message for message in sim.messages)
    collected = sim.score
    sim.step(InputState())
    assert sim.score == collected


def test_entry_preserves_changes_already_made_during_play():
    sim = workshop()
    sim._step_edit(InputState(interact=True))
    row = list(sim.tiles[11]); row[20] = "="; sim.tiles[11] = "".join(row)
    before = list(sim.tiles)
    sim._enter_edit()
    sim._step_edit(InputState(interact=True))
    assert sim.tiles == before and sim.original_tiles == before


def test_generated_workshop_route_can_be_walked_and_climbed_in_actual_physics():
    sim = GameSim.from_play_now(seed="omega-fixture-1")
    # The earlier cache objective remains supported for maps without a skyway.
    sim.chapter_map_upper = [{}]
    sim._begin_flight()
    sim._enter_edit()
    assert sim.edit_reward is not None
    gx, gy = sim.edit_reward
    sim.edit_ops = [{"op": "place", "x": gx, "y": y, "tile": "L"} for y in range(gy, sim.edit_start[1] + 1)]
    assert sim._refresh_edit_preview() and sim.edit_goal_ready
    sim._seal_edit()
    reward = next(e for e in sim.entities if e.extra.get("edit_route_bonus"))
    for _ in range(240):
        if sim.scene == "flight":
            sim.step(InputState())
            continue
        right = sim.body.center[0] < gx * TILE + 4
        sim.step(InputState(right=right, up=not right))
        if not reward.alive:
            break
    assert not reward.alive, "the forecasted fixture route must work with normal movement and climbing"


def test_sealed_cache_survives_save_reload_but_a_collected_cache_does_not(tmp_path):
    sim = GameSim.from_play_now(seed="omega-fixture-1")
    sim.chapter_map_upper = [{}]
    sim._begin_flight(); sim._enter_edit()
    gx, gy = sim.edit_reward
    sim.edit_ops = [{"op": "place", "x": gx, "y": y, "tile": "L"} for y in range(gy, sim.edit_start[1] + 1)]
    assert sim._refresh_edit_preview()
    sim._seal_edit()
    sim.save_path = tmp_path / "workshop.json"
    sim.save_to_disk()
    sim.load_from_disk()
    reward = next(e for e in sim.entities if e.alive and e.extra.get("edit_route_bonus"))
    assert (reward.x, reward.y) == (gx, gy)
    reward.alive = False
    sim.save_to_disk(); sim.load_from_disk()
    assert not any(e.alive and e.extra.get("edit_reward") for e in sim.entities)
