"""Save/load, reroll retention, and corruption rejection."""

from __future__ import annotations

import json
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from .canonical import sha256_json
from .identity import WorldIdentity

SAVE_VERSION = "1.0.0"
WEB_STORAGE_PREFIX = "omega-omarchy.file.v1."

# Reroll rule (explicit):
# KEEP: character, settings, accessibility, converted capabilities, share policy,
#       omega-code history, local customizations, play-time.
# ARCHIVE: previous world identity + sealed receipt written to archives/.
# RESET: generated chapters, penguins-in-world, uncleared bosses, zone deltas,
#        in-flight combat. Campaign chapter progress tied to the old seed is archived,
#        not copied onto the new seed.


REROLL_POLICY = {
    "retain": [
        "character",
        "settings",
        "accessibility",
        "convertedCapabilities",
        "sharePolicy",
        "omegaHistory",
        "localCustomizations",
        "playSeconds",
        "rerollRootSeed",
    ],
    "archive": ["identity", "receipt", "chapters", "zoneDeltas", "penguins", "bossState"],
    "reset": ["chapters", "zoneDeltas", "penguins", "bossState", "combat", "currentChapter"],
}


class SaveError(ValueError):
    """Save bytes are corrupt, mismatched, or forged."""


def user_data_dir(
    environ: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
) -> Path:
    """Return the freedesktop data root without trusting relative overrides."""

    values = os.environ if environ is None else environ
    configured = values.get("XDG_DATA_HOME", "")
    if configured and Path(configured).is_absolute():
        root = Path(configured)
    else:
        root = (home or Path.home()) / ".local" / "share"
    return root / "omega-omarchy"


def _browser_storage() -> Any | None:
    """Return pygbag's localStorage bridge without affecting native imports."""

    if sys.platform != "emscripten":
        return None
    try:
        from platform import window

        return window.localStorage
    except (AttributeError, ImportError):
        return None


def _browser_key(path: Path) -> str:
    path = Path(path)
    namespace = "archive." if path.parent.name == "archives" else ""
    return f"{WEB_STORAGE_PREFIX}{namespace}{path.name}"


def _envelope(payload: dict[str, Any]) -> dict[str, Any]:
    body = {key: value for key, value in payload.items() if key != "saveDigest"}
    return {**body, "saveDigest": sha256_json(body)}


def make_save(world_record: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "progress": progress,
        "saveVersion": SAVE_VERSION,
        "world": world_record,
        "worldDigest": world_record["identityDigest"],
    }
    return _envelope(payload)


def validate_save(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise SaveError("save is not an object")
    digest = record.get("saveDigest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise SaveError("save missing digest")
    body = {key: value for key, value in record.items() if key != "saveDigest"}
    if sha256_json(body) != digest:
        raise SaveError("save digest mismatch")
    if body.get("saveVersion") != SAVE_VERSION:
        raise SaveError("unsupported save version")
    world = body.get("world")
    if not isinstance(world, dict) or "identity" not in world:
        raise SaveError("save missing world identity")
    identity = WorldIdentity.from_record(world["identity"])
    if identity.digest() != world.get("identityDigest"):
        raise SaveError("identity digest mismatch")
    if body.get("worldDigest") != identity.digest():
        raise SaveError("envelope world digest mismatch")
    return record


def write_save(path: Path, record: dict[str, Any]) -> None:
    path = Path(path)
    encoded = json.dumps(record, indent=2, sort_keys=True)
    storage = _browser_storage()
    if storage is not None:
        storage.setItem(_browser_key(path), encoded)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(encoded, encoding="utf-8")
    tmp.replace(path)


def read_save(path: Path) -> dict[str, Any]:
    try:
        storage = _browser_storage()
        if storage is not None:
            stored = storage.getItem(_browser_key(Path(path)))
            if stored is None:
                raise OSError("browser save does not exist")
            raw = str(stored)
        else:
            raw = Path(path).read_text(encoding="utf-8")
        record = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SaveError(f"unreadable save: {exc}") from exc
    return validate_save(record)


def reroll_progress(previous: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a save's progress into retained live state and an archive record."""

    retain = {key: previous.get(key) for key in REROLL_POLICY["retain"] if key in previous}
    archive = {key: previous.get(key) for key in REROLL_POLICY["archive"] if key in previous}
    retain["currentChapter"] = "corrupted-install"
    retain["rerolls"] = int(previous.get("rerolls", 0)) + 1
    return retain, archive
