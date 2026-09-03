"""Reachability and completeness without rare events."""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable

LADDER_TILES = {"L", "+"}
WALK_ON = {"#", "=", "+", "B", "D", "G"}
PASSABLE = {".", "S", "X", "P", "H", "C", "E", "O", "!", "^", "L", "+", "W", "N", "M"}
BLOCKING = {"#", "D", "G"}
BREAKABLE = {"B", "D"}
PENGUIN_GLYPHS = {"P", "H"}


def _at(tiles: list[str], x: int, y: int) -> str:
    if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        return "#"
    return tiles[y][x]


def _air(tiles: list[str], x: int, y: int) -> bool:
    return _at(tiles, x, y) not in BLOCKING


def _standable(tiles: list[str], x: int, y: int) -> bool:
    if not _air(tiles, x, y):
        return False
    if _at(tiles, x, y) in LADDER_TILES:
        return True
    return _at(tiles, x, y + 1) in WALK_ON


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


def _clear_arc(tiles: list[str], x: int, y: int, nx: int, ny: int) -> bool:
    steps = max(abs(nx - x), abs(ny - y), 1)
    for i in range(1, steps + 1):
        ix = x + int(round((nx - x) * i / steps))
        iy = y + int(round((ny - y) * i / steps))
        if not _air(tiles, ix, iy):
            return False
    return True


def reachable_from(tiles: list[str], start: tuple[int, int]) -> set[tuple[int, int]]:
    """Discrete platformer reachability: walk, fall, ladders, bumpers, jumps."""

    width = len(tiles[0])
    height = len(tiles)
    sx, sy = start
    seen: set[tuple[int, int]] = set()
    queue: deque[tuple[int, int]] = deque()
    if not _air(tiles, sx, sy):
        return seen
    queue.append((sx, sy))
    seen.add((sx, sy))
    network_nodes = [(x, y) for x, y, _ in iter_positions(tiles, "N")]
    network_links: dict[tuple[int, int], tuple[int, int]] = {}
    for index in range(0, len(network_nodes) - 1, 2):
        left, right = network_nodes[index], network_nodes[index + 1]
        network_links[left] = right
        network_links[right] = left

    def offer(nx: int, ny: int) -> None:
        if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and _air(tiles, nx, ny):
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
            if not _air(tiles, nx, y):
                continue
            if _standable(tiles, x, y) or _at(tiles, x, y) in LADDER_TILES:
                offer(nx, y)
        # ladders
        if _at(tiles, x, y) in LADDER_TILES or _at(tiles, x, y + 1) in LADDER_TILES:
            offer(x, y - 1)
            offer(x, y + 1)
        # bumper
        if _at(tiles, x, y) == "^":
            offer(x, y - 4)
        # Paired network hardware is a bidirectional traversal edge. This is
        # the same pairing instantiated by GameSim from sealed chapter data.
        if _at(tiles, x, y) == "N" and (x, y) in network_links:
            offer(*network_links[(x, y)])
        # jump from solid footing: same-height gap crosses and ledges up to 4
        if _standable(tiles, x, y):
            for dx in range(-6, 7):
                for dy in range(-4, 2):
                    if dx == 0 and dy >= 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    if not _standable(tiles, nx, ny):
                        continue
                    if _clear_arc(tiles, x, y, nx, ny):
                        offer(nx, ny)
    return seen


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


def validate_level(tiles: list[str], *, require_logo: bool = False) -> dict[str, Any]:
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
