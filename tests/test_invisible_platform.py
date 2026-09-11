from dataclasses import replace

import pytest

from omega_omarchy.invisible_platform import platform_alpha
from omega_omarchy.physics import Body, InputState, TILE, step_body
from omega_omarchy.reachability import reachable_from


def body(x=0, y=0):
    return Body(x=x, y=y, vx=0, vy=0, on_ground=False, coyote=0, buffer=0, facing=1)


def test_hidden_platform_collides_and_can_be_stood_on():
    tiles = [".........." for _ in range(8)] + ["....III..."] + ["..........", "##########"]
    player = body(5 * TILE, 3 * TILE)
    assert platform_alpha(player, 5, 8, 200, reduced_motion=True) == 0
    for _ in range(90):
        player = step_body(player, InputState(), tiles)
    assert player.on_ground and player.feet[1] == pytest.approx(8 * TILE, abs=1e-5)
    assert platform_alpha(player, 5, 8, 200) == 235
    assert (5, 7) in reachable_from(tiles, (4, 7))


@pytest.mark.parametrize("player", [body(4 * TILE - 10, 8 * TILE - 18), body(4 * TILE, 8 * TILE + 16), body(5 * TILE, 8 * TILE - 18)])
def test_adjacent_shoulder_head_and_standing_reveal_immediately(player):
    assert platform_alpha(player, 4, 8, 300) == 235


def test_far_platform_has_a_short_faint_shimmer_every_six_seconds():
    player = body()
    alphas = [platform_alpha(player, 12, 10, tick, run_x=11) for tick in range(360)]
    assert sum(alpha > 0 for alpha in alphas) == 12
    assert max(alphas) <= 56
    assert all(platform_alpha(player, 12, 10, tick, reduced_motion=True) == 0 for tick in range(1200))
    near = replace(player, x=12 * TILE, y=10 * TILE - 18)
    assert platform_alpha(near, 12, 10, 0, reduced_motion=True) == 235
    assert platform_alpha(player, 12, 10, 200) == 0, "leaving the platform must hide it again"
