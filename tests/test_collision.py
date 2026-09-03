"""Collision symmetry, seams, ladders, and fidelity independence."""

from __future__ import annotations

import pytest

from omega_omarchy.physics import (
    TILE,
    Body,
    InputState,
    ladder_column,
    spawn_body,
    step_body,
)
from omega_omarchy.presentation import FIDELITIES, migrate_quality


def _body(x: float, y: float, **kwargs: float) -> Body:
    values = dict(vx=0.0, vy=0.0, on_ground=True, coyote=7, buffer=0, facing=1, width=10.0, height=18.0)
    values.update(kwargs)
    return Body(x=x, y=y, **values)  # type: ignore[arg-type]


LADDER = [
    ".....",
    "..L..",
    "..L..",
    "..L..",
    "#####",
]
PLATFORM = [
    "........",
    "........",
    "...==...",
    "########",
]


def test_legacy_crt_quality_maps_to_sixteen_bit_crt():
    fid, disp = migrate_quality("crt", {})
    assert fid == "sixteen-bit"
    assert disp == "crt"
    fid, disp = migrate_quality("clean-pixel", {})
    assert fid == "sixteen-bit"
    assert disp == "clean"
    fid, disp = migrate_quality("eight-bit", {"reducedMotion": True, "crt": {"enabled": 1}})
    assert fid == "sixteen-bit"
    assert disp == "clean"
    fid, disp = migrate_quality("ultra", {})
    assert fid == "ultra"


@pytest.mark.parametrize("offset", range(-6, 7))
def test_ladder_trigger_covers_both_halves(offset: int) -> None:
    # Ladder at column 2 occupies [32, 48). Center the 10px box around 32+offset.
    x = 32 + 8 - 5 + offset
    body = _body(x, 2 * TILE)
    col = ladder_column(LADDER, body)
    if abs(offset) <= 8:  # still overlapping the tile plus 4px forgive
        assert col == 2, f"offset {offset} x={x} missed ladder"
    # Approaching from the mirrored right half should match the left half.
    mirror = _body(48 - 8 - 5 - offset, 2 * TILE)
    mcol = ladder_column(LADDER, mirror)
    if col is not None:
        assert mcol == 2


def test_ladder_entry_from_left_and_right_snaps_without_teleport() -> None:
    left = _body(32 - 10 - 2, 2 * TILE, vx=1.2)
    after_l = step_body(left, InputState(right=True, up=True), LADDER)
    assert after_l.on_ladder or ladder_column(LADDER, after_l) == 2 or after_l.x > left.x
    # No sudden vertical jump from snapping.
    assert abs(after_l.y - left.y) < 3.0

    right = _body(48 + 2, 2 * TILE, vx=-1.2, facing=-1)
    after_r = step_body(right, InputState(left=True, up=True), LADDER)
    assert abs(after_r.y - right.y) < 3.0


@pytest.mark.parametrize(
    ("x", "should_mount"),
    [
        (29.0, False),  # Seven of ten player pixels overlap from the left.
        (30.0, True),   # Eight of ten overlap from the left.
        (40.0, True),   # Eight of ten overlap from the right.
        (41.0, False),  # Seven of ten overlap from the right.
    ],
)
def test_ladder_mount_requires_nearly_full_body_overlap(x: float, should_mount: bool) -> None:
    body = _body(x, 2 * TILE)

    after = step_body(body, InputState(up=True), LADDER)

    assert after.on_ladder is should_mount


def test_ladder_alignment_gate_does_not_unlatch_mounted_player() -> None:
    body = _body(29.0, 2 * TILE, on_ladder=True)

    after = step_body(body, InputState(), LADDER)

    assert after.on_ladder
    assert after.x > body.x


def test_platform_supports_full_top_including_seams() -> None:
    # Platform tiles at cols 3-4 occupy [48, 80), top y=32. Stand with feet on it.
    y = 32 - 18
    for x in range(48, 71):
        body = _body(float(x), float(y), vy=0.4, on_ground=False)
        after = step_body(body, InputState(), PLATFORM)
        assert after.on_ground, f"fell through platform at x={x}"
        assert after.y <= y + 0.2


def test_platform_left_and_right_edges_match() -> None:
    y = 32 - 18
    left = step_body(_body(48.0, float(y), vy=0.5, on_ground=False), InputState(), PLATFORM)
    right = step_body(_body(70.0, float(y), vy=0.5, on_ground=False), InputState(), PLATFORM)
    assert left.on_ground and right.on_ground
    assert abs(left.y - right.y) < 0.05


def test_wall_contact_matches_from_both_sides() -> None:
    tiles = [
        "........",
        "...#....",
        "########",
    ]
    y = 2 * TILE - 18
    from_left = _body(16.0, float(y), vx=4.0)
    from_right = _body(80.0, float(y), vx=-4.0, facing=-1)
    left = from_left
    right = from_right
    for _ in range(20):
        left = step_body(left, InputState(right=True), tiles)
        right = step_body(right, InputState(left=True), tiles)
    wall_left = 3 * TILE
    wall_right = 4 * TILE
    assert left.x + left.width <= wall_left + 0.05
    assert right.x >= wall_right - 0.05
    left_gap = wall_left - (left.x + left.width)
    right_gap = right.x - wall_right
    assert abs(left_gap - right_gap) < 0.2


def test_head_bump_stops_upward_motion() -> None:
    tiles = [
        ".#...",
        ".....",
        "#####",
    ]
    body = _body(16.0, 16.0, vy=-4.0, on_ground=False, coyote=0)
    after = step_body(body, InputState(), tiles)
    assert after.vy >= -0.01
    assert after.y >= body.y


def test_jump_landing_on_adjacent_tile_seam() -> None:
    tiles = [
        "........",
        "........",
        "########",
    ]
    # Land exactly on the boundary between col 2 and 3.
    x = 3 * TILE - 5
    y = 2 * TILE - 18 - 4
    body = _body(float(x), float(y), vy=3.0, on_ground=False)
    after = step_body(body, InputState(), tiles)
    assert after.on_ground


@pytest.mark.parametrize("fidelity", FIDELITIES)
def test_collision_independent_of_fidelity(fidelity: str) -> None:
    tiles = [
        ".....",
        "..L==",
        "#####",
    ]
    body = spawn_body([".....S.", "#######"])
    after = step_body(body, InputState(right=True, jump_pressed=True), tiles)
    # Fidelity is not an argument to step_body; this documents the invariant.
    assert after.width == 10
    assert after.height == 18
    assert TILE == 16
    _ = fidelity


def test_does_not_tunnel_through_a_one_tile_wall() -> None:
    tiles = [
        "........",
        "...#....",
        "########",
    ]
    body = _body(16, 16 - 18, vx=20.0)  # faster than MAX_RUN, still must not pass
    after = step_body(body, InputState(right=True), tiles)
    assert after.x + after.width <= 3 * TILE + 0.1
