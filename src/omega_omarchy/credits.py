"""Portable, deterministic credit timeline. No Git, network, or mixer required."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

FPS = 60
SILENT_TAIL = 5.0
CAST_THEME_FADE_SECONDS = 2.5
ROLL_OPENING_HOLD = 3.0
# Logical pixels per second: about ten seconds for a full screen to pass.
# A target rather than a hard cap: never omit names or shrink below the floor.
ROLL_TARGET_SPEED = 18.0
PATRON_FONT_SIZES = (8, 7.75, 7.5, 7.25, 7, 6.75, 6.5)


def scrub_distance(held_seconds: float) -> float:
    """Integrated hold travel: pause for precision, then ramp from 4x to 32x."""
    t = max(0.0, held_seconds - 0.25)
    ramp = min(t, 3.0)
    return 4 * ramp + (28 / 6) * ramp * ramp + 32 * max(0.0, t - 3)


@lru_cache(maxsize=1)
def credit_manifest() -> dict:
    return json.loads((Path(__file__).parent / "data" / "credits.json").read_text(encoding="utf-8"))


def roll_duration() -> float:
    return float(credit_manifest()["music"]["duration"]) + SILENT_TAIL


def title_duration() -> float:
    return sum(card["seconds"] for card in credit_manifest()["castCards"])


def cast_card(seconds: float) -> tuple[dict, float]:
    cards = credit_manifest()["castCards"]
    for card in cards:
        if seconds < card["seconds"]:
            return card, max(0.0, seconds)
        seconds -= card["seconds"]
    return cards[-1], float(cards[-1]["seconds"])


def roll_offset(seconds: float, height: float) -> float:
    # Original linear timing anchors STARRING and every subsequent credit.
    # Finish the last seal above the frame as the recording ends, then leave
    # five seconds of unbroken black.
    duration = float(credit_manifest()["music"]["duration"])
    return (height + 105.0) * max(0.0, min(1.0, seconds / duration)) - 105.0


def roll_opening_offset(seconds: float, height: float, start: float, join: float) -> float:
    """Hold, then smoothly join the original scroll position and velocity.

    Joining before STARRING enters keeps that cue and every later credit on
    its existing soundtrack frame. A much longer future roster may shorten
    the hold to leave at least half the opening available for movement.
    """
    if seconds >= join:
        return roll_offset(seconds, height)
    hold = min(ROLL_OPENING_HOLD, join / 2)
    if seconds <= hold:
        return start
    span = join - hold
    t = (seconds - hold) / span
    end = roll_offset(join, height)
    speed = (height + 105.0) / float(credit_manifest()["music"]["duration"])
    # Cubic Hermite: start at rest, arrive at the ordinary rolling speed.
    return (2 * t**3 - 3 * t**2 + 1) * start + (-2 * t**3 + 3 * t**2) * end + (t**3 - t**2) * span * speed
