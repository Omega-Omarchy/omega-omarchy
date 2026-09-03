from __future__ import annotations

import os
from dataclasses import replace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.combat import make_foe
from omega_omarchy.physics import InputState, TILE
from omega_omarchy.presentation import apply_presentation
from omega_omarchy.render import (
    BOSS_WORLD_HEIGHT,
    ENEMY_WORLD_HEIGHT,
    PROLOGUE_DOOR_END_SCALE,
    PROLOGUE_MIND_BRAIN,
    PROLOGUE_MIND_HERO_ANGLE,
    PROLOGUE_MIND_HERO_FEET_Y,
    PROLOGUE_MIND_HERO_HEIGHT,
    PROLOGUE_MIND_HERO_X,
    SLIDE_WORLD_DROP,
    Renderer,
    background_parallax_y,
    foreground_parallax_y,
)
from omega_omarchy.sim import (
    BATTLE_INTER_ACTION_TICKS,
    PROLOGUE_LOGIN_FLASH_HOLD_TICKS,
    PROLOGUE_LOGIN_FLASH_IN_TICKS,
    RARE_BS_RESET_ITEM,
    Entity,
    GameSim,
)


def _drain_battle_timeline(sim: GameSim, limit: int = 240) -> list[str]:
    actors: list[str] = []
    for _ in range(limit):
        if sim.battle_actor and (not actors or actors[-1] != sim.battle_actor):
            actors.append(sim.battle_actor)
        if not sim.battle_queue and sim.battle_delay_ticks == 0:
            break
        sim.step(InputState())
    return actors


def test_side_item_is_a_projectile_and_awards_score_on_conversion():
    sim = GameSim.from_play_now()
    assert sim.body is not None
    cx, cy = sim.body.center
    target = Entity(
        "enemy",
        int((cx + 42) // TILE),
        int(cy // TILE),
        extra={"hp": 2, "variant": "hydra-node", "home": int((cx + 42) // TILE), "dir": 1},
    )
    sim.entities = [target]
    before = sim.inventory.count("logic-bomb")
    sim._use_side_item()
    assert sim.projectiles
    assert sim.projectiles[0]["y"] < cy - 2
    assert sim.inventory.count("logic-bomb") == before - 1
    for _ in range(20):
        sim._tick_projectiles()
        if target.extra.get("converted"):
            break
    assert target.extra.get("converted") is not True
    assert target.extra["hp"] > 0, "starting strength is deliberately just under the old baseline"
    sim.item_strength = 100
    sim.attack_timer = 0
    sim.action_reset_ticks = 0
    sim._use_side_item()
    for _ in range(20):
        sim._tick_projectiles()
        if target.extra.get("converted"):
            break
    assert target.extra.get("converted") is True
    assert sim.score >= 250


def test_pause_exposes_item_and_attack_loadout_selection():
    sim = GameSim.from_play_now()
    sim.scene = "pause"
    sim.paused_from = "action"
    sim.pause_cursor = 2
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "items"
    sim.step(InputState(down_pressed=True))
    assert sim.item_menu_row == 1
    sim.step(InputState(right_pressed=True))
    sim.step(InputState(jump_pressed=True))
    assert sim.current_attack == "patch-strike"
    sim.step(InputState(interact=True))
    assert sim.scene == "pause"


def test_new_sessions_default_to_ultra_and_crt_exposes_independent_controls():
    sim = GameSim.from_play_now()
    assert sim.fidelity == "ultra"
    assert sim.quality == "ultra"
    sim.set_presentation(display="crt")
    assert sim.pause_rows() == (
        "fidelity",
        "display",
        "scanlines",
        "curvature",
        "phosphor",
        "items",
        "controls",
        "reroll",
        "omega-code",
    )
    sim.scene = "pause"
    before_scanline = float(sim.settings["crt"]["scanline"])
    before_curve = float(sim.settings["crt"]["curvatureControl"])
    sim.pause_cursor = 2
    sim.step(InputState(right_pressed=True))
    assert float(sim.settings["crt"]["scanline"]) > before_scanline
    assert float(sim.settings["crt"]["curvatureControl"]) == before_curve
    sim.pause_cursor = 3
    sim.step(InputState(right_pressed=True))
    assert float(sim.settings["crt"]["curvatureControl"]) > before_curve
    assert float(sim.settings["crt"]["scanline"]) > before_scanline


def test_curvature_uses_cached_banded_geometry_not_full_frame_index_maps():
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    renderer._vs = 3
    source = pygame.Surface((960, 540))
    source.fill((40, 80, 160))
    curved = renderer._curve(source, 0.5)
    assert curved.get_size() == source.get_size()
    assert len(renderer._curve_cache) == 1
    geometry = next(iter(renderer._curve_cache.values()))
    assert isinstance(geometry, tuple)
    assert len(geometry) <= source.get_height() // 2
    assert all(len(band) == 3 for band in geometry)
    pygame.quit()


def test_legacy_paired_crt_control_migrates_to_independent_controls():
    migrated = apply_presentation(
        {
            "quality": "ultra",
            "display": "crt",
            "crt": {"intensity": 0.35, "phosphor": 0.2},
        }
    )
    assert migrated["crt"]["scanline"] == 0.35
    assert migrated["crt"]["curvatureControl"] == 0.35
    assert migrated["crt"]["phosphor"] == 0.2


def test_new_enemy_roster_replaces_boss_derivatives_and_supports_special_behaviors():
    sim = GameSim.from_play_now()
    seen = set()
    assert sim.world is not None
    for chapter_index in range(len(sim.world.chapters)):
        sim._load_chapter(chapter_index)
        seen.update(str(entity.extra.get("variant")) for entity in sim.entities if entity.kind == "enemy")
    assert {"justice-signaler", "consensus-crier", "packet-wasp", "lint-launcher"} <= seen
    assert not seen.intersection({"bureaucrat-drone", "hydra-node", "goliath-fragment"})

    assert sim.body is not None
    tx = int(sim.body.center[0] // TILE) + 3
    ty = int(sim.body.center[1] // TILE)
    shooter = Entity(
        "enemy",
        tx,
        ty,
        extra={"variant": "consensus-crier", "behavior": "shoot", "cooldown": 1, "hp": 2},
    )
    sim.entities = [shooter]
    sim._tick_enemy_behaviors()
    assert sim.enemy_projectiles


def test_tool_pickup_status_uses_the_actual_tool_name():
    sim = GameSim.from_play_now()
    assert sim.body is not None
    tx = int((sim.body.x + sim.body.width / 2) // TILE)
    ty = int((sim.body.y + 4) // TILE)
    sim.entities = [Entity("item", tx, ty, extra={"item": "patch-cable"})]
    sim.step(InputState())
    assert "patch cable recovered" in sim.messages[-1].lower()


def test_crt_persistence_resets_across_fidelity_frame_sizes():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    renderer = Renderer()
    sizes = []
    for fidelity in ("sixteen-bit", "high", "ultra"):
        sim.set_presentation(fidelity=fidelity, display="crt")
        sizes.append(renderer.frame(sim).get_size())
    assert sizes == [(320, 180), (640, 360), (960, 540)]
    pygame.quit()


def test_crt_bloom_preserves_color_balance_without_rgb_tint_shift():
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    renderer._vs = 1
    source = pygame.Surface((64, 64))
    source.fill((40, 80, 160))
    out = renderer._crt(
        source,
        {"persistence": 0.0, "bloom": 0.1, "scanlines": 0.001, "noise": 0.001, "vignette": 0.001},
    )
    r, g, b, _ = out.get_at((32, 31))
    assert b > g > r
    assert r / b < 0.45
    pygame.quit()


def test_event_and_rpg_scenes_do_not_cache_traversal_sprite():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim.set_presentation(fidelity="high", display="clean")
    renderer = Renderer()
    sim._enter_edit()
    renderer.frame(sim)
    assert not any("side-idle" in key for key in renderer.cache)
    assert any("david_ots" in key for key in renderer.cache)
    renderer.cache.clear()
    sim.editing = False
    sim.scene = "action"
    sim._begin_combat(Entity("boss", 1, 1, extra={"boss": "package-bureaucrat"}), boss=True)
    renderer.frame(sim)
    assert not any("side-idle" in key for key in renderer.cache)
    assert any("david_battle" in key for key in renderer.cache)
    pygame.quit()


def test_prologue_capture_and_transfer_use_scene_specific_character_art():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim.scene = "prologue"
    renderer = Renderer()
    sim.story_beat = 2
    renderer.frame(sim)
    assert "fidelity/ultra/characters/david_prologue-captured.png" in renderer.cache
    renderer.cache.clear()
    sim.story_beat = 4
    renderer.frame(sim)
    assert "fidelity/ultra/characters/david_prologue-transfer.png" in renderer.cache
    assert not any("side-idle" in key for key in renderer.cache)
    renderer.cache.clear()
    sim.story_beat = 6
    sim.story_ticks = 90
    first_transit = renderer.frame(sim)
    assert "fidelity/ultra/ui/prologue-rift.png" in renderer.cache
    assert not any("characters/" in key for key in renderer.cache)
    sim.story_ticks = 91
    second_transit = renderer.frame(sim)
    assert pygame.image.tobytes(first_transit, "RGBA") != pygame.image.tobytes(second_transit, "RGBA")
    renderer.cache.clear()
    sim.story_beat = 7
    sim.story_ticks = 120
    renderer.frame(sim)
    assert "fidelity/ultra/ui/stage-world-map.png" not in renderer.cache
    sim.story_ticks = len(sim.story_copy) * 2
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "prologue"
    assert sim.story_transition_ticks == 1
    submitted = renderer.frame(sim)
    assert "fidelity/ultra/ui/stage-world-map.png" not in renderer.cache
    sim.story_transition_ticks = PROLOGUE_LOGIN_FLASH_IN_TICKS
    whiteout = renderer.frame(sim)
    assert tuple(whiteout.get_at((1, 1))[:3]) == (255, 255, 255)
    sim.story_transition_ticks += PROLOGUE_LOGIN_FLASH_HOLD_TICKS + 1
    renderer.frame(sim)
    assert "fidelity/ultra/ui/stage-world-map.png" in renderer.cache
    assert pygame.image.tobytes(submitted, "RGBA") != pygame.image.tobytes(whiteout, "RGBA")
    pygame.quit()


def test_both_mind_machine_beats_share_the_corrected_table_alignment():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim.scene = "prologue"
    renderer = Renderer()
    hero_calls: list[tuple[object, ...]] = []
    wave_calls: list[dict[str, object]] = []
    renderer._prologue_hero = lambda *args, **kwargs: hero_calls.append((*args[2:], kwargs))
    renderer._prologue_mind_waves = lambda *args, **kwargs: wave_calls.append(kwargs)
    for beat in (4, 5):
        sim.story_beat = beat
        renderer.frame(sim)
    assert len(hero_calls) == 2 and len(wave_calls) == 2
    for call in hero_calls:
        assert call[:5] == (
            "prologue-transfer",
            PROLOGUE_MIND_HERO_X,
            PROLOGUE_MIND_HERO_FEET_Y,
            PROLOGUE_MIND_HERO_HEIGHT,
            {"angle": PROLOGUE_MIND_HERO_ANGLE},
        )
    assert all(call["brain"] == PROLOGUE_MIND_BRAIN for call in wave_calls)
    assert PROLOGUE_MIND_HERO_X < 172 and PROLOGUE_MIND_HERO_ANGLE < -5.0
    pygame.quit()


def test_doorway_recession_preserves_continuity_then_finishes_25_percent_smaller():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim.scene = "prologue"
    sim.story_beat = 2
    sim.story_ticks = 175
    renderer = Renderer()
    heights: list[float] = []
    renderer._prologue_hero = lambda *args, **kwargs: heights.append(float(args[5]))
    renderer._prologue_sled = lambda *args, **kwargs: None
    renderer._prologue_orbs = lambda *args, **kwargs: None
    renderer.frame(sim)
    assert heights == [44 * PROLOGUE_DOOR_END_SCALE]
    assert abs(PROLOGUE_DOOR_END_SCALE - 0.58 * 0.75) < 1e-9
    pygame.quit()


def test_bosses_have_more_than_twice_the_enemy_render_height():
    assert BOSS_WORLD_HEIGHT > ENEMY_WORLD_HEIGHT * 2


def test_enemy_contact_enters_turn_battle_and_foe_gets_a_visible_reply():
    sim = GameSim.from_play_now()
    foe = Entity("enemy", 4, 4, extra={"variant": "dogma-sprite", "hp": 2})
    sim.entities = [foe]
    sim._begin_combat(foe, boss=False)
    assert sim.scene == "turn"
    assert sim.combat is not None and sim.combat.mode == "turn"
    before_round = sim.combat.round_index
    sim.step(InputState(jump_pressed=True))
    assert sim.combat is not None
    assert sim.battle_actor == "player"
    assert sim.combat.round_index == before_round
    actors = _drain_battle_timeline(sim)
    assert actors == ["player", "foe"]
    assert sim.combat is not None and sim.combat.round_index == before_round + 1
    assert "meter rises" in sim.combat.log[-1]
    assert {popup.get("side") for popup in sim.floaters if popup.get("space") == "battle"} >= {"player", "foe"}


def test_kick_breaks_distinct_optional_tile_and_score_rises_at_source():
    sim = GameSim.from_play_now()
    assert sim.body is not None
    cx, cy = sim.body.center
    tx = int((cx + sim.body.facing * 14) // TILE)
    ty = int(cy // TILE)
    row = list(sim.tiles[ty])
    row[tx] = "D"
    sim.tiles[ty] = "".join(row)
    before = sim.score
    sim._side_attack()
    assert sim.tiles[ty][tx] == "."
    assert sim.score > before
    assert any(popup.get("space") == "world" and popup.get("x") == tx * TILE + 8 for popup in sim.floaters)


def test_omega_block_breaks_when_david_straddles_its_tile_boundary():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.body = replace(sim.body, x=2 * TILE - sim.body.width / 2, facing=1)
    block = Entity("omega-block", 2, 3, extra={"letter": "O", "omega": True})
    row = list(sim.tiles[3])
    row[2] = "B"
    sim.tiles[3] = "".join(row)
    sim.entities = [block]
    sim._kick_breakable()
    assert not block.alive
    assert sim.tiles[3][2] == "."


def test_omega_block_head_bump_uses_body_overlap_not_center_tile():
    sim = _flat_action_sim()
    assert sim.body is not None
    row = list(sim.tiles[1])
    row[1] = "B"
    sim.tiles[1] = "".join(row)
    block = Entity("omega-block", 1, 1, extra={"letter": "O", "omega": True})
    sim.entities = [block]
    sim.body = replace(sim.body, x=2 * TILE - sim.body.width / 2 - 0.2)
    sim.step(InputState(jump=True, jump_pressed=True))
    for _ in range(8):
        if not block.alive:
            break
        sim.step(InputState(jump=True))
    assert not block.alive


def test_edit_cursor_is_bounded_and_edits_preview_undo_reset_then_cancel():
    sim = GameSim.from_play_now()
    sim._enter_edit()
    bounds = sim._edit_bounds()
    for _ in range(40):
        sim.step(InputState(left=True, up=True))
    assert sim.edit_cursor == (bounds[0], bounds[1])
    sim.step(InputState(turn_pressed=True))
    assert sim.edit_tile_index == 1
    cx, cy = sim.edit_cursor
    untouched = sim.original_tiles[cy][cx]
    sim.step(InputState(action_pressed=True))
    assert sim.edit_ops[-1]["tile"] == "L"
    assert sim.tiles[cy][cx] == "L"
    assert sim.edit_reward is not None
    sim.step(InputState(interact=True))
    assert sim.scene == "edit"
    assert not sim.edit_ops
    assert sim.tiles[cy][cx] == untouched
    sim.step(InputState(action_pressed=True))
    assert sim.tiles[cy][cx] == "L"
    sim.step(InputState(customize=True))
    assert not sim.edit_ops
    assert sim.tiles[cy][cx] == untouched
    sim.step(InputState(interact=True))
    assert sim.scene == "flight" and sim.flight_direction == "in"


def test_edit_budget_counts_net_map_changes_instead_of_input_history():
    sim = GameSim.from_play_now()
    sim._enter_edit()
    reserved = sim.edit_reserved_cells()
    min_x, min_y, max_x, max_y = sim._edit_bounds()
    empty = next(
        (x, y)
        for y in range(min_y, max_y + 1)
        for x in range(min_x, max_x + 1)
        if sim.original_tiles[y][x] == "." and (x, y) not in reserved
    )
    sim.edit_cursor = empty
    sim.step(InputState(action_pressed=True))
    assert sim.edit_budget_used == 1

    sim.step(InputState(turn_pressed=True))
    sim.step(InputState(action_pressed=True))
    assert sim.tiles[empty[1]][empty[0]] == "L"
    assert sim.edit_budget_used == 1, "swapping an event-placed tile is budget neutral"

    sim.step(InputState(item=True))
    assert sim.tiles[empty[1]][empty[0]] == "."
    assert sim.edit_budget_used == 0, "erasing an event-placed tile restores its point"

    existing = next(
        (x, y)
        for y in range(min_y, max_y + 1)
        for x in range(min_x, max_x + 1)
        if sim.original_tiles[y][x] in {"#", "=", "L", "+", "^", "D"}
        and (x, y) not in reserved
    )
    sim.edit_cursor = existing
    sim.step(InputState(item=True))
    assert sim.edit_budget_used == 1, "erasing a preexisting map tile still consumes budget"


def test_oligarchy_event_switches_hud_to_companion_logo_asset():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim.hud_wordmark = "OLIGARCHY"
    renderer = Renderer()
    renderer.frame(sim)
    assert "ui/oligarchy-logo-hud.png" in renderer.cache
    pygame.quit()


def test_stage_selection_uses_powered_artifact_emblem_and_shorter_side_meter():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim.scene = "stage-map"
    sim.stage_map_transition_ticks = 0
    renderer = Renderer()
    renderer.frame(sim)
    assert "ui/omega-omarchy-icon.png" in renderer.cache

    meter = pygame.Surface((320, 180))
    meter.fill((0, 0, 0))
    renderer._vs = 1
    renderer._side_meter(meter, 3, 37, 100, 100, "BS", (255, 0, 0))
    assert meter.get_at((3, 37 + 62))[:3] != (0, 0, 0)
    assert meter.get_at((3, 37 + 63))[:3] == (0, 0, 0)

    renderer._fid_cur = "sixteen-bit"
    assert renderer._legible_text_color((100, 80, 60)) == (115, 92, 69)
    renderer._fid_cur = "ultra"
    assert renderer._legible_text_color((100, 80, 60)) == (100, 80, 60)
    pygame.quit()


def test_hud_uses_penguin_art_instead_of_a_letter_counter_prefix():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    renderer = Renderer()
    renderer.frame(sim)
    assert "fidelity/ultra/items/penguin.png" in renderer.cache
    pygame.quit()


def _flat_action_sim() -> GameSim:
    sim = GameSim.from_play_now()
    sim.tiles = [".......", ".......", ".......", ".S.....", "#######"]
    sim.original_tiles = list(sim.tiles)
    assert sim.body is not None
    sim.body = replace(sim.body, x=TILE + 3, y=4 * TILE - 18, vx=0, vy=0, on_ground=True, facing=1)
    sim.entities = []
    sim.projectiles = []
    sim.enemy_projectiles = []
    return sim


def test_ladders_are_deferred_until_after_dynamic_platform_art():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = _flat_action_sim()
    row = list(sim.tiles[2])
    row[2] = "L"
    sim.tiles[2] = "".join(row)
    sim.entities = [Entity("moving-platform", 1, 2, extra={"width": 4})]
    sim.scene = "flight"
    sim.edit_player_ghost = None
    sim.cam_x = sim.cam_y = 0.0
    renderer = Renderer(ensure_assets=False)
    calls: list[str] = []

    def fake_fid(_sim: GameSim, rel: str) -> pygame.Surface:
        calls.append(rel)
        return pygame.Surface((16, 16), pygame.SRCALPHA)

    renderer._fid = fake_fid  # type: ignore[method-assign]
    renderer._vs = 1
    renderer._iw, renderer._ih = 320, 180
    renderer._world(pygame.Surface((320, 180)), sim)
    deck = next(index for index, rel in enumerate(calls) if rel.endswith("_=.png"))
    ladder = next(index for index, rel in enumerate(calls) if rel.endswith("_L.png"))
    assert deck < ladder
    pygame.quit()


def test_hostile_shots_wait_for_visible_mobs_then_ricochet_with_a_fixed_budget():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.tiles = ["......." for _ in range(13)] + ["#######"]
    sim.original_tiles = list(sim.tiles)
    shooter = Entity(
        "enemy",
        2,
        12,
        extra={"variant": "consensus-crier", "behavior": "shoot", "cooldown": 1, "hp": 2},
    )
    sim.entities = [shooter]
    sim.cam_x = sim.cam_y = 0.0
    sim._tick_enemy_behaviors()
    assert not sim.enemy_projectiles
    shooter.y = 8
    shooter.extra["cooldown"] = 1
    sim._tick_enemy_behaviors()
    assert sim.enemy_projectiles

    sim.entities = []
    sim.enemy_projectiles = [
        {"x": 3 * TILE - 3.0, "y": 2 * TILE + 8.0, "vx": 2.0, "vy": 0.0, "life": 5}
    ]
    row = list(sim.tiles[2])
    row[3] = "B"
    sim.tiles[2] = "".join(row)
    untouched = sim.tiles[2]
    sim._tick_enemy_projectiles()
    shot = sim.enemy_projectiles[0]
    assert shot["vx"] < 0 and shot["ricochets"] == 1
    assert shot["life"] == 4 and shot["distance_left"] == 8.0
    assert sim.tiles[2] == untouched
    for _ in range(4):
        sim._tick_enemy_projectiles()
    assert not sim.enemy_projectiles, "a bounce must not renew time or travel distance"


def test_edit_flight_leaves_a_pose_ghost_and_protects_player_and_helper_cells():
    sim = GameSim.from_play_now()
    assert sim.body is not None
    sim.body = replace(sim.body, vx=1.0, facing=-1, on_ground=True)
    expected_frame = sim.side_sprite_frame()
    sim._begin_flight()
    assert sim.edit_player_ghost is not None
    assert sim.edit_player_ghost["frame"] == expected_frame
    assert sim.edit_player_ghost["facing"] == -1
    sim._enter_edit()
    player_cells = sim.edit_reserved_cells()
    assert player_cells
    protected = next(iter(player_cells))
    sim.edit_cursor = protected
    sim.step(InputState(action_pressed=True))
    assert not sim.edit_ops
    assert "protected" in sim.messages[-1]

    helper = Entity(
        "enemy",
        10,
        8,
        extra={"variant": "justice-signaler", "converted": True, "companion": True},
    )
    sim.entities.append(helper)
    helper_cells = sim._rect_cells(10 * TILE, 8 * TILE - 8, TILE, 24)
    assert helper_cells <= sim.edit_reserved_cells()
    sim.edit_ops = [{"op": "remove", "x": 10, "y": 8}]
    assert not sim._refresh_edit_preview(), "direct edit payloads cannot bypass protected cells"


def test_corrupted_code_and_talking_points_penalize_score_without_underflow():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.tiles = [".......", ".......", ".......", ".MMM...", "#######"]
    sim.body = replace(sim.body, x=TILE + 3, y=3 * TILE, vy=1.0, on_ground=False)
    sim.score = 50
    for _ in range(12):
        sim._tick_corruption_pit()
    assert sim.score == 30
    sim.body = replace(sim.body, x=5 * TILE, y=3 * TILE)
    sim._tick_corruption_pit()
    assert sim.pit_exposure_ticks == 0

    cx, cy = sim.body.center
    sim.enemy_projectiles = [{"x": cx, "y": cy, "vx": 0.0, "vy": 0.0, "life": 3}]
    sim._tick_enemy_projectiles()
    assert sim.score == 0
    sim.enemy_projectiles = [{"x": cx, "y": cy, "vx": 0.0, "vy": 0.0, "life": 3}]
    sim._tick_enemy_projectiles()
    assert sim.score == 0


def test_score_pressure_fills_persistent_bs_and_touch_grass_usb_clears_it():
    sim = _flat_action_sim()
    sim.score = 200
    sim._penalize_score(40, "talking point")
    assert sim.score == 160
    assert sim.player_bs == 4
    sim.inventory = [RARE_BS_RESET_ITEM]
    sim.selected_item = 0
    sim._use_side_item()
    assert sim.player_bs == 0
    assert RARE_BS_RESET_ITEM not in sim.inventory
    assert "Nature remains emulated" in sim.messages[-1]


def test_boss_can_be_converted_entirely_in_side_view():
    sim = _flat_action_sim()
    boss_id = CAMPAIGN_ROSTER[0].boss.id
    boss = Entity("boss", 5, 3, extra={"boss": boss_id, "hp": 2, "max_hp": 2})
    sim.entities = [boss]
    assert sim._damage_side_enemy(boss, 2, item="logic-bomb")
    assert boss.extra["converted"] is True
    assert boss_id in sim.converted
    assert CAMPAIGN_ROSTER[0].boss.capability in sim.converted
    assert sim.scene == "chapter-complete"
    assert sim.combat is None


def test_score_loss_popup_starts_above_the_complete_player_sprite():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.score = 50
    sim._penalize_score(10, "test pressure")
    popup = sim.floaters[-1]
    assert popup["y"] <= sim.body.feet[1] - 36 - 7


def test_pit_can_revert_a_helper_and_traps_them_beyond_reengagement():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.tiles = [".......", ".......", ".......", ".MMM...", "#######"]
    sim.body = replace(sim.body, x=TILE + 3, y=3 * TILE, on_ground=False)
    sim.converted = ["faction-truce", "justice-signaler"]
    helper = Entity(
        "enemy",
        1,
        3,
        extra={"variant": "justice-signaler", "converted": True, "companion": True, "hp": 0},
    )
    sim.entities = [helper]
    sim.tick = 3  # deterministic one-in-four reversion branch for this fixture
    assert sim._maybe_revert_pit_companion() == "justice-signaler"
    assert "justice-signaler" not in sim.converted
    assert not helper.extra["converted"] and not helper.extra["companion"] and helper.extra["hp"] > 0
    assert sim.tiles[int(helper.y)][int(helper.x)] == "M"
    assert abs(helper.x - sim.body.x / TILE) >= 1, "the trapped helper should remain visible beside David"
    assert helper.extra["pit_trapped"] and helper.extra["unrecruitable"]
    assert helper.extra["pit_corrupted"], "the stranded former helper receives the red corruption treatment"
    sim._begin_combat(helper, boss=False)
    assert sim.combat is None


def test_item_pickups_fill_a_capped_strength_meter_and_scale_effectiveness():
    sim = _flat_action_sim()
    assert sim.body is not None
    starting = sim.item_effectiveness
    sim.entities = [Entity("item", 1, 2, extra={"item": "checksum-key"})]
    sim.step(InputState())
    assert sim.item_strength > 25
    assert sim.item_effectiveness > starting
    sim.item_strength = 99
    sim._increase_item_strength("patch-cable")
    assert sim.item_strength == 100
    assert sim.item_effectiveness == 1.25


def test_tilting_lifts_and_updrafts_have_real_player_physics():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.tiles = ["........", "........", "........", "........", "########"]
    sim.body = replace(sim.body, x=2 * TILE + 3, y=3 * TILE - 18, vx=0, vy=0, on_ground=False)
    tilt = Entity("tilt-platform", 1, 3, extra={"width": 5, "phase": 0.0, "angle": 0.0})
    lift = Entity(
        "moving-platform",
        1,
        3,
        extra={"width": 4, "axis": "vertical", "range": 2, "phase": 0.0, "base_x": 1.0, "base_y": 3.0},
    )
    wind = Entity("wind-column", 2, 1, extra={"width": 1, "height": 3, "strength": 0.5})
    sim.entities = [tilt]
    sim._step_action(InputState())
    assert sim.body.on_ground
    assert abs(sim.body.feet[1] - 3 * TILE) < 1
    for _ in range(8):
        sim._tick_traversal_features()
    assert abs(float(tilt.extra["angle"])) > 0.01

    sim.entities = [lift]
    before_y = sim.body.y
    sim.tick = 1
    sim._tick_traversal_features()
    assert lift.y != 3
    assert sim.body.y != before_y, "a rider should be carried by a moving lift"

    # A moving deck may pass visually behind either ladder glyph without
    # catching or carrying a climber on that foreground traversal plane.
    lift.x, lift.y = 1, 3
    lift.extra.update({"prev_x": 1.0, "prev_y": 3.0, "base_x": 1.0, "base_y": 3.0})
    previous = replace(
        sim.body,
        x=2 * TILE,
        y=3 * TILE - sim.body.height - 2,
        vy=1.0,
        on_ground=False,
        on_ladder=True,
    )
    sim.body = replace(previous, y=previous.y + 4)
    crossing_y = sim.body.y
    sim._resolve_traversal_platforms(previous)
    assert sim.body.y == crossing_y and not sim.body.on_ground
    before = (sim.body.x, sim.body.y)
    sim.tick = 2
    sim._tick_traversal_features()
    assert (sim.body.x, sim.body.y) == before

    sim.entities = [wind]
    sim.body = replace(sim.body, x=2 * TILE + 3, y=2 * TILE, vy=1.0)
    sim._apply_wind_columns()
    assert sim.body.vy < 1.0


def test_pivot_platform_accumulates_torque_until_a_far_side_rider_drops():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.tiles = ["........", "........", "........", "........", "........", "########"]
    tilt = Entity("tilt-platform", 1, 3, extra={"width": 5, "phase": 0.0, "angle": 0.0})
    sim.entities = [tilt]
    sim.body = replace(sim.body, x=5 * TILE, y=3 * TILE - 18, vx=0, vy=0, on_ground=False)
    peak = 0.0
    for _ in range(180):
        sim.step(InputState())
        peak = max(peak, abs(float(tilt.extra.get("angle") or 0.0)))
        if sim.body.feet[1] > 3 * TILE + 8:
            break
    assert peak > 0.25, "sustained off-center weight must keep increasing the angle"
    assert sim.body.feet[1] > 3 * TILE + 8, "the tilted deck must eventually shed its rider"


def test_pivot_platform_counts_partial_body_overlap_at_both_far_edges():
    for side, body_x in (("left", 2 * TILE - 9), ("right", 7 * TILE - 1)):
        sim = _flat_action_sim()
        assert sim.body is not None
        tilt = Entity(
            "tilt-platform",
            2,
            3,
            extra={"width": 5, "phase": 0.0, "angle": 0.0},
        )
        sim.entities = [tilt]
        sim.body = replace(
            sim.body,
            x=body_x,
            y=3 * TILE - sim.body.height,
            vx=0.0,
            vy=0.0,
            on_ground=True,
        )
        sim._tick_traversal_features()
        velocity = float(tilt.extra.get("angular_velocity") or 0.0)
        if side == "left":
            assert velocity < 0
        else:
            assert velocity > 0


def test_player_and_helper_projectiles_stop_at_closed_or_closing_boss_gates():
    for glyph in ("G", "g"):
        sim = _flat_action_sim()
        row = list(sim.tiles[2])
        row[3] = glyph
        sim.tiles[2] = "".join(row)
        target = Entity(
            "enemy",
            5,
            2,
            extra={"variant": "lint-launcher", "hp": 3, "max_hp": 3},
        )
        sim.entities = [target]
        sim.projectiles = [
            {"x": 3 * TILE - 4, "y": 2 * TILE + 8, "vx": 4, "vy": 0, "life": 20, "power": 2},
            {
                "x": 3 * TILE - 5,
                "y": 2 * TILE + 8,
                "vx": 4,
                "vy": 0,
                "life": 20,
                "power": 2,
                "ally": True,
            },
        ]
        sim._tick_projectiles()
        assert sim.projectiles == []
        assert target.extra["hp"] == 3


def test_foreground_plane_tracks_vertical_ascent_without_a_time_bob():
    assert foreground_parallax_y(80, 80, 3) == 0
    assert foreground_parallax_y(40, 80, 3) == 120
    assert foreground_parallax_y(40, 80, 3) == foreground_parallax_y(40, 80, 3)


def test_structural_parallax_planes_are_ground_registered_during_ascent():
    assert background_parallax_y(80, 80, 0.6, 3) == 0
    assert background_parallax_y(40, 80, 0.6, 3) > 0
    assert background_parallax_y(40, 80, 0.6, 3) == background_parallax_y(40, 80, 0.6, 3)


def test_gust_pulls_adjacent_player_toward_center_and_fades_at_its_peak():
    sim = _flat_action_sim()
    assert sim.body is not None
    wind = Entity("wind-column", 3, 1, extra={"width": 1, "height": 4, "strength": 0.6})
    sim.entities = [wind]
    center_x = (3.5 * TILE)
    sim.body = replace(sim.body, x=2 * TILE + 1, y=3 * TILE, vx=0.0, vy=1.0, on_ground=True)
    assert sim.body.center[0] < center_x
    sim._apply_wind_columns()
    assert sim.body.vx > 0, "the adjacent tile must be drawn toward the gust core"
    assert sim.body.vx > 0.35, "the adjacent-tile pull should be strong enough to feel deliberate"
    first_distance = abs(sim.body.center[0] - center_x)
    for _ in range(5):
        sim.body = replace(sim.body, x=sim.body.x + sim.body.vx)
        sim._apply_wind_columns()
    assert abs(sim.body.center[0] - center_x) < first_distance

    sim.body = replace(sim.body, x=3 * TILE + 3, y=TILE - sim.body.height / 2, vx=0.0, vy=1.0)
    sim._apply_wind_columns()
    assert sim.body.vy == 1.0, "lift should dissipate at the top peak"


def test_gust_releases_horizontal_control_at_its_center():
    sim = _flat_action_sim()
    assert sim.body is not None
    wind = Entity("wind-column", 3, 1, extra={"width": 1, "height": 4, "strength": 0.6})
    sim.entities = [wind]
    sim.body = replace(sim.body, x=3 * TILE + 3, y=3 * TILE, vx=1.25, vy=0.0, on_ground=False)

    sim._apply_wind_columns()

    assert sim.body.center[0] == 3.5 * TILE
    assert sim.body.vx == 1.25, "centered players must retain enough horizontal control to exit"

    for _ in range(12):
        sim._step_action(InputState(right=True))
    assert sim.body.center[0] > 4 * TILE, "holding away after centering must escape the gust core"


def test_gust_edge_has_a_cliff_strength_pull_and_jump_matches_ground_strength():
    sim = _flat_action_sim()
    assert sim.body is not None
    wind = Entity("wind-column", 3, 1, extra={"width": 1, "height": 4, "strength": 0.6})
    sim.entities = [wind]
    influence = TILE * 1.4
    sim.body = replace(
        sim.body,
        x=3 * TILE - influence - sim.body.width / 2 + 0.1,
        y=3 * TILE,
        vx=0.0,
        vy=0.0,
        on_ground=True,
    )
    sim._apply_wind_columns()
    assert sim.body.vx > 0.9, "the gust field must acquire the player strongly right to its edge"

    sim.body = replace(
        sim.body,
        x=3 * TILE + 3,
        y=4 * TILE - sim.body.height,
        vx=0.0,
        vy=0.0,
        on_ground=True,
        air_jump_used=False,
    )
    baseline = _flat_action_sim()
    baseline._step_action(InputState(jump=True, jump_pressed=True))
    sim._step_action(InputState(jump=True, jump_pressed=True))
    assert sim.body.air_jump_used is False
    assert sim.body.vy == baseline.body.vy, "gust jumps should match the grounded jump impulse"


def test_gust_can_carry_the_player_through_a_solid_column():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.tiles = [
        "........",
        "...#....",
        "...#....",
        "...#....",
        "...#....",
        "########",
    ]
    sim.body = replace(
        sim.body,
        x=2 * TILE + 5,
        y=5 * TILE - sim.body.height,
        vx=0.0,
        vy=0.0,
        on_ground=True,
    )
    sim.entities = [
        Entity(
            "wind-column",
            3,
            1,
            extra={"width": 1, "height": 4, "strength": 0.45},
        )
    ]
    for _ in range(36):
        sim._step_action(InputState(right=True))
    assert sim.body.x > 4 * TILE, "gust-phase collision must clear the complete obstacle"


def test_edit_selector_uses_a_slow_repeat_instead_of_one_tile_per_tick():
    sim = _flat_action_sim()
    sim.cam_x = sim.cam_y = 0
    sim.edit_cursor = (2, 2)
    sim._step_edit(InputState(right=True, right_pressed=True))
    assert sim.edit_cursor == (3, 2)
    sim._step_edit(InputState(right=True))
    assert sim.edit_cursor == (3, 2)


def test_slide_is_a_kick_and_knocks_a_non_boss_backward_once():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.body = replace(sim.body, y=sim.body.feet[1] - 12, height=12, sliding=True, slide_ticks=12)
    target = Entity("enemy", 2, 3, extra={"hp": 2, "variant": "cache-gremlin", "home": 2, "dir": 1})
    sim.entities = [target]
    sim._slide_attack()
    assert target.extra["hp"] == 1
    assert target.x == 3
    assert target.extra["contact_grace"] > 0
    sim._slide_attack()
    assert target.extra["hp"] == 1, "one slide may kick a given mob only once"


def test_regular_kick_knocks_a_non_boss_backward_but_not_a_boss():
    sim = _flat_action_sim()
    target = Entity("enemy", 2, 3, extra={"hp": 3, "variant": "cache-gremlin", "home": 2, "dir": 1})
    sim.entities = [target]
    sim._side_attack()
    assert target.x == 3
    assert target.extra["hp"] == 2

    boss = Entity("boss", 2, 3, extra={"boss": "package-bureaucrat"})
    sim.combat = None
    sim.scene = "action"
    sim.entities = [boss]
    sim._side_attack()
    assert boss.x == 2


def test_complete_visual_sprite_collects_pickups_above_logical_hitbox():
    sim = _flat_action_sim()
    # Row 1 overlaps David's hair/upper visual but not his 18px logical body.
    sim.entities = [Entity("item", 1, 1, extra={"item": "patch-cable"})]
    before = sim.inventory.count("patch-cable")
    sim.step(InputState())
    assert sim.inventory.count("patch-cable") == before + 1


def test_ground_throw_uses_torso_height_and_requires_a_neutral_pose_frame():
    sim = _flat_action_sim()
    assert sim.body is not None
    sim._use_side_item()
    assert sim.projectiles[-1]["y"] < sim.body.center[1] - 8
    count = len(sim.projectiles)
    sim._use_side_item()
    assert len(sim.projectiles) == count

    sim.attack_timer = 1
    sim._step_action(InputState())
    assert sim.attack_timer == 0 and sim.action_reset_ticks == 1 and sim.action_kind == ""
    sim._use_side_item()
    assert len(sim.projectiles) == count
    sim._step_action(InputState())
    sim._use_side_item()
    assert len(sim.projectiles) == count + 1


def test_sign_carriers_convert_into_following_side_and_rpg_companions():
    sim = _flat_action_sim()
    justice = Entity("enemy", 4, 3, extra={"hp": 1, "variant": "justice-signaler", "home": 4, "dir": 1})
    target = Entity("enemy", 5, 3, extra={"hp": 2, "variant": "cache-gremlin", "home": 5, "dir": -1})
    sim.entities = [justice, target]
    sim._convert_side_enemy(justice)
    assert justice.extra["companion"]
    assert "justice-signaler" in sim.converted
    old_x = justice.x
    justice.extra["assist_cooldown"] = 1
    sim._tick_companions()
    assert justice.x != old_x
    assert any(shot.get("ally") for shot in sim.projectiles)

    sim._begin_combat(target, boss=False)
    assert sim.combat is not None
    sim._step_turn(InputState(jump_pressed=True))
    actors = _drain_battle_timeline(sim)
    assert actors == ["player", "justice-signaler", "foe"]
    assert sim.combat is not None
    assert any("Justice Signaler assists" in line for line in sim.combat.log)


def test_two_helpers_take_separate_delayed_rpg_stages():
    sim = _flat_action_sim()
    sim.converted = ["justice-signaler", "detractabot"]
    target = Entity("enemy", 5, 3, extra={"hp": 3, "variant": "cache-gremlin", "home": 5})
    sim._begin_combat(target, boss=False)
    sim._step_turn(InputState(jump_pressed=True))
    assert sim.battle_delay_ticks == 18
    for _ in range(18):
        sim.step(InputState())
    assert sim.battle_actor == ""
    assert sim.battle_delay_ticks == BATTLE_INTER_ACTION_TICKS
    for _ in range(BATTLE_INTER_ACTION_TICKS):
        sim.step(InputState())
    assert sim.battle_actor == "justice-signaler"
    assert _drain_battle_timeline(sim) == ["justice-signaler", "detractabot", "foe"]


def test_rpg_action_copy_wraps_without_clipping_or_abbreviation():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = _flat_action_sim()
    renderer = Renderer()
    renderer.frame(sim)
    message = "COMBO · RECEIPTS ATTACHED: Reason and Linux Freedom expose the repeated claim."
    surface = pygame.Surface((renderer._iw, renderer._ih))
    lines = renderer.wrapped_text(
        surface,
        message,
        (18, 151, 166, 21),
        (255, 255, 255),
        max_lines=3,
        logical_size=6,
    )
    assert " ".join(lines) == message
    assert len(lines) <= 3
    assert not any("…" in line for line in lines)
    pygame.quit()


def test_held_slide_end_pose_is_idle_and_active_slide_is_dropped_to_surface():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.body = replace(sim.body, slide_locked=True, sliding=False, crouching=False, vx=0.0)
    renderer = Renderer()
    renderer.frame(sim)
    assert any(key.endswith("characters/david_side-idle.png") for key in renderer.cache)
    assert not any(key.endswith("characters/david_side-slide.png") for key in renderer.cache)
    assert SLIDE_WORLD_DROP >= 8
    pygame.quit()


def test_hardware_chapter_renders_dedicated_foreground_and_network_frame():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    idx = next(i for i, chapter in enumerate(CAMPAIGN_ROSTER) if chapter.id == "distro-front")
    sim._load_chapter(idx)
    renderer = Renderer()
    renderer.frame(sim)
    assert "fidelity/ultra/bg/front/foreground-1.png" in renderer.cache
    node = next(entity for entity in sim.entities if entity.kind == "network")
    sim._begin_network_transition(node)
    frame = renderer.frame(sim)
    assert sim.scene == "network"
    assert frame.get_size() == (960, 540)
    assert "fidelity/ultra/ui/network-ethernet.png" in renderer.cache
    assert "fidelity/ultra/ui/network-ethernet-overlay.png" in renderer.cache
    pygame.quit()


def test_every_boss_map_has_a_closing_room_gate_and_boss_warp_stages_its_entrance():
    sim = GameSim.from_play_now()
    assert sim.world is not None and sim.body is not None
    for chapter_index in range(len(sim.world.chapters)):
        sim._load_chapter(chapter_index)
        boss_map = next(
            i
            for i, entities in enumerate(sim.chapter_map_entities)
            if any(entity.kind == "boss" for entity in entities)
        )
        assert any(entity.kind == "boss-gate" for entity in sim.chapter_map_entities[boss_map])
        gate = next(entity for entity in sim.chapter_map_entities[boss_map] if entity.kind == "boss-gate")
        map_height = len(sim.chapter_map_tiles[boss_map])
        assert int(gate.extra["height"]) == map_height
        assert {gy for _, gy in gate.extra["cells"]} == set(range(map_height))

    resolved = sim.dev_warp("corrupted-install:boss")
    assert resolved == "corrupted-install:boss:map-1"
    gate = next(entity for entity in sim.entities if entity.kind == "boss-gate")
    assert sim.body.x < gate.x * TILE
    sim.body = replace(sim.body, x=(gate.x + 1) * TILE + 1)
    sim._tick_boss_gates()
    assert gate.extra["state"] == "closing"
    assert all(sim.tiles[gy][gx] == "g" for gx, gy in gate.extra["cells"]), "the player cannot reverse through a closing gate"
    for _ in range(int(gate.extra["close_total"])):
        sim._tick_boss_gates()
    assert gate.extra["state"] == "closed"
    assert all(sim.tiles[gy][gx] == "G" for gx, gy in gate.extra["cells"])


def test_boss_is_inert_and_untargetable_until_player_clears_gate():
    sim = GameSim.from_play_now()
    assert sim.body is not None
    gate = next(entity for entity in sim.entities if entity.kind == "boss-gate")
    boss = next(entity for entity in sim.entities if entity.kind == "boss")
    boss.extra["ability_cooldown"] = 1
    initial = (boss.x, boss.extra.get("offset_y", 0.0))
    sim._tick_boss_behaviors()
    assert (boss.x, boss.extra.get("offset_y", 0.0)) == initial
    assert sim._nearest_side_target(boss.x * TILE, boss.y * TILE, TILE * 2) is None
    sim._begin_combat(boss, boss=True)
    assert sim.combat is None

    sim.body = replace(sim.body, x=(gate.x + 1) * TILE + 1)
    sim._tick_boss_gates()
    assert sim._boss_arena_ready(boss)
    sim._tick_boss_behaviors()
    assert (boss.x, boss.extra.get("offset_y", 0.0)) != initial


def test_side_view_damage_carries_into_enemy_and_boss_rpg_starting_state():
    sim = _flat_action_sim()
    enemy = Entity(
        "enemy",
        5,
        3,
        extra={"hp": 3, "max_hp": 3, "variant": "lint-launcher", "home": 5},
    )
    untouched = sim._carry_side_pressure(make_foe("lint-launcher"), enemy)[0]
    sim._damage_side_enemy(enemy, 1)
    sim._begin_combat(enemy, boss=False)
    assert sim.combat is not None
    assert sim.combat.foe.corruption < untouched.corruption
    assert sim.combat.foe.bs < untouched.bs
    assert sim.combat.foe.trust > untouched.trust
    assert "Field pressure carries over" in sim.combat.log[-1]

    sim.combat = None
    sim.scene = "action"
    boss = Entity("boss", 6, 3, extra={"boss": "package-bureaucrat", "hp": 10, "max_hp": 10})
    sim._damage_side_enemy(boss, 3, item="logic-bomb")
    assert sim.combat is None, "a ranged field hit should not skip directly into the encounter"
    sim._begin_combat(boss, boss=True)
    assert sim.combat is not None and sim.combat.boss_id == "package-bureaucrat"
    assert "Field pressure carries over" in sim.combat.log[-1]


def test_detractabot_ships_as_a_named_convertible_companion_and_commissar_matches_costume():
    from omega_omarchy.campaign import BOSSES
    from omega_omarchy.combat import make_foe

    foe = make_foe("detractabot")
    assert foe.name == "Detractabot"
    assert BOSSES["distro-commander"].name == "The Distro Commissar"


def test_walk_interstitial_temporarily_uses_idle_pose():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = _flat_action_sim()
    assert sim.body is not None
    sim.tick = 6
    sim.body = replace(sim.body, vx=1.0, on_ground=True)
    renderer = Renderer()
    renderer.frame(sim)
    assert any(key.endswith("characters/david_side-idle.png") for key in renderer.cache)
    assert not any(key.endswith("characters/david_side-walk-1.png") for key in renderer.cache)
    pygame.quit()
