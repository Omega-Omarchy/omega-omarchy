from omega_omarchy.physics import (
    AIR_JUMP_VEL,
    LADDER_SLIDE_SPEED,
    MAX_RUN,
    MOMENTUM_SLIDE_FRAMES,
    SLIDE_FRAMES,
    TILE,
    Body,
    InputState,
    step_body,
)


def _body(x: float, y: float, **kwargs: float) -> Body:
    values = dict(vx=0.0, vy=0.0, on_ground=True, coyote=7, buffer=0, facing=1)
    values.update(kwargs)
    return Body(x=x, y=y, **values)  # type: ignore[arg-type]


def test_step_body_climbs_ladder():
    tiles = [
        ".....",
        "..L..",
        "..L..",
        "..L..",
        "..#..",
    ]
    body = _body(2 * TILE + 3, 3 * TILE - 4)
    after = step_body(body, InputState(up=True), tiles)
    assert after.y < body.y
    down = step_body(after, InputState(down=True), tiles)
    assert down.y > after.y


def test_ladder_climb_latches_without_holding_up_and_jump_detaches():
    tiles = [
        ".....",
        "..L..",
        "..L..",
        "..L..",
        "..#..",
    ]
    body = _body(2 * TILE + 3, 3 * TILE - 4)
    climbing = step_body(body, InputState(up=True), tiles)
    assert climbing.on_ladder
    held = step_body(climbing, InputState(), tiles)
    assert held.on_ladder
    assert abs(held.y - climbing.y) < 0.01
    assert held.vy == 0
    jumped = step_body(held, InputState(jump_pressed=True), tiles)
    assert jumped.vy < 0
    assert not jumped.on_ladder


def test_step_body_bounces_on_bumper():
    tiles = [
        ".....",
        ".....",
        "..^..",
        "#####",
    ]
    body = _body(2 * TILE + 3, 2 * TILE + 2, vy=1.2, on_ground=False, coyote=0)
    after = step_body(body, InputState(), tiles)
    assert after.vy < 0


def test_down_direction_pushes_into_crouch_slide_without_moving_feet():
    tiles = [".....", ".....", ".....", "#####"]
    body = _body(2 * TILE + 3, 3 * TILE - 18)
    feet_before = body.feet[1]
    after = step_body(body, InputState(down=True, right=True, right_pressed=True), tiles)
    assert after.crouching and after.sliding
    assert after.height == 12
    assert after.vx > 3
    assert abs(after.feet[1] - feet_before) < 0.01


def test_ladder_can_dismount_horizontally_onto_platform_at_foot_level():
    tiles = [
        ".....",
        "..L..",
        "..L..",
        "..L=.",
        "#####",
    ]
    body = _body(2 * TILE + 3, 3 * TILE - 18, on_ladder=True)
    after = step_body(body, InputState(right=True), tiles)
    assert not after.on_ladder
    assert after.x > body.x


def test_airborne_jump_adds_height_once():
    tiles = [".....", ".....", ".....", "#####"]
    body = _body(2 * TILE + 3, 3 * TILE - 18)
    first = step_body(body, InputState(jump=True, jump_pressed=True), tiles)
    boosted = step_body(first, InputState(jump=True, jump_pressed=True), tiles)
    spent = step_body(boosted, InputState(jump=True, jump_pressed=True), tiles)
    assert boosted.vy <= AIR_JUMP_VEL
    assert boosted.air_jump_used
    assert spent.vy > boosted.vy, "a third press should receive gravity, not another air jump"


def test_double_tap_direction_starts_a_short_rush():
    tiles = [".......", ".......", ".......", "#######"]
    body = _body(2 * TILE + 3, 3 * TILE - 18)
    first = step_body(body, InputState(right=True, right_pressed=True), tiles)
    coast = step_body(first, InputState(), tiles)
    rushed = step_body(coast, InputState(right=True, right_pressed=True), tiles)
    assert rushed.rushing
    assert rushed.rush_ticks > 0
    assert rushed.vx > MAX_RUN


def test_double_tap_rush_persists_while_forward_is_held_then_stops_on_release():
    tiles = ["...........", "...........", "...........", "###########"]
    body = _body(2 * TILE + 3, 3 * TILE - 18)
    body = step_body(body, InputState(right=True, right_pressed=True), tiles)
    body = step_body(body, InputState(), tiles)
    body = step_body(body, InputState(right=True, right_pressed=True), tiles)
    for _ in range(30):
        body = step_body(body, InputState(right=True), tiles)
    assert body.rushing and body.rush_ticks > 0
    released = step_body(body, InputState(), tiles)
    assert not released.rushing and released.rush_ticks == 0


def test_direction_then_down_also_starts_push_off_slide():
    tiles = [".....", ".....", ".....", "#####"]
    body = _body(2 * TILE + 3, 3 * TILE - 18)
    after = step_body(body, InputState(down=True, down_pressed=True, left=True), tiles)
    assert after.crouching and after.sliding
    assert after.facing == -1 and after.vx < -3


def test_ladder_end_controls_do_not_remount_outward():
    tiles = [
        ".......",
        ".......",
        "...+...",
        "...L...",
        "...L...",
        "...+...",
        "#######",
    ]
    top = _body(3 * TILE + 3, 2 * TILE - 18)
    assert not step_body(top, InputState(up=True), tiles).on_ladder
    assert step_body(top, InputState(down=True), tiles).on_ladder

    bottom = _body(3 * TILE + 3, 5 * TILE - 18)
    assert not step_body(bottom, InputState(down=True), tiles).on_ladder
    assert step_body(bottom, InputState(up=True), tiles).on_ladder


def test_down_jump_slides_ladder_without_advancing_climb_pose():
    tiles = [
        ".......",
        "...+...",
        "...L...",
        "...L...",
        "...L...",
        "...+...",
        "#######",
    ]
    body = _body(3 * TILE + 3, 3 * TILE, on_ground=True, on_ladder=True, climb_phase=2, climb_ticks=4)
    after = step_body(body, InputState(down=True, jump=True, jump_pressed=True), tiles)
    assert after.on_ladder and after.ladder_sliding
    assert after.vy == LADDER_SLIDE_SPEED
    assert after.climb_phase == 2 and after.climb_ticks == 4
    continued = step_body(after, InputState(down=True, jump=True), tiles)
    assert continued.on_ladder and continued.ladder_sliding
    assert continued.climb_phase == 2 and continued.climb_ticks == 4


def test_ladder_platform_crossing_is_walkable_and_mountable():
    tiles = [
        ".......",
        "...L...",
        "...L...",
        "===+===",
        "...L...",
        "...+...",
        "#######",
    ]
    standing = _body(1 * TILE + 3, 3 * TILE - 18)
    walked = step_body(standing, InputState(right=True), tiles)
    for _ in range(20):
        walked = step_body(walked, InputState(right=True), tiles)
    assert walked.x > 3 * TILE, "the crossing must support an uninterrupted walk"

    above_crossing = _body(3 * TILE + 3, 3 * TILE - 18)
    mounted = step_body(above_crossing, InputState(down=True), tiles)
    assert mounted.on_ladder


def test_down_alone_is_inert_and_never_changes_standing_height():
    tiles = [".....", ".....", ".....", "#####"]
    body = _body(2 * TILE + 3, 3 * TILE - 18)
    after = step_body(body, InputState(down=True, down_pressed=True), tiles)
    assert not after.crouching and not after.sliding and not after.slide_locked
    assert after.height == body.height == 18
    assert abs(after.feet[0] - body.feet[0]) < 0.001
    assert abs(after.feet[1] - body.feet[1]) < 0.001


def test_held_slide_combo_locks_in_place_until_released():
    tiles = ["...........", "...........", "...........", "###########"]
    body = _body(2 * TILE + 3, 3 * TILE - 18)
    body = step_body(body, InputState(down=True, right=True, right_pressed=True), tiles)
    for _ in range(SLIDE_FRAMES + 2):
        body = step_body(body, InputState(down=True, right=True), tiles)
    assert body.slide_locked and not body.sliding
    assert not body.crouching and body.height == 18 and body.vx == 0
    locked_x = body.x
    body = step_body(body, InputState(down=True, right=True), tiles)
    assert body.x == locked_x and body.vx == 0
    released = step_body(body, InputState(), tiles)
    assert not released.slide_locked and not released.crouching
    assert released.height == 18


def test_airborne_double_tap_cannot_start_or_continue_a_rush():
    tiles = ["...........", "...........", "...........", "###########"]
    body = _body(
        2 * TILE + 3,
        TILE,
        on_ground=False,
        rushing=True,
        tap_direction=1,
        tap_ticks=8,
        vx=4.0,
    )
    after = step_body(body, InputState(right=True, right_pressed=True), tiles)
    assert not after.rushing
    assert after.rush_ticks == 0


def test_sprinting_into_a_slide_preserves_extra_momentum_duration():
    tiles = ["...........", "...........", "...........", "###########"]
    body = _body(2 * TILE + 3, 3 * TILE - 18, rushing=True, rush_ticks=11, vx=4.35)
    after = step_body(body, InputState(down=True, right=True, down_pressed=True), tiles)
    assert after.sliding
    assert after.slide_ticks == MOMENTUM_SLIDE_FRAMES
    assert after.slide_ticks > SLIDE_FRAMES


def test_slide_cannot_cancel_until_the_standing_hitbox_clears_an_overhang():
    tiles = [
        ".........",
        ".........",
        "..###....",
        ".........",
        "#########",
    ]
    body = _body(
        2 * TILE + 3,
        4 * TILE - 12,
        height=12,
        vx=2.0,
        sliding=True,
        slide_ticks=0,
    )
    for _ in range(30):
        body = step_body(body, InputState(), tiles)
        if body.x + body.width <= 5 * TILE:
            assert body.sliding and body.height == 12
        if not body.sliding:
            break
    assert body.x >= 5 * TILE
    assert not body.sliding and body.height == 18


def test_ladder_deck_is_one_way_for_jump_and_lands_on_descent():
    tiles = [
        ".......",
        ".......",
        "===+===",
        "...L...",
        "...L...",
        "#######",
    ]
    body = _body(3 * TILE + 3, 5 * TILE - 18)
    body = step_body(body, InputState(jump=True, jump_pressed=True), tiles)
    emerged_above = False
    for _ in range(55):
        body = step_body(body, InputState(), tiles)
        emerged_above = emerged_above or body.feet[1] < 2 * TILE - 0.1
    assert emerged_above, "an ordinary jump must pass through the crossing from below"
    assert body.on_ground
    assert abs(body.feet[1] - 2 * TILE) < 0.01


def test_climbing_straight_up_always_emerges_standing_on_crossing():
    tiles = [
        ".......",
        ".......",
        "===+===",
        "...L...",
        "...L...",
        "#######",
    ]
    body = _body(3 * TILE + 3, 4 * TILE - 8, on_ladder=True)
    for _ in range(30):
        body = step_body(body, InputState(up=True), tiles)
        if body.on_ground and not body.on_ladder and abs(body.feet[1] - 2 * TILE) < 0.01:
            break
    assert body.on_ground and not body.on_ladder
    assert abs(body.feet[1] - 2 * TILE) < 0.01
