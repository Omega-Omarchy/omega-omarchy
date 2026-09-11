import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from omega_omarchy.render import Renderer, background_parallax_y, parallax_offset


def test_parallax_offset_is_finite_and_never_wraps():
    assert parallax_offset(1500, 320, 0, 4000, 1.0) == 0
    assert parallax_offset(1500, 320, 4000, 4000, 1.0) == -1180
    assert -1180 <= parallax_offset(1500, 320, 2000, 4000, 0.4) <= 0


def test_background_parallax_y_scales_with_climb_height():
    short = abs(background_parallax_y(0, 200, 0.58, 1))
    tall = abs(background_parallax_y(0, 800, 0.58, 1))
    assert tall > short
    assert tall > 40


def test_authored_parallax_travel_advances_at_walking_cadence():
    # Ultra's far strip is 4230 px wide over a 960 px viewport. At a modest
    # two-world-pixel camera step it should advance on most frames, rather than
    # holding for tens of frames before jumping one raster pixel.
    offsets = [parallax_offset(4230, 960, x, 4000, 0.58) for x in range(0, 120, 2)]
    assert len(set(offsets)) >= 50


def test_fitted_text_stays_inside_requested_width():
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    surface = pygame.Surface((320, 180))
    rect = renderer.fit_text(surface, "agent-under-saved-policy is intentionally long", (20, 20, 90, 12))
    assert rect.left >= 20
    assert rect.right <= 110
    pygame.quit()
