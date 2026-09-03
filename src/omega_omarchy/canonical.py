"""Canonical JSON and digest helpers. Matches Limitless Library's record binding."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def sha256_file_bytes(data: bytes) -> str:
    return sha256_bytes(data)


def without(value: dict[str, Any], field: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != field}
