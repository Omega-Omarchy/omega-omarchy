"""Complete character art; custom packs are digest-pinned, built-ins receive fixes."""

from __future__ import annotations

import base64
from dataclasses import replace
from hashlib import sha256
from functools import lru_cache
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import struct
import sys
import zipfile
import zlib

from .canonical import sha256_json
from .character import Character, DAVID
from .presentation import FIDELITIES, SPRITE_SIZE, view_scale
from .runtime_assets import asset_dir
from .save import user_data_dir

POSES = {
    "side-idle": "Standing, right-facing profile; neutral feet and hands.",
    "side-walk-0": "Right-facing walk: left leg forward, right leg behind (contact A).",
    "side-walk-1": "Right-facing walk: left support leg, right leg passing (passing A).",
    "side-walk-2": "Right-facing walk: right leg forward, left leg behind (contact B).",
    "side-walk-3": "Right-facing walk: right support leg, left leg passing (passing B).",
    "side-jump": "Rising jump, right-facing, knees lifted.",
    "side-fall": "Descending jump, right-facing, braced to land.",
    "side-land": "Brief compressed landing, right-facing, feet grounded.",
    "side-crouch": "Low crouch facing right, feet grounded.",
    "side-slide": "Low feet-first slide to the right, bracing hand behind; preserve canvas headroom.",
    "side-climb-0": "Rear-facing ladder climb: left hand high, right knee high.",
    "side-climb-1": "Rear-facing ladder climb: passing A.",
    "side-climb-2": "Rear-facing ladder climb: right hand high, left knee high.",
    "side-climb-3": "Rear-facing ladder climb: passing B.",
    "side-action": "Grounded forward kick to the right, supporting foot planted.",
    "side-air-action": "Airborne forward kick to the right.",
    "side-bomb": "Overhand throw to the right, empty hand; projectile is rendered separately.",
    "side-hurt": "Brief recoil, right-facing; no damage effects baked in.",
    "battle": "Right-facing full-body battle stance; may reuse idle.",
    "away": "Full-body back view, looking away from camera.",
    "flight": "Full-body back view flying away, visible hands and feet, no trail.",
    "ots": "Rear view from head to upper thighs, both arms/hands visible; no desk or monitor.",
    "portrait": "Face closeup from hairline to chin, eyes level, matching David's framing.",
    "turn": "Front portrait for facing the viewer; may reuse portrait.",
    "prologue-captured": "Slumped seated body facing right; no chair, orbs, cuffs or machinery.",
    "prologue-transfer": "Supine diagonal three-quarter view: boots lower left, head upper right; no bed or machine.",
}
BUILTIN_NAMES = {"omarch-king": "The Omarch King", "omarch-queen": "The Omarch Queen"}
ID_RE = re.compile(r"[a-z][a-z0-9-]{1,47}\Z")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
MAX_PACK_BYTES = 12 * 1024 * 1024
MAX_ZIP_BYTES = 4 * 1024 * 1024


@lru_cache(maxsize=256)
def decode_png(data: bytes) -> bytes:
    """Decode our narrow 8-bit RGBA contract, including imported browser PNGs.

    pygbag's image loader requires preloaded resources. Dynamic imports use
    pygame.image.frombytes instead; this decoder also validates at admission.
    """
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("Invalid character PNG.")
    width, height = struct.unpack(">II", data[16:24])
    if not (0 < width <= 252 and 0 < height <= 288) or data[24:29] != bytes((8, 6, 0, 0, 0)):
        raise ValueError("Character PNG must be noninterlaced 8-bit RGBA within the pose dimensions.")
    offset, compressed, finished = 8, bytearray(), False
    while offset + 12 <= len(data):
        size = struct.unpack(">I", data[offset:offset + 4])[0]
        end = offset + size + 12
        if end > len(data):
            raise ValueError("Truncated character PNG.")
        kind, payload = data[offset + 4:offset + 8], data[offset + 8:end - 4]
        if zlib.crc32(kind + payload) & 0xffffffff != struct.unpack(">I", data[end - 4:end])[0]:
            raise ValueError("Character PNG checksum failed.")
        if kind == b"IDAT":
            compressed.extend(payload)
        if kind == b"IEND":
            finished = size == 0 and end == len(data)
            break
        offset = end
    if not finished:
        raise ValueError("Character PNG has no valid end marker.")
    stride = width * 4
    expected = (stride + 1) * height
    try:
        decoder = zlib.decompressobj()
        filtered = decoder.decompress(bytes(compressed), expected + 1)
        if len(filtered) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("Character PNG has invalid or oversized pixel data.")
    except zlib.error as error:
        raise ValueError("Character PNG pixel compression is invalid.") from error
    result, prior = bytearray(), bytearray(stride)
    for y in range(height):
        begin = y * (stride + 1)
        filter_type = filtered[begin]
        row = bytearray(filtered[begin + 1:begin + 1 + stride])
        if filter_type not in range(5):
            raise ValueError("Unknown character PNG filter.")
        if filter_type:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                up, upper_left = prior[x], prior[x - 4] if x >= 4 else 0
                if filter_type == 1:
                    prediction = left
                elif filter_type == 2:
                    prediction = up
                elif filter_type == 3:
                    prediction = (left + up) // 2
                else:
                    p = left + up - upper_left
                    a, b, c = abs(p - left), abs(p - up), abs(p - upper_left)
                    prediction = left if a <= b and a <= c else up if b <= c else upper_left
                row[x] = (row[x] + prediction) & 255
        result.extend(row)
        prior = row
    return bytes(result)


def pose_size(pose: str, fidelity: str) -> tuple[int, int]:
    vs = view_scale(fidelity)
    if pose in {"portrait", "turn"}:
        edge = {"sixteen-bit": 48, "high": 64, "ultra": 96}[fidelity]
        return edge, edge
    if pose == "ots":
        return 80 * vs, 96 * vs
    if pose == "prologue-captured":
        return 48 * vs, 54 * vs
    if pose == "prologue-transfer":
        return 84 * vs, 58 * vs
    w, h = SPRITE_SIZE[fidelity]
    return (w + 8, h + 8) if pose == "flight" else (w, h)


def expected_files() -> set[str]:
    return {f"{fid}/{pose}.png" for fid in FIDELITIES for pose in POSES}


def _metadata(record: dict) -> None:
    if not isinstance(record, dict):
        raise ValueError("Character manifest must be an object.")
    if record.get("schemaVersion") != 1 or not ID_RE.fullmatch(str(record.get("id", ""))):
        raise ValueError("Character pack needs schemaVersion 1 and a lowercase id (2–48 letters/digits/hyphens).")
    for key, limit in (("name", 24), ("author", 120), ("license", 240)):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit or not value.isprintable():
            raise ValueError(f"Character pack needs a printable {key} of at most {limit} characters.")


def validate_pack(root: Path) -> dict:
    work = validate_pack_steps(root)
    while True:
        try:
            next(work)
        except StopIteration as done:
            return done.value


def validate_pack_steps(root: Path):
    """Validate one PNG per step so startup can share time with rendering."""
    root = Path(root)
    manifest_path = root / "manifest.json"
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 64 * 1024:
        raise ValueError("Invalid character manifest.")
    record = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("Character manifest must be an object.")
    _metadata(record)
    files = record.get("files")
    if not isinstance(files, dict) or set(files) != expected_files():
        raise ValueError("Character pack must supply all 26 poses at all three fidelities (78 PNGs).")
    digest = record.get("digest")
    if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest) or digest != sha256_json({k: v for k, v in record.items() if k != "digest"}):
        raise ValueError("Character manifest digest mismatch.")
    total = 0
    for relative, expected in files.items():
        path = root / relative
        if path.is_symlink() or path.parent.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("Character assets must be local regular files.")
        size = path.stat().st_size
        total += size
        if size > 1024 * 1024 or total > MAX_PACK_BYTES:
            raise ValueError("Character pack exceeds its size limit.")
        data = path.read_bytes()
        if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise ValueError(f"Invalid PNG: {relative}")
        fid, filename = relative.split("/")
        if struct.unpack(">II", data[16:24]) != pose_size(filename[:-4], fid) or data[24:26] != bytes((8, 6)):
            raise ValueError(f"Wrong dimensions or format: {relative}; use 8-bit RGBA PNG.")
        if "sha256:" + sha256(data).hexdigest() != expected:
            raise ValueError(f"Character asset digest mismatch: {relative}")
        pixels = decode_png(data)
        alpha = pixels[3::4]
        if max(alpha) < 200 or min(alpha) != 0:
            raise ValueError(f"Character pose needs an opaque subject and transparent background: {relative}")
        yield
    return record


def pack_character(record: dict, *, builtin: bool = False) -> Character:
    kind = record["id"] if builtin and record["id"] in BUILTIN_NAMES else "custom"
    return replace(DAVID, name=record["name"], kind=kind, asset_pack=record["id"], asset_digest=record["digest"])


def available_characters(*, assets: Path | None = None, storage: Path | None = None) -> tuple[list[Character], list[str]]:
    roster, errors = [DAVID], []
    for result in character_preload_steps(assets=assets, storage=storage):
        if isinstance(result, str):
            errors.append(result)
        elif result is not None:
            roster.append(result[0])
    return roster, errors


def character_preload_steps(*, assets: Path | None = None, storage: Path | None = None):
    """Yield between files, then return each validated character and its root."""
    assets = assets or asset_dir()
    storage = storage or user_data_dir() / "characters"
    seen = set()
    candidates = [(assets / "character-packs" / key, True) for key in BUILTIN_NAMES]
    candidates += [(p.parent, False) for p in sorted((assets / "character-packs").glob("*/manifest.json")) if p.parent.name not in BUILTIN_NAMES]
    candidates += [(p.parent, False) for p in sorted(storage.glob("*/*/manifest.json"))]
    for root, builtin in candidates:
        if not (root / "manifest.json").is_file():
            continue
        try:
            record = yield from validate_pack_steps(root)
            key = (record["id"], record["digest"])
            if key not in seen:
                yield pack_character(record, builtin=builtin), root
                seen.add(key)
        except (ValueError, OSError, TypeError, KeyError) as error:
            yield f"{root.name}: {error}"


def resolve_pack(character: dict, *, assets: Path | None = None, storage: Path | None = None) -> Path | None:
    pack_id, digest = character.get("assetPack", ""), character.get("assetDigest", "")
    if not pack_id:
        return None
    if not isinstance(pack_id, str) or not ID_RE.fullmatch(pack_id) or not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
        raise ValueError("Invalid saved character pack identity.")
    bundled = (assets or asset_dir()) / "character-packs" / pack_id
    candidates = [bundled,
                  (storage or user_data_dir() / "characters") / pack_id / digest[7:]]
    for root in candidates:
        if (root / "manifest.json").is_file():
            try:
                record = validate_pack(root)
            except (ValueError, OSError, KeyError, TypeError):
                continue
            builtin_fix = root == bundled and pack_id in BUILTIN_NAMES and character.get("kind") == pack_id
            if record["id"] == pack_id and (record["digest"] == digest or builtin_fix):
                return root
    raise ValueError(f"Character art unavailable: {pack_id}. Reinstall its saved version.")


def install_pack(source: Path, *, storage: Path | None = None) -> Path:
    source = Path(source)
    record = validate_pack(source)
    dest = (storage or user_data_dir() / "characters") / record["id"] / record["digest"][7:]
    if dest.exists():
        validate_pack(dest)
        return dest
    dest.mkdir(parents=True)
    try:
        for relative in ["manifest.json", *sorted(record["files"])]:
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target)
        validate_pack(dest)
    except Exception:
        shutil.rmtree(dest)
        raise
    return dest


def install_zip(data: bytes, *, storage: Path | None = None) -> Path:
    import tempfile

    if len(data) > MAX_ZIP_BYTES:
        raise ValueError("Character ZIP must be at most 4 MiB.")
    with zipfile.ZipFile(BytesIO(data)) as archive, tempfile.TemporaryDirectory(prefix="omega-character-") as temp:
        entries = archive.infolist()
        allowed = expected_files() | {"manifest.json"}
        if len(entries) != len(allowed) or {e.filename for e in entries} != allowed:
            raise ValueError("Character ZIP must contain manifest.json and the 78 PNGs at its root.")
        if sum(e.file_size for e in entries) > MAX_PACK_BYTES or any(e.file_size > 1024 * 1024 for e in entries):
            raise ValueError("Expanded character ZIP exceeds its size limit.")
        for entry in entries:
            target = Path(temp) / entry.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(entry))
        return install_pack(Path(temp), storage=storage)


def restore_browser_characters() -> None:
    if sys.platform != "emscripten":
        return
    from platform import window

    try:
        storage = window.localStorage
        keys = [str(storage.key(index)) for index in range(storage.length)]
    except Exception:
        return
    for key in keys:
        if key.startswith("omega-omarchy.character.v1."):
            try:
                encoded = str(storage.getItem(key))
                if len(encoded) > MAX_ZIP_BYTES * 4 // 3 + 8:
                    continue
                install_zip(base64.b64decode(encoded, validate=True))
            except (ValueError, OSError, zipfile.BadZipFile, RuntimeError, KeyError, TypeError):
                continue


def poll_browser_import() -> str:
    if sys.platform != "emscripten":
        return ""
    from platform import window

    encoded = str(window.omegaCharacterImport or "")
    if not encoded:
        return ""
    window.omegaCharacterImport = ""
    try:
        if len(encoded) > MAX_ZIP_BYTES * 4 // 3 + 8:
            raise ValueError("Character ZIP is too large.")
        root = install_zip(base64.b64decode(encoded, validate=True))
        record = validate_pack(root)
        message = f"Installed {record['name']}. Select it during character setup."
        try:
            window.localStorage.setItem("omega-omarchy.character.v1." + record["digest"], encoded)
        except Exception:
            message += " Browser storage is full; keep the ZIP to import next time."
        return message
    except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError, RuntimeError) as error:
        return f"Character import failed: {error}"
