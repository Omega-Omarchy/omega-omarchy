from dataclasses import replace

from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.physics import TILE, InputState
from omega_omarchy.sim import (
    BOSS_FIELD_HEALTH,
    BOSS_BEHAVIORS,
    CANNON_ENTRY_LOCK_TICKS,
    CANNON_MAX_POWER,
    CANNON_MAX_CHARGE_TICKS,
    COW_LEVEL_FLOOR,
    GOLIATH_FIRE_INTERVAL_MULTIPLIER,
    PROLOGUE_BEAT_TICKS,
    OMEGA_LETTERS,
    PROLOGUE_BEATS,
    PROLOGUE_LOGIN_TRANSITION_TICKS,
    PROLOGUE_PASSWORD,
    PROLOGUE_SKIP_COOL_TICKS,
    PROLOGUE_SKIP_HOLD_TICKS,
    PROLOGUE_TYPE_TICKS,
    STAGE_MAP_INPUT_LOCK_TICKS,
    STAGE_MAP_TRANSITION_TICKS,
    Entity,
    GameSim,
    cow_cannon_geometry,
)


def test_install_completion_opens_skippable_animated_prologue():
    sim = GameSim.new()
    sim.confirm_play_now()
    assert sim.scene == "prologue"
    assert sim.story_beat == 0

    for _ in range(PROLOGUE_BEAT_TICKS + 60):
        sim.step(InputState())
    assert sim.story_beat == 0, "every beat must wait for explicit player input"
    sim.step(InputState(jump_pressed=True))
    assert sim.story_beat == 1
    for _ in range(PROLOGUE_SKIP_HOLD_TICKS // 2):
        sim.step(InputState(turn=True))
    assert sim.scene == "prologue"
    partial_fill = sim.story_skip_ticks
    sim.step(InputState())
    assert sim.story_skip_ticks == partial_fill - PROLOGUE_SKIP_COOL_TICKS
    for _ in range(PROLOGUE_SKIP_HOLD_TICKS):
        sim.step(InputState(turn=True))
        if sim.scene == "stage-map":
            break
    assert sim.scene == "stage-map"
    assert sim.story_beat == len(PROLOGUE_BEATS) - 1
    assert any("CONSCIOUSNESS MOUNTED" in message for message in sim.messages)
    for _ in range(STAGE_MAP_INPUT_LOCK_TICKS):
        sim.step(InputState())
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "action"


def test_prologue_has_eight_input_paced_story_beats_with_exact_requested_copy():
    assert len(PROLOGUE_BEATS) == 8
    assert len(PROLOGUE_PASSWORD) == 33
    assert PROLOGUE_BEATS[0][0] == "The Omarch Thesis"
    assert PROLOGUE_BEATS[1][:2] == (
        "The End of the Personal",
        "But Big Desktop and Little Napoleon joined forces to call personal a privilege — and ownership a security risk.",
    )
    assert PROLOGUE_BEATS[2][:2] == (
        "The Reckoning",
        "The silent orbs ushered {character_name} toward the door. Choice would be erased. What-You-See-Is-What-You-Regret computing would persist.",
    )
    assert PROLOGUE_BEATS[3][:2] == (
        "The Mind Machine",
        "{character_name} was taken to a machine that previously existed only as a terrifying rumor.",
    )
    assert PROLOGUE_BEATS[4][1].startswith("They moved {character_name}'s consciousness")
    assert PROLOGUE_BEATS[5][1] == (
        "But {character_name}'s will was too strong, and one stubborn process survived the transfer. It called itself OMEGA."
    )

    sim = GameSim.new()
    sim.confirm_play_now()
    for expected_beat in range(1, len(PROLOGUE_BEATS)):
        sim.step(InputState(jump_pressed=True))
        assert sim.scene == "prologue"
        assert sim.story_beat == expected_beat - 1
        assert sim.story_ticks == len(sim.story_copy) * PROLOGUE_TYPE_TICKS
        sim.step(InputState(jump_pressed=True))
        assert sim.scene == "prologue"
        assert sim.story_beat == expected_beat
    for _ in range(PROLOGUE_BEAT_TICKS * 2):
        sim.step(InputState())
    assert sim.scene == "prologue", "the password screen must wait for input"
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "prologue"
    assert sim.story_transition_ticks == 1
    for _ in range(PROLOGUE_LOGIN_TRANSITION_TICKS):
        sim.step(InputState())
        if sim.scene == "stage-map":
            break
    assert sim.scene == "stage-map"
    assert sim.pending_chapter == 0


def test_stage_map_uses_spatial_navigation_and_non_linear_unlocks():
    sim = GameSim.from_play_now()
    sim._open_stage_map(0)
    assert sim.scene == "stage-map"
    assert sim.unlocked_stage_indices() == (0,)

    sim.step(InputState(left_pressed=True))
    assert sim.stage_cursor == 0, "the input that dismissed the prior screen must not select a stage"
    for _ in range(STAGE_MAP_TRANSITION_TICKS + STAGE_MAP_INPUT_LOCK_TICKS):
        sim.step(InputState())

    sim.step(InputState(left_pressed=True))
    assert sim.stage_cursor == 1
    sim.step(InputState(down_pressed=True))
    assert sim.stage_cursor == 3
    sim.step(InputState(right_pressed=True))
    assert sim.stage_cursor == 2
    sim.step(InputState(up_pressed=True))
    assert sim.stage_cursor == 0
    sim.step(InputState(right_pressed=True))
    assert sim.stage_cursor == 5
    sim.step(InputState(down_pressed=True))
    assert sim.stage_cursor == 4
    sim.step(InputState(left_pressed=True))
    assert sim.stage_cursor == 2
    sim.step(InputState(left_pressed=True))
    assert sim.stage_cursor == 3

    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "stage-map"
    assert sim.chapter_index == 0
    assert "LOCKED" in sim.messages[-1]

    sim.converted.append(CAMPAIGN_ROSTER[0].boss.id)
    assert sim.unlocked_stage_indices() == (0, 1, 2, 3)
    sim.stage_cursor = 3
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "action"
    assert sim.chapter_index == 3

    sim.converted.extend(CAMPAIGN_ROSTER[index].boss.id for index in (1, 2, 3))
    assert sim.unlocked_stage_indices() == (0, 1, 2, 3, 4)
    sim.converted.append(CAMPAIGN_ROSTER[4].boss.id)
    assert sim.unlocked_stage_indices() == (0, 1, 2, 3, 4, 5)


def test_boss_fifteen_warps_use_boss_geometry_for_current_and_goliath_levels():
    sim = GameSim.from_play_now()
    assert sim.body is not None

    resolved = sim.dev_warp("distro-front:boss-15")
    boss = next(entity for entity in sim.entities if entity.kind == "boss")
    gate = next(entity for entity in sim.entities if entity.kind == "boss-gate")
    player_center_tiles = (sim.body.x + sim.body.width / 2) / TILE
    boss_center_tiles = float(boss.extra.get("arena_x", boss.x)) + 0.5
    assert resolved == f"distro-front:boss-15:map-{sim.map_index + 1}"
    assert boss_center_tiles - player_center_tiles == 15
    assert sim.body.x < gate.x * TILE, "the encounter gate must remain available for QA"

    resolved = sim.dev_warp("goliath-amalgam:boss-15")
    boss = next(entity for entity in sim.entities if entity.kind == "boss")
    player_center_tiles = (sim.body.x + sim.body.width / 2) / TILE
    boss_center_tiles = float(boss.extra.get("arena_x", boss.x)) + 0.5
    assert resolved == f"goliath-amalgam:boss-15:map-{sim.map_index + 1}"
    assert sim.chapter_index == len(CAMPAIGN_ROSTER) - 1
    assert boss_center_tiles - player_center_tiles == 15


def test_goliath_field_encounter_runs_penguin_duel_minions_then_surrender():
    sim = GameSim.from_play_now()
    sim.dev_warp("goliath-amalgam:boss-15")
    boss = next(entity for entity in sim.entities if entity.kind == "boss")

    assert sim.goliath_stage == "penguin"
    assert boss.extra["behavior"] == "cyber-penguin"
    assert boss.extra["ability"] == "malware-fish"
    assert boss.extra["hp"] == BOSS_FIELD_HEALTH
    assert boss.extra["base_cooldown"] == 64 * GOLIATH_FIRE_INTERVAL_MULTIPLIER

    assert sim._damage_side_enemy(boss, BOSS_FIELD_HEALTH)
    assert sim.goliath_stage == "duel"
    assert boss.extra["converted"] is False
    assert boss.extra["hp"] == BOSS_FIELD_HEALTH
    assert boss.extra["ability"] == BOSS_BEHAVIORS["goliath"][2]
    assert boss.extra["base_cooldown"] == (
        BOSS_BEHAVIORS["goliath"][1] * GOLIATH_FIRE_INTERVAL_MULTIPLIER
    )

    assert sim._damage_side_enemy(boss, BOSS_FIELD_HEALTH)
    minions = [entity for entity in sim.entities if entity.extra.get("goliath_minion")]
    assert sim.goliath_stage == "minions"
    assert boss.extra["converted"] is True
    assert len(minions) == 2
    assert {entity.extra["behavior"] for entity in minions} == {"jump", "fly-shoot"}
    sim._patrol_enemies()
    assert all(isinstance(entity.x, int) for entity in minions)
    assert "goliath" not in sim.converted
    assert sim.ending is False

    for index, minion in enumerate(minions, start=1):
        assert sim._damage_side_enemy(minion, 5)
        assert sim.goliath_minions_defeated == index
        assert sim.ending is (index == 2)
    assert sim.goliath_stage == "surrendered"
    assert "goliath" in sim.converted
    assert sim.scene == "ending"
    assert any("surrenders" in message for message in sim.messages)


def test_goliath_rpg_conversion_advances_one_phase_instead_of_ending_early():
    sim = GameSim.from_play_now()
    sim.dev_warp("goliath-amalgam:boss-15")
    assert sim.body is not None
    boss = next(entity for entity in sim.entities if entity.kind == "boss")
    gate = next(entity for entity in sim.entities if entity.kind == "boss-gate")
    sim.body = replace(sim.body, x=(gate.x + 1) * TILE + 1)
    sim._tick_boss_gates()

    sim._begin_combat(boss, boss=True)
    assert sim.combat is not None
    assert sim.combat.foe.id == "goliath-cyborg-penguin"
    sim.combat = replace(sim.combat, foe=replace(sim.combat.foe, converted=True))
    sim._finish_combat(converted=True)
    assert sim.goliath_stage == "duel"
    assert sim.scene == "action"
    assert "goliath" not in sim.converted

    sim._begin_combat(boss, boss=True)
    assert sim.combat is not None
    assert sim.combat.foe.id == "goliath"
    sim.combat = replace(sim.combat, foe=replace(sim.combat.foe, converted=True))
    sim._finish_combat(converted=True)
    assert sim.goliath_stage == "minions"
    assert len([entity for entity in sim.entities if entity.extra.get("goliath_minion")]) == 2
    assert sim.ending is False


def test_five_omega_blocks_open_a_door_to_the_cow_level():
    sim = GameSim.from_play_now()
    omega_blocks = [
        (map_index, entity)
        for map_index, entities in enumerate(sim.chapter_map_entities)
        for entity in entities
        if entity.kind == "omega-block"
    ]
    assert len(omega_blocks) == len(OMEGA_LETTERS)
    assert {str(entity.extra["letter"]) for _, entity in omega_blocks} == set(OMEGA_LETTERS)
    assert all(
        sim._omega_block_has_attack_position(
            sim.chapter_map_tiles[map_index], int(entity.x), int(entity.y)
        )
        for map_index, entity in omega_blocks
    )

    for map_index, entity in omega_blocks:
        sim._activate_map(map_index, reset_body=True)
        sim._trigger_block(entity)
    assert sim.omega_letters == OMEGA_LETTERS
    assert all(entity.alive for _, entity in omega_blocks)
    assert all(sim.chapter_map_tiles[map_index][int(entity.y)][int(entity.x)] == "B" for map_index, entity in omega_blocks)

    door = next(
        entity
        for entity in sim.entities
        if entity.kind == "omega-door" and not entity.extra.get("exit")
    )
    assert sim.body is not None
    sim.body = replace(
        sim.body,
        x=door.x * TILE + 3,
        y=(door.y + 1) * TILE - sim.body.height,
        vx=0.0,
        vy=0.0,
        on_ground=True,
    )
    sim.step(InputState(up=True, up_pressed=True))
    assert sim.map_index == sim.secret_map_index
    assert sim.active_palette == "cow"
    assert sim.omega_letters == "", "the Cow Level begins a fresh OMEGA accounting run"
    assert sim.omega_door_spawned, "resetting OMEGA must not revoke the existing route"
    animals = [
        entity
        for entity in sim.entities
        if entity.kind == "enemy" and entity.extra.get("friendly_animal")
    ]
    assert len(animals) >= 6
    assert {str(entity.extra.get("variant")) for entity in animals} == {"cow", "llama"}

    cow = next(entity for entity in animals if entity.extra.get("variant") == "cow")
    sim._damage_side_enemy(cow, 0.1, item="patch-cable")
    assert cow.extra.get("converted") is True
    assert cow.extra.get("companion") is True
    assert "cow" in sim.active_companions


def test_cow_level_breaks_up_its_foundation_with_a_step_and_low_ground():
    spec = GameSim._cow_level_spec()
    tiles = spec["tiles"]
    floor = COW_LEVEL_FLOOR
    assert len(tiles) == 36 and len(tiles[0]) == 236
    assert all(tiles[floor - 1][x] == "#" for x in range(45, 51))
    assert all(tiles[floor][x] == "." for x in range(90, 97))
    assert sum(row.count("B") for row in tiles) >= 35
    assert sum(row[108:].count("B") for row in tiles) >= 15
    assert sum(row[108:].count("C") for row in tiles) >= 20
    assert all(
        tiles[y + 1][x] in "#=+BDG"
        for y, row in enumerate(tiles[:-1])
        for x, cell in enumerate(row)
        if cell == "P"
    ), "bonus-stage penguins must use ordinary supported placement"


def test_cow_cannon_loads_aims_charges_and_breaks_unbreakable_contacts():
    sim = GameSim.from_play_now()
    sim.dev_warp("cow")
    assert sim.body is not None
    cannon = next(entity for entity in sim.entities if entity.kind == "cow-cannon")
    assert CANNON_MAX_POWER == 19.8
    low_geometry = cow_cannon_geometry(cannon, 16.0)
    high_geometry = cow_cannon_geometry(cannon, 68.0)
    assert low_geometry["base"] == high_geometry["base"]
    assert low_geometry["pivot"] == high_geometry["pivot"]
    assert low_geometry["muzzle"] != high_geometry["muzzle"]
    hatch_x, hatch_y = cow_cannon_geometry(cannon, sim.cannon_angle)["hatch"]
    sim.body = replace(
        sim.body,
        x=hatch_x + 18 - sim.body.width / 2,
        y=hatch_y - 10 - sim.body.height / 2,
        vx=0.0,
        vy=1.0,
        on_ground=False,
    )
    sim.step(InputState())
    assert sim.cannon_loaded
    assert sim.cannon_entry_lock_ticks == CANNON_ENTRY_LOCK_TICKS

    # A held entry jump cannot spill into charge; a fresh post-lock press can.
    sim.step(InputState(jump=True, jump_pressed=True))
    for _ in range(CANNON_ENTRY_LOCK_TICKS - 1):
        sim.step(InputState(jump=True))
    assert sim.cannon_charge_ticks == 0
    sim.step(InputState())
    start_angle = sim.cannon_angle
    sim.step(InputState(up=True, jump=True, jump_pressed=True))
    for _ in range(11):
        sim.step(InputState(up=True, jump=True))
    assert sim.cannon_angle > start_angle
    assert sim.cannon_charge_ticks == 12
    assert sim.cannon_charge_ticks < CANNON_MAX_CHARGE_TICKS

    sim.step(InputState())
    assert sim.cannon_launch_active and not sim.cannon_loaded
    assert sim.body.vx > 0 and sim.body.vy < 0
    tx = int((sim.body.x + sim.body.width + sim.body.vx) // TILE)
    ty = int((sim.body.y + sim.body.height / 2) // TILE)
    row = list(sim.tiles[ty])
    row[tx] = "#"
    sim.tiles[ty] = "".join(row)
    sim._cannon_break_path()
    assert sim.tiles[ty][tx] == ".", "forward cannon motion must break even foundation material"

    down_tx = int(sim.body.center[0] // TILE)
    down_ty = int((sim.body.y + sim.body.height + 3) // TILE)
    row = list(sim.tiles[down_ty])
    row[down_tx] = "#"
    sim.tiles[down_ty] = "".join(row)
    sim.body = replace(sim.body, vx=0.0, vy=3.0)
    sim._cannon_break_path()
    assert sim.tiles[down_ty][down_tx] == "#", "downward-only contact must retain landing collision"

    sim.body = replace(
        sim.body,
        x=4 * TILE,
        y=COW_LEVEL_FLOOR * TILE - sim.body.height,
        vx=0.0,
        vy=0.0,
        on_ground=True,
    )
    sim.cannon_launch_active = True
    sim.cannon_launch_ticks = 5
    sim._step_action(InputState())
    assert not sim.cannon_launch_active
    assert all("CANNON RUN COMPLETE" not in message for message in sim.messages)


def test_all_generated_bosses_have_triple_field_health():
    sim = GameSim.from_play_now()
    for chapter_index in range(len(CAMPAIGN_ROSTER)):
        sim._load_chapter(chapter_index)
        boss = next(
            entity
            for entities in sim.chapter_map_entities
            for entity in entities
            if entity.kind == "boss"
        )
        assert boss.extra["hp"] == BOSS_FIELD_HEALTH == 30
        assert boss.extra["max_hp"] == BOSS_FIELD_HEALTH


def test_bs_resets_at_each_chapter_and_secret_level_start():
    sim = GameSim.from_play_now()
    sim.player_bs = 77
    sim._load_chapter(1)
    assert sim.player_bs == 0
    sim.player_bs = 64
    sim._enter_secret_level()
    assert sim.player_bs == 0


def test_reset_omega_blocks_do_not_clone_the_unlocked_cow_door():
    sim = GameSim.from_play_now()
    omega_blocks = [
        (map_index, entity)
        for map_index, entities in enumerate(sim.chapter_map_entities)
        for entity in entities
        if entity.kind == "omega-block"
    ]
    for map_index, entity in omega_blocks:
        sim._activate_map(map_index, reset_body=True)
        sim._trigger_block(entity)
    assert sim.omega_door_spawned
    door_map = sim.omega_door_map
    refreshed = omega_blocks[0][1]
    sim._trigger_block(refreshed)
    assert sum(entity.kind == "omega-door" and not entity.extra.get("exit") for entity in sim.entities) == 1
    assert sim.omega_door_map == door_map


def test_three_score_chains_have_distinct_names_and_bonuses():
    sim = GameSim.from_play_now()
    combinations = (
        (("socket", "pickup"), "PACKAGE SOCKET", 250),
        (("capability", "pickup"), "CAPABILITY CIRCUIT", 350),
        (("proof", "momentum"), "PROOF × MOMENTUM", 300),
    )
    running_score = 0
    for events, expected_name, bonus in combinations:
        sim.combo_events.clear()
        for event in events:
            sim._score_combo_event(event, x=24, y=32)
        running_score += bonus
        assert sim.combo_name == expected_name
        assert sim.score == running_score
        assert any(expected_name in message for message in sim.messages)


def test_boss_field_profiles_move_and_emit_their_named_abilities():
    sim = GameSim.from_play_now()
    boss = next(entity for entity in sim.entities if entity.kind == "boss")
    boss_id = str(boss.extra["boss"])
    _, _, ability = BOSS_BEHAVIORS[boss_id]
    assert sim.body is not None
    sim.body = replace(sim.body, x=boss.x * TILE - TILE * 3, y=boss.y * TILE - 18)
    boss.extra["ability_cooldown"] = 1
    initial = (boss.x, float(boss.extra.get("offset_y") or 0.0))
    gate = next(entity for entity in sim.entities if entity.kind == "boss-gate")
    sim.body = replace(sim.body, x=(gate.x + 1) * TILE + 1)
    sim._tick_boss_gates()
    sim._tick_boss_behaviors()

    assert (boss.x, float(boss.extra.get("offset_y") or 0.0)) != initial
    assert sim.enemy_projectiles
    assert {shot.get("style") for shot in sim.enemy_projectiles} == {ability}


def test_every_boss_ability_has_a_distinct_field_pattern():
    expected_shots = {
        "forms": 3,
        "version-volley": 5,
        "banner-wave": 2,
        "lock-pulse": 8,
        "gravity-shard": 2,
        "argument-storm": 7,
    }
    for chapter_index, spec in enumerate(CAMPAIGN_ROSTER):
        sim = GameSim.from_play_now()
        sim._load_chapter(chapter_index)
        assert sim.body is not None
        boss = Entity(
            "boss",
            10,
            8,
            extra={
                "boss": spec.boss.id,
                "hp": 10,
                "max_hp": 10,
                "behavior": BOSS_BEHAVIORS[spec.boss.id][0],
                "ability_cooldown": 1,
                "home_x": 10,
                "home_y": 8,
            },
        )
        sim.entities = [boss]
        sim.body = replace(sim.body, x=8 * TILE, y=8 * TILE - 18)
        sim.enemy_projectiles = []
        sim._tick_boss_behaviors()
        ability = BOSS_BEHAVIORS[spec.boss.id][2]
        assert len(sim.enemy_projectiles) == expected_shots[ability]
        assert {shot["style"] for shot in sim.enemy_projectiles} == {ability}


def test_cow_warp_is_a_direct_deterministic_playtest_entry():
    sim = GameSim.from_play_now()
    resolved = sim.dev_warp("cow")
    assert resolved.endswith(":cow")
    assert sim.developer_mode is True
    assert sim.active_palette == "cow"


def test_cow_level_animals_do_not_persist_through_the_exit_door():
    sim = GameSim.from_play_now()
    sim.dev_warp("cow")
    sim.converted.extend(["cow", "llama"])
    sim._spawn_persistent_companions()
    assert {"cow", "llama"}.issubset(set(sim.active_companions))
    sim._leave_secret_level()
    assert "cow" not in sim.active_companions and "llama" not in sim.active_companions
    assert not any(
        entity.extra.get("companion") and entity.extra.get("variant") in {"cow", "llama"}
        for entity in sim.entities
    )


def test_persistent_helpers_return_from_cow_level_at_the_players_saved_position():
    sim = GameSim.from_play_now()
    assert sim.body is not None
    sim.converted.extend(["justice-signaler", "detractabot"])
    sim.body = replace(sim.body, x=34 * TILE, y=sim.body.y)
    return_x = sim.body.x
    sim._enter_secret_level()
    sim._leave_secret_level()
    assert sim.body is not None and sim.body.x == return_x
    helpers = [entity for entity in sim.entities if entity.extra.get("companion")]
    assert {entity.extra.get("variant") for entity in helpers} == {"justice-signaler", "detractabot"}
    assert all(abs(entity.x * TILE - sim.body.center[0]) < 4 * TILE for entity in helpers)


def test_completed_omega_route_spawns_on_a_nearby_visible_surface():
    sim = GameSim.from_play_now()
    assert sim.body is not None
    sim.tiles = ["." * 30, "." * 30, "." * 30, "." * 30, "#" * 30]
    sim.original_tiles = list(sim.tiles)
    sim.entities = []
    sim.body = replace(sim.body, x=10 * TILE, y=4 * TILE - sim.body.height)
    sim.cam_x = 5 * TILE
    sim.omega_letters = OMEGA_LETTERS
    door = sim._spawn_omega_door()
    assert door is not None
    assert abs(door.x * TILE - sim.body.center[0]) <= 6 * TILE
    assert sim.cam_x <= door.x * TILE <= sim.cam_x + 320
