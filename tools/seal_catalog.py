#!/usr/bin/env python3
"""Seal Limitless game capsules using the real OSS sealer."""

from __future__ import annotations

import json
from pathlib import Path

from limitless_library.catalog import seal_capsule

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "integrations" / "limitless" / "catalog"


def main() -> None:
    for draft_path in CATALOG.glob("*/capsule.draft.json"):
        root = draft_path.parent
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        # exact-component drafts may carry a placeholder digest; sealer overwrites.
        for offer in draft.get("offers", []):
            if offer.get("kind") == "exact-component":
                files = []
                for item in offer.get("files") or []:
                    files.append({"source": item["source"]})
                offer["files"] = files or offer["files"]
        sealed = seal_capsule(draft, root)
        dest = root / "capsule.json"
        dest.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"sealed {sealed['id']} -> {dest}")


if __name__ == "__main__":
    main()
