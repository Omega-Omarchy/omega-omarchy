"""Reversible, validated OMARCHY-logo zone edits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import sha256_json
from .reachability import find_boss, find_spawn, normalize_ladder_tiles, validate_level

MAX_OPS = 24
MAX_PLACED = 16
ALLOWED_TILES = {".", "=", "#", "L", "+", "^"}
FORBIDDEN_REMOVE = {"S", "X", "!"}
OP_KINDS = {"place", "remove", "move", "mirror"}


@dataclass(frozen=True)
class ZoneDelta:
    world_digest: str
    chapter_id: str
    generator_version: str
    content_digest: str
    operations: tuple[dict[str, Any], ...]
    delta_id: str

    def to_record(self) -> dict[str, Any]:
        return {
            "chapterId": self.chapter_id,
            "contentDigest": self.content_digest,
            "deltaId": self.delta_id,
            "generatorVersion": self.generator_version,
            "operations": list(self.operations),
            "worldDigest": self.world_digest,
        }


def _tiles_of(chapter: dict[str, Any]) -> list[str]:
    return list(chapter["tiles"])


def _set_tile(tiles: list[str], x: int, y: int, glyph: str) -> list[str]:
    if y < 0 or y >= len(tiles) or x < 0 or x >= len(tiles[0]):
        raise ValueError("out-of-bounds edit")
    row = list(tiles[y])
    row[x] = glyph
    tiles = list(tiles)
    tiles[y] = "".join(row)
    return tiles


def apply_operations(tiles: list[str], operations: list[dict[str, Any]]) -> list[str]:
    out = list(tiles)
    for op in operations:
        kind = op.get("op")
        if kind not in OP_KINDS:
            raise ValueError(f"unsupported op {kind}")
        if kind == "place":
            glyph = op.get("tile", "=")
            if glyph not in ALLOWED_TILES:
                raise ValueError("tile not in bounded palette")
            x, y = int(op["x"]), int(op["y"])
            if out[y][x] in FORBIDDEN_REMOVE:
                raise ValueError("cannot overwrite progression anchor")
            out = _set_tile(out, x, y, glyph)
        elif kind == "remove":
            x, y = int(op["x"]), int(op["y"])
            current = out[y][x]
            if current in FORBIDDEN_REMOVE:
                raise ValueError("cannot remove progression anchor")
            out = _set_tile(out, x, y, ".")
        elif kind == "move":
            x, y = int(op["x"]), int(op["y"])
            nx, ny = int(op["nx"]), int(op["ny"])
            current = out[y][x]
            if current in FORBIDDEN_REMOVE:
                raise ValueError("cannot move progression anchor")
            out = _set_tile(out, nx, ny, current)
            out = _set_tile(out, x, y, ".")
        elif kind == "mirror":
            x, y = int(op["x"]), int(op["y"])
            width = len(out[0])
            mx = width - 1 - x
            current = out[y][x]
            if current in FORBIDDEN_REMOVE:
                raise ValueError("cannot mirror progression anchor")
            out = _set_tile(out, mx, y, current)
    return out


def validate_proposed(
    chapter: dict[str, Any],
    operations: list[dict[str, Any]],
    *,
    world_digest: str,
    generator_version: str,
    content_digest: str,
) -> dict[str, Any]:
    errors: list[str] = []
    if len(operations) > MAX_OPS:
        errors.append("resource-abuse:too-many-ops")
    placed = sum(1 for op in operations if op.get("op") == "place")
    if placed > MAX_PLACED:
        errors.append("resource-abuse:too-many-placed")
    tiles = _tiles_of(chapter)
    try:
        spawn = find_spawn(tiles)
        boss = find_boss(tiles)
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "tiles": tiles}
    try:
        edited = normalize_ladder_tiles(apply_operations(tiles, operations))
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)], "tiles": tiles}
    # Progression anchors must remain.
    if edited[spawn[1]][spawn[0]] != "S":
        errors.append("progression-damage:spawn")
    if edited[boss[1]][boss[0]] != "X":
        errors.append("invalid-boss-access")
    for y, row in enumerate(tiles):
        for x, cell in enumerate(row):
            if cell == "!" and edited[y][x] != "!":
                errors.append("progression-damage:anchor")
    try:
        report = validate_level(edited, require_logo=False)
    except ValueError as exc:
        errors.append(f"invalid-boss-access:{exc}")
        report = {"ok": False, "errors": [str(exc)], "bossReachableWithoutRare": False}
    if not report.get("bossReachableWithoutRare", False):
        errors.append("softlock:boss-unreachable")
    if not report.get("ok") and "boss-unreachable" in report.get("errors", []):
        errors.append("invalid-boss-access")
    ok = not errors
    record = {
        "chapterId": chapter["chapterId"],
        "contentDigest": content_digest,
        "generatorVersion": generator_version,
        "operations": operations,
        "worldDigest": world_digest,
    }
    return {
        "ok": ok,
        "errors": errors,
        "tiles": edited,
        "reachability": report,
        "proposedDigest": sha256_json(record),
    }


def make_delta(
    chapter: dict[str, Any],
    operations: list[dict[str, Any]],
    *,
    world_digest: str,
    generator_version: str,
    content_digest: str,
) -> tuple[ZoneDelta | None, dict[str, Any]]:
    report = validate_proposed(
        chapter,
        operations,
        world_digest=world_digest,
        generator_version=generator_version,
        content_digest=content_digest,
    )
    if not report["ok"]:
        return None, report
    record = {
        "chapterId": chapter["chapterId"],
        "contentDigest": content_digest,
        "generatorVersion": generator_version,
        "operations": operations,
        "worldDigest": world_digest,
    }
    delta_id = sha256_json(record)
    delta = ZoneDelta(
        world_digest=world_digest,
        chapter_id=chapter["chapterId"],
        generator_version=generator_version,
        content_digest=content_digest,
        operations=tuple(operations),
        delta_id=delta_id,
    )
    report["delta"] = delta.to_record()
    return delta, report


def apply_delta(chapter: dict[str, Any], delta: ZoneDelta) -> dict[str, Any]:
    if delta.chapter_id != chapter["chapterId"]:
        raise ValueError("delta chapter mismatch")
    edited = normalize_ladder_tiles(apply_operations(list(chapter["tiles"]), list(delta.operations)))
    out = dict(chapter)
    out["tiles"] = edited
    out["activeDelta"] = delta.to_record()
    return out


def revert_delta(chapter: dict[str, Any], original_tiles: list[str]) -> dict[str, Any]:
    out = dict(chapter)
    out["tiles"] = list(original_tiles)
    out.pop("activeDelta", None)
    return out
