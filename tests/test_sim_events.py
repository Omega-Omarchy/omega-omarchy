from dataclasses import replace
from pathlib import Path

from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.combat import enter_turn_based
from omega_omarchy.physics import TILE, InputState
from omega_omarchy.sim import (
    FLIGHT_TICKS,
    LEVEL_INTRO_TICKS,
    NETWORK_TICKS,
    STAGE_MAP_INPUT_LOCK_TICKS,
    STAGE_MAP_TRANSITION_TICKS,
    Entity,
    GameSim,
)


def _drain_battle_timeline(sim: GameSim, limit: int = 240) -> None:
    for _ in range(limit):
        if not sim.battle_queue and sim.battle_delay_ticks == 0:
            break
        sim.step(InputState())


def _drain_stage_entry(sim: GameSim) -> None:
    for _ in range(STAGE_MAP_TRANSITION_TICKS + STAGE_MAP_INPUT_LOCK_TICKS):
        sim.step(InputState())


def _drain_level_intro(sim: GameSim) -> None:
    for _ in range(LEVEL_INTRO_TICKS):
        sim.step(InputState())


def test_recruiting_garden_gatekeeper_holds_oligarchy_until_dismiss():
    sim = GameSim.from_play_now()
    idx = next(i for i, chapter in enumerate(CAMPAIGN_ROSTER) if chapter.id == "walled-garden")
    sim._load_chapter(idx)
    sim.converted.extend(CAMPAIGN_ROSTER[index].boss.id for index in (0, 1, 2))
    sim._begin_combat(Entity("boss", 1, 1, extra={"boss": "garden-gatekeeper"}), boss=True)
    assert sim.combat is not None
    sim.combat = enter_turn_based(sim.combat)
    sim.scene = "turn"
    sim.combat = replace(
        sim.combat,
        foe=replace(sim.combat.foe, corruption=10, trust=70, bs=10),
        mode="turn",
    )
    sim.step(InputState(interact=True))
    _drain_battle_timeline(sim)
    assert sim.scene == "oligarchy"
    assert sim.oligarchy is True
    assert sim.hud_wordmark == "OLIGARCHY"
    assert sim.chapter_index == idx
    sim.dismiss_oligarchy()
    assert sim.scene == "chapter-complete"
    sim.step(InputState(turn_pressed=True))
    assert sim.scene == "stage-map"
    assert sim.stage_cursor == idx + 1
    _drain_stage_entry(sim)
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "level-intro"
    _drain_level_intro(sim)
    assert sim.scene == "action"
    assert sim.chapter_index == idx + 1


def test_logo_pickup_flies_backward_then_enters_edit():
    sim = GameSim.from_play_now()
    logos = [entity for entity in sim.entities if entity.kind == "logo" and entity.alive]
    assert logos, "fixture world must expose a deterministic OMARCHY logo"
    logo = logos[0]
    assert sim.body is not None
    sim.body = replace(sim.body, x=logo.x * TILE + 3, y=logo.y * TILE - 2, vx=0, vy=0)
    sim.step(InputState())
    assert sim.scene == "flight"
    assert sim.flight_ticks == FLIGHT_TICKS - 1 or sim.flight_ticks == FLIGHT_TICKS
    assert not logo.alive
    guard = 0
    while sim.scene == "flight" and guard < FLIGHT_TICKS + 5:
        sim.step(InputState())
        guard += 1
    assert sim.scene == "edit"
    assert sim.editing is True


def test_hardware_network_node_runs_interstitial_and_lands_on_its_pair():
    sim = GameSim.from_play_now()
    sim.converted.extend(["justice-signaler", "detractabot"])
    idx = next(i for i, chapter in enumerate(CAMPAIGN_ROSTER) if chapter.id == "distro-front")
    sim._load_chapter(idx)
    node = next(
        entity
        for entity in sim.entities
        if entity.kind == "network" and int(entity.extra.get("direction") or 0) == 1
    )
    assert sim.body is not None
    sim.body = replace(
        sim.body,
        x=node.x * TILE + 3,
        y=(node.y + 1) * TILE - sim.body.height,
        vx=0,
        vy=0,
        on_ground=True,
    )
    sim.step(InputState())
    assert sim.scene == "network"
    assert sim.network_ticks in {NETWORK_TICKS, NETWORK_TICKS - 1}
    assert sim.network_protocol in {"ethernet", "wifi"}
    destination_map = int(node.extra["targetMap"])
    destination_portal = str(node.extra["targetPortal"])
    for _ in range(NETWORK_TICKS + 2):
        sim.step(InputState())
    assert sim.scene == "action"
    assert sim.map_index == destination_map
    landed = next(entity for entity in sim.entities if entity.extra.get("portal") == destination_portal)
    assert int(sim.body.center[0] // TILE) == int(landed.x)
    companions = [entity for entity in sim.entities if entity.extra.get("companion")]
    assert {entity.extra.get("variant") for entity in companions} == {"justice-signaler", "detractabot"}
    assert all(abs(entity.x * TILE - sim.body.center[0]) < 3 * TILE for entity in companions)
    assert (sim.cam_x, sim.cam_y) == sim.camera_target(), "portal arrival must snap the camera"
    assert sim.network_armed is False
    for _ in range(50):
        sim.step(InputState())
    assert sim.scene == "action", "waiting on the destination must not bounce back"
    assert sim.network_armed is False
    direction = 1 if landed.x == 0 else -1
    for _ in range(10):
        sim.step(InputState(right=direction > 0, left=direction < 0))
    assert sim.network_armed is True
    for _ in range(10):
        sim.step(InputState(right=direction < 0, left=direction > 0))
        if sim.scene == "network":
            break
    assert sim.scene == "network", "only an exit and deliberate re-entry may reactivate a portal"


def test_chapter_one_completion_is_terminal_until_development_opt_in():
    sim = GameSim.from_play_now()
    sim.converted.extend(["provenance-pass", "package-bureaucrat"])
    sim._advance_after_boss("package-bureaucrat")
    assert sim.scene == "chapter-complete"
    assert sim.chapter_index == 0
    assert sim.pending_chapter == 1

    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "chapter-credits"
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "chapter-complete"
    sim.step(InputState(turn_pressed=True))
    assert sim.scene == "stage-map"
    assert sim.chapter_index == 0
    _drain_stage_entry(sim)
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "level-intro"
    _drain_level_intro(sim)
    assert sim.scene == "action"
    assert sim.chapter_index == 1
    assert not sim.post_boss


def test_chapter_completion_save_restores_the_completion_boundary(tmp_path: Path):
    save_path = tmp_path / "chapter-one.json"
    sim = GameSim.from_play_now()
    sim.converted.extend(["provenance-pass", "package-bureaucrat"])
    sim._advance_after_boss("package-bureaucrat")
    sim.save_path = save_path
    sim.step(InputState(action_pressed=True))
    assert save_path.is_file()

    restored = GameSim.from_play_now()
    restored.save_path = save_path
    restored.load_from_disk()
    assert restored.scene == "chapter-complete"
    assert restored.chapter_index == 0
    assert restored.pending_chapter == 1


def test_later_chapter_end_screen_also_survives_save_restore(tmp_path: Path):
    save_path = tmp_path / "later-chapter.json"
    index = 2
    spec = CAMPAIGN_ROSTER[index]
    sim = GameSim.from_play_now()
    sim._load_chapter(index)
    sim.converted.append(spec.boss.id)
    sim._advance_after_boss(spec.boss.id)
    sim.save_path = save_path
    sim.step(InputState(action_pressed=True))

    restored = GameSim.from_play_now()
    restored.save_path = save_path
    restored.load_from_disk()
    assert restored.scene == "chapter-complete"
    assert restored.chapter_index == index
    assert restored.pending_chapter == index + 1


def test_every_pre_goliath_victory_has_an_end_screen():
    sim = GameSim.from_play_now()
    for index, spec in enumerate(CAMPAIGN_ROSTER[:-1]):
        sim._load_chapter(index)
        sim._advance_after_boss(spec.boss.id)
        if "oligarchy" in spec.events:
            assert sim.scene == "oligarchy"
            sim.dismiss_oligarchy()
        assert sim.scene == "chapter-complete"
        assert sim.pending_chapter == index + 1


def test_walled_garden_stage_subtitle_is_revenue_retreat():
    garden = next(spec for spec in CAMPAIGN_ROSTER if spec.id == "walled-garden")
    assert garden.name == "The Walled Garden"
    assert garden.boss.title == "Revenue Retreat"


def test_bs_overload_opens_recovery_and_retry_restores_checkpoint():
    sim = GameSim.from_play_now()
    sim.score = 250
    sim._begin_combat(Entity("enemy", 8, 8, extra={"variant": "lint-launcher"}), boss=False)
    assert sim.combat is not None
    sim.combat = replace(sim.combat, player=replace(sim.combat.player, bs=99), mode="turn")
    sim.scene = "turn"
    sim.step(InputState(action_pressed=True))
    assert sim.scene == "turn" and sim.battle_actor == "player"
    _drain_battle_timeline(sim)
    assert sim.scene == "recovery"
    assert sim.combat is None
    assert sim.recovery_reason == "argument-overload"

    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "action"
    assert sim.body is not None and sim.body.x < 100
    assert sim.score == 150
    assert not sim.recovery_reason


def test_checkpoint_retry_reopens_and_rearms_the_boss_gate():
    sim = GameSim.from_play_now()
    sim.dev_warp("boss")
    assert sim.body is not None
    gate = next(entity for entity in sim.entities if entity.kind == "boss-gate")
    boss = next(entity for entity in sim.entities if entity.kind == "boss")
    sim.body = replace(sim.body, x=(gate.x + 1) * TILE + 1)
    sim._tick_boss_gates()
    for _ in range(int(gate.extra["close_total"])):
        sim._tick_boss_gates()
    assert gate.extra["state"] == "closed"
    assert boss.extra["arena_ready"] is True
    sim.projectiles = [{"x": 1, "y": 1, "vx": 1, "life": 10}]
    sim.enemy_projectiles = [{"x": 1, "y": 1, "vx": 1, "vy": 0, "life": 10}]

    sim._retry_checkpoint()

    assert gate.extra["state"] == "open"
    assert gate.extra["closing_ticks"] == 0
    assert boss.extra["arena_ready"] is False
    assert all(
        sim.tiles[gy][gx] == sim.original_tiles[gy][gx]
        for gx, gy in gate.extra["cells"]
    )
    assert sim.projectiles == [] and sim.enemy_projectiles == []


def test_action_mode_pressure_uses_the_same_visible_recovery_path():
    sim = GameSim.from_play_now()
    sim.selected_attack = "patch-strike"
    sim._begin_combat(Entity("enemy", 8, 8, extra={"variant": "lint-launcher"}), boss=False)
    assert sim.combat is not None
    sim.combat = replace(sim.combat, player=replace(sim.combat.player, bs=99), mode="action")
    sim.scene = "action"
    sim.step(InputState(action_pressed=True))
    assert sim.scene == "recovery"
    assert sim.combat is None
