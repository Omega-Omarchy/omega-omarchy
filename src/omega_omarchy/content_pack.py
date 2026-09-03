"""Versioned, data-only content packs with fail-closed validation."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from .canonical import sha256_file_bytes, sha256_json
from .identity import GENERATOR_VERSION, SCHEMA_VERSION

PACK_SCHEMA_VERSION = "1.0.0"
MAX_MANIFEST_BYTES = 128 * 1024
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_PACK_BYTES = 24 * 1024 * 1024
MAX_FILES = 256
MAX_JSON_NODES = 20_000
MAX_JSON_DEPTH = 16

PACK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{2,63}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?$")
CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]{1,95}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

EXECUTABLE_SUFFIXES = {
    ".appimage",
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".dylib",
    ".exe",
    ".js",
    ".lua",
    ".py",
    ".pyc",
    ".sh",
    ".so",
    ".wasm",
}
ALLOWED_SUFFIXES = {"", ".json", ".md", ".ogg", ".png", ".txt", ".wav"}
# The first public contract is intentionally smaller than the eventual pack
# shape. Unknown/unfinished entry kinds fail closed instead of appearing to
# install while having no effect.
ENTRY_KINDS = {"chapter", "chapter-addon"}
ENGINE_RECIPES = {
    "archive-stacks",
    "broken-bridge",
    "bumper-gallery",
    "sky-well",
    "suspended-chain",
    "switchback",
    "twin-towers",
}
ENGINE_ENEMY_MOTIFS = {
    "cache-gremlin",
    "consensus-crier",
    "garden-glitch",
    "justice-signaler",
    "detractabot",
    "lint-launcher",
    "packet-wasp",
    "void-orbiter",
}
ENGINE_ITEMS = {
    "checksum-key",
    "fork-beacon",
    "logic-bomb",
    "manifest",
    "mirror-cache",
    "patch-cable",
    "penguin-flock",
    "touch-grass-usb",
}
ENGINE_CHAPTERS = {"corrupted-install"}
UNSAFE_KEYS = {"command", "commands", "executable", "hook", "hooks", "python", "script", "scripts", "shell"}
MANIFEST_FIELDS = {
    "authors",
    "capabilities",
    "contentDigest",
    "dependencies",
    "entryPoints",
    "files",
    "gameSchemaVersion",
    "generatorVersion",
    "homepage",
    "id",
    "license",
    "loadAfter",
    "loadBefore",
    "loadOrder",
    "schemaVersion",
    "source",
    "version",
}


class PackValidationError(ValueError):
    """A content pack is unsafe, incompatible, corrupt, or malformed."""


@dataclass(frozen=True)
class ContentPack:
    pack_id: str
    version: str
    schema_version: str
    game_schema_version: str
    generator_version: str
    license: str
    authors: tuple[str, ...]
    load_order: int
    dependencies: tuple[str, ...]
    load_after: tuple[str, ...]
    load_before: tuple[str, ...]
    capabilities: tuple[str, ...]
    content_digest: str
    root: Path
    entries: tuple[dict[str, Any], ...]
    files: tuple[dict[str, Any], ...]
    homepage: str | None = None
    source: str | None = None

    def identity(self) -> dict[str, str]:
        return {"id": self.pack_id, "version": self.version, "digest": self.content_digest}


def _safe_relative_path(raw: Any) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise PackValidationError("pack paths must be non-empty POSIX relative paths")
    path = PurePosixPath(raw)
    if (
        path.as_posix() != raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} or not part.isprintable() for part in path.parts)
    ):
        raise PackValidationError(f"unsafe pack path: {raw}")
    return path


def _string_list(manifest: dict[str, Any], name: str) -> tuple[str, ...]:
    value = manifest.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise PackValidationError(f"{name} must be a list of non-empty strings")
    if len(value) != len(set(value)):
        raise PackValidationError(f"{name} contains duplicates")
    return tuple(value)


def _json_object(data: bytes, source: str) -> dict[str, Any]:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise PackValidationError(f"{source} contains duplicate JSON key {key}")
            out[key] = value
        return out

    def reject_constant(value: str) -> None:
        raise PackValidationError(f"{source} contains non-finite number {value}")

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=no_duplicates, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackValidationError(f"invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise PackValidationError(f"{source} entry point must contain a JSON object")
    return value


def _inspect_json(value: Any, *, source: str, depth: int = 0, count: list[int] | None = None) -> None:
    count = count if count is not None else [0]
    count[0] += 1
    if count[0] > MAX_JSON_NODES:
        raise PackValidationError(f"{source} exceeds JSON node limit")
    if depth > MAX_JSON_DEPTH:
        raise PackValidationError(f"{source} exceeds JSON nesting limit")
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in UNSAFE_KEYS:
                raise PackValidationError(f"{source} requests executable field {key}")
            _inspect_json(child, source=source, depth=depth + 1, count=count)
    elif isinstance(value, list):
        for child in value:
            _inspect_json(child, source=source, depth=depth + 1, count=count)


def _content_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or not CONTENT_ID_RE.fullmatch(value):
        raise PackValidationError(f"{field} is not a valid content id")
    return value


def _content_ids(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PackValidationError(f"{field} must be a non-empty list")
    result = tuple(_content_id(item, field) for item in value)
    if len(result) != len(set(result)):
        raise PackValidationError(f"{field} contains duplicates")
    return result


def _validate_generation(value: Any, source: str, *, addon: bool) -> None:
    if not isinstance(value, dict):
        raise PackValidationError(f"{source} generation must be an object")
    allowed = {"heightBase", "recipes", "sectorMotifs", "sectorWidth", "widthBase"}
    unknown = set(value) - allowed
    if unknown:
        raise PackValidationError(f"{source} generation has unsupported fields: {sorted(unknown)}")
    if "recipes" in value:
        recipes = _content_ids(value["recipes"], f"{source}.generation.recipes")
        unsupported = set(recipes) - ENGINE_RECIPES
        if unsupported:
            raise PackValidationError(f"{source} requests unsupported recipes: {sorted(unsupported)}")
    elif not addon:
        raise PackValidationError(f"{source} base chapter requires generation.recipes")
    if "sectorMotifs" in value:
        _content_ids(value["sectorMotifs"], f"{source}.generation.sectorMotifs")
    elif not addon:
        raise PackValidationError(f"{source} base chapter requires generation.sectorMotifs")
    if "widthBase" in value:
        widths = value["widthBase"]
        if not isinstance(widths, dict) or set(widths) != {"casual", "standard", "precise"}:
            raise PackValidationError(f"{source} widthBase must define casual, standard and precise")
        if not all(
            not isinstance(width, bool) and isinstance(width, int) and 160 <= width <= 512
            for width in widths.values()
        ):
            raise PackValidationError(f"{source} widthBase values must be 160..512")
    elif not addon:
        raise PackValidationError(f"{source} base chapter requires generation.widthBase")
    for name, low, high in (("heightBase", 32, 96), ("sectorWidth", 20, 64)):
        if name in value and (
            isinstance(value[name], bool) or not isinstance(value[name], int) or not low <= value[name] <= high
        ):
            raise PackValidationError(f"{source} {name} must be {low}..{high}")
        if name not in value and not addon:
            raise PackValidationError(f"{source} base chapter requires generation.{name}")


def _validate_entry(entry: dict[str, Any], source: str) -> dict[str, Any]:
    _inspect_json(entry, source=source)
    kind = entry.get("kind")
    if kind not in ENTRY_KINDS:
        raise PackValidationError(f"{source} has unsupported kind {kind}")
    _content_id(entry.get("id"), f"{source}.id")
    if kind in {"chapter", "chapter-addon"}:
        allowed = {"kind", "id", "chapterId", "generation", "enemyMotifs", "itemPool"}
        if kind == "chapter":
            allowed |= {"name", "blurb", "palette", "boss"}
        unknown_fields = set(entry) - allowed
        if unknown_fields:
            raise PackValidationError(f"{source} has unsupported fields: {sorted(unknown_fields)}")
        chapter_id = _content_id(entry.get("chapterId"), f"{source}.chapterId")
        if chapter_id not in ENGINE_CHAPTERS:
            raise PackValidationError(f"{source} targets unsupported chapter {chapter_id}")
        if kind == "chapter":
            for field in ("name", "blurb", "palette"):
                if not isinstance(entry.get(field), str) or not entry[field].strip():
                    raise PackValidationError(f"{source}.{field} must be non-empty text")
            boss = entry.get("boss")
            if not isinstance(boss, dict) or set(boss) != {"id", "name"}:
                raise PackValidationError(f"{source}.boss must be an object")
            _content_id(boss.get("id"), f"{source}.boss.id")
            if not isinstance(boss.get("name"), str) or not boss["name"].strip():
                raise PackValidationError(f"{source}.boss.name must be non-empty text")
        _validate_generation(entry.get("generation") or {}, source, addon=kind == "chapter-addon")
        for field in ("enemyMotifs", "itemPool"):
            if field in entry:
                identifiers = _content_ids(entry[field], f"{source}.{field}")
                supported = ENGINE_ENEMY_MOTIFS if field == "enemyMotifs" else ENGINE_ITEMS
                unknown = set(identifiers) - supported
                if unknown:
                    raise PackValidationError(f"{source}.{field} contains unsupported ids: {sorted(unknown)}")
        if kind == "chapter-addon" and not any(
            entry.get(field) for field in ("generation", "enemyMotifs", "itemPool")
        ):
            raise PackValidationError(f"{source} chapter-addon makes no changes")
    return entry


def _digest_basis(manifest: dict[str, Any], files: Iterable[dict[str, Any]]) -> dict[str, Any]:
    names = (
        "authors",
        "capabilities",
        "dependencies",
        "entryPoints",
        "gameSchemaVersion",
        "generatorVersion",
        "homepage",
        "id",
        "license",
        "loadAfter",
        "loadBefore",
        "loadOrder",
        "schemaVersion",
        "source",
        "version",
    )
    return {
        "manifest": {name: manifest.get(name) for name in names},
        "files": [
            {"bytes": item["bytes"], "digest": item["digest"], "mediaType": item["mediaType"], "path": item["path"]}
            for item in sorted(files, key=lambda item: item["path"])
        ],
    }


def expected_content_digest(manifest: dict[str, Any]) -> str:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise PackValidationError("files must be an array of tables")
    return sha256_json(_digest_basis(manifest, files))


def validate_pack(root: Path) -> ContentPack:
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise PackValidationError(f"pack root is not a regular directory: {root}")
    root = root.resolve()
    manifest_path = root / "pack.toml"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PackValidationError("pack.toml is required and may not be a symlink")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise PackValidationError("pack.toml exceeds size limit")
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PackValidationError(f"invalid pack.toml: {exc}") from exc

    unknown_manifest = set(manifest) - MANIFEST_FIELDS
    if unknown_manifest:
        raise PackValidationError(f"unsupported manifest fields: {sorted(unknown_manifest)}")

    required_text = (
        "id",
        "version",
        "schemaVersion",
        "gameSchemaVersion",
        "generatorVersion",
        "license",
        "contentDigest",
    )
    for field in required_text:
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise PackValidationError(f"manifest field {field} is required")
    pack_id = manifest["id"]
    if not PACK_ID_RE.fullmatch(pack_id):
        raise PackValidationError("manifest id is invalid")
    if not VERSION_RE.fullmatch(manifest["version"]):
        raise PackValidationError("manifest version must be semantic x.y.z")
    if manifest["schemaVersion"] != PACK_SCHEMA_VERSION:
        raise PackValidationError(f"unsupported pack schema {manifest['schemaVersion']}")
    if manifest["gameSchemaVersion"] != SCHEMA_VERSION:
        raise PackValidationError(f"incompatible game schema {manifest['gameSchemaVersion']}")
    if manifest["generatorVersion"] != GENERATOR_VERSION:
        raise PackValidationError(f"incompatible generator {manifest['generatorVersion']}")
    if not SHA256_RE.fullmatch(manifest["contentDigest"]):
        raise PackValidationError("contentDigest must be a sha256 digest")
    if not manifest["license"].strip() or manifest["license"].lower() in {"none", "unknown"}:
        raise PackValidationError("pack license must be explicit")
    authors = _string_list(manifest, "authors")
    entry_points = _string_list(manifest, "entryPoints")
    dependencies = _string_list(manifest, "dependencies")
    load_after = _string_list(manifest, "loadAfter")
    load_before = _string_list(manifest, "loadBefore")
    capabilities = _string_list(manifest, "capabilities")
    if not authors or not entry_points or not capabilities:
        raise PackValidationError("authors, entryPoints and capabilities may not be empty")
    unsupported_capabilities = set(capabilities) - {"chapter-profile"}
    if unsupported_capabilities:
        raise PackValidationError(f"unsupported capabilities: {sorted(unsupported_capabilities)}")
    for field, references in (
        ("dependencies", dependencies),
        ("loadAfter", load_after),
        ("loadBefore", load_before),
    ):
        invalid = [reference for reference in references if not PACK_ID_RE.fullmatch(reference)]
        if invalid:
            raise PackValidationError(f"{field} contains invalid pack ids: {invalid}")
        if pack_id in references:
            raise PackValidationError(f"{field} may not reference the pack itself")
    for field in ("homepage", "source"):
        if field in manifest and (not isinstance(manifest[field], str) or not manifest[field].strip()):
            raise PackValidationError(f"manifest field {field} must be non-empty text")
    load_order = manifest.get("loadOrder")
    if isinstance(load_order, bool) or not isinstance(load_order, int) or not -10_000 <= load_order <= 10_000:
        raise PackValidationError("loadOrder must be an integer from -10000 to 10000")

    raw_files = manifest.get("files")
    if not isinstance(raw_files, list) or not 1 <= len(raw_files) <= MAX_FILES:
        raise PackValidationError(f"files must contain 1..{MAX_FILES} entries")
    files: list[dict[str, Any]] = []
    declared: set[str] = set()
    total_bytes = 0
    for item in raw_files:
        if not isinstance(item, dict) or set(item) != {"path", "digest", "bytes", "mediaType"}:
            raise PackValidationError("each files entry requires exactly path, digest, bytes and mediaType")
        relative = _safe_relative_path(item["path"])
        path_text = relative.as_posix()
        if path_text in declared:
            raise PackValidationError(f"duplicate declared file {path_text}")
        declared.add(path_text)
        candidate = root.joinpath(*relative.parts)
        if candidate.is_symlink() or not candidate.is_file():
            raise PackValidationError(f"declared file is missing, non-regular, or symlinked: {path_text}")
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise PackValidationError(f"declared file escapes pack root: {path_text}")
        suffix = candidate.suffix.lower()
        if suffix in EXECUTABLE_SUFFIXES or suffix not in ALLOWED_SUFFIXES:
            raise PackValidationError(f"unsupported or executable file type: {path_text}")
        if not isinstance(item["digest"], str) or not SHA256_RE.fullmatch(item["digest"]):
            raise PackValidationError(f"invalid file digest: {path_text}")
        size = candidate.stat().st_size
        declared_size = item["bytes"]
        if isinstance(declared_size, bool) or not isinstance(declared_size, int):
            raise PackValidationError(f"bytes must be an integer: {path_text}")
        if size > MAX_FILE_BYTES or declared_size != size:
            raise PackValidationError(f"size mismatch or limit exceeded: {path_text}")
        total_bytes += size
        digest = sha256_file_bytes(candidate.read_bytes())
        if item["digest"] != digest:
            raise PackValidationError(f"digest mismatch: {path_text}")
        if not isinstance(item["mediaType"], str) or not item["mediaType"]:
            raise PackValidationError(f"mediaType missing: {path_text}")
        files.append({"path": path_text, "digest": digest, "bytes": size, "mediaType": item["mediaType"]})
    if total_bytes > MAX_PACK_BYTES:
        raise PackValidationError("pack exceeds total size limit")

    actual = set()
    for candidate in root.rglob("*"):
        if candidate.is_symlink():
            raise PackValidationError(f"symlinks are forbidden: {candidate.relative_to(root)}")
        if candidate.is_file() and candidate != manifest_path:
            actual.add(candidate.relative_to(root).as_posix())
    undeclared = actual - declared
    missing = declared - actual
    if undeclared or missing:
        raise PackValidationError(
            f"file declaration mismatch; undeclared={sorted(undeclared)} missing={sorted(missing)}"
        )
    if not {"LICENSE", "ATTRIBUTION.md"} <= declared:
        raise PackValidationError("LICENSE and ATTRIBUTION.md must be declared")
    if any(point not in declared for point in entry_points):
        raise PackValidationError("every entry point must be a declared file")
    if expected_content_digest({**manifest, "files": files}) != manifest["contentDigest"]:
        raise PackValidationError("contentDigest does not bind the canonical manifest and file list")

    entries: list[dict[str, Any]] = []
    entry_ids: set[str] = set()
    for point in entry_points:
        if not point.endswith(".json"):
            raise PackValidationError(f"entry point must be JSON: {point}")
        entry = _validate_entry(_json_object((root / point).read_bytes(), point), point)
        entry_id = str(entry["id"])
        if entry_id in entry_ids:
            raise PackValidationError(f"duplicate entry id {entry_id}")
        entry_ids.add(entry_id)
        entries.append(entry)

    return ContentPack(
        pack_id=pack_id,
        version=manifest["version"],
        schema_version=manifest["schemaVersion"],
        game_schema_version=manifest["gameSchemaVersion"],
        generator_version=manifest["generatorVersion"],
        license=manifest["license"],
        authors=authors,
        load_order=load_order,
        dependencies=dependencies,
        load_after=load_after,
        load_before=load_before,
        capabilities=capabilities,
        content_digest=manifest["contentDigest"],
        root=root,
        entries=tuple(entries),
        files=tuple(files),
        homepage=manifest.get("homepage"),
        source=manifest.get("source"),
    )


def order_packs(packs: Iterable[ContentPack]) -> tuple[ContentPack, ...]:
    by_id: dict[str, ContentPack] = {}
    for pack in packs:
        if pack.pack_id in by_id:
            raise PackValidationError(f"duplicate pack id {pack.pack_id}")
        by_id[pack.pack_id] = pack
    edges: dict[str, set[str]] = {pack_id: set() for pack_id in by_id}
    indegree = {pack_id: 0 for pack_id in by_id}
    for pack in by_id.values():
        for dependency in pack.dependencies:
            if dependency not in by_id:
                raise PackValidationError(f"{pack.pack_id} missing dependency {dependency}")
        for predecessor in set(pack.dependencies + pack.load_after):
            if predecessor not in by_id:
                raise PackValidationError(f"{pack.pack_id} loadAfter references missing pack {predecessor}")
            if pack.pack_id not in edges[predecessor]:
                edges[predecessor].add(pack.pack_id)
                indegree[pack.pack_id] += 1
        for successor in pack.load_before:
            if successor not in by_id:
                raise PackValidationError(f"{pack.pack_id} loadBefore references missing pack {successor}")
            if successor not in edges[pack.pack_id]:
                edges[pack.pack_id].add(successor)
                indegree[successor] += 1
    ordered: list[ContentPack] = []
    ready = [pack for pack in by_id.values() if indegree[pack.pack_id] == 0]
    while ready:
        ready.sort(key=lambda pack: (pack.load_order, pack.pack_id, pack.version))
        pack = ready.pop(0)
        ordered.append(pack)
        for successor in sorted(edges[pack.pack_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(by_id[successor])
    if len(ordered) != len(by_id):
        raise PackValidationError("content-pack ordering constraints contain a cycle")
    seen_entries: dict[str, str] = {}
    for pack in ordered:
        for entry in pack.entries:
            entry_id = str(entry["id"])
            if entry_id in seen_entries:
                raise PackValidationError(
                    f"content id conflict {entry_id}: {seen_entries[entry_id]} vs {pack.pack_id}"
                )
            seen_entries[entry_id] = pack.pack_id
    return tuple(ordered)


def load_pack_set(paths: Iterable[Path]) -> tuple[ContentPack, ...]:
    return order_packs(validate_pack(path) for path in paths)


def pack_set_digest(packs: Iterable[ContentPack]) -> str:
    return sha256_json([pack.identity() for pack in packs])


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _render_manifest(manifest: dict[str, Any]) -> str:
    scalar_fields = (
        "id",
        "version",
        "schemaVersion",
        "gameSchemaVersion",
        "generatorVersion",
        "license",
        "homepage",
        "source",
    )
    list_fields = ("authors", "entryPoints", "dependencies", "loadAfter", "loadBefore")
    lines: list[str] = []
    for field in scalar_fields:
        if field in manifest:
            if not isinstance(manifest[field], str):
                raise PackValidationError(f"manifest field {field} must be text")
            lines.append(f"{field} = {_toml_string(manifest[field])}")
    for field in list_fields:
        values = manifest.get(field)
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise PackValidationError(f"manifest field {field} must be a string list")
        lines.append(f"{field} = [{', '.join(_toml_string(value) for value in values)}]")
    load_order = manifest.get("loadOrder")
    if isinstance(load_order, bool) or not isinstance(load_order, int):
        raise PackValidationError("manifest field loadOrder must be an integer")
    lines.append(f"loadOrder = {load_order}")
    capabilities = manifest.get("capabilities")
    if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
        raise PackValidationError("manifest field capabilities must be a string list")
    lines.append(f"capabilities = [{', '.join(_toml_string(value) for value in capabilities)}]")
    lines.append(f"contentDigest = {_toml_string(manifest['contentDigest'])}")
    for item in manifest["files"]:
        lines.extend(
            (
                "",
                "[[files]]",
                f"path = {_toml_string(item['path'])}",
                f"digest = {_toml_string(item['digest'])}",
                f"bytes = {item['bytes']}",
                f"mediaType = {_toml_string(item['mediaType'])}",
            )
        )
    return "\n".join(lines) + "\n"


def seal_pack(root: Path) -> ContentPack:
    """Atomically refresh a pack's declared files and canonical digest."""

    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise PackValidationError(f"pack root is not a regular directory: {root}")
    root = root.resolve()
    manifest_path = root / "pack.toml"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise PackValidationError("pack.toml is required and may not be a symlink")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise PackValidationError("pack.toml exceeds size limit")
    try:
        manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise PackValidationError(f"invalid pack.toml: {exc}") from exc
    unknown = set(manifest) - MANIFEST_FIELDS
    if unknown:
        raise PackValidationError(f"unsupported manifest fields: {sorted(unknown)}")

    media_types = {
        "": "text/plain",
        ".json": "application/json",
        ".md": "text/markdown",
        ".ogg": "audio/ogg",
        ".png": "image/png",
        ".txt": "text/plain",
        ".wav": "audio/wav",
    }
    files: list[dict[str, Any]] = []
    total_bytes = 0
    for candidate in sorted(root.rglob("*")):
        if candidate.is_symlink():
            raise PackValidationError(f"symlinks are forbidden: {candidate.relative_to(root)}")
        if not candidate.is_file() or candidate == manifest_path:
            continue
        relative = candidate.relative_to(root).as_posix()
        _safe_relative_path(relative)
        suffix = candidate.suffix.lower()
        if suffix in EXECUTABLE_SUFFIXES or suffix not in ALLOWED_SUFFIXES:
            raise PackValidationError(f"unsupported or executable file type: {relative}")
        size = candidate.stat().st_size
        if size > MAX_FILE_BYTES:
            raise PackValidationError(f"file exceeds size limit: {relative}")
        total_bytes += size
        files.append(
            {
                "path": relative,
                "digest": sha256_file_bytes(candidate.read_bytes()),
                "bytes": size,
                "mediaType": media_types[suffix],
            }
        )
    if not 1 <= len(files) <= MAX_FILES or total_bytes > MAX_PACK_BYTES:
        raise PackValidationError("pack file count or total size exceeds limits")
    candidate_manifest = {**manifest, "files": files}
    candidate_manifest["contentDigest"] = expected_content_digest(candidate_manifest)
    rendered = _render_manifest(candidate_manifest)

    # Validate a private copy first, so a failed seal never corrupts the
    # contributor's source manifest.
    with tempfile.TemporaryDirectory(prefix="omega-pack-seal-") as temp:
        staging = Path(temp) / "pack"
        shutil.copytree(root, staging)
        (staging / "pack.toml").write_text(rendered, encoding="utf-8")
        validate_pack(staging)
    manifest_path.write_text(rendered, encoding="utf-8")
    return validate_pack(root)
