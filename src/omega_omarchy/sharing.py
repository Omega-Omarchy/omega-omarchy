"""Asynchronous sharing: seeds, challenges, ghosts, replay. Multiplayer is a seam."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .canonical import sha256_json
from .omega_codes import decode_text, encode_text, make_payload, seed_payload


@dataclass
class GhostFrame:
    tick: int
    x: float
    y: float
    facing: int


def encode_replay(seed: str, identity_digest: str, frames: list[dict[str, Any]]) -> dict[str, Any]:
    return make_payload(
        "replay",
        {
            "frames": frames,
            "identityDigest": identity_digest,
            "seed": seed,
        },
    )


def encode_ghost(seed: str, identity_digest: str, samples: list[GhostFrame]) -> dict[str, Any]:
    return make_payload(
        "ghost",
        {
            "identityDigest": identity_digest,
            "samples": [{"facing": s.facing, "tick": s.tick, "x": s.x, "y": s.y} for s in samples],
            "seed": seed,
        },
    )


def encode_challenge(name: str, seed: str, identity_digest: str, rules: dict[str, Any]) -> dict[str, Any]:
    return make_payload(
        "challenge",
        {"identityDigest": identity_digest, "name": name, "rules": rules, "seed": seed},
    )


def encode_character_ref(character: dict[str, Any]) -> dict[str, Any]:
    return make_payload("character", character)


def import_code(text: str) -> dict[str, Any]:
    return decode_text(text)


# Reserved seam for later synchronous play. Do not call in 0.1.0.
class SyncMultiplayerSeam:
    version = "omega-omarchy.sync-seam/0"
    authority = "later-deterministic-or-narrow-server"
    enabled = False

    def connect(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("synchronous multiplayer is not part of this release")
