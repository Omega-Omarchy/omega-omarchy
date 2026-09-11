"""Chapter 1's paced route grammar, independent of rendering and simulation."""

from __future__ import annotations

from typing import Any

from .rng import Stream


def _pick_fresh(options: tuple[str, ...], history: list[str], stream: Stream) -> str:
    """Prefer the least-used option, avoiding the previous two when possible."""

    candidates = [item for item in options if item not in history[-2:]]
    candidates = candidates or [item for item in options if item not in history[-1:]] or list(options)
    least = min(history.count(item) for item in candidates)
    return str(stream.choice([item for item in candidates if history.count(item) == least]))


def plan_chapter_one(
    width: int,
    sector_width: int,
    recipes: tuple[str, ...],
    motifs: tuple[str, ...],
    stream: Stream,
    *,
    include_optional: bool,
) -> list[dict[str, Any]]:
    """Partition the playable interior and assign decisions before decoration.

    Spawn and boss approaches are outside the partition. Width variation never
    creates tiny leftover sectors. A calm opening, early discovery, middle
    breather and final remix are stable; intervening challenges vary by seed.
    """

    available = width - 44
    count = max(4, min(available // 24, round(available / sector_width)))
    sizes = [available // count + (i < available % count) for i in range(count)]
    for i in range(count - 1):
        shift = stream.randint(-6, 6)
        shift = max(24 - sizes[i], min(sizes[i + 1] - 24, shift))
        sizes[i] += shift
        sizes[i + 1] -= shift

    middle = count // 2
    beats = ["arrival", "discovery"]
    history: list[str] = ["discovery"]
    for i in range(2, count - 1):
        if i == middle:
            beat = "breather"
        else:
            beat = _pick_fresh(("traversal", "encounter", "discovery"), history, stream)
            history.append(beat)
        beats.append(beat)
    beats.append("climax")

    routes = {
        "arrival": ("terraces",),
        "discovery": ("overpass", "ridge"),
        "traversal": ("stepping-stones", "ridge", "overpass"),
        "encounter": ("courtyard",),
        "breather": ("cache-garden",),
        "climax": ("stepping-stones", "overpass"),
    }
    route_history: list[str] = []
    recipe_history: list[str] = []
    family_history: list[str] = []
    motif_history: list[str] = []
    sections: list[dict[str, Any]] = []
    x = 20
    for i, (size, beat) in enumerate(zip(sizes, beats)):
        route = _pick_fresh(routes[beat], route_history, stream)
        route_history.append(route)
        motif = _pick_fresh(motifs, motif_history, stream)
        motif_history.append(motif)
        branch = None
        if include_optional and beat in {"discovery", "climax"}:
            families = {
                "sky-well": "tower", "twin-towers": "tower",
                "switchback": "switchback", "archive-stacks": "switchback",
            }
            fresh = tuple(recipe for recipe in recipes if families.get(recipe, "chain") not in family_history[-1:])
            branch = _pick_fresh(fresh or recipes, recipe_history, stream)
            recipe_history.append(branch)
            family_history.append(families.get(branch, "chain"))
        sections.append({
            "x": x,
            "width": size,
            "beat": beat,
            "route": route,
            "recipe": branch or route,
            "branchRecipe": branch,
            "motif": motif,
            "mirrored": stream.chance(0.5) if beat != "arrival" else False,
            "rise": 1 if beat == "arrival" else stream.randint(2, 3),
        })
        x += size
    return sections


def paint_chapter_one_section(
    canvas: list[list[str]],
    section: dict[str, Any],
    floor: int,
    difficulty: str,
    *,
    include_optional: bool,
) -> dict[str, Any]:
    """Paint a connected ground challenge and, where planned, a reward loop.

    All measurements are local to a section. Main-route steps rise at most one
    tile at a time, gaps are bounded, and branch ladders rejoin on both sides.
    Mirroring changes the approach without changing seam heights.
    """

    x0, width = int(section["x"]), int(section["width"])
    center = width // 2
    mirror = bool(section["mirrored"])
    pits: list[tuple[int, int]] = []
    rewards: list[tuple[int, int]] = []

    def world_x(x: int) -> int:
        return x0 + (width - 1 - x if mirror else x)

    def put(x: int, y: int, glyph: str) -> None:
        if 0 <= x < width and 0 < y < len(canvas):
            canvas[y][world_x(x)] = glyph

    def deck(left: int, right: int, y: int) -> None:
        for x in range(left, right):
            put(x, y, "=")

    def ladder(x: int, top: int, bottom: int) -> None:
        for y in range(top, bottom + 1):
            put(x, y, "L")

    def mound(left: int, right: int, rise: int) -> None:
        for x in range(left, right):
            for y in range(floor - rise, floor):
                put(x, y, "#")

    def gap(left: int, span: int) -> None:
        for x in range(left, left + span):
            for y in range(floor, len(canvas) - 1):
                put(x, y, "M")
        ends = sorted((world_x(left), world_x(left + span - 1)))
        pits.append((ends[0], ends[1] + 1))

    def reward(x: int, y: int, glyph: str) -> None:
        put(x, y, glyph)
        rewards.append((world_x(x), y))

    route = section["route"]
    rise = int(section["rise"])
    if route == "terraces":
        mound(5, center + 3, 1)
        deck(center + 4, width - 3, floor - 4)
        if include_optional:
            reward(width - 5, floor - 5, "O")
    elif route == "ridge":
        for step in range(rise):
            mound(5 + step * 3, width - 5 - step * 3, step + 1)
        reward(center, floor - rise - 1, "C")
    elif route == "stepping-stones":
        span = 2 if difficulty == "casual" else 3
        gap(6, span)
        gap(width - 6 - span, span)
        deck(center - 2, center + 3, floor - 3)
        reward(center, floor - 4, "C")
    elif route == "overpass":
        gap(center - 1, 2 if difficulty == "casual" else 3)
        deck(4, width - 4, floor - 4)
        ladder(5, floor - 5, floor - 1)
        ladder(width - 6, floor - 5, floor - 1)
        reward(width - 9, floor - 5, "C")
    elif route == "courtyard":
        mound(center - 1, center + 2, 1)
        deck(4, 10, floor - 3)
        deck(width - 10, width - 4, floor - 3)
        put(7, floor - 4, "E")
        put(width - 7, floor - 1, "E")
        reward(center, floor - 2, "C")
    elif route == "cache-garden":
        deck(4, 11, floor - 3)
        reward(7, floor - 4, "P")
        reward(width - 7, floor - 1, "C")

    recipe = section["branchRecipe"]
    if recipe:
        # Keep early discoveries in view; reserve the tall silhouette for the
        # late remix. Three distinct shapes replace a tower in every sector.
        high = 16 if section["beat"] == "climax" else 9
        high = min(high, floor - 4)
        if recipe in {"sky-well", "twin-towers"}:
            top = floor - high
            deck(4, width - 4, top)
            ladder(5, top - 1, floor - 1)
            ladder(width - 6, top - 1, floor - 1)
            deck(5, center - 2, floor - 5)
            reward(center + 2, top - 1, "O")
        elif recipe in {"switchback", "archive-stacks"}:
            deck(3, center + 1, floor - 4)
            deck(center - 2, width - 3, floor - 7)
            deck(4, center + 2, floor - high)
            ladder(5, floor - high - 1, floor - 1)
            ladder(width - 5, floor - 8, floor - 1)
            reward(center - 2, floor - high - 1, "O")
        else:
            # Short spans and a safe floor below make a horizontal reward
            # route. The bumper is a shortcut, never a completion dependency.
            for left, top in ((3, floor - 3), (center - 3, floor - 6), (width - 9, floor - 9)):
                deck(left, left + 6, top)
                ladder(left + 1, top - 1, floor - 1)
            if recipe == "bumper-gallery":
                put(9, floor - 1, "^")
            reward(width - 4, floor - 10, "O")

    # The remix introduces one opponent only after the final landing. No
    # enemies or breakable obstacles are scattered into gap takeoff zones.
    if section["beat"] == "climax":
        put(2 if mirror else width - 3, floor - 1, "E")
    return {"pits": pits, "rewards": rewards}
