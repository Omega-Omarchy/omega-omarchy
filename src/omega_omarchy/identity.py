"""World identity binding: seed + generator + schema + ordered content digests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import canonical_json_bytes, sha256_json

GENERATOR_VERSION = "3.8.0"
SCHEMA_VERSION = "1.0.0"
COMPATIBILITY_TARGET = "omega-omarchy/linux-web/1"


@dataclass(frozen=True)
class WorldIdentity:
    seed: str
    generator_version: str
    schema_version: str
    content_pack_ids: tuple[str, ...]
    content_digest: str
    difficulty: str
    accessibility_profile: str
    compatibility_target: str = COMPATIBILITY_TARGET

    def to_record(self) -> dict[str, Any]:
        return {
            "accessibilityProfile": self.accessibility_profile,
            "compatibilityTarget": self.compatibility_target,
            "contentDigest": self.content_digest,
            "contentPackIds": list(self.content_pack_ids),
            "difficulty": self.difficulty,
            "generatorVersion": self.generator_version,
            "schemaVersion": self.schema_version,
            "seed": self.seed,
        }

    def digest(self) -> str:
        return sha256_json(self.to_record())

    def world_id(self) -> str:
        return self.digest()

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> WorldIdentity:
        required = (
            "seed",
            "generatorVersion",
            "schemaVersion",
            "contentPackIds",
            "contentDigest",
            "difficulty",
            "accessibilityProfile",
            "compatibilityTarget",
        )
        missing = [key for key in required if key not in record]
        if missing:
            raise ValueError(f"identity missing fields: {missing}")
        packs = record["contentPackIds"]
        if not isinstance(packs, list) or not all(isinstance(item, str) for item in packs):
            raise ValueError("contentPackIds must be an ordered list of strings")
        return cls(
            seed=str(record["seed"]),
            generator_version=str(record["generatorVersion"]),
            schema_version=str(record["schemaVersion"]),
            content_pack_ids=tuple(packs),
            content_digest=str(record["contentDigest"]),
            difficulty=str(record["difficulty"]),
            accessibility_profile=str(record["accessibilityProfile"]),
            compatibility_target=str(record["compatibilityTarget"]),
        )


# Re-export for callers that import identity.sha256_json
__all__ = [
    "COMPATIBILITY_TARGET",
    "GENERATOR_VERSION",
    "SCHEMA_VERSION",
    "WorldIdentity",
    "canonical_json_bytes",
    "sha256_json",
]
