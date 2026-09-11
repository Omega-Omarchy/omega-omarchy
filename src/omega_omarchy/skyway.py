"""Workshop-only upper routes and their deterministic platform grammar."""

from __future__ import annotations

from math import ceil

from .physics import AIR_JUMP_VEL, GRAVITY, JUMP_VEL, MAX_FALL, MAX_RUN, TILE
from .rng import Streams
from .reachability import reachable_from

SKYWAY_HEIGHT = 20
SKYWAY_BARRIER = 17


def arena_descent_clearance(height: int) -> int:
    """Conservative running double-jump reach from the highest deck to ground.

    Include time accelerating to terminal fall speed and three tiles for the
    player's width, initial rush momentum, and a clear landing before the gate.
    """
    drop = max(0, height - 4 - 8) * TILE
    airborne_ticks = drop / MAX_FALL + 2 * abs(JUMP_VEL + AIR_JUMP_VEL) / GRAVITY + MAX_FALL / GRAVITY
    return ceil(airborne_ticks * MAX_RUN / TILE) + 3


def add_skyway(tiles: list[str], seed: str, chapter_id: str, *, pad: bool = True) -> tuple[list[str], dict]:
    """Reserve the top screen for an optional connected route.

    K is a one-way ceiling with no visible terrain or support from above.
    A workshop-built lift is the sole entrance, including during cannon flight.
    No required collectible or progression anchor is placed above the seal.
    """
    width = len(tiles[0])
    canvas = [list("." * width) for _ in range(SKYWAY_HEIGHT)] + [list(row) for row in tiles] if pad else [list(row) for row in tiles]
    if not pad and any(cell != "." for row in canvas[:SKYWAY_HEIGHT] for cell in row):
        raise ValueError("Skyway requires an empty upper screen.")
    rng = Streams(f"{seed}:skyway:{chapter_id}:{width}")["layout"]
    canvas[SKYWAY_BARRIER] = ["K"] * width
    boss_columns = [xx for row in tiles for xx, cell in enumerate(row) if cell == "X"]
    gate_x = max(2, min(boss_columns) - 12) if boss_columns else width
    # Leave a clear descent before the arena. Tiny editor fixtures still get
    # one short route; campaign maps reserve the full approach margin.
    clearance = arena_descent_clearance(len(canvas))
    end_x = max(6, gate_x - clearance) if gate_x < width and width >= 40 else width - 3
    decks, branches = [], []
    x, index = 2, 0
    previous_shape = ""
    while x < end_x:
        span = min(rng.randint(8, 12), end_x - x)
        if span < 3:
            break
        shape = rng.choice([name for name in ("terrace", "split-deck", "high-road") if name != previous_shape])
        y = 11 if index % 2 == 0 else 12
        invisible = chapter_id == "walled-garden" and index % 3 != 0
        for xx in range(x, x + span):
            # Visible landing pads make the hidden span readable and leave a
            # safe surface from which to discover the next platform.
            canvas[y][xx] = "I" if invisible and x + 2 <= xx < x + span - 2 else "="
        decks.append({"x": x, "y": y, "width": span, "shape": shape, "invisible": invisible})
        if shape == "split-deck" and span >= 9:
            canvas[y][x + span // 2] = "."
        if shape == "high-road" and span >= 9:
            for xx in range(x + 2, x + span - 2):
                canvas[y - 3][xx] = "="
            canvas[y - 4][x + span // 2] = "C"
            branches.append({"x": x + 2, "y": y - 3, "width": span - 4})
        elif index % 3 == 1:
            canvas[y - 1][x + 1] = "C"
        previous_shape = shape
        x += span + 2
        index += 1
    # Each module begins on a solid visible pad. Lifts always arrive here,
    # including when the module's middle is an invisible platform.
    entries = [[deck["x"], deck["y"] - 1] for deck in decks]
    return ["".join(row) for row in canvas], {
        "version": 3, "barrierY": SKYWAY_BARRIER, "height": SKYWAY_HEIGHT,
        "approachClearanceTiles": clearance,
        "endX": end_x, "bossGateX": gate_x if boss_columns else None,
        "decks": decks, "branches": branches, "entries": entries, "lifts": [],
        "unlocked": False,
    }


def upper_route_report(tiles: list[str], spec: dict) -> dict:
    entries = [tuple(point) for point in spec.get("entries", [])]
    if not entries:
        return {"ok": False, "errors": ["upper-route-missing-landing"]}
    reached = reachable_from(tiles, entries[0])
    missing = [list(point) for point in entries if point not in reached]
    rewards = [(x, y) for y, row in enumerate(tiles[:int(spec["barrierY"])]) for x, cell in enumerate(row) if cell == "C"]
    return {"ok": not missing and all(point in reached for point in rewards),
            "errors": [f"upper-landing-unreachable:{x}:{y}" for x, y in missing]
                      + [f"upper-reward-unreachable:{x}:{y}" for x, y in rewards if (x, y) not in reached],
            "reachableCount": len(reached), "landings": len(entries)}


def garden_invisible_platforms(tiles: list[str]) -> list[str]:
    """Hide short optional mid-level spans while retaining ladder landings."""
    result = list(tiles)
    floor = len(tiles) - 4
    changed = 0
    for y in range(max(SKYWAY_HEIGHT + 3, floor - 24), floor - 5):
        for x in range(20, len(tiles[0]) - 22):
            if changed >= 18:
                return result
            if tiles[y][x:x + 3] != "===" or result[y][x - 1] == "I":
                continue
            if any(cell in "L+OPH" for row in tiles[y - 2:y + 3] for cell in row[x - 2:x + 5]):
                continue
            result[y] = result[y][:x] + "III" + result[y][x + 3:]
            changed += 3
    return result
