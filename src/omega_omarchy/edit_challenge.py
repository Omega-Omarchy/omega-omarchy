"""Geometry-aware objectives for the optional over-the-shoulder workshop."""

from __future__ import annotations

from .reachability import WALK_ON, normalize_ladder_tiles, reachable_from


def cache_goal(
    tiles: list[str],
    start: tuple[int, int],
    bounds: tuple[int, int, int, int],
    reserved: set[tuple[int, int]],
    reached: set[tuple[int, int]],
) -> tuple[int, int] | None:
    """Find a visible, initially disconnected cache with a bounded scaffold.

    The scaffold is only a feasibility check, never placed in the real map.
    Actual movement still needs a playtest; this shares generation's static
    graph rather than promising an exact physics solution.
    """
    sx, sy = start
    left, top, right, bottom = bounds
    candidates = [
        (x, y)
        for y in range(max(top + 2, sy - 8), min(bottom - 1, sy - 5) + 1)
        for x in range(max(left + 2, sx - 9), min(right - 2, sx + 10) + 1)
        if abs(x - sx) >= 4 and tiles[y][x] == "."
        and (x, y) not in reached and (x, y) not in reserved
    ]
    candidates.sort(key=lambda p: (abs(p[0] - sx - 7) + abs(p[1] - sy + 6), p[1], p[0]))
    for x, y in candidates:
        # Reachability records landings, not every pickup touched mid-jump.
        # Keep the cache beyond the ordinary jump plus full sprite footprint
        # of nearby reachable cells; otherwise an apparently disconnected
        # floating cache could already be collectible with no construction.
        if any(abs(rx - x) <= 6 and ry <= y + 5 for rx, ry in reached):
            continue
        # Leave a full-height landing beside the proposed ladder. Anchors,
        # items, helpers and existing geometry are never silently replaced.
        if any(tiles[yy][x + dx] != "." or (x + dx, yy) in reserved
               for yy in range(max(0, y - 2), y + 1) for dx in (-1, 0, 1)):
            continue
        feet = sorted(
            ((fx, fy) for fx, fy in reached
             if left + 1 <= fx <= right - 1 and abs(fx - x) <= 6
             and y < fy <= min(bottom, y + 12) and fy + 1 < len(tiles)
             and tiles[fy + 1][fx] in WALK_ON),
            key=lambda point: (abs(point[0] - x) + point[1] - y, point),
        )
        for fx, fy in feet:
            scaffold = {(fx, yy): "L" for yy in range(y, fy + 1)}
            # On elevated branches there may be no floor below the cache.
            # Prove a ladder from an existing ledge plus a short bridge.
            if fx != x:
                scaffold.update({(xx, y + 1): "=" for xx in range(min(fx, x), max(fx, x) + 1) if xx != fx})
            if len(scaffold) > 15 or any(tiles[yy][xx] not in {".", "L", "+", "="}
                                         or (xx, yy) in reserved for xx, yy in scaffold):
                continue
            preview = list(tiles)
            for (xx, yy), tile in scaffold.items():
                preview[yy] = preview[yy][:xx] + tile + preview[yy][xx + 1:]
            preview = normalize_ladder_tiles(preview)
            changed = {(xx, yy) for yy, row in enumerate(preview) for xx, cell in enumerate(row) if cell != tiles[yy][xx]}
            if (len(changed) <= 16 and not changed & reserved
                    and all(left <= xx <= right and top <= yy <= bottom for xx, yy in changed)
                    and (x, y) in reachable_from(preview, start)):
                return x, y
    return None
