"""Deterministic macro-route generation for large, sealed worlds."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .campaign import CAMPAIGN_ROSTER
from .canonical import sha256_json
from .character import DEFAULT_CHARACTER_NAME
from .chapter_design import paint_chapter_one_section, plan_chapter_one
from .content import ContentIndex, load_content
from .identity import GENERATOR_VERSION, SCHEMA_VERSION, WorldIdentity
from .reachability import find_spawn, normalize_ladder_tiles, reachable_from, validate_level
from .skyway import SKYWAY_HEIGHT, add_skyway, garden_invisible_platforms, upper_route_report
from .rng import Streams

MAX_LAYOUT_RETRIES = 12
ALGORITHM = "macro-route-v13-descent-skyways"

NETWORK_OPERATIONS = (
    "Ethernet link training",
    "ARP neighbor discovery",
    "DHCP lease negotiation",
    "DNS route lookup",
    "WPA key exchange",
    "mesh route election",
    "packet checksum synchronization",
    "encrypted tunnel negotiation",
)


def _render(canvas: list[list[str]]) -> list[str]:
    return ["".join(row) for row in canvas]


def _put(canvas: list[list[str]], x: int, y: int, glyph: str) -> None:
    if 0 <= y < len(canvas) and 0 <= x < len(canvas[0]):
        canvas[y][x] = glyph


def _platform(canvas: list[list[str]], x0: int, x1: int, y: int) -> None:
    for x in range(max(1, x0), min(len(canvas[0]) - 1, x1)):
        _put(canvas, x, y, "=")


def _ladder(canvas: list[list[str]], x: int, top: int, bottom: int) -> None:
    for y in range(top, bottom + 1):
        _put(canvas, x, y, "L")


def _seal_secret(canvas: list[list[str]], x: int, floor: int) -> None:
    """Place a collectible in a sealed vault with a breakable entrance."""

    y = floor - 2
    for yy in range(y - 1, y + 2):
        for xx in range(x - 1, x + 2):
            _put(canvas, xx, yy, "D")
    _put(canvas, x, y, "H")


def _scatter_floating_blocks(
    canvas: list[list[str]],
    floor: int,
    stream: Any,
) -> int:
    """Add optional Mario-like reward blocks without touching route geometry."""

    width = len(canvas[0])
    target = max(8, width // 24)
    candidates = [
        (x, y)
        for y in range(max(3, floor - 18), floor - 2)
        for x in range(20, width - 20)
        if canvas[y][x] == "."
        and canvas[y - 1][x] == "."
        and canvas[y + 1][x] == "."
        and canvas[y + 2][x] == "."
        and any(
            canvas[stand_y][x] in {"#", "=", "+", "D"}
            for stand_y in range(y + 3, min(len(canvas), y + 6))
        )
        and all(canvas[yy][x] not in {"L", "+"} for yy in range(y + 1, min(floor, y + 5)))
        and all(canvas[y][nx] not in {"B", "D", "G", "X", "S"} for nx in range(max(0, x - 3), min(width, x + 4)))
    ]
    placed = 0
    while candidates and placed < target:
        pick = stream.randint(0, len(candidates) - 1)
        x, y = candidates.pop(pick)
        if canvas[y][x] != ".":
            continue
        _put(canvas, x, y, "B")
        placed += 1
        candidates = [(cx, cy) for cx, cy in candidates if abs(cx - x) > 4 or abs(cy - y) > 2]
    return placed


def _install_ground_relief(
    canvas: list[list[str]],
    floor: int,
    stream: Any,
    *,
    reserved_columns: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Add sparse one-tile plateaus and depressions to the main foundation.

    The macro grammar historically left every non-pit route on one perfectly
    flat, three-tile-deep slab. Relief is installed only in untouched stretches
    after gameplay features are placed, so it cannot bury a pickup, ladder,
    gate, spawn, portal, or boss. A one-tile change is always jump-traversable.
    """

    width = len(canvas[0])
    relief: list[dict[str, Any]] = []
    reserved: set[int] = set(reserved_columns or ())
    kinds = ["step", "low"]
    if stream.chance(0.38):
        kinds.append("step" if stream.chance(0.5) else "low")
    for kind in kinds:
        spans = list(range(4, 8))
        span = spans[stream.randint(0, len(spans) - 1)]
        candidates: list[int] = []
        for x0 in range(22, width - span - 24):
            check = range(x0 - 2, x0 + span + 2)
            if any(x in reserved for x in check):
                continue
            if not all(canvas[floor - 2][x] == "." and canvas[floor - 1][x] == "." for x in check):
                continue
            if not all(canvas[y][x] == "#" for y in range(floor, len(canvas)) for x in check):
                continue
            candidates.append(x0)
        if not candidates:
            continue
        x0 = candidates[stream.randint(0, len(candidates) - 1)]
        for x in range(x0, x0 + span):
            canvas[floor - 1 if kind == "step" else floor][x] = "#" if kind == "step" else "."
        reserved.update(range(x0 - 4, x0 + span + 4))
        relief.append({"kind": kind, "x": x0, "width": span, "delta": -1 if kind == "step" else 1})
    return relief


def _separate_edit_pickups(tiles: list[str]) -> list[str]:
    """Keep edit triggers out of ladder traffic by a two-cell clear moat."""

    canvas = [list(row) for row in tiles]
    if not canvas:
        return []
    height, width = len(canvas), len(canvas[0])

    def clear_of_ladders(x: int, y: int) -> bool:
        return all(
            canvas[yy][xx] not in {"L", "+"}
            for yy in range(max(0, y - 2), min(height, y + 3))
            for xx in range(max(0, x - 2), min(width, x + 3))
        )

    pickups = [(x, y) for y, row in enumerate(canvas) for x, cell in enumerate(row) if cell == "O"]
    invalid = [(x, y) for x, y in pickups if not clear_of_ladders(x, y)]
    if not invalid:
        return tiles
    for x, y in invalid:
        canvas[y][x] = "."

    candidates = [
        (x, y)
        for y in range(2, max(2, height - 8))
        for x in range(6, width - 6)
        if canvas[y][x] == "."
        and canvas[y + 1][x] == "="
        and clear_of_ladders(x, y)
        and all(abs(x - ox) > 4 or abs(y - oy) > 3 for ox, oy in pickups if (ox, oy) not in invalid)
    ]
    candidates.sort(key=lambda point: (point[0], point[1]))
    for index, _ in enumerate(invalid):
        if not candidates:
            fallback = [
                (x, y)
                for x in range(10, width - 10)
                for y in range(4, max(5, height - 9))
                if all(
                    canvas[yy][xx] == "."
                    for yy in range(y - 2, y + 2)
                    for xx in range(x - 2, x + 3)
                )
                and clear_of_ladders(x, y)
            ]
            if not fallback:
                raise RuntimeError("could not preserve ladder-separated edit pickup")
            x, y = fallback[len(fallback) // 2]
            for px in range(x - 1, x + 2):
                canvas[y + 1][px] = "="
            candidates = [(x, y)]
        target = round((index + 1) * (len(candidates) - 1) / (len(invalid) + 1))
        x, y = candidates.pop(target)
        canvas[y][x] = "O"
        candidates = [(cx, cy) for cx, cy in candidates if abs(cx - x) > 4 or abs(cy - y) > 3]
    return _render(canvas)


def _ensure_edit_pickup_count(tiles: list[str], target: int, *, min_rise: int = 4) -> list[str]:
    canvas = [list(row) for row in tiles]
    height, width = len(canvas), len(canvas[0])

    def safe(x: int, y: int) -> bool:
        return (
            canvas[y][x] == "."
            and canvas[y + 1][x] == "="
            and all(
                canvas[yy][xx] not in {"L", "+"}
                for yy in range(max(0, y - 2), min(height, y + 3))
                for xx in range(max(0, x - 2), min(width, x + 3))
            )
            and all(
                abs(x - ox) > 5 or abs(y - oy) > 3
                for oy, row in enumerate(canvas)
                for ox, cell in enumerate(row)
                if cell == "O"
            )
        )

    while sum(row.count("O") for row in canvas) < target:
        candidates = [
            (x, y)
            for x in range(8, width - 8)
            for y in range(3, max(4, height - 4 - min_rise))
            if safe(x, y)
        ]
        if not candidates:
            raise RuntimeError("could not add ladder-separated edit pickup")
        x, y = candidates[len(candidates) // 2]
        canvas[y][x] = "O"
    return _render(canvas)


def _normalize_block_clearance(tiles: list[str]) -> list[str]:
    """A floating block has either zero or at least two empty cells below it."""

    canvas = [list(row) for row in tiles]
    support = {"#", "=", "+", "B", "D", "G"}
    for y in range(1, len(canvas) - 2):
        for x in range(len(canvas[0])):
            if canvas[y][x] != "B" or canvas[y + 1][x] != "." or canvas[y + 2][x] not in support:
                continue
            if canvas[y - 1][x] == ".":
                canvas[y - 1][x] = "B"
                canvas[y][x] = "."
            else:
                # The only safe fallback is the explicitly allowed direct
                # placement; this remains optional route geometry.
                canvas[y + 1][x] = "="
    return _render(canvas)


def _ensure_workshop_routes(tiles: list[str]) -> list[str]:
    """Keep every workshop trigger reachable before its skyway is unlocked."""
    canvas = [list(row) for row in tiles]
    reached = reachable_from(tiles, find_spawn(tiles))
    stranded = [(x, y) for y, row in enumerate(tiles) for x, cell in enumerate(row) if cell == "O" and (x, y) not in reached]
    for ox, oy in stranded:
        candidates = [
            (canvas[y + 1][x] != "=", abs(x - ox) + abs(y - oy), x, y)
            for x, y in reached
            if 3 <= x < len(tiles[0]) - 3 and 2 <= y < len(tiles) - 1
            and canvas[y][x] == "." and canvas[y + 1][x] in {"=", "#"}
            and all(canvas[yy][xx] not in {"L", "+", "O", "S", "X", "N"}
                    for yy in range(y - 2, min(len(tiles), y + 3)) for xx in range(x - 2, x + 3))
        ]
        if not candidates:
            raise RuntimeError("could not place a reachable workshop trigger")
        _, _, x, y = min(candidates)
        canvas[oy][ox] = "."
        canvas[y][x] = "O"
        canvas[y + 1][x] = "="
    return _render(canvas)


def _normalize_penguin_support(tiles: list[str]) -> list[str]:
    """Give every visible penguin a stable perch without cutting traversal."""

    canvas = [list(row) for row in tiles]
    if not canvas:
        return []
    height, width = len(canvas), len(canvas[0])
    supports = {"#", "=", "+", "B", "D", "G"}
    for y in range(height - 1):
        for x in range(width):
            if canvas[y][x] not in {"P", "H"} or canvas[y + 1][x] in supports:
                continue
            if canvas[y + 1][x] == ".":
                canvas[y + 1][x] = "="
                continue
            # Never overwrite a ladder, bumper, portal, or hazard. Relocate
            # to the nearest empty cell already backed by a real surface.
            candidates = [
                (distance, nx, ny)
                for distance in range(1, 9)
                for ny in range(max(0, y - distance), min(height - 1, y + distance + 1))
                for nx in range(max(0, x - distance), min(width, x + distance + 1))
                if abs(nx - x) + abs(ny - y) == distance
                and canvas[ny][nx] == "."
                and canvas[ny + 1][nx] in supports
            ]
            if not candidates:
                continue
            _, nx, ny = min(candidates)
            glyph = canvas[y][x]
            canvas[y][x] = "."
            canvas[ny][nx] = glyph
    return _render(canvas)


def _ensure_penguin_routes(tiles: list[str]) -> list[str]:
    """Relocate only penguins that lack a normal or breakable traversal path."""

    canvas = [list(row) for row in tiles]
    if not canvas:
        return []
    supports = {"#", "=", "+", "B", "D", "G"}

    def breakable_reach() -> set[tuple[int, int]]:
        opened = ["".join("." if cell in {"B", "D"} else cell for cell in row) for row in canvas]
        return reachable_from(opened, find_spawn(_render(canvas)))

    reached = breakable_reach()
    stranded = [
        (x, y, cell)
        for y, row in enumerate(canvas)
        for x, cell in enumerate(row)
        if cell in {"P", "H"} and (x, y) not in reached
    ]
    for x, y, glyph in stranded:
        candidates = [
            (abs(nx - x) + abs(ny - y), nx, ny)
            for nx, ny in reached
            if 0 <= ny < len(canvas) - 1
            and 0 <= nx < len(canvas[0])
            and canvas[ny][nx] == "."
            and canvas[ny + 1][nx] in supports
        ]
        if not candidates:
            continue
        _, nx, ny = min(candidates)
        canvas[y][x] = "."
        canvas[ny][nx] = glyph
    return _render(canvas)


def _traversal_features(
    tiles: list[str], floor: int, stream: Any, *, sections: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Place optional physical toys in open, reachable parts of the route."""

    width = len(tiles[0])
    active = [section for section in sections or [] if section["beat"] in {"discovery", "traversal", "climax"}]

    def allowed(x: int, span: int) -> bool:
        return not sections or any(
            int(section["x"]) + 2 <= x and x + span <= int(section["x"]) + int(section["width"]) - 2
            for section in active
        )

    def preferred_position(index: int, fraction: float) -> int:
        if not active:
            return round(width * fraction)
        section = active[index % len(active)]
        return int(section["x"]) + stream.randint(4, int(section["width"]) - 8)

    def open_span(
        preferred: int, span: int, y: int, travel: int = 0, vertical_travel: int = 0,
    ) -> int | None:
        candidates = sorted(range(18, width - span - 18), key=lambda x: (abs(x - preferred), x))
        for x in candidates:
            if allowed(x - travel, span + travel * 2) and all(
                tiles[yy][xx] == "."
                for yy in range(max(0, y - 2 - vertical_travel), min(len(tiles), y + 2 + vertical_travel))
                for xx in range(x - travel, x + span + travel)
            ):
                return x
        return None

    tilting: list[dict[str, Any]] = []
    for index, fraction in enumerate((0.18, 0.68)):
        span = 4 + ((stream.randint(0, 2) + index) % 3)
        y = floor - (5 + index * 2)
        x = open_span(preferred_position(index * 2, fraction), span, y)
        if x is not None:
            tilting.append(
                {
                    "id": f"tilt-{index + 1}",
                    "x": x,
                    "y": y,
                    "width": span,
                    "pivot": round((span - 1) / 2, 2),
                    "phase": round(stream.random() * 6.283, 4),
                }
            )

    moving: list[dict[str, Any]] = []
    for index, (fraction, axis) in enumerate(((0.37, "vertical"), (0.84, "horizontal"))):
        span = 4 + index
        y = floor - (12 if axis == "vertical" else 6)
        x = open_span(
            preferred_position(index * 2 + 1, fraction), span, y,
            travel=4 if sections and axis == "horizontal" else 0,
            vertical_travel=5 if sections and axis == "vertical" else 0,
        )
        if x is not None:
            moving.append(
                {
                    "id": f"lift-{index + 1}",
                    "x": x,
                    "y": y,
                    "width": span,
                    "axis": axis,
                    "range": 5 if axis == "vertical" else 4,
                    "phase": round(stream.random() * 6.283, 4),
                }
            )

    winds: list[dict[str, Any]] = []
    for index, fraction in enumerate((0.47, 0.77)):
        preferred = preferred_position(index * 2, fraction)
        candidates = sorted(range(18, width - 18), key=lambda x: (abs(x - preferred), x))
        for x in candidates:
            top = floor - 14
            if allowed(x, 1) and all(tiles[y][x] == "." for y in range(top, floor)) and tiles[floor][x] in {"#", "="}:
                winds.append(
                    {"id": f"updraft-{index + 1}", "x": x, "y": top, "width": 1, "height": 14, "strength": 0.42}
                )
                break
    return {"tiltingPlatforms": tilting, "movingPlatforms": moving, "windColumns": winds}


def _split_runtime_maps(
    tiles: list[str],
    links: list[dict[str, Any]],
    features: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Cut linked hardware islands into independently mounted tile maps."""

    if not links:
        return []
    width = len(tiles[0])
    origins = [0, *(int(link["exitX"]) for link in links)]
    ends = [*(int(link["entryX"]) + 1 for link in links), width]
    maps: list[dict[str, Any]] = []
    for index, (origin, end) in enumerate(zip(origins, ends)):
        map_features: dict[str, list[dict[str, Any]]] = {}
        for key, specs in features.items():
            selected = []
            for spec in specs:
                x = float(spec["x"])
                span = float(spec.get("width") or 1)
                if origin <= x and x + span <= end:
                    local = dict(spec)
                    local["x"] = x - origin
                    selected.append(local)
            map_features[key] = selected
        maps.append(
            {
                "id": f"hardware-island-{index + 1}",
                "tiles": [row[origin:end] for row in tiles],
                "originX": origin,
                **map_features,
                "portals": [],
            }
        )
    for index, link in enumerate(links):
        left_id = f"{link['id']}-left"
        right_id = f"{link['id']}-right"
        common = {"link": str(link["id"]), "protocol": str(link["protocol"])}
        maps[index]["portals"].append(
            {
                **common,
                "id": left_id,
                "x": len(maps[index]["tiles"][0]) - 1,
                "y": int(link["y"]),
                "targetMap": index + 1,
                "targetPortal": right_id,
                "direction": 1,
                "operation": str(link["forwardOperation"]),
            }
        )
        maps[index + 1]["portals"].append(
            {
                **common,
                "id": right_id,
                "x": 0,
                "y": int(link["y"]),
                "targetMap": index,
                "targetPortal": left_id,
                "direction": -1,
                "operation": str(link["reverseOperation"]),
            }
        )
    return maps


def _install_hardware_network_links(
    canvas: list[list[str]],
    floor: int,
    stream: Any,
) -> list[dict[str, Any]]:
    """Split Distro Front into hardware islands joined by network portals."""

    width = len(canvas[0])
    operations = stream.shuffle(list(NETWORK_OPERATIONS))
    links: list[dict[str, Any]] = []
    for index, fraction in enumerate((0.25, 0.50, 0.75)):
        left = max(24, min(width - 34, round(width * fraction) - 4))
        right = left + 9
        # Seven empty columns are wider than the normal six-tile jump model.
        # The bottom seal remains intact; the two N nodes are the graph edge.
        for x in range(left + 1, right):
            for y in range(1, len(canvas) - 1):
                _put(canvas, x, y, ".")
        for x in (left, right):
            _put(canvas, x, floor - 2, ".")
            _put(canvas, x, floor - 1, "N")
            _put(canvas, x, floor, "#")
        protocol = "ethernet" if index % 2 == 0 else "wifi"
        links.append(
            {
                "id": f"hardware-link-{index + 1}",
                "entryX": left,
                "exitX": right,
                "y": floor - 1,
                "protocol": protocol,
                "forwardOperation": operations[index * 2],
                "reverseOperation": operations[index * 2 + 1],
            }
        )
    return links


def _paint_sector_recipe(
    canvas: list[list[str]], recipe: str, x0: int, x1: int, floor: int, *, reward: str
) -> None:
    """Layer a deterministic optional traversal recipe into a macro sector."""

    center = (x0 + x1) // 2

    def rise(tiles: int) -> int:
        return max(3, floor - tiles)

    if recipe == "switchback":
        _platform(canvas, x0 + 3, center + 1, rise(5))
        _ladder(canvas, x0 + 5, rise(6), floor - 1)
        _platform(canvas, center - 1, x1 - 3, rise(11))
        _ladder(canvas, center + 1, rise(12), rise(5))
        _platform(canvas, x0 + 4, center, rise(18))
        _ladder(canvas, x0 + 6, rise(19), rise(11))
        _put(canvas, x1 - 6, rise(19), reward)
    elif recipe == "sky-well":
        summit = rise(28)
        _ladder(canvas, center, summit, floor - 1)
        _platform(canvas, center - 8, center, rise(8))
        _platform(canvas, center, center + 9, rise(16))
        _platform(canvas, center - 7, center + 8, summit)
        _put(canvas, center + 4, summit - 1, reward)
    elif recipe == "bumper-gallery":
        for i, (dx, steps) in enumerate(((5, 1), (11, 6), (18, 11), (24, 16), (28, 22))):
            x = min(x1 - 4, x0 + dx)
            y = rise(steps)
            _put(canvas, x, y, "^")
            if i:
                _platform(canvas, x - 2, min(x1 - 2, x + 3), y + 2)
        _put(canvas, min(x1 - 5, x0 + 25), rise(24), reward)
    elif recipe == "twin-towers":
        left, right = x0 + 7, x1 - 7
        _ladder(canvas, left, rise(22), floor - 1)
        _ladder(canvas, right, rise(26), floor - 1)
        _platform(canvas, left - 3, center, rise(12))
        _platform(canvas, center, right + 4, rise(18))
        _platform(canvas, left - 2, right + 3, rise(28))
        _put(canvas, center, rise(29), reward)
        _put(canvas, center + 2, rise(29), "D")
        _put(canvas, center + 3, rise(29), "C")
    elif recipe == "suspended-chain":
        heights = (rise(6), rise(10), rise(16), rise(22), rise(16))
        for i, y in enumerate(heights):
            left = x0 + 3 + i * 6
            _platform(canvas, left, min(x1 - 2, left + 6), y)
            if i in {0, 2, 3}:
                _ladder(canvas, left + 1, y - 1, floor - 1 if i == 0 else heights[i - 1] - 1)
        _put(canvas, min(x1 - 4, x0 + 24), rise(23), reward)
    elif recipe == "archive-stacks":
        for i in range(5):
            left = x0 + 3 + i * 6
            top = rise(4 + i * 4)
            _platform(canvas, left, min(x1 - 2, left + 7), top)
            _ladder(canvas, left + 1, top - 1, floor - 1)
        _put(canvas, min(x1 - 4, x0 + 26), rise(22), reward)
    elif recipe == "broken-bridge":
        y = floor - 9
        _platform(canvas, x0 + 3, center - 2, y)
        _platform(canvas, center + 3, x1 - 3, y)
        _ladder(canvas, x0 + 5, y - 1, floor - 1)
        _ladder(canvas, x1 - 6, y - 1, floor - 1)
        _put(canvas, center, y + 2, "^")
        _put(canvas, x1 - 6, y - 1, reward)


def _paint_macro_level(
    chapter_id: str,
    chapter_index: int,
    streams: Streams,
    *,
    difficulty: str,
    include_optional: bool,
    force_logo: bool,
    attempt: int,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a large level from terrain grammar rather than chunks.

    Named RNG streams independently control terrain, loot, encounters,
    decoration, and secrets. A cosmetic draw can never rewrite collision.
    """

    layout = streams["layout"]
    loot = streams["loot"]
    encounters = streams["encounters"]
    cosmetics = streams["cosmetics"]
    rare = streams["rare"]
    generation = dict((profile or {}).get("generation") or {})
    width_bases = generation.get("widthBase") or {"casual": 256, "standard": 288, "precise": 320}
    width_base = int(width_bases[difficulty])
    width = width_base + chapter_index * 24 + layout.randint(0, 4) * 8
    # Taller than the legacy strip by design: every chapter can stage several
    # full-screen climbs instead of keeping all action near one floor.
    height_base = int(generation.get("heightBase") or 60)
    height = height_base + chapter_index * 2 + layout.randint(0, 2) * 2
    floor = height - 4
    canvas = [["." for _ in range(width)] for _ in range(height)]

    # Stable lower foundation. Pits remove the upper substrate but retain a
    # bottom seal so falling/rescue behavior stays bounded.
    for y in range(floor, height):
        for x in range(width):
            canvas[y][x] = "#"

    sector_w = int(generation.get("sectorWidth") or 32)
    sector_count = max(6, (width - 16) // sector_w)
    edit_pickup_target = 3 if chapter_index < 3 else 2
    edit_pickup_sectors = {
        min(sector_count - 1, max(0, round((i + 1) * sector_count / (edit_pickup_target + 1)) - 1))
        for i in range(edit_pickup_target)
    }
    sector_types = tuple(
        generation.get("sectorMotifs")
        or ("ruin", "canopy", "relay", "ravine", "spire", "archive", "foundry", "garden")
    )
    recipes = tuple(
        generation.get("recipes")
        or (
            "switchback",
            "sky-well",
            "bumper-gallery",
            "twin-towers",
            "suspended-chain",
            "archive-stacks",
            "broken-bridge",
        )
    )
    placements: list[dict[str, Any]] = []
    protected: set[int] = set(range(0, 18)) | set(range(width - 20, width))
    pit_ranges: list[tuple[int, int]] = []
    route_plan = (
        plan_chapter_one(width, sector_w, recipes, sector_types, layout, include_optional=include_optional)
        if chapter_index == 0 else []
    )
    if route_plan:
        sector_count = len(route_plan)

    for sector in range(sector_count):
        if route_plan:
            section = route_plan[sector]
            painted = paint_chapter_one_section(
                canvas, section, floor, difficulty, include_optional=include_optional,
            )
            pit_ranges.extend(painted["pits"])
            placement = {
                **section,
                "id": f"{chapter_id}/{sector:02d}-{section['route']}",
                "algorithm": ALGORITHM,
            }
            placement["digest"] = sha256_json(placement)
            placements.append(placement)
            continue
        x0 = 8 + sector * sector_w
        x1 = min(width - 8, x0 + sector_w)
        if x1 - x0 < 18:
            continue
        motif = sector_types[(layout.randint(0, len(sector_types) - 1) + chapter_index + sector) % len(sector_types)]
        recipe = recipes[(layout.randint(0, len(recipes) - 1) + chapter_index * 2 + sector) % len(recipes)]
        placement = {
            "id": f"{chapter_id}/{sector:02d}-{motif}",
            "x": x0,
            "width": x1 - x0,
            "motif": motif,
            "recipe": recipe,
            "algorithm": ALGORITHM,
        }
        placement["digest"] = sha256_json(placement)
        placements.append(placement)

        # Unique, optional vertical silhouettes vary the playable skyline.
        if cosmetics.chance(0.72):
            marker_x = x0 + cosmetics.randint(5, max(5, x1 - x0 - 6))
            marker_y = floor - cosmetics.randint(6, 14)
            _platform(canvas, marker_x - 2, marker_x + 3, marker_y + 1)

        # Traversable gaps remain below the validator's six-tile jump.
        if sector > 0 and sector < sector_count - 1 and layout.chance(0.64):
            gap_w = layout.randint(2, 3 if difficulty == "casual" else 4)
            gx = x0 + layout.randint(8, max(8, x1 - x0 - gap_w - 7))
            if not any((gx + d) in protected for d in range(gap_w)):
                for x in range(gx, gx + gap_w):
                    for y in range(floor, height - 1):
                        _put(canvas, x, y, "M")
                pit_ranges.append((gx, gx + gap_w))

        if include_optional:
            recipe_reward = "O" if sector in edit_pickup_sectors else ("C" if loot.chance(0.72) else "P")
            if chapter_index == 0 and force_logo and sector == 0:
                recipe_reward = "O"
            _paint_sector_recipe(
                canvas,
                recipe,
                x0,
                x1,
                floor,
                reward=recipe_reward,
            )
            if rare.chance(0.14):
                _put(canvas, min(x1 - 4, x0 + 10), floor - 2, "P")

        safe_xs = [
            x for x in range(x0 + 5, x1 - 5)
            if all(not (a - 2 <= x < b + 2) for a, b in pit_ranges)
        ]
        if safe_xs and loot.chance(0.82):
            _put(canvas, safe_xs[loot.randint(0, len(safe_xs) - 1)], floor - 1, "C" if loot.chance(0.62) else "P")
        if safe_xs and encounters.chance(0.76):
            ex = safe_xs[encounters.randint(0, len(safe_xs) - 1)]
            _put(canvas, ex, floor - 1, "E")
        if safe_xs and (sector + chapter_index) % 3 == 1:
            bx = safe_xs[layout.randint(0, len(safe_xs) - 1)]
            _put(canvas, bx, floor - 1, "B")

    # Fixed grammar anchors and roomy start/boss arenas.
    for x in range(0, 18):
        for y in range(floor, height):
            _put(canvas, x, y, "#")
        _put(canvas, x, floor - 1, ".")
    for x in range(width - 20, width):
        for y in range(floor, height):
            _put(canvas, x, y, "#")
        _put(canvas, x, floor - 1, ".")
    _put(canvas, 4, floor - 1, "S")
    _put(canvas, width - 8, floor - 1, "X")
    _put(canvas, width - 13, floor - 1, "E")

    if chapter_index == 0 and force_logo and "O" not in "".join(_render(canvas)):
        upper = floor - 12
        _platform(canvas, 18, 42, upper + 1)
        _ladder(canvas, 19, upper, floor - 1)
        _ladder(canvas, 40, upper, floor - 1)
        _put(canvas, 30, upper, "O")

    if include_optional:
        breather = next((section for section in route_plan if section["beat"] == "breather"), None)
        secret_x = (
            int(breather["x"]) + int(breather["width"]) // 2
            if breather else width // 2 + 5 + rare.randint(0, 7)
        )
        _seal_secret(canvas, secret_x, floor)
        if breather:
            # The crate keeps a solid base after its shell is broken, so its
            # penguin can be reached without relocating it out of the vault.
            _put(canvas, secret_x, floor - 1, "#")

    network_links: list[dict[str, Any]] = []
    if chapter_id == "distro-front":
        network_links = _install_hardware_network_links(canvas, floor, streams["narrative"])

    floating_blocks = _scatter_floating_blocks(canvas, floor, loot)
    seams = {
        x for section in route_plan
        for edge in (int(section["x"]), int(section["x"]) + int(section["width"]))
        for x in range(edge - 2, edge + 3)
    }
    ground_relief = _install_ground_relief(canvas, floor, layout, reserved_columns=seams)

    normalized = normalize_ladder_tiles(_render(canvas))
    normalized = _normalize_block_clearance(normalized)
    normalized = _normalize_penguin_support(normalized)
    normalized = _ensure_edit_pickup_count(
        _separate_edit_pickups(normalized), edit_pickup_target,
        min_rise=1 if route_plan else 4,
    )
    normalized = _ensure_penguin_routes(normalized)
    normalized = _ensure_workshop_routes(normalized)
    features = _traversal_features(normalized, floor, streams["layout"], sections=route_plan)
    runtime_maps = _split_runtime_maps(normalized, network_links, features)
    normalized, upper = add_skyway(normalized, streams.seed, chapter_id)
    if chapter_id == "walled-garden":
        normalized = garden_invisible_platforms(normalized)
    for specs in features.values():
        for feature in specs:
            feature["y"] += SKYWAY_HEIGHT
    for link in network_links:
        link["y"] += SKYWAY_HEIGHT
    for map_index, spec in enumerate(runtime_maps):
        local_tiles = list(spec["tiles"])
        # Every independently mounted island needs a workshop of its own.
        if not any("O" in row for row in local_tiles):
            y = len(local_tiles) - 5
            x = next((x for x in range(4, len(local_tiles[0]) - 4) if local_tiles[y][x] == "." and local_tiles[y + 1][x] == "#"), None)
            if x is not None:
                local_tiles[y] = local_tiles[y][:x] + "O" + local_tiles[y][x + 1:]
        spec["tiles"], spec["upperTraversal"] = add_skyway(local_tiles, f"{streams.seed}:map-{map_index}", chapter_id)
        for key in (*features, "portals"):
            for feature in spec.get(key, []):
                feature["y"] += SKYWAY_HEIGHT
    height += SKYWAY_HEIGHT
    edit_pickups = sum(row.count("O") for row in normalized)
    return {
        "chapterId": chapter_id,
        "tiles": normalized,
        "width": width,
        "height": height,
        "upperTraversal": upper,
        "placements": placements,
        "algorithm": ALGORITHM,
        "macroSectors": len(placements),
        "recipeCount": len({str(placement["recipe"]) for placement in placements}),
        "pitCount": len(pit_ranges),
        "floatingBlockCount": floating_blocks,
        "groundContourCount": len(ground_relief),
        "groundContours": ground_relief,
        "editPickupCount": edit_pickups,
        "networkLinks": network_links,
        "hardwareSegments": len(network_links) + 1 if network_links else 0,
        "maps": runtime_maps,
        "mapCount": len(runtime_maps) if runtime_maps else 1,
        **features,
        "attempt": attempt,
    }


def assemble_chapter(
    index: ContentIndex,
    chapter_id: str,
    streams: Streams,
    *,
    include_optional: bool,
    force_logo: bool,
    difficulty: str = "standard",
) -> dict[str, Any]:
    work = assemble_chapter_steps(index, chapter_id, streams, include_optional=include_optional,
                                  force_logo=force_logo, difficulty=difficulty)
    return _finish_work(work)


def _finish_work(work):
    while True:
        try:
            next(work)
        except StopIteration as done:
            return done.value


def assemble_chapter_steps(index, chapter_id, streams, *, include_optional, force_logo, difficulty="standard"):
    """Generate and validate a chapter from its sealed content profile."""

    profile = index.chapter_profile(chapter_id)
    chapter_index = next(i for i, spec in enumerate(CAMPAIGN_ROSTER) if spec.id == chapter_id)
    last_error = "unassembled"
    for attempt in range(MAX_LAYOUT_RETRIES):
        yield "Building terrain"
        chapter = _paint_macro_level(
            chapter_id,
            chapter_index,
            streams,
            difficulty=difficulty,
            include_optional=include_optional,
            force_logo=force_logo,
            attempt=attempt,
            profile=profile,
        )
        yield "Checking traversal"
        report = validate_level(chapter["tiles"], require_logo=False, require_all_logos=True)
        yield "Checking upper routes"
        upper_report = upper_route_report(chapter["tiles"], chapter["upperTraversal"])
        chapter["upperTraversal"]["reachability"] = upper_report
        for spec in chapter["maps"]:
            yield "Checking island routes"
            spec["upperTraversal"]["reachability"] = upper_route_report(spec["tiles"], spec["upperTraversal"])
        chapter["reachability"] = report
        if report["ok"] and report["bossReachableWithoutRare"] and upper_report["ok"] and all(spec["upperTraversal"]["reachability"]["ok"] for spec in chapter["maps"]):
            return chapter
        last_error = ",".join(report["errors"]) or "unknown"
    raise RuntimeError(f"chapter {chapter_id} failed procedural generation: {last_error}")


@dataclass
class SealedWorld:
    identity: WorldIdentity
    chapters: list[dict[str, Any]]
    receipt: dict[str, Any]
    character: dict[str, Any]
    settings: dict[str, Any]

    def to_record(self) -> dict[str, Any]:
        return {
            "chapters": self.chapters,
            "character": self.character,
            "identity": self.identity.to_record(),
            "identityDigest": self.identity.digest(),
            "receipt": self.receipt,
            "settings": self.settings,
        }

    def seal_digest(self) -> str:
        return sha256_json(self.to_record())


def generate_world(
    seed: str,
    *,
    difficulty: str = "standard",
    accessibility_profile: str = "default",
    character: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    force_logo: bool = False,
    content: ContentIndex | None = None,
) -> SealedWorld:
    return _finish_work(generate_world_steps(seed, difficulty=difficulty,
        accessibility_profile=accessibility_profile, character=character, settings=settings,
        force_logo=force_logo, content=content))


def generate_world_steps(seed: str, *, difficulty="standard", accessibility_profile="default",
                         character=None, settings=None, force_logo=False, content=None):
    """Same sealed world as the blocking API, with progress before each work unit."""
    if difficulty not in {"casual", "standard", "precise"}:
        raise ValueError("unknown difficulty")
    content = content or load_content()
    streams = Streams(seed)
    settings = dict(settings or {})
    include_optional = settings.get("includeOptionalChunks", True)
    chapters = []
    yield 0.02, "Preparing world content"
    for chapter_index, spec in enumerate(CAMPAIGN_ROSTER):
        profile = content.chapter_profile(spec.id) or {}
        work = assemble_chapter_steps(
            content,
            spec.id,
            streams,
            include_optional=include_optional,
            force_logo=force_logo and spec.id == "corrupted-install",
            difficulty=difficulty,
        )
        island_checks = 0
        while True:
            try:
                label = next(work)
                within_chapter = {"Building terrain": 0, "Checking traversal": .4,
                                  "Checking upper routes": .7}.get(label, .8 + min(.15, island_checks * .03))
                if label == "Checking island routes":
                    island_checks += 1
                yield 0.04 + 0.90 * (chapter_index + within_chapter) / len(CAMPAIGN_ROSTER), f"{spec.name}: {label.lower()}"
            except StopIteration as done:
                chapter = done.value
                break
        boss = profile.get("boss") or {}
        chapter["name"] = str(profile.get("name") or spec.name)
        chapter["blurb"] = str(profile.get("blurb") or spec.blurb)
        chapter["palette"] = str(profile.get("palette") or spec.palette)
        chapter["bossId"] = str(boss.get("id") or spec.boss.id)
        chapter["bossName"] = str(boss.get("name") or spec.boss.name)
        chapter["enemyMotifs"] = list(profile.get("enemyMotifs") or [])
        chapter["itemPool"] = list(profile.get("itemPool") or [])
        chapter["contentProfile"] = str(profile.get("id") or "engine-fallback")
        chapter["contentAddons"] = list(profile.get("addons") or [])
        chapter["events"] = list(spec.events)
        chapters.append(chapter)
    yield 0.96, "Sealing world identity"
    identity = WorldIdentity(
        seed=seed,
        generator_version=GENERATOR_VERSION,
        schema_version=SCHEMA_VERSION,
        content_pack_ids=content.pack_ids,
        content_digest=content.digest,
        difficulty=difficulty,
        accessibility_profile=accessibility_profile,
    )
    receipt = {
        "generatorVersion": GENERATOR_VERSION,
        "generatorAlgorithm": ALGORITHM,
        "schemaVersion": SCHEMA_VERSION,
        "contentPackIds": list(content.pack_ids),
        "contentPackIdentities": content.pack_identities(),
        "contentDigest": content.digest,
        "authoredContentIdentities": content.ordered_identities(),
        "chunkIdentities": [placement for chapter in chapters for placement in chapter["placements"]],
        "streamSnapshot": streams.snapshot(),
        "forceLogo": bool(force_logo),
    }
    receipt["receiptDigest"] = sha256_json({key: value for key, value in receipt.items() if key != "receiptDigest"})
    return SealedWorld(
        identity=identity,
        chapters=chapters,
        receipt=receipt,
        character=character or {"kind": "david", "name": DEFAULT_CHARACTER_NAME},
        settings=settings,
    )


def world_identity_for_fixture(seed: str = "omega-fixture-1") -> WorldIdentity:
    return generate_world(seed, force_logo=True).identity
