"""Authored, digest-bound content chunks. Levels are assembled, not invented."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .campaign import CAMPAIGN_ROSTER
from .canonical import sha256_json
from .content_pack import ContentPack, PackValidationError, load_pack_set
from .identity import GENERATOR_VERSION, SCHEMA_VERSION

# Tile legend:
# . empty  # solid  = platform  B block  D kick-break tile  P penguin  S spawn
# X boss-anchor  L ladder  + ladder/deck crossing  ^ bumper  O omarchy-logo  E enemy  ! progression-anchor
# H hidden-penguin (optional, not required)  C collectible-item  G gate
#
# Jump envelope: ~3 tiles high, 3-tile gaps are jumpable; 8-tile gaps are not.
# Chapter one is a single authored map, not concatenated 20x12 scraps.


def _rows(*lines: str) -> tuple[str, ...]:
    width = len(lines[0])
    if any(len(line) != width for line in lines):
        raise ValueError("ragged chunk")
    return lines


# Later-chapter chunks stay 20x12. Chapter one is a single authored map.


def _chunk(
    chunk_id: str,
    chapter: str,
    role: str,
    tiles: tuple[str, ...],
    *,
    tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    height = len(tiles)
    width = len(tiles[0])
    entities: list[dict[str, Any]] = []
    anchors: list[str] = []
    for y, row in enumerate(tiles):
        for x, cell in enumerate(row):
            if cell == "S":
                entities.append({"type": "spawn", "x": x, "y": y})
                anchors.append("spawn")
            elif cell == "X":
                entities.append({"type": "boss-anchor", "x": x, "y": y})
                anchors.append("boss")
            elif cell == "P":
                entities.append({"type": "penguin", "x": x, "y": y, "required": False})
            elif cell == "H":
                entities.append({"type": "penguin", "x": x, "y": y, "required": False, "secret": True})
            elif cell == "B":
                entities.append({"type": "block", "x": x, "y": y})
            elif cell == "E":
                entities.append({"type": "enemy", "x": x, "y": y})
            elif cell == "O":
                entities.append({"type": "omarchy-logo", "x": x, "y": y})
            elif cell == "C":
                entities.append({"type": "item", "x": x, "y": y, "item": "logic-bomb"})
            elif cell == "!":
                entities.append({"type": "progression-anchor", "x": x, "y": y})
                anchors.append(f"progress-{x}-{y}")
            elif cell == "^":
                entities.append({"type": "bumper", "x": x, "y": y})
            elif cell in {"L", "+"}:
                entities.append({"type": "ladder", "x": x, "y": y})
            elif cell == "W":
                entities.append({"type": "enemy", "x": x, "y": y, "variant": "warden"})
            elif cell == "G":
                entities.append({"type": "gate", "x": x, "y": y})
    return {
        "id": chunk_id,
        "chapter": chapter,
        "role": role,
        "width": width,
        "height": height,
        "tiles": list(tiles),
        "entities": entities,
        "anchors": anchors,
        "tags": list(tags),
        "digest": "",  # filled by index
    }


def _paint(width: int, height: int) -> list[list[str]]:
    return [["." for _ in range(width)] for _ in range(height)]


def _put(grid: list[list[str]], x: int, y: int, ch: str) -> None:
    if 0 <= y < len(grid) and 0 <= x < len(grid[0]) and ch != " ":
        grid[y][x] = ch


def _hline(grid: list[list[str]], x0: int, x1: int, y: int, ch: str) -> None:
    for x in range(x0, x1):
        _put(grid, x, y, ch)


def _vline(grid: list[list[str]], x: int, y0: int, y1: int, ch: str) -> None:
    for y in range(y0, y1):
        _put(grid, x, y, ch)


def _box(grid: list[list[str]], x: int, y: int, w: int, h: int, ch: str) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            _put(grid, xx, yy, ch)


def _freeze(grid: list[list[str]]) -> tuple[str, ...]:
    rows = tuple("".join(row) for row in grid)
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("ragged authored map")
    return rows


def _c1_authored() -> tuple[str, ...]:
    """First level: ~5–8 minutes of authored beats on one map.

    Ground walkway is row 16 (solid at 17). Pits drop to row 18 (solid at 19).
    The OMARCHY logo lives on an upper route; a sealed crate holds a secret
    penguin that ordinary jumping cannot reach.
    """

    w, h = 200, 22
    g = _paint(w, h)
    _hline(g, 0, w, 21, "#")
    _hline(g, 0, w, 19, "#")

    def pit(x0: int, x1: int) -> None:
        for x in range(x0, x1):
            _put(g, x, 19, ".")
            _put(g, x, 20, ".")

    # 1. Safe opening — movement through a ruined boot splash.
    _put(g, 3, 18, "S")
    _vline(g, 12, 10, 16, "#")
    _hline(g, 10, 16, 10, "=")

    # 2. Hardware closet: penguin block, empty block, bomb block.
    _put(g, 24, 15, "B")
    _put(g, 28, 15, "B")
    _put(g, 32, 15, "B")

    # 3. Partition canyon — rising complexity, coyote pits, recovery floor.
    pit(40, 43)
    pit(48, 52)
    _hline(g, 44, 47, 16, "=")
    _hline(g, 53, 58, 14, "=")
    _put(g, 56, 13, "^")

    # 4. Logic shrine.
    _vline(g, 64, 12, 16, "#")
    _put(g, 66, 18, "C")
    _hline(g, 64, 70, 12, "=")

    # 5. Dogma Sprite patrol — bump converts; converted becomes a step.
    _put(g, 78, 18, "E")
    _vline(g, 82, 10, 16, "#")

    # 6. Vertical well with ladders on BOTH sides and a mid shortcut.
    _vline(g, 92, 8, 19, "L")
    _vline(g, 108, 8, 19, "L")
    _hline(g, 93, 108, 8, "=")
    _hline(g, 96, 104, 14, "=")
    _put(g, 100, 18, "P")

    # 7. OMARCHY shrine (optional upper route). Staged, not on the floor.
    _hline(g, 110, 124, 6, "=")
    _put(g, 112, 6, "^")
    _put(g, 118, 5, "O")
    _vline(g, 116, 3, 6, "#")
    _vline(g, 120, 3, 6, "#")

    # 8. Sealed crate — editing exposes it. Visible vault, no entrance.
    _box(g, 128, 2, 7, 5, "#")
    _put(g, 131, 4, "H")
    _hline(g, 124, 128, 6, "=")
    _hline(g, 135, 142, 6, "=")

    # Lower alcove + backtracking drop.
    pit(140, 143)
    _put(g, 141, 20, "P")

    # Checksum Warden: Logic Bomb, not a bump. Gate guards an optional stash.
    _put(g, 150, 18, "W")
    _put(g, 154, 14, "G")
    _put(g, 155, 14, "G")
    _hline(g, 154, 160, 13, "=")
    _put(g, 157, 12, "C")

    # 9. Approach pillars and a second dogma.
    pit(160, 163)
    _put(g, 166, 18, "E")
    _vline(g, 170, 8, 16, "#")
    _vline(g, 172, 11, 16, "#")
    _hline(g, 170, 178, 7, "=")

    # 10. Provenance desk / Package Bureaucrat.
    _hline(g, 178, 190, 17, "=")
    _put(g, 180, 16, "B")
    _put(g, 184, 16, "B")
    _put(g, 176, 18, "!")
    _put(g, 192, 18, "X")
    _vline(g, 175, 10, 16, "#")
    _vline(g, 196, 10, 16, "#")
    _hline(g, 175, 198, 9, "=")

    return _freeze(g)


def _c1_secret() -> tuple[str, ...]:
    # Shared optional chunk for later chapters only.
    return _rows(
        "....................",
        "................H...",
        "...............==...",
        "....................",
        "......B.............",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....O...............",
        "####################",
    )


def _flat(role_mark: str = ".") -> tuple[str, ...]:
    ground = role_mark + "." * 18 + "."
    return _rows(
        "....................",
        "....................",
        "....................",
        "....................",
        "........B...........",
        "....................",
        "......====..........",
        "....................",
        "....................",
        "....................",
        "....C.........E.....",
        "####################",
    )


def _gap() -> tuple[str, ...]:
    return _rows(
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "....===....===......",
        "....................",
        "....................",
        "....................",
        "P...................",
        "#####...###...######",
    )


def _ladder_well() -> tuple[str, ...]:
    return _rows(
        "....................",
        "....H...............",
        "....==..............",
        "....L...............",
        "....L...............",
        "....L....B..........",
        "....L...............",
        "....L...............",
        "....L...............",
        "....L...............",
        "...............E....",
        "####################",
    )


def _garden() -> tuple[str, ...]:
    return _rows(
        "....................",
        "....................",
        "....========........",
        "....................",
        "..........B.........",
        "....................",
        "....====............",
        "....................",
        "....................",
        "....................",
        "E........C..........",
        "####################",
    )


def _core() -> tuple[str, ...]:
    return _rows(
        "....................",
        "....................",
        "....................",
        "..........H.........",
        ".........====.......",
        "....................",
        "....L...............",
        "....L....B..........",
        "....L...............",
        "....L...............",
        "..........E.........",
        "####################",
    )


def _boss_arena(chapter: str) -> tuple[str, ...]:
    return _rows(
        "....................",
        "....................",
        "....................",
        "....................",
        "....B......B........",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        "!..............X....",
        "####################",
    )


def _start_for(chapter: str) -> tuple[str, ...]:
    return _rows(
        "....................",
        "....................",
        "....................",
        "....................",
        "......B.............",
        "....................",
        "....................",
        "....................",
        "....................",
        "....................",
        ".S...C..............",
        "####################",
    )


def authored_chunks() -> list[dict[str, Any]]:
    # Chapter 1's generation profile is external pack data. These compact
    # authored chunks remain only as explicit scaffolding for later chapters.
    chunks: list[dict[str, Any]] = []
    mids = {
        "package-wilderness": [_flat(), _gap(), _ladder_well()],
        "distro-front": [_flat(), _gap(), _garden()],
        "walled-garden": [_garden(), _flat(), _gap()],
        "singularity-core": [_core(), _ladder_well(), _gap()],
        "goliath-amalgam": [_core(), _flat(), _gap()],
    }
    for chapter in CAMPAIGN_ROSTER[1:]:
        chunks.append(_chunk(f"{chapter.id}-start", chapter.id, "start", _start_for(chapter.id)))
        for index, tiles in enumerate(mids[chapter.id]):
            role = "mid"
            chunks.append(_chunk(f"{chapter.id}-mid-{index}", chapter.id, role, tiles))
        chunks.append(_chunk(f"{chapter.id}-boss", chapter.id, "boss", _boss_arena(chapter.id), tags=("boss",)))
    # Dedicated optional logo chunk reused in test mode for later chapters.
    chunks.append(
        _chunk(
            "shared-optional-logo",
            "shared",
            "optional",
            _c1_secret(),
            tags=("secret", "logo"),
        )
    )
    sealed = []
    for chunk in chunks:
        body = {key: chunk[key] for key in chunk if key != "digest"}
        chunk["digest"] = sha256_json(body)
        sealed.append(chunk)
    return sealed


CONTENT_PACK_ID = "omega-core-1"
BUILTIN_PACK = Path(__file__).resolve().parent / "data" / "content-packs" / "omega-core"


class ContentCompatibilityError(ValueError):
    """A sealed world references a different exact set of content packs."""


@dataclass(frozen=True)
class ContentIndex:
    packs: tuple[ContentPack, ...]
    generator_version: str
    schema_version: str
    chunks: tuple[dict[str, Any], ...]
    profiles: dict[str, dict[str, Any]]
    digest: str

    @property
    def pack_id(self) -> str:
        """Compatibility alias for callers that predate ordered pack sets."""

        return self.packs[0].pack_id

    @property
    def pack_ids(self) -> tuple[str, ...]:
        return tuple(pack.pack_id for pack in self.packs)

    def pack_identities(self) -> list[dict[str, str]]:
        return [pack.identity() for pack in self.packs]

    def chapter_profile(self, chapter_id: str) -> dict[str, Any] | None:
        profile = self.profiles.get(chapter_id)
        return deepcopy(profile) if profile is not None else None

    def chunks_for(self, chapter: str, role: str | None = None) -> list[dict[str, Any]]:
        out = [chunk for chunk in self.chunks if chunk["chapter"] in {chapter, "shared"}]
        if role is not None:
            out = [chunk for chunk in out if chunk["role"] == role]
        return out

    def by_id(self, chunk_id: str) -> dict[str, Any]:
        for chunk in self.chunks:
            if chunk["id"] == chunk_id:
                return chunk
        raise KeyError(chunk_id)

    def ordered_identities(self) -> list[dict[str, str]]:
        return [
            {"id": chunk["id"], "digest": chunk["digest"]}
            for chunk in sorted(self.chunks, key=lambda item: item["id"])
        ]


def _extend_unique(target: list[Any], additions: Iterable[Any]) -> None:
    for value in additions:
        if value not in target:
            target.append(value)


def _compose_profiles(packs: tuple[ContentPack, ...]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    addons: list[tuple[ContentPack, dict[str, Any]]] = []
    for pack in packs:
        for entry in pack.entries:
            kind = entry["kind"]
            chapter_id = str(entry.get("chapterId") or "")
            if kind == "chapter":
                if chapter_id in profiles:
                    raise PackValidationError(f"multiple base chapter profiles target {chapter_id}")
                profile = deepcopy(entry)
                profile["sourcePack"] = pack.pack_id
                profiles[chapter_id] = profile
            elif kind == "chapter-addon":
                addons.append((pack, entry))
    for pack, addon in addons:
        chapter_id = str(addon["chapterId"])
        if chapter_id not in profiles:
            raise PackValidationError(f"{pack.pack_id} extends missing chapter {chapter_id}")
        profile = profiles[chapter_id]
        generation = profile.setdefault("generation", {})
        for field in ("recipes", "sectorMotifs"):
            _extend_unique(generation.setdefault(field, []), addon.get("generation", {}).get(field, []))
        for field in ("enemyMotifs", "itemPool"):
            _extend_unique(profile.setdefault(field, []), addon.get(field, []))
        profile.setdefault("addons", []).append({"id": addon["id"], "sourcePack": pack.pack_id})
    return profiles


def load_content(extra_pack_paths: Iterable[Path] = ()) -> ContentIndex:
    packs = load_pack_set((BUILTIN_PACK, *(Path(path) for path in extra_pack_paths)))
    chunks = authored_chunks()
    identity = {
        "packs": [pack.identity() for pack in packs],
        "legacyChunks": [
            {"id": chunk["id"], "digest": chunk["digest"]}
            for chunk in sorted(chunks, key=lambda item: item["id"])
        ],
    }
    return ContentIndex(
        packs=packs,
        generator_version=GENERATOR_VERSION,
        schema_version=SCHEMA_VERSION,
        chunks=tuple(chunks),
        profiles=_compose_profiles(packs),
        digest=sha256_json(identity),
    )


def require_exact_content(identity: Any, content: ContentIndex) -> None:
    expected = tuple(identity.content_pack_ids)
    available = content.pack_ids
    if expected != available:
        missing = [pack_id for pack_id in expected if pack_id not in available]
        extra = [pack_id for pack_id in available if pack_id not in expected]
        raise ContentCompatibilityError(
            f"content pack set mismatch; expected={list(expected)} available={list(available)} "
            f"missing={missing} extra={extra}"
        )
    if identity.content_digest != content.digest:
        raise ContentCompatibilityError(
            f"content digest mismatch for {list(expected)}; expected={identity.content_digest} "
            f"available={content.digest}"
        )
