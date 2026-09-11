"""Visibility changes presentation only; invisible platforms remain solid."""

from __future__ import annotations

from .physics import Body, TILE
from .presentation import CHAR_WORLD_HEIGHT


def platform_alpha(body: Body | None, x: int, y: int, tick: int, *, run_x: int | None = None, reduced_motion: bool = False) -> int:
    if body is not None:
        # Use the visible silhouette, so brushing the platform with the head
        # or shoulder reveals it even before the smaller physics box arrives.
        feet_x, feet_y = body.feet
        left, right = feet_x - 11, feet_x + 11
        top, bottom = feet_y - CHAR_WORLD_HEIGHT, feet_y
        dx = max(x * TILE - right, left - (x + 1) * TILE, 0)
        dy = max(y * TILE - bottom, top - (y + 1) * TILE, 0)
        if dx * dx + dy * dy <= 16 * 16:
            return 235
    if reduced_motion:
        return 0
    # A contiguous platform shares one short shimmer every six seconds; spans
    # do not become a constant stream of independently flashing tiles.
    origin = x if run_x is None else run_x
    phase = (tick + origin * 83 + y * 137) % 360
    shimmer = (10, 18, 28, 38, 48, 56, 56, 48, 38, 28, 18, 10)
    return shimmer[phase] if phase < len(shimmer) else 0
