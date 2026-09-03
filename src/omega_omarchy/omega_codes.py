"""Omega Codes: standard QR payloads for seeds and safe references."""

from __future__ import annotations

import json
from importlib import import_module
from typing import Any

from .canonical import sha256_json

SCHEMA = "omega-omarchy.omega-code/1"
KINDS = {
    "seed",
    "character",
    "challenge",
    "customization",
    "replay",
    "ghost",
}


class OmegaCodeError(ValueError):
    pass


def make_payload(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    if kind not in KINDS:
        raise OmegaCodeError(f"unsupported kind {kind}")
    payload = {"body": body, "kind": kind, "schema": SCHEMA, "v": 1}
    payload["digest"] = sha256_json({key: payload[key] for key in payload if key != "digest"})
    return payload


def encode_text(payload: dict[str, Any]) -> str:
    if payload.get("schema") != SCHEMA:
        raise OmegaCodeError("unknown schema")
    expected = sha256_json({key: payload[key] for key in payload if key != "digest"})
    if payload.get("digest") != expected:
        raise OmegaCodeError("payload digest mismatch")
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def decode_text(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OmegaCodeError("not JSON") from exc
    if not isinstance(payload, dict):
        raise OmegaCodeError("payload must be an object")
    if payload.get("schema") != SCHEMA:
        raise OmegaCodeError("unknown schema")
    if payload.get("kind") not in KINDS:
        raise OmegaCodeError("unknown kind")
    expected = sha256_json({key: payload[key] for key in payload if key != "digest"})
    if payload.get("digest") != expected:
        raise OmegaCodeError("payload digest mismatch")
    return payload


def seed_payload(seed: str, identity_record: dict[str, Any]) -> dict[str, Any]:
    return make_payload(
        "seed",
        {
            "seed": seed,
            "generatorVersion": identity_record["generatorVersion"],
            "schemaVersion": identity_record["schemaVersion"],
            "contentDigest": identity_record["contentDigest"],
            "contentPackIds": identity_record["contentPackIds"],
            "identityDigest": sha256_json(identity_record),
        },
    )


def render_qr(payload: dict[str, Any], *, box_size: int = 4, border: int = 2) -> Any:
    # QR export is an offline/native utility. Dynamic imports keep Pillow and
    # qrcode out of the browser game's dependency graph.
    qrcode = import_module("qrcode")
    Image = import_module("PIL.Image")

    text = encode_text(payload)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(text)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    # Tokyo-night framed QR: lime modules on near-black, bronze quiet-zone frame.
    module = 1 if box_size < 3 else box_size
    quiet = border * module
    n = len(matrix)
    size = n * module + 2 * quiet + 8
    img = Image.new("RGB", (size, size), (26, 27, 38))
    pixels = img.load()
    origin = 4 + quiet
    on = (185, 242, 124)
    off = (19, 20, 28)
    for y in range(n):
        for x in range(n):
            color = on if matrix[y][x] else off
            for dy in range(module):
                for dx in range(module):
                    pixels[origin + x * module + dx, origin + y * module + dy] = color
    # bronze triangular-ish corner ticks
    bronze = (196, 132, 72)
    for i in range(8):
        pixels[i, 0] = bronze
        pixels[0, i] = bronze
        pixels[size - 1 - i, 0] = bronze
        pixels[size - 1, i] = bronze
        pixels[i, size - 1] = bronze
        pixels[0, size - 1 - i] = bronze
        pixels[size - 1 - i, size - 1] = bronze
        pixels[size - 1, size - 1 - i] = bronze
    return img
