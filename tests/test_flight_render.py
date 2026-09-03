import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from omega_omarchy.render import Renderer
from omega_omarchy.sim import GameSim


def test_flight_scene_draws_preset_flight_asset():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim.quality = "sixteen-bit"
    sim.fidelity = "sixteen-bit"
    sim._begin_flight()
    renderer = Renderer()
    renderer.frame(sim)
    cached = " ".join(renderer.cache)
    assert "flight" in cached
    assert "david_side-idle" not in cached.split("flight")[0] or "flight.png" in cached
    pygame.quit()


def test_flight_endpoint_matches_the_bottom_aligned_edit_sprite():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim._begin_flight()
    sim.flight_ticks = 1
    renderer = Renderer()
    renderer.frame(sim)
    ots, x, y = renderer._ots_layout(sim)
    assert x == 4 * renderer._vs
    assert y + ots.get_height() == renderer._ih
    pygame.quit()


def test_flight_leaves_a_translucent_grayscale_pose_in_the_world():
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    sim._begin_flight()
    renderer = Renderer()
    renderer.frame(sim)
    ghost = pygame.Surface((renderer._iw, renderer._ih), pygame.SRCALPHA)
    renderer._edit_ghost(ghost, sim, int(sim.cam_x), int(sim.cam_y))
    colored = [ghost.get_at((x, y)) for y in range(ghost.get_height()) for x in range(ghost.get_width())]
    visible = [pixel for pixel in colored if pixel.a]
    assert visible
    assert all(pixel.r == pixel.g == pixel.b for pixel in visible)
    assert max(pixel.a for pixel in visible) <= 138
    pygame.quit()
