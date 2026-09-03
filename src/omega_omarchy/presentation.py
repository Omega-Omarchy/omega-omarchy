"""Art fidelity vs display treatment.

Collision, TILE size, and hitbox dimensions never change with these values.
Legacy `quality` strings from saves/installer are migrated in place.
"""

from __future__ import annotations

from typing import Any

FIDELITIES = ("sixteen-bit", "high", "ultra")
DISPLAYS = ("clean", "crt")

# Historical installer values. Kept so old saves and tests keep working.
LEGACY_QUALITY = ("eight-bit", "sixteen-bit", "clean-pixel", "crt", "high", "ultra")

_QUALITY_TO_FIDELITY = {
    "eight-bit": "sixteen-bit",
    "sixteen-bit": "sixteen-bit",
    "clean-pixel": "sixteen-bit",
    "crt": "sixteen-bit",
    "high": "high",
    "ultra": "ultra",
}

SPRITE_SIZE = {
    # Authored run/jump silhouettes use a wider source canvas at every tier.
    # Rendering remains foot-anchored at CHAR_WORLD_HEIGHT and collision stays
    # on the unchanged 10x18 Body, so this adds art room rather than reach.
    "sixteen-bit": (40, 36),
    "high": (80, 72),
    "ultra": (120, 108),
}

# Source texels. On screen a tile is always TILE world-pixels, scaled by VIEW_SCALE.
TILE_ART_SIZE = {
    "sixteen-bit": 16,
    "high": 32,
    "ultra": 64,
}

BLOCK_ART_SIZE = {
    "sixteen-bit": 16,
    "high": 32,
    "ultra": 64,
}

# Multiply the 320×180 logical canvas. Collision TILE is unchanged.
VIEW_SCALE = {
    "sixteen-bit": 1,
    "high": 2,
    "ultra": 3,
}

CHAR_WORLD_HEIGHT = 36  # player sprite occupies this many world pixels vertically


def view_scale(fidelity: str) -> int:
    return VIEW_SCALE.get(fidelity, 1)


def canvas_size(fidelity: str) -> tuple[int, int]:
    vs = view_scale(fidelity)
    return 320 * vs, 180 * vs

PARALLAX_LAYERS = {
    "sixteen-bit": 2,
    "high": 3,
    "ultra": 4,
}

CRT_SCANLINE_DEFAULT = 0.12
CRT_CURVATURE_DEFAULT = 0.12
CRT_PHOSPHOR_DEFAULT = 0.12


def crt_controls(
    scanline: float = CRT_SCANLINE_DEFAULT,
    curvature: float = CRT_CURVATURE_DEFAULT,
    phosphor: float = CRT_PHOSPHOR_DEFAULT,
    *,
    enabled: bool = False,
) -> dict[str, float]:
    """Expand the three player-facing CRT controls into renderer parameters."""

    scanline = max(0.0, min(1.0, float(scanline)))
    curvature = max(0.0, min(1.0, float(curvature)))
    phosphor = max(0.0, min(1.0, float(phosphor)))
    return {
        # ``intensity`` remains as a compatibility alias for the older paired
        # scanline/curvature control. New saves use independent masters.
        "intensity": scanline,
        "scanline": scanline,
        "curvatureControl": curvature,
        "phosphor": phosphor,
        "scanlines": 0.14 + scanline * 0.62,
        "scanlineSize": scanline,
        "curvature": curvature,
        "chromatic": 0.0,
        "bloom": 0.10 + phosphor * 0.38,
        "noise": 0.0,
        "vignette": 0.06 + curvature * 0.12,
        "persistence": 0.02 + phosphor * 0.10,
        "mask": 0.08 + phosphor * 0.42,
        "enabled": 1.0 if enabled else 0.0,
    }


def migrate_quality(quality: str | None, settings: dict[str, Any] | None = None) -> tuple[str, str]:
    """Return (fidelity, display) for a legacy or current settings record."""

    settings = dict(settings or {})
    quality = str(quality or settings.get("quality") or "ultra")
    fid = settings.get("fidelity")
    if fid == "eight-bit":
        fid = "sixteen-bit"
    if fid not in FIDELITIES:
        fid = _QUALITY_TO_FIDELITY.get(quality, "ultra")
    disp = settings.get("display")
    crt = settings.get("crt") or {}
    crt_on = float(crt.get("enabled") or 0) > 0
    if disp not in DISPLAYS:
        if quality == "crt" or crt_on:
            disp = "crt"
        else:
            disp = "clean"
    if settings.get("reducedMotion"):
        disp = "clean"
    return str(fid), str(disp)


def apply_presentation(settings: dict[str, Any], *, quality: str | None = None) -> dict[str, Any]:
    """Write migrated fidelity/display back onto settings without dropping legacy keys."""

    out = dict(settings)
    fid, disp = migrate_quality(quality or out.get("quality"), out)
    out["fidelity"] = fid
    out["display"] = disp
    out["quality"] = quality or out.get("quality") or fid
    if out["quality"] == "eight-bit":
        out["quality"] = "sixteen-bit"
    incoming = dict(out.get("crt") or {})
    legacy_intensity = float(incoming.get("intensity", CRT_SCANLINE_DEFAULT))
    scanline = float(incoming.get("scanline", legacy_intensity))
    curvature = float(incoming.get("curvatureControl", legacy_intensity))
    phosphor = float(incoming.get("phosphor", CRT_PHOSPHOR_DEFAULT))
    crt = crt_controls(scanline, curvature, phosphor, enabled=disp == "crt")
    # Keep intentionally supplied low-level values for migrated saves and
    # rendering tests. Once a master control exists, it owns the linked values.
    if not {"intensity", "scanline", "curvatureControl", "phosphor"}.intersection(incoming):
        crt.update(incoming)
    crt["enabled"] = 1.0 if disp == "crt" else 0.0
    out["crt"] = crt
    return out


def cycle_fidelity(current: str, delta: int) -> str:
    if current not in FIDELITIES:
        current = "ultra"
    return FIDELITIES[(FIDELITIES.index(current) + delta) % len(FIDELITIES)]


def cycle_display(current: str, delta: int) -> str:
    if current not in DISPLAYS:
        current = "clean"
    return DISPLAYS[(DISPLAYS.index(current) + delta) % len(DISPLAYS)]
