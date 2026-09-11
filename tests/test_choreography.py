from dataclasses import replace
from math import dist

import pytest

from omega_omarchy.articulation import custodian_pose, custodian_x
from omega_omarchy.character_pack import available_characters
from omega_omarchy.physics import InputState, TILE
from omega_omarchy.render import Renderer, PROLOGUE_MIND_HERO_ANGLE
from omega_omarchy.sim import GameSim, SKYWAY_TRANSFER_TICKS, BOSS_SETTLE_TICKS, BOSS_DEFEAT_HOLD_TICKS


def test_custodians_enter_when_orbs_leave_and_malfunction_without_drift():
    for right, home in ((False, 94), (True, 238)):
        off = custodian_x(home, 143, right=right, staging="orb-machine")
        assert off > 360 if right else off < -40
        assert custodian_x(home, 324, right=right, staging="orb-machine") == home
        origins = [custodian_x(home, t, right=right, staging="corrupt") for t in range(1800)]
        assert max(origins) - min(origins) > 8
        assert all(abs(x - home) <= 7 for x in origins)
        for tick in range(0, 1800, 7):
            pose = custodian_pose(origins[tick], 122, tick, right=right, corrupt=True)
            assert dist(pose.shoulder, pose.elbow) == pytest.approx(27)
            assert dist(pose.elbow, pose.wrist) == pytest.approx(24)
            assert pose.elbow[1] < pose.shoulder[1] and pose.wrist[1] < pose.elbow[1]
        assert custodian_x(home, 300, staging="corrupt", reduced=True) == home
        assert custodian_pose(home, 122, 12, corrupt=True, reduced=True) == custodian_pose(home, 122, 999, corrupt=True, reduced=True)


def test_royal_table_rotations_preserve_david_and_use_existing_art():
    sim = GameSim.from_play_now()
    values = {}
    for char in available_characters()[0][:3]:
        sim.world.character = char.to_record()
        values[char.kind] = Renderer._transfer_angle(sim)
    assert values["david"] == PROLOGUE_MIND_HERO_ANGLE
    assert values["david"] < values["omarch-queen"] < values["omarch-king"]


def test_skyway_contact_moves_the_body_through_the_world_before_arrival():
    sim = GameSim.from_play_now()
    sim.tiles = ["...................."] * 20 + ["####################"]
    sim.entities = sim._skyway_lift_pair({"lower": [4, 19], "upper": [12, 4]})
    lower = max(sim.entities, key=lambda e: e.y)
    sim.body = replace(sim.body, x=4 * TILE + 3, y=20 * TILE - 18, vx=0, vy=0)
    start = (sim.body.x, sim.body.y)
    sim._begin_network_transition(lower)
    for _ in range(SKYWAY_TRANSFER_TICKS // 2):
        sim.step(InputState())
    assert sim.scene == "network"
    assert start[0] < sim.body.x < 12 * TILE + 3
    assert 5 * TILE - 18 < sim.body.y < start[1]
    for _ in range(SKYWAY_TRANSFER_TICKS // 2):
        sim.step(InputState())
    assert sim.scene == "action" and not sim.network_armed
    assert sim.body.x == pytest.approx(12 * TILE + 3)
    assert sim.body.feet[1] == pytest.approx(5 * TILE)


def test_rpg_poses_wait_for_their_actor_and_return_to_rest():
    sim = GameSim.from_play_now()
    for tick in range(100):
        sim.tick = tick
        assert Renderer._boss_pose_rel(sim, "package-bureaucrat", idle_motion=False) == "bosses/package-bureaucrat.png"
        assert Renderer._battle_player_pose(sim) == "battle"
    sim.battle_actor, sim.battle_stage_ticks, sim.battle_delay_ticks = "player", 24, 12
    sim.battle_player_action = "patch"
    assert Renderer._battle_player_pose(sim) == "side-action"
    sim.battle_player_action = "demonstrate"
    assert Renderer._battle_player_pose(sim) == "side-air-action"
    sim.battle_actor = "foe"
    assert Renderer._battle_player_pose(sim) == "battle"
    assert Renderer._boss_pose_rel(sim, "package-bureaucrat", active=True, idle_motion=False).endswith("-active.png")
    sim.battle_delay_ticks = 0
    assert Renderer._battle_player_pose(sim) == "battle"


def defeated_field_boss():
    sim = GameSim.from_play_now()
    sim.dev_warp("boss")
    boss = next(e for e in sim.entities if e.kind == "boss")
    boss.extra["offset_y"] = -48
    sim._damage_side_enemy(boss, 999)
    return sim, boss


def test_boss_returns_to_floor_and_holds_defeat_before_tally():
    sim, boss = defeated_field_boss()
    assert sim.scene == "boss-defeat" and not sim.post_boss
    camera = sim.camera_target()
    start = boss.y
    score = sim.score
    for _ in range(BOSS_SETTLE_TICKS):
        sim.step(InputState(jump_pressed=True))
    assert boss.y > start and not boss.extra["defeat_settling"]
    assert sim.camera_target() == camera
    floor_row = int(boss.y) + 1
    assert sim.tiles[floor_row][int(boss.x)] in "#=I+BDGg"
    for _ in range(BOSS_DEFEAT_HOLD_TICKS - 1):
        sim.step(InputState(jump_pressed=True))
    assert sim.scene == "boss-defeat"
    sim.step(InputState())
    assert sim.scene == "chapter-complete" and sim.score == score


def test_saving_during_defeat_restores_progress_without_reward_duplication(tmp_path):
    sim, _ = defeated_field_boss()
    sim.save_path = tmp_path / "defeat.json"
    sim.save_to_disk()
    loaded = GameSim.from_play_now()
    loaded.save_path = sim.save_path
    loaded.load_from_disk()
    assert loaded.scene == "boss-defeat"
    for _ in range(BOSS_SETTLE_TICKS + BOSS_DEFEAT_HOLD_TICKS):
        loaded.step(InputState())
    assert loaded.scene == "chapter-complete" and loaded.score == sim.score
