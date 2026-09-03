"""Lightweight runtime asset lookup shared by native and browser builds."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from .omarchy_adapter import DEFAULT_THEME, theme_to_game_palette

PALETTE = theme_to_game_palette(DEFAULT_THEME)
BRONZE = (196, 132, 72)


def asset_dir() -> Path:
    """Resolve baked runtime art without importing the offline asset toolchain."""

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root) / "assets"
    configured = os.environ.get("OMEGA_ASSET_ROOT", "")
    if configured and Path(configured).is_absolute():
        return Path(configured)
    packaged = Path(__file__).resolve().parent.parent / "assets"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "assets"
