"""Reachability and completeness without rare events."""

from __future__ import annotations

from collections import deque
from functools import lru_cache
from math import floor
from typing import Any, Iterable

from .physics import AIR_JUMP_VEL, GRAVITY, JUMP_VEL, MAX_FALL, MAX_RUN, TILE

LADDER_TILES = {"L", "+"}
WALK_ON = {"#", "=", "I", "+", "B", "D", "G", "g"}
PASSABLE = {".", "S", "X", "P", "H", "C", "E", "O", "!", "^", "L", "+", "W", "N", "M"}
BLOCKING = {"#", "=", "I", "B", "D", "G", "g"}
BREAKABLE = {"B", "D"}
PENGUIN_GLYPHS = {"P", "H"}


def _at(tiles: list[str], x: int, y: int) -> str:
    if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return "#"
    return tiles[y][x]


def _air(tiles: list[str], x: int, y: int) -> bool:
    return _at(tiles, x, y) not in BLOCKING


def _standable(tiles: list[str], x: int, y: int) -> bool:
    if not _body_clear(tiles, x, y):
        return False
    if _at(tiles, x, y) in LADDER_TILES:
        return True
    return _at(tiles, x, y + 1) in WALK_ON


def _body_clear(tiles: list[str], x: int, y: int, *, slide: bool = False) -> bool:
    """A node is the feet cell: standing needs this cell AND the one above."""
    return _air(tiles, x, y) and (slide or _air(tiles, x, y - 1))


def _regular_deck_neighbor(tiles: list[str], x: int, y: int) -> bool:
    """A crossing exists only where a normal ``=`` platform meets a ladder."""

    return _at(tiles, x - 1, y) == "=" or _at(tiles, x + 1, y) == "="


def ladder_endpoint_issues(tiles: list[str]) -> list[str]:
    """Report ladder runs that do not meet a usable landing at both ends."""

    issues: list[str] = []
    width = len(tiles[0]) if tiles else 0
    for x in range(width):
        rows = [y for y, row in enumerate(tiles) if row[x] in LADDER_TILES]
        while rows:
            top = bottom = rows.pop(0)
            while rows and rows[0] == bottom + 1:
                bottom = rows.pop(0)
            top_crossing = tiles[top][x] == "+" and _regular_deck_neighbor(tiles, x, top)
            bottom_crossing = tiles[bottom][x] == "+" and _regular_deck_neighbor(tiles, x, bottom)
            bottom_floor = _at(tiles, x, bottom + 1) in WALK_ON
            if not top_crossing:
                issues.append(f"ladder-top-invalid:{x}:{top}")
            if not (bottom_crossing or bottom_floor):
                issues.append(f"ladder-bottom-invalid:{x}:{bottom}")
    return issues


def normalize_ladder_tiles(tiles: list[str]) -> list[str]:
    """Add traversable ladder/deck crossings and repair unsafe endpoints."""

    canvas = [list(row) for row in tiles]
    if not canvas:
        return []
    height, width = len(canvas), len(canvas[0])
    downgraded: set[tuple[int, int]] = set()
    # A ladder can never terminate under an impassable ceiling. Continue a
    # normal platform through it as a ``+`` crossing; discard isolated walls,
    # gates, and reward blocks that would make the endpoint unusable.
    for y in range(1, height):
        for x in range(width):
            if canvas[y][x] not in LADDER_TILES:
                continue
            above = canvas[y - 1][x]
            if above == "=":
                adjacent_platform = any(
                    0 <= nx < width and canvas[y - 1][nx] == "=" for nx in (x - 1, x + 1)
                )
                canvas[y - 1][x] = "+" if adjacent_platform else "."
            elif above in {"#", "B", "D", "G"}:
                canvas[y - 1][x] = "."
    # Downgrade authored/orphan crossings first. A wall, block, gate, or another
    # ladder crossing is not a walkable platform connection by itself.
    snapshot = ["".join(row) for row in canvas]
    for y in range(height):
        for x in range(width):
            if canvas[y][x] == "+" and not _regular_deck_neighbor(snapshot, x, y):
                canvas[y][x] = "L"
                downgraded.add((x, y))
    for y in range(height):
        for x in range(width):
            if canvas[y][x] != "L":
                continue
            if any(0 <= nx < width and canvas[y][nx] == "=" for nx in (x - 1, x + 1)):
                canvas[y][x] = "+"

    def add_crossing(x: int, y: int) -> None:
        if (x, y) in downgraded:
            return
        if any(0 <= nx < width and canvas[y][nx] == "=" for nx in (x - 1, x + 1)):
            canvas[y][x] = "+"
            return
        for nx in (x - 1, x + 1):
            if 0 <= nx < width and canvas[y][nx] == ".":
                canvas[y][nx] = "="
                canvas[y][x] = "+"
                return

    snapshot = ["".join(row) for row in canvas]
    for issue in ladder_endpoint_issues(snapshot):
        kind, x_text, y_text = issue.split(":")
        x, y = int(x_text), int(y_text)
        if kind in {"ladder-top-invalid", "ladder-bottom-invalid"}:
            add_crossing(x, y)
    # A repair can encounter a boundary or occupied neighbors. Never emit a
    # semantically invalid crossing in that case; validation will ask the
    # generator for a different layout.
    snapshot = ["".join(row) for row in canvas]
    for y in range(height):
        for x in range(width):
            if canvas[y][x] == "+" and not _regular_deck_neighbor(snapshot, x, y):
                canvas[y][x] = "L"
    return ["".join(row) for row in canvas]


def iter_positions(tiles: list[str], glyphs: Iterable[str]) -> list[tuple[int, int, str]]:
    found = []
    wanted = set(glyphs)
    for y, row in enumerate(tiles):
        for x, cell in enumerate(row):
            if cell in wanted:
                found.append((x, y, cell))
    return found


@lru_cache(maxsize=256)
def _jump_sweeps(dx: int, dy: int) -> tuple:
    """Swept 10×18 bodies under the game's ordinary and single air-jump laws.

    Each candidate ends on the descending crossing of the destination deck.
    Horizontal speed is bounded by normal running; no rush, bumper, cannon,
    head-bump shortcut or straight-line diagonal is certified as a jump.
    """
    sweeps = []
    for air_tick in (None, 2, 6, 10, 14, 18, 24, 32):
        points = [(0.0, 0.0)]
        yy, vy = 0.0, JUMP_VEL
        for tick in range(1, 100):
            if tick > 1:
                vy = min(MAX_FALL, vy + GRAVITY)
            if tick == air_tick:
                vy = min(0.0, vy) + AIR_JUMP_VEL
            previous = yy
            yy += vy
            points.append((float(tick), yy))
            if vy > 0 and previous <= dy * TILE <= yy:
                fraction = (dy * TILE - previous) / vy
                duration = tick - 1 + fraction
                if duration <= 0 or abs(dx * TILE / duration) > MAX_RUN:
                    break
                points[-1] = (duration, float(dy * TILE))
                occupied, ceilings, decks = set(), set(), set()
                last_x, last_y = 8.0, 16.0
                for time, offset in points[1:]:
                    xx, feet = 8 + dx * TILE * time / duration, 16 + offset
                    # A swept rectangle checks head/shoulders as well as feet;
                    # sampling only the endpoints can cut platform corners.
                    x0, x1 = floor((min(xx, last_x) - 5) / TILE), floor((max(xx, last_x) + 5 - 1e-6) / TILE)
                    y0, y1 = floor((min(feet, last_y) - 18) / TILE), floor((max(feet, last_y) - 1e-6) / TILE)
                    occupied.update((cx, cy) for cx in range(x0, x1 + 1) for cy in range(y0, y1 + 1))
                    if feet < last_y:
                        ceilings.update((cx, cy) for cx in range(x0, x1 + 1) for cy in range(y0, y1 + 1)
                                        if feet - 18 < (cy + 1) * TILE <= last_y - 18)
                    elif feet > last_y:
                        decks.update((cx, cy) for cx in range(x0, x1 + 1) for cy in range(y0, y1 + 1)
                                     if last_y <= cy * TILE < feet - 1e-6)
                    last_x, last_y = xx, feet
                sweep = (tuple(sorted(occupied)), tuple(sorted(ceilings)), tuple(sorted(decks)))
                if sweep not in sweeps:
                    sweeps.append(sweep)
                break
    return tuple(sweeps)


def _clear_arc(tiles: list[str], x: int, y: int, nx: int, ny: int) -> bool:
    for occupied, ceilings, decks in _jump_sweeps(nx - x, ny - y):
        if (all(_at(tiles, x + xx, y + yy) not in BLOCKING for xx, yy in occupied)
                and all(_at(tiles, x + xx, y + yy) != "K" for xx, yy in ceilings)
                and all(_at(tiles, x + xx, y + yy) != "+" for xx, yy in decks)):
            return True
    return False


def reachable_from(tiles: list[str], start: tuple[int, int]) -> set[tuple[int, int]]:
    """Conservative static routes with standing, slide, ladder and jump clearance.

    Moving platforms, gusts and enemy timing require playtesting. Results are
    cached by immutable geometry, never by mutable map identity.
    """
    return set(_reachable(tuple(tiles), start))


@lru_cache(maxsize=48)
def _reachable(rows: tuple[str, ...], start: tuple[int, int]) -> frozenset:
    tiles = list(rows)

    width = len(tiles[0])
    height = len(tiles)
    sx, sy = start
    seen: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    if not _body_clear(tiles, sx, sy):
        return frozenset()
    queue.append((sx, sy))
    seen.add((sx, sy))
    network_nodes = [(x, y) for x, y, _ in iter_positions(tiles, "N")]
    network_links: dict[tuple[int, int], tuple[int, int]] = {}
    for index in range(0, len(network_nodes) - 1, 2):
        left, right = network_nodes[index], network_nodes[index + 1]
        network_links[left] = right
        network_links[right] = left

    def offer(nx: int, ny: int) -> None:
        if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and _body_clear(tiles, nx, ny):
            seen.add((nx, ny))
            queue.append((nx, ny))

    while queue:
        x, y = queue.popleft()
        # fall
        if not _standable(tiles, x, y) and _at(tiles, x, y) not in LADDER_TILES:
            offer(x, y + 1)
        # walk / step off ledges
        for dx in (-1, 1):
            nx = x + dx
            if not _body_clear(tiles, nx, y):
                continue
            if _standable(tiles, x, y) or _at(tiles, x, y) in LADDER_TILES:
                offer(nx, y)
        # ladders
        if _at(tiles, x, y) in LADDER_TILES or _at(tiles, x, y + 1) in LADDER_TILES:
            if _at(tiles, x, y - 2) != "K":
                offer(x, y - 1)
            offer(x, y + 1)
        # Paired network hardware is a bidirectional traversal edge. This is
        # the same pairing instantiated by GameSim from sealed chapter data.
        if _at(tiles, x, y) == "N" and (x, y) in network_links:
            offer(*network_links[(x, y)])
        # A low tunnel is traversable only from grounded standing space and
        # with a continuous floor. Its low cells cannot launch standing jumps.
        if _standable(tiles, x, y):
            for direction in (-1, 1):
                nx = x + direction
                if _body_clear(tiles, nx, y) or not _body_clear(tiles, nx, y, slide=True):
                    continue
                while 0 <= nx < width and _body_clear(tiles, nx, y, slide=True) and _at(tiles, nx, y + 1) in WALK_ON:
                    if _body_clear(tiles, nx, y):
                        offer(nx, y)
                        break
                    seen.add((nx, y))
                    nx += direction
        # The real jump impulses permit an early double jump to gain height,
        # or a later one to extend a gap. Every candidate checks the full arc.
        if _standable(tiles, x, y):
            for dx in range(-8, 9):
                for dy in range(-6, 7):
                    if dx == 0 and dy >= 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if (nx, ny) in seen or not _standable(tiles, nx, ny):
                        continue
                    if _clear_arc(tiles, x, y, nx, ny):
                        offer(nx, ny)
    return frozenset(seen)


def find_spawn(tiles: list[str]) -> tuple[int, int]:
    spots = iter_positions(tiles, "S")
    if not spots:
        raise ValueError("chunk assembly missing spawn")
    return spots[0][0], spots[0][1]


def find_boss(tiles: list[str]) -> tuple[int, int]:
    spots = iter_positions(tiles, "X")
    if not spots:
        raise ValueError("chunk assembly missing boss anchor")
    return spots[0][0], spots[0][1]


def _penguin_report(
    tiles: list[str],
    start: tuple[int, int],
    reached: set[tuple[int, int]],
) -> tuple[list[dict[str, Any]], list[str]]:
    opened = ["".join("." if cell in BREAKABLE else cell for cell in row) for row in tiles]
    reached_after_breaking = reachable_from(opened, start)
    penguins: list[dict[str, Any]] = []
    issues: list[str] = []
    for x, y, glyph in iter_positions(tiles, PENGUIN_GLYPHS):
        supported = _at(tiles, x, y + 1) in WALK_ON
        reachable = (x, y) in reached
        breakable_route = (x, y) in reached_after_breaking
        penguins.append(
            {
                "x": x,
                "y": y,
                "secret": glyph == "H",
                "supported": supported,
                "reachable": reachable,
                "reachableAfterBreaking": breakable_route,
            }
        )
        if not supported:
            issues.append(f"penguin-floating:{x}:{y}")
        if not reachable and not breakable_route:
            issues.append(f"penguin-trapped:{x}:{y}")
    return penguins, issues


def penguin_issues(tiles: list[str]) -> list[str]:
    """Report unsupported penguins or penguins lacking even a breakable route."""

    start = find_spawn(tiles)
    reached = reachable_from(tiles, start)
    return _penguin_report(tiles, start, reached)[1]


def validate_level(
    tiles: list[str], *, require_logo: bool = False, require_all_logos: bool = False,
) -> dict[str, Any]:
    spawn = find_spawn(tiles)
    boss = find_boss(tiles)
    reached = reachable_from(tiles, spawn)
    boss_ok = False
    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1)):
        if (boss[0] + dx, boss[1] + dy) in reached:
            boss_ok = True
            break
    optional_secrets = []
    for x, y, glyph in iter_positions(tiles, "H"):
        optional_secrets.append({"x": x, "y": y, "reachable": (x, y) in reached})
    logos = [(x, y) for x, y, _ in iter_positions(tiles, "O")]
    logo_ok = True if not require_logo else bool(logos) and any((x, y) in reached for x, y in logos)
    errors = []
    if not boss_ok:
        errors.append("boss-unreachable")
    if require_logo and not logo_ok:
        errors.append("logo-unreachable")
    if require_all_logos:
        errors.extend(f"logo-unreachable:{x}:{y}" for x, y in logos if (x, y) not in reached)
    errors.extend(ladder_endpoint_issues(tiles))
    penguins, penguin_errors = _penguin_report(tiles, spawn, reached)
    errors.extend(penguin_errors)
    return {
        "ok": not errors,
        "errors": errors,
        "spawn": spawn,
        "boss": boss,
        "reachableCount": len(reached),
        "optionalSecrets": optional_secrets,
        "penguins": penguins,
        "logos": logos,
        "bossReachableWithoutRare": boss_ok,
    }
