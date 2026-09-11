from dataclasses import replace

import pytest

from omega_omarchy.generation import generate_world
from omega_omarchy.physics import Body, InputState, TILE, step_body
from omega_omarchy.reachability import find_spawn, reachable_from
from omega_omarchy.sim import GameSim, NETWORK_TICKS
from omega_omarchy.skyway import SKYWAY_BARRIER, arena_descent_clearance, upper_route_report


@pytest.fixture(scope="module", params=["omega-fixture-1", "skyway-b", "skyway-c"])
def world(request):
    return generate_world(request.param, force_logo=True)


def test_every_chapter_and_island_has_a_locked_connected_upper_route(world):
    for chapter in world.chapters:
        for spec in [chapter, *chapter["maps"]]:
            tiles, upper = spec["tiles"], spec["upperTraversal"]
            assert set(tiles[SKYWAY_BARRIER]) == {"K"}
            assert not upper["unlocked"] and not upper["lifts"]
            assert upper_route_report(tiles, upper)["ok"]
            assert len(upper["entries"]) >= (4 if upper["endX"] >= 50 else 1)
            assert upper["decks"][-1]["x"] + upper["decks"][-1]["width"] <= upper["endX"]
            if upper["bossGateX"] is not None:
                assert upper["endX"] <= upper["bossGateX"] - arena_descent_clearance(len(tiles))
                assert all(set(row[upper["endX"]:]) == {"."} for row in tiles[:SKYWAY_BARRIER])
            start = find_spawn(tiles) if any("S" in row for row in tiles) else (int(spec["portals"][0]["x"]), int(spec["portals"][0]["y"]))
            reached = reachable_from(tiles, start)
            assert not any(y < SKYWAY_BARRIER for x, y in reached)
            assert any("O" in row for row in tiles[SKYWAY_BARRIER + 1:])
            assert all((x, y) in reached for y, row in enumerate(tiles) for x, cell in enumerate(row) if cell == "O")
            shapes = [deck["shape"] for deck in upper["decks"]]
            assert all(a != b for a, b in zip(shapes, shapes[1:]))


def test_invisible_platforms_concentrate_in_walled_garden(world):
    counts = {c["chapterId"]: sum(row.count("I") for row in c["tiles"]) for c in world.chapters}
    assert counts["walled-garden"] >= 30
    assert counts["walled-garden"] > sum(count for name, count in counts.items() if name != "walled-garden")
    garden = next(c for c in world.chapters if c["chapterId"] == "walled-garden")
    assert any("I" in row for row in garden["tiles"][SKYWAY_BARRIER + 1:])
    assert garden["reachability"]["bossReachableWithoutRare"]


def test_final_skyway_cannot_jump_into_arena_before_landing(world):
    # Remove intervening terrain: even the longest unobstructed descent must
    # land before the gate, including an air jump at any point in the fall.
    for chapter in world.chapters:
        tiles, upper = chapter["tiles"], chapter["upperTraversal"]
        width, floor = len(tiles[0]), len(tiles) - 4
        empty = ["." * width for _ in range(floor)] + ["#" * width] * 4
        for air_jump_tick in range(1, 260, 5):
            body = Body((upper["endX"] - 1) * TILE + 6, 8 * TILE - 18,
                        4.35, 0, True, 7, 0, 1)
            for tick in range(400):
                body = step_body(body, InputState(right=True, jump_pressed=tick in {0, air_jump_tick}), empty)
                assert body.x + 12 < upper["bossGateX"] * TILE
                if tick > 0 and body.on_ground:
                    break
            assert body.on_ground


def test_skyway_deck_gaps_cross_with_ordinary_physics(world):
    for chapter in world.chapters:
        for spec in [chapter, *chapter["maps"]]:
            for left, right in zip(spec["upperTraversal"]["decks"], spec["upperTraversal"]["decks"][1:]):
                body = Body((left["x"] + left["width"] - 1) * TILE + 3,
                            left["y"] * TILE - 18, 2.15, 0, True, 7, 0, 1)
                landed = False
                for tick in range(65):
                    body = step_body(body, InputState(right=True, jump_pressed=tick == 0), spec["tiles"])
                    if tick > 2 and body.on_ground and body.x >= right["x"] * TILE:
                        landed = body.feet[1] <= right["y"] * TILE + 1
                        break
                assert landed, (chapter["chapterId"], left, right, body)


def enter_workshop(sim):
    sim._begin_flight(); sim._enter_edit()
    x, y = sim.edit_start
    column = x + 6
    sim.edit_ops = [{"op": "place", "x": column, "y": yy, "tile": "L"} for yy in range(y - 4, y + 1)]
    assert sim._refresh_edit_preview() and sim.edit_goal_ready
    return column


def test_only_a_sealed_connected_edit_builds_a_two_way_lift_and_it_survives_reload(tmp_path):
    sim = GameSim.from_play_now()
    column = enter_workshop(sim)
    assert not sim.active_upper_route["unlocked"]
    sim._step_edit(InputState(customize=True))
    sim._seal_edit()
    assert not sim.active_upper_route["unlocked"]
    column = enter_workshop(sim)
    sim._seal_edit()
    assert sim.active_upper_route["unlocked"]
    pair = [e for e in sim.entities if e.extra.get("skyway")]
    assert len(pair) == 2
    lower = max(pair, key=lambda e: e.y)
    # Use ordinary movement and climbing to reach the constructed lift.
    for _ in range(240):
        if sim.scene == "flight":
            sim.step(InputState()); continue
        if sim.scene == "network":
            break
        right = sim.body.center[0] < column * TILE + 4
        sim.step(InputState(right=right, up=not right, up_pressed=not right))
    assert sim.scene == "network", (sim.body, lower, sim.messages[-3:])
    for _ in range(NETWORK_TICKS):
        sim.step(InputState())
    assert sim.body.feet[1] < SKYWAY_BARRIER * TILE
    assert not sim.network_armed, "standing on the arrival lift must not bounce back"
    upper = min(pair, key=lambda e: e.y)
    for _ in range(20):
        sim.step(InputState(right=True))
    assert sim.network_armed
    sim.network_armed = True
    sim._begin_network_transition(upper)
    for _ in range(NETWORK_TICKS):
        sim.step(InputState())
    assert sim._tile_under_player() == (lower.x, lower.y)
    sim.save_path = tmp_path / "skyway.json"
    sim.save_to_disk(); sim.load_from_disk()
    assert sim.active_upper_route["unlocked"]
    assert len([e for e in sim.entities if e.extra.get("skyway")]) == 2
    assert sim.skyway_reserved_cells()


def test_disconnected_edits_and_cannon_launches_cannot_open_the_seal():
    sim = GameSim.from_play_now()
    sim._begin_flight(); sim._enter_edit()
    x, y = sim.edit_start
    sim.edit_ops = [{"op": "place", "x": x + 8, "y": y - 8, "tile": "="}]
    assert sim._refresh_edit_preview() and not sim.edit_goal_ready
    sim._seal_edit()
    assert not sim.active_upper_route["unlocked"]
    sim.body = replace(sim.body, x=80, y=(SKYWAY_BARRIER + 1) * TILE + 3, vx=0, vy=-60)
    sim.cannon_launch_active = True
    sim._cannon_break_path()
    assert set(sim.tiles[SKYWAY_BARRIER]) == {"K"}
    body = step_body(sim.body, InputState(), sim.tiles, ballistic=True)
    assert body.y >= (SKYWAY_BARRIER + 1) * TILE
    phased = step_body(sim.body, InputState(), sim.tiles, ballistic=True, phase_solids=True)
    assert phased.y >= (SKYWAY_BARRIER + 1) * TILE
    falling = replace(sim.body, y=(SKYWAY_BARRIER - 1) * TILE, vy=40, on_ground=False)
    falling = step_body(falling, InputState(), sim.tiles, ballistic=True)
    for _ in range(10):
        falling = step_body(falling, InputState(), sim.tiles, ballistic=True)
    assert falling.y > (SKYWAY_BARRIER + 1) * TILE


def test_secret_map_has_a_workshop_and_recoverable_upper_tier(tmp_path):
    sim = GameSim.from_play_now()
    sim.dev_warp("cow")
    assert sim.active_upper_route
    assert upper_route_report(sim.tiles, sim.active_upper_route)["ok"]
    assert any("O" in row for row in sim.tiles)
    # The spawn-side construction also checks sealing an ephemeral map,
    # which is absent from the chapter's ordinary maps array.
    enter_workshop(sim); sim._seal_edit()
    assert sim.active_upper_route["unlocked"]
    sim.save_path = tmp_path / "cow-skyway.json"
    sim.save_to_disk(); sim.load_from_disk()
    assert sim.map_index == sim.secret_map_index
    assert sim.active_upper_route["unlocked"]
    assert len([e for e in sim.entities if e.extra.get("skyway")]) == 2
