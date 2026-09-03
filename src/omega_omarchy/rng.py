"""Deterministic named streams. A cosmetics draw never rewrites layout."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Iterator


STREAMS = ("layout", "loot", "cosmetics", "encounters", "narrative", "rare")


def _mix(seed: str, stream: str, index: int = 0) -> int:
    material = f"{seed}|{stream}|{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


class Stream:
    """A named, seekable deterministic integer/float/choice source."""

    def __init__(self, seed: str, name: str):
        if name not in STREAMS:
            raise ValueError(f"unknown stream {name}")
        self.seed = seed
        self.name = name
        self.index = 0

    def _next_u64(self) -> int:
        value = _mix(self.seed, self.name, self.index)
        self.index += 1
        return value

    def randint(self, lo: int, hi: int) -> int:
        if hi < lo:
            raise ValueError("empty range")
        span = hi - lo + 1
        return lo + (self._next_u64() % span)

    def random(self) -> float:
        return (self._next_u64() >> 11) / float(1 << 53)

    def chance(self, p: float) -> bool:
        return self.random() < p

    def choice(self, items: list[object]) -> object:
        if not items:
            raise ValueError("choice from empty sequence")
        return items[self.randint(0, len(items) - 1)]

    def shuffle(self, items: list[object]) -> list[object]:
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.randint(0, i)
            out[i], out[j] = out[j], out[i]
        return out


class Streams:
    def __init__(self, seed: str):
        self.seed = seed
        self._streams = {name: Stream(seed, name) for name in STREAMS}

    def __getitem__(self, name: str) -> Stream:
        return self._streams[name]

    def snapshot(self) -> dict[str, int]:
        return {name: stream.index for name, stream in self._streams.items()}
