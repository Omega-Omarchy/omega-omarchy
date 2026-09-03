"""Default protagonist and a compact player-created character."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canonical import sha256_json

HAIR_PRESETS = ("long-wave", "long-straight", "short", "bun")
BODY_PRESETS = ("lean", "compact", "tall")
SHIRT_PRESETS = ("omarchy-black", "terminal-green", "tokyo-night", "bronze")
PHILOSOPHIES = ("speed", "taste", "patience", "fork")
PALETTES = ("tokyo-night", "gruvbox", "catppuccin", "flexoki")
DEFAULT_CHARACTER_NAME = "David"
FALLBACK_CHARACTER_NAME = "Player"


@dataclass(frozen=True)
class Character:
    name: str
    kind: str  # "david" | "custom"
    body: str
    hair: str
    shirt: str
    philosophy: str
    palette: str
    derived_from_photo: bool = False

    def to_record(self) -> dict[str, Any]:
        return {
            "body": self.body,
            "derivedFromPhoto": self.derived_from_photo,
            "hair": self.hair,
            "kind": self.kind,
            "name": self.name,
            "palette": self.palette,
            "philosophy": self.philosophy,
            "shirt": self.shirt,
        }

    def digest(self) -> str:
        return sha256_json(self.to_record())

    def ability_bias(self) -> dict[str, float]:
        return {
            "speed": {"speed": 1.12, "taste": 1.0, "patience": 0.92, "fork": 1.0}[self.philosophy],
            "jump": {"speed": 1.0, "taste": 1.04, "patience": 1.08, "fork": 1.0}[self.philosophy],
            "reason": {"speed": 0.92, "taste": 1.1, "patience": 1.12, "fork": 1.04}[self.philosophy],
        }


DAVID = Character(
    name=DEFAULT_CHARACTER_NAME,
    kind="david",
    body="lean",
    hair="long-wave",
    shirt="omarchy-black",
    philosophy="taste",
    palette="tokyo-night",
)


def parse_character(record: dict[str, Any] | None) -> Character:
    if not record:
        return DAVID
    kind = record.get("kind", "custom")
    if kind == "david" and record.get("name", DEFAULT_CHARACTER_NAME) == DEFAULT_CHARACTER_NAME:
        return DAVID
    hair = record.get("hair", "long-wave")
    body = record.get("body", "lean")
    shirt = record.get("shirt", "omarchy-black")
    philosophy = record.get("philosophy", "taste")
    palette = record.get("palette", "tokyo-night")
    if hair not in HAIR_PRESETS:
        raise ValueError("unknown hair preset")
    if body not in BODY_PRESETS:
        raise ValueError("unknown body preset")
    if shirt not in SHIRT_PRESETS:
        raise ValueError("unknown shirt preset")
    if philosophy not in PHILOSOPHIES:
        raise ValueError("unknown philosophy")
    if palette not in PALETTES:
        raise ValueError("unknown palette")
    name = str(record.get("name") or FALLBACK_CHARACTER_NAME).strip()[:24] or FALLBACK_CHARACTER_NAME
    return Character(
        name=name,
        kind="custom",
        body=body,
        hair=hair,
        shirt=shirt,
        philosophy=philosophy,
        palette=palette,
        derived_from_photo=bool(record.get("derivedFromPhoto", False)),
    )
