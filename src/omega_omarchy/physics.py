"""Side-scrolling movement with a documented AABB collision model.

World space is pixels. TILE is always 16 world-pixels and never changes with
art fidelity or display treatment.

Body.x, Body.y
    Top-left of the axis-aligned hitbox, in world pixels.
Body.width, Body.height
    Hitbox size. Default 10×18. Independent of sprite resolution.

Visual sprites are drawn with their feet at the hitbox bottom-center:

    feet = (body.x + body.width / 2, body.y + body.height)
    blit  = (feet.x - sprite_w / 2, feet.y - sprite_h)

A solid tile occupies its complete logical cell
[tx*TILE, (tx+1)*TILE) × [ty*TILE, (ty+1)*TILE). Sampling is inclusive on the
minimum edge and exclusive on the maximum, with a tiny symmetric epsilon so
left and right approaches match. Horizontal and vertical resolution use the
same contact search; motion is sub-stepped so ordinary speeds cannot tunnel.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

TILE = 16
GRAVITY = 0.28
MAX_FALL = 5.6
ACCEL = 0.55
DECEL = 0.45
MAX_RUN = 2.15
JUMP_VEL = -5.15
STAND_HEIGHT = 18.0
CROUCH_HEIGHT = 12.0
SLIDE_SPEED = 3.85
SLIDE_CLEAR_SPEED = 2.7
SLIDE_FRAMES = 20
MOMENTUM_SLIDE_FRAMES = 34
RUSH_SPEED = 4.35
RUSH_FRAMES = 11
DOUBLE_TAP_FRAMES = 13
AIR_JUMP_VEL = -2.65
LADDER_SLIDE_SPEED = 4.4
COYOTE_FRAMES = 7
BUFFER_FRAMES = 7
PRECISION_ASSIST_COYOTE = 12
PRECISION_ASSIST_BUFFER = 10
EPS = 1e-6
LADDER_FORGIVE = 4.0
LADDER_SNAP = 0.35
LADDER_ENTRY_RATIO = 0.80
# Lowercase ``g`` is the invisible collision phase while a boss gate's art is
# visibly descending; it becomes the ordinary rendered ``G`` when closed.
SOLID = frozenset({"#", "=", "+", "B", "D", "G", "g"})
LADDER_GLYPHS = frozenset({"L", "+"})


@dataclass(frozen=True)
class InputState:
    left: bool = False
    right: bool = False
    left_pressed: bool = False
    right_pressed: bool = False
    up: bool = False
    down: bool = False
    up_pressed: bool = False
    down_pressed: bool = False
    jump: bool = False
    jump_pressed: bool = False
    action: bool = False
    action_pressed: bool = False
    interact: bool = False
    turn: bool = False
    turn_pressed: bool = False
    item: bool = False
    customize: bool = False
    pause: bool = False


@dataclass(frozen=True)
class Body:
    x: float
    y: float
    vx: float
    vy: float
    on_ground: bool
    coyote: int
    buffer: int
    facing: int
    width: float = 10.0
    height: float = 18.0
    on_ladder: bool = False
    crouching: bool = False
    sliding: bool = False
    slide_ticks: int = 0
    slide_locked: bool = False
    rushing: bool = False
    rush_ticks: int = 0
    tap_direction: int = 0
    tap_ticks: int = 0
    air_jump_used: bool = False
    ladder_sliding: bool = False
    climb_phase: int = 0
    climb_ticks: int = 0

    @property
    def feet(self) -> tuple[float, float]:
        return self.x + self.width / 2.0, self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2.0, self.y + self.height / 2.0


def _tile_at(tiles: list[str], tx: int, ty: int) -> str:
    if ty < 0 or ty >= len(tiles) or tx < 0 or tx >= len(tiles[0]):
        return "#"
    return tiles[ty][tx]


def _solid(glyph: str, *, ignore_ladder_deck: bool = False) -> bool:
    return glyph in SOLID and not (ignore_ladder_deck and glyph == "+")


def _range(x: float, size: float) -> tuple[int, int]:
    lo = int(x // TILE)
    hi = int((x + size - EPS) // TILE)
    return lo, hi


def _collides(
    tiles: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    ignore_ladder_deck: bool = False,
) -> bool:
    x0, x1 = _range(x, w)
    y0, y1 = _range(y, h)
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            if _solid(_tile_at(tiles, tx, ty), ignore_ladder_deck=ignore_ladder_deck):
                return True
    return False


def overlapping_tiles(
    tiles: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    glyphs: Iterable[str] | None = None,
) -> list[tuple[int, int, str]]:
    wanted = None if glyphs is None else set(glyphs)
    x0, x1 = _range(x, w)
    y0, y1 = _range(y, h)
    found: list[tuple[int, int, str]] = []
    for ty in range(y0, y1 + 1):
        for tx in range(x0, x1 + 1):
            glyph = _tile_at(tiles, tx, ty)
            if wanted is None or glyph in wanted:
                found.append((tx, ty, glyph))
    return found


def _overlaps_glyph(
    tiles: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    glyph: str,
    *,
    inflate: float = 0.0,
) -> bool:
    return bool(
        overlapping_tiles(
            tiles,
            x - inflate,
            y,
            w + 2 * inflate,
            h,
            glyphs={glyph},
        )
    )


def ladder_column(tiles: list[str], body: Body) -> int | None:
    hits = overlapping_tiles(
        tiles,
        body.x - LADDER_FORGIVE,
        body.y,
        body.width + 2 * LADDER_FORGIVE,
        body.height + 2.0,
        glyphs=LADDER_GLYPHS,
    )
    if not hits:
        return None
    cx = body.x + body.width / 2.0
    hits.sort(key=lambda item: abs((item[0] + 0.5) * TILE - cx))
    return hits[0][0]


def _ladder_entry_aligned(body: Body, col: int) -> bool:
    """Return whether enough of the player is over a ladder to mount it.

    General ladder detection stays forgiving so an already-mounted player
    remains latched, but a new mount requires nearly the full collision width.
    """
    ladder_left = col * TILE
    ladder_right = ladder_left + TILE
    overlap = max(
        0.0,
        min(body.x + body.width, ladder_right) - max(body.x, ladder_left),
    )
    return overlap + EPS >= body.width * LADDER_ENTRY_RATIO


def _ladder_bounds(tiles: list[str], col: int, body: Body) -> tuple[int, int] | None:
    """Return the contiguous ladder run nearest the player's center."""

    rows = [y for y, row in enumerate(tiles) if 0 <= col < len(row) and row[col] in LADDER_GLYPHS]
    if not rows:
        return None
    center_row = int(body.center[1] // TILE)
    anchor = min(rows, key=lambda row: abs(row - center_row))
    top = bottom = anchor
    while top - 1 in rows:
        top -= 1
    while bottom + 1 in rows:
        bottom += 1
    return top, bottom


def _axis_move(
    tiles: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    delta: float,
    axis: str,
    *,
    ignore_ladder_deck: bool = False,
) -> tuple[float, bool]:
    """Move along one axis. Returns (position, hit)."""

    if abs(delta) < EPS:
        return (x if axis == "x" else y), False
    if axis == "x":
        target, other = x + delta, y
    else:
        target, other = y + delta, x
    if axis == "x":
        blocked = _collides(tiles, target, y, w, h, ignore_ladder_deck=ignore_ladder_deck)
    else:
        blocked = _collides(tiles, x, target, w, h, ignore_ladder_deck=ignore_ladder_deck)
    if not blocked:
        return target, False
    lo, hi = (x if axis == "x" else y), target
    for _ in range(24):
        mid = (lo + hi) / 2.0
        if axis == "x":
            hit = _collides(tiles, mid, y, w, h, ignore_ladder_deck=ignore_ladder_deck)
        else:
            hit = _collides(tiles, x, mid, w, h, ignore_ladder_deck=ignore_ladder_deck)
        if hit:
            hi = mid
        else:
            lo = mid
        if abs(hi - lo) < EPS:
            break
    return lo, True


def _nudge_out(tiles: list[str], body: Body) -> Body:
    # ``+`` is a one-way ladder deck. It is never valid to eject a body from
    # one: the player may be climbing or jumping through its underside.
    ignore_deck = True
    if not _collides(tiles, body.x, body.y, body.width, body.height, ignore_ladder_deck=ignore_deck):
        return body
    for dist in range(1, int(body.height) + 6):
        for dx, dy in ((0, -dist), (0, dist), (-dist, 0), (dist, 0)):
            nx, ny = body.x + dx, body.y + dy
            if not _collides(tiles, nx, ny, body.width, body.height, ignore_ladder_deck=ignore_deck):
                return replace(body, x=nx, y=ny)
    return body


def _one_way_deck_landing(
    tiles: list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    delta: float,
) -> float | None:
    """Return the landing y when a descending body crosses a ``+`` deck.

    Ordinary solid resolution cannot model a pass-through platform because a
    body is allowed to overlap it on the way up. Only a downward crossing of
    the tile's top face is solid.
    """

    if delta <= 0:
        return None
    old_feet = y + h
    new_feet = old_feet + delta
    x0, x1 = _range(x, w)
    candidates: list[float] = []
    first_row = max(0, int((old_feet - EPS) // TILE))
    last_row = min(len(tiles) - 1, int((new_feet + EPS) // TILE))
    for ty in range(first_row, last_row + 1):
        deck = ty * TILE
        if old_feet > deck + EPS or new_feet < deck - EPS:
            continue
        for tx in range(x0, x1 + 1):
            if _tile_at(tiles, tx, ty) == "+":
                candidates.append(deck - h)
                break
    return min(candidates) if candidates else None


def _ladder_exit_available(tiles: list[str], body: Body, direction: int) -> bool:
    """Allow a horizontal dismount when a nearby platform meets the feet."""

    nx = body.x + direction * (TILE * 0.62)
    if _collides(tiles, nx, body.y, body.width, body.height):
        return False
    # A platform top may be a few pixels above or below the player's feet.
    for offset in (-3.0, -1.0, 1.0, 3.0, 5.0):
        if _collides(tiles, nx, body.y + offset, body.width, body.height + 1.0):
            return True
    return False


def step_body(
    body: Body,
    inp: InputState,
    tiles: list[str],
    *,
    speed_scale: float = 1.0,
    jump_scale: float = 1.0,
    precision_assist: bool = False,
    phase_solids: bool = False,
    ballistic: bool = False,
    ground_strength_jump: bool = False,
) -> Body:
    # Authored gusts may carry the player through an otherwise solid obstacle.
    # The exception is intentionally frame-scoped by the simulation: as soon
    # as the body leaves the gust field, ordinary collision resumes.
    if not phase_solids:
        body = _nudge_out(tiles, body)
    # Down by itself is intentionally inert. The low hitbox belongs only to a
    # moving Down+direction slide. Once its momentum expires, a held combo
    # locks locomotion but restores the normal standing body and idle art.
    if ballistic:
        # A cannon launch is a committed trajectory. Gravity, bumpers, and
        # collision still apply, but ordinary run/slide input must not shave
        # its authored momentum down to the normal movement cap.
        inp = InputState()
        body = replace(
            body,
            on_ladder=False,
            crouching=False,
            sliding=False,
            slide_ticks=0,
            slide_locked=False,
            rushing=False,
            rush_ticks=0,
            ladder_sliding=False,
        )
    slide_direction = -1 if inp.left and not inp.right else (1 if inp.right and not inp.left else 0)
    slide_combo = bool(inp.down and slide_direction and body.on_ground and not body.on_ladder)
    slide_started = bool(
        slide_combo
        and not body.slide_locked
        and (
            inp.down_pressed
            or (slide_direction < 0 and inp.left_pressed)
            or (slide_direction > 0 and inp.right_pressed)
        )
    )
    momentum_slide = bool(slide_started and body.rushing and body.on_ground)
    # Once a low body has entered a tunnel, duration and input cancellation no
    # longer take precedence over physical clearance. Keep sliding until the
    # complete standing AABB can be restored without intersecting the ceiling.
    clearance_required = bool(
        not phase_solids
        and body.height < STAND_HEIGHT
        and _collides(
            tiles,
            body.x,
            body.y - (STAND_HEIGHT - body.height),
            body.width,
            STAND_HEIGHT,
        )
    )
    slide_ticks = (
        MOMENTUM_SLIDE_FRAMES
        if momentum_slide
        else (SLIDE_FRAMES if slide_started else max(0, body.slide_ticks - 1))
    )
    if clearance_required:
        slide_ticks = max(1, slide_ticks)
    sliding = bool(
        slide_started
        or (body.sliding and ((slide_ticks > 0 and slide_combo) or clearance_required))
    )
    slide_locked = bool(
        slide_combo
        and (
            body.slide_locked
            or (body.sliding and slide_ticks == 0)
        )
    )
    crouching = bool(sliding)
    height = body.height
    y_adjust = 0.0
    if crouching and height > CROUCH_HEIGHT:
        y_adjust = height - CROUCH_HEIGHT
        height = CROUCH_HEIGHT
    elif not crouching and height < STAND_HEIGHT:
        proposed_y = body.y - (STAND_HEIGHT - height)
        if phase_solids or not _collides(tiles, body.x, proposed_y, body.width, STAND_HEIGHT):
            y_adjust = proposed_y - body.y
            height = STAND_HEIGHT
        else:
            crouching = True
    if y_adjust:
        body = replace(body, y=body.y + y_adjust, height=height)

    max_run = MAX_RUN * speed_scale
    accel = ACCEL * speed_scale
    vx = body.vx
    tap_direction = body.tap_direction
    tap_ticks = max(0, body.tap_ticks - 1)
    pressed_direction = -1 if inp.left_pressed and not inp.right_pressed else (1 if inp.right_pressed and not inp.left_pressed else 0)
    rush_started = bool(
        pressed_direction
        and pressed_direction == body.tap_direction
        and body.tap_ticks > 0
        and body.on_ground
        and not crouching
        and not body.on_ladder
    )
    if pressed_direction:
        tap_direction = pressed_direction
        tap_ticks = DOUBLE_TAP_FRAMES
    held_direction = -1 if inp.left and not inp.right else (1 if inp.right and not inp.left else 0)
    rush_continues = bool(body.rushing and body.on_ground and held_direction == body.facing)
    rush_ticks = RUSH_FRAMES if (rush_started or rush_continues) else 0
    rushing = bool((rush_started or rush_continues) and not crouching and not body.on_ladder)

    if ballistic:
        facing = body.facing
    elif slide_started:
        slide_speed = SLIDE_SPEED
        if momentum_slide:
            slide_speed = max(SLIDE_SPEED, min(RUSH_SPEED * 1.08, abs(body.vx) * 1.08))
        vx = slide_direction * slide_speed * speed_scale
        facing = slide_direction
    elif sliding:
        facing = body.facing
        vx *= 0.94
        if clearance_required and abs(vx) < SLIDE_CLEAR_SPEED * speed_scale:
            vx = facing * SLIDE_CLEAR_SPEED * speed_scale
    elif slide_locked:
        # Require the combo to be released before ordinary locomotion can
        # resume. Holding it cannot leak into a crouched walk animation.
        facing = body.facing
        vx = 0.0
    elif rushing:
        facing = pressed_direction or body.facing
        vx = facing * RUSH_SPEED * speed_scale
    elif inp.left and not inp.right:
        vx -= accel
        facing = -1
    elif inp.right and not inp.left:
        vx += accel
        facing = 1
    else:
        facing = body.facing
        if vx > 0:
            vx = max(0.0, vx - DECEL)
        elif vx < 0:
            vx = min(0.0, vx + DECEL)
    speed_cap = max(max_run, abs(vx)) if ballistic else max_run
    if sliding:
        speed_cap = max(speed_cap, SLIDE_SPEED * speed_scale)
    if rushing:
        speed_cap = max(speed_cap, RUSH_SPEED * speed_scale)
    vx = max(-speed_cap, min(speed_cap, vx))

    on_ground = body.on_ground
    coyote = body.coyote
    buffer = body.buffer
    air_jump_used = body.air_jump_used
    if on_ground:
        coyote = PRECISION_ASSIST_COYOTE if precision_assist else COYOTE_FRAMES
        air_jump_used = False
    else:
        coyote = max(0, coyote - 1)
    if inp.jump_pressed:
        buffer = PRECISION_ASSIST_BUFFER if precision_assist else BUFFER_FRAMES
    else:
        buffer = max(0, buffer - 1)

    col = ladder_column(tiles, body)
    touching_ladder = col is not None
    ladder_bounds = _ladder_bounds(tiles, col, body) if col is not None else None
    on_bumper = _overlaps_glyph(tiles, body.x, body.y, body.width, body.height, "^")

    vy = body.vy
    climbing = False
    # Ladder contact is latched once the player begins climbing. Releasing the
    # direction holds position instead of re-enabling gravity; jump cleanly
    # detaches, while walking off the ladder naturally drops the latch as soon
    # as the overlap ends.
    exit_direction = -1 if inp.left and not inp.right else (1 if inp.right and not inp.left else 0)
    walking_off = bool(body.on_ladder and exit_direction and _ladder_exit_available(tiles, body, exit_direction))
    intent = -1 if inp.up and not inp.down else (1 if inp.down and not inp.up else 0)
    entry_allowed = False
    if ladder_bounds is not None and col is not None and _ladder_entry_aligned(body, col):
        top, bottom = ladder_bounds
        run_top = top * TILE
        if intent < 0:
            # At the top landing, Up keeps walking rather than remounting.
            entry_allowed = body.y > run_top + EPS
        elif intent > 0:
            # At the bottom landing, Down keeps walking/crouching rather than remounting.
            entry_allowed = body.feet[1] < bottom * TILE - EPS
    ladder_sliding = bool(
        body.on_ladder
        and touching_ladder
        and inp.down
        and (inp.jump_pressed or (body.ladder_sliding and inp.jump))
    )
    jump_detaches = inp.jump_pressed and not ladder_sliding
    climbing = touching_ladder and (body.on_ladder or entry_allowed) and not jump_detaches and not walking_off
    if climbing:
        # Mounting consumes horizontal momentum; a latched ladder should not
        # leak an earlier run/rush into a sideways drift.
        vx = 0.0
        rushing = False
        rush_ticks = 0
        sliding = False
        slide_ticks = 0
        vy = LADDER_SLIDE_SPEED if ladder_sliding else (-1.7 if inp.up else (1.7 if inp.down else 0.0))
        if ladder_sliding:
            buffer = 0
        on_ground = True
        coyote = COYOTE_FRAMES
        air_jump_used = False
    else:
        vy = body.vy + GRAVITY
        vy = min(MAX_FALL, vy)

    jumped = False
    if on_bumper and vy >= 0:
        vy = JUMP_VEL * jump_scale * 1.2
        buffer = 0
        coyote = 0
        on_ground = False
        jumped = True
    elif inp.jump_pressed and ground_strength_jump and not climbing:
        # Gusts grant the same clean impulse as solid footing. This is kept
        # separate from ``on_ground`` so an airborne gust jump cannot also
        # start a ground-only rush or slide.
        vy = JUMP_VEL * jump_scale
        buffer = 0
        coyote = 0
        on_ground = False
        air_jump_used = False
        jumped = True
    elif buffer > 0 and coyote > 0:
        vy = JUMP_VEL * jump_scale
        buffer = 0
        coyote = 0
        on_ground = False
        jumped = True
    elif inp.jump_pressed and not climbing and not on_ground and not air_jump_used:
        # A single airborne jump adds height without becoming a full second jump.
        vy = min(0.0, vy) + AIR_JUMP_VEL * jump_scale
        buffer = 0
        air_jump_used = True
        jumped = True

    # Sub-step so high speed cannot skip a tile.
    remaining_x, remaining_y = vx, vy
    x, y = body.x, body.y
    hit_x = hit_y = False
    steps = max(1, int(max(abs(remaining_x), abs(remaining_y)) / (TILE / 4)) + 1)
    for _ in range(steps):
        dx = remaining_x / steps
        dy = remaining_y / steps
        if phase_solids:
            x = max(0.0, min(len(tiles[0]) * TILE - body.width, x + dx))
            hx = False
        else:
            x, hx = _axis_move(
                tiles,
                x,
                y,
                body.width,
                body.height,
                dx,
                "x",
                # A crossing's side is not a wall; neighboring ``=`` tiles still
                # provide the ordinary platform edge.
                ignore_ladder_deck=True,
            )
        hit_x = hit_x or hx
        old_y = y
        if phase_solids:
            y = max(0.0, min(len(tiles) * TILE - body.height, y + dy))
            hy = False
        else:
            y, hy = _axis_move(
                tiles,
                x,
                y,
                body.width,
                body.height,
                dy,
                "y",
                # Resolve ordinary solids first. Ladder decks are one-way and get
                # a top-face crossing test below.
                ignore_ladder_deck=True,
            )
        deck_y = (
            None
            if (climbing or phase_solids)
            else _one_way_deck_landing(tiles, x, old_y, body.width, body.height, dy)
        )
        if deck_y is not None and deck_y <= y + EPS:
            y = deck_y
            hy = True
        hit_y = hit_y or hy
        if hx:
            remaining_x = 0.0
            vx = 0.0
        if hy:
            remaining_y = 0.0

    landed = False
    if hit_y:
        if vy > 0:
            landed = True
            on_ground = True
            vy = 0.0
        else:
            vy = 0.0
            on_ground = False
    else:
        normal_ground = not phase_solids and _collides(
            tiles,
            x,
            y + 1.0,
            body.width,
            body.height,
            ignore_ladder_deck=True,
        )
        deck_ground = (
            not phase_solids
            and _one_way_deck_landing(tiles, x, y, body.width, body.height, 1.0) is not None
        )
        on_ground = (normal_ground or deck_ground) and vy >= 0 and not jumped

    # Climbing upward lands cleanly on the first ladder/deck crossing instead
    # of floating an entire body above it. Descending intentionally passes
    # through the same deck.
    deck_landed = False
    if climbing and vy < 0 and col is not None:
        old_feet = body.feet[1]
        new_feet = y + body.height
        deck_tops = [row * TILE for row, line in enumerate(tiles) if line[col] == "+"]
        # Do not instantly re-land on the deck the player is leaving. Only a
        # crossing that was strictly above the previous feet is an arrival.
        crossed = [deck for deck in deck_tops if new_feet <= deck < old_feet - EPS]
        if crossed:
            deck = max(crossed)
            y = deck - body.height
            vy = 0.0
            on_ground = True
            climbing = False
            ladder_sliding = False
            deck_landed = True
    elif climbing and vy > 0 and col is not None and ladder_bounds is not None:
        _, bottom = ladder_bounds
        if tiles[bottom][col] == "+":
            old_feet = body.feet[1]
            new_feet = y + body.height
            deck = bottom * TILE
            if old_feet <= deck <= new_feet:
                y = deck - body.height
                vy = 0.0
                on_ground = True
                climbing = False
                ladder_sliding = False
                deck_landed = True

    if climbing and col is not None:
        target = col * TILE + (TILE - body.width) / 2.0
        snapped = x + (target - x) * LADDER_SNAP
        if phase_solids or not _collides(tiles, snapped, y, body.width, body.height):
            x = snapped

    climb_phase = body.climb_phase
    climb_ticks = body.climb_ticks
    if climbing and abs(vy) > 0.2 and not ladder_sliding:
        climb_ticks += 1
        if climb_ticks >= 6:
            climb_phase = (climb_phase + (1 if vy > 0 else -1)) % 4
            climb_ticks = 0
    elif not climbing:
        climb_ticks = 0

    return Body(
        x=x,
        y=y,
        vx=0.0 if hit_x else vx,
        vy=vy,
        on_ground=on_ground or landed or deck_landed,
        coyote=coyote,
        buffer=buffer,
        facing=facing,
        width=body.width,
        height=body.height,
        on_ladder=touching_ladder and climbing,
        crouching=crouching,
        sliding=sliding,
        slide_ticks=slide_ticks,
        slide_locked=slide_locked,
        rushing=rushing,
        rush_ticks=rush_ticks,
        tap_direction=tap_direction,
        tap_ticks=tap_ticks,
        air_jump_used=air_jump_used,
        ladder_sliding=ladder_sliding and climbing,
        climb_phase=climb_phase,
        climb_ticks=climb_ticks,
    )


def spawn_body(tiles: list[str]) -> Body:
    from .reachability import find_spawn

    sx, sy = find_spawn(tiles)
    # Center the 10px box in the spawn tile; sit on the tile below.
    x = sx * TILE + (TILE - 10) / 2.0
    y = sy * TILE + TILE - 18
    return Body(x=x, y=y, vx=0.0, vy=0.0, on_ground=True, coyote=COYOTE_FRAMES, buffer=0, facing=1)
