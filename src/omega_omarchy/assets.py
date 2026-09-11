"""Original production pixel art. Private photo references are never packaged."""

from __future__ import annotations

import math
import shutil
import wave
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .runtime_assets import BRONZE, PALETTE, asset_dir

# Quality presets each get purpose-built character views. The 8-bit OTS asset
# is a separately composed back-of-head sprite, never an upscale of the side view.

PRESETS = ("eight-bit", "sixteen-bit", "clean-pixel", "crt", "high", "ultra")
VIEWS = (
    "side-idle",
    "side-walk-0",
    "side-walk-1",
    "side-walk-2",
    "side-walk-3",
    "side-jump",
    "side-fall",
    "side-land",
    "side-crouch",
    "side-slide",
    "side-climb-0",
    "side-climb-1",
    "side-climb-2",
    "side-climb-3",
    "side-action",
    "side-air-action",
    "flight",
    "away",
    "ots",
    "portrait",
    "turn",
)

BRONZE_DARK = (92, 58, 32)
BRONZE_LIGHT = (232, 186, 124)
HAIR = (110, 72, 42)
HAIR_LIGHT = (156, 108, 64)
HAIR_DARK = (64, 40, 24)
SKIN = (224, 176, 144)
SKIN_SHADOW = (196, 140, 112)
BEARD = (74, 54, 42)
BEARD_GREY = (138, 128, 118)
SHIRT = (16, 16, 18)
EYE = (74, 144, 200)
LIME = (185, 242, 124)
PENGUIN_BLACK = (24, 28, 36)
PENGUIN_WHITE = (236, 240, 248)
PENGUIN_GOLD = (232, 176, 64)
KEY = (255, 0, 255)  # magenta key
_BUILT_ROOTS: set[Path] = set()


def _new(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _px(img: Image.Image, x: int, y: int, color: tuple[int, ...] | None) -> None:
    if color is None:
        return
    if 0 <= x < img.width and 0 <= y < img.height:
        if len(color) == 3:
            img.putpixel((x, y), (*color, 255))
        else:
            img.putpixel((x, y), color)


def _rect(img: Image.Image, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            _px(img, xx, yy, color)


def _david_side(scale: int, frame: str) -> Image.Image:
    """Side-view David: long hair, beard, black Omarchy shirt."""

    w, h = 16 * scale, 24 * scale
    img = _new(w, h)
    s = scale
    # walk bob
    bob = 0
    leg = 0
    arm = 0
    if frame == "side-walk-0":
        leg, arm = 1, -1
    elif frame == "side-walk-1":
        bob = 0
    elif frame == "side-walk-2":
        leg, arm = -1, 1
    elif frame == "side-jump":
        bob = -2
        leg = 1
    hx = 5 * s
    hy = (2 + bob) * s
    # hair volume
    _rect(img, hx - 2 * s, hy, 10 * s, 8 * s, HAIR)
    _rect(img, hx - 3 * s, hy + 3 * s, 4 * s, 10 * s, HAIR_DARK)  # long back
    _rect(img, hx + 6 * s, hy + 2 * s, 3 * s, 8 * s, HAIR_LIGHT)  # front fall
    # head
    _rect(img, hx, hy + 2 * s, 6 * s, 6 * s, SKIN)
    _rect(img, hx + 4 * s, hy + 4 * s, 2 * s, 2 * s, EYE)
    # beard + grey chin
    _rect(img, hx, hy + 6 * s, 6 * s, 3 * s, BEARD)
    _rect(img, hx + 2 * s, hy + 8 * s, 3 * s, 1 * s, BEARD_GREY)
    # torso / black shirt + white mark
    tx, ty = 4 * s, (10 + bob) * s
    _rect(img, tx, ty, 8 * s, 7 * s, SHIRT)
    _rect(img, tx + 2 * s, ty + 2 * s, 4 * s, 2 * s, (245, 245, 248))  # Omarchy plate
    # arms
    _rect(img, tx - s + arm * s, ty + s, 2 * s, 5 * s, SKIN)
    _rect(img, tx + 7 * s - arm * s, ty + s, 2 * s, 5 * s, SKIN)
    # legs
    _rect(img, tx + s, ty + 7 * s, 2 * s, 5 * s + leg * s, (20, 22, 28))
    _rect(img, tx + 5 * s, ty + 7 * s, 2 * s, 5 * s - leg * s, (20, 22, 28))
    return img


def _david_ots(scale: int) -> Image.Image:
    """Separately composed over-the-shoulder back view — not an upscaled side sprite."""

    w, h = 40 * scale, 48 * scale
    img = _new(w, h)
    s = scale
    # shoulders / shirt back
    _rect(img, 8 * s, 28 * s, 24 * s, 16 * s, SHIRT)
    _rect(img, 10 * s, 30 * s, 20 * s, 3 * s, (40, 40, 48))
    # neck
    _rect(img, 17 * s, 24 * s, 6 * s, 6 * s, SKIN_SHADOW)
    # back of head
    _rect(img, 12 * s, 8 * s, 16 * s, 18 * s, HAIR)
    _rect(img, 14 * s, 6 * s, 12 * s, 6 * s, HAIR_LIGHT)
    # long hair down the back
    _rect(img, 10 * s, 20 * s, 6 * s, 18 * s, HAIR_DARK)
    _rect(img, 24 * s, 18 * s, 7 * s, 16 * s, HAIR)
    # ear hint
    _rect(img, 26 * s, 16 * s, 2 * s, 3 * s, SKIN)
    # looking at a tiny lime world in front (composition, not HUD)
    _rect(img, 2 * s, 2 * s, 8 * s, 5 * s, LIME)
    return img


def _david_flight(scale: int) -> Image.Image:
    w, h = 20 * scale, 28 * scale
    img = _new(w, h)
    s = scale
    # receding along Z: slightly smaller, hair streaming toward viewer
    _rect(img, 6 * s, 4 * s, 8 * s, 10 * s, HAIR)
    _rect(img, 4 * s, 8 * s, 12 * s, 4 * s, HAIR_LIGHT)
    _rect(img, 7 * s, 8 * s, 6 * s, 6 * s, SKIN)
    _rect(img, 6 * s, 14 * s, 8 * s, 8 * s, SHIRT)
    _rect(img, 8 * s, 16 * s, 4 * s, 2 * s, (245, 245, 248))
    _rect(img, 7 * s, 22 * s, 3 * s, 5 * s, (20, 22, 28))
    _rect(img, 11 * s, 22 * s, 3 * s, 5 * s, (20, 22, 28))
    return img


def _david_portrait(scale: int) -> Image.Image:
    w, h = 32 * scale, 32 * scale
    img = _new(w, h)
    s = scale
    _rect(img, 4 * s, 4 * s, 24 * s, 24 * s, HAIR)
    _rect(img, 8 * s, 8 * s, 16 * s, 16 * s, SKIN)
    _rect(img, 12 * s, 14 * s, 3 * s, 3 * s, EYE)
    _rect(img, 19 * s, 14 * s, 3 * s, 3 * s, EYE)
    _rect(img, 10 * s, 20 * s, 12 * s, 6 * s, BEARD)
    _rect(img, 14 * s, 24 * s, 6 * s, 2 * s, BEARD_GREY)
    _rect(img, 6 * s, 26 * s, 20 * s, 6 * s, SHIRT)
    _rect(img, 12 * s, 28 * s, 8 * s, 2 * s, (245, 245, 248))
    return img


def _preset_scale(preset: str) -> int:
    return {"eight-bit": 1, "sixteen-bit": 2, "clean-pixel": 2, "crt": 2, "high": 3, "ultra": 4}[preset]


def _quantize(img: Image.Image, colors: int) -> Image.Image:
    """Reduce color depth while preserving the source alpha channel."""

    alpha = img.convert("RGBA").getchannel("A")
    pal = img.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    out = pal.convert("RGBA")
    out.putalpha(alpha)
    return out


def _fidelity_finish(img: Image.Image, fidelity: str) -> Image.Image:
    """Finish a shared Ultra source at SNES, 32-bit, or full rendered quality."""

    img = img.convert("RGBA")
    if fidelity == "sixteen-bit":
        # SNES-class art: full target resolution, modeled shading retained,
        # selective palette economy rather than NES-like half-res crushing.
        img = ImageEnhance.Contrast(img).enhance(1.06)
        return ImageEnhance.Sharpness(_quantize(img, 64)).enhance(1.03)
    if fidelity == "high":
        # 32-bit-era raster art: broad color range and smooth silhouettes, but
        # still materially flatter than the unquantized Ultra source.
        return _quantize(ImageEnhance.Contrast(img).enhance(1.025), 256)
    # Ultra keeps modeled gradients/materials and gets a restrained final sharpen.
    img = ImageEnhance.Contrast(img).enhance(1.06)
    return ImageEnhance.Sharpness(img).enhance(1.18)


# 3×5 caps so OMARCHY stays legible on a hardware block, larger than the
# concept-art plate relative to the cube.
_OMARCHY_BITS = {
    "O": ("111", "101", "101", "101", "111"),
    "M": ("101", "111", "101", "101", "101"),
    "A": ("010", "101", "111", "101", "101"),
    "R": ("110", "101", "110", "101", "101"),
    "C": ("111", "100", "100", "100", "111"),
    "H": ("101", "101", "111", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
}

_OMARCHY_MICRO_BITS = {
    "O": ("11", "10", "10", "10", "11"),
    "M": ("11", "11", "11", "10", "10"),
    "A": ("01", "10", "11", "10", "10"),
    "R": ("11", "10", "11", "10", "10"),
    "C": ("11", "10", "10", "10", "11"),
    "H": ("10", "10", "11", "10", "10"),
    "Y": ("10", "10", "01", "01", "01"),
}


def _omarchy_glyph_size(block: int) -> tuple[int, int]:
    if block >= 56:
        return 2, 2
    if block >= 40:
        return 2, 1
    return 1, 1


def blit_omarchy_mark(img: Image.Image, cx: int, cy: int, scale: int, gap: int, color: tuple[int, int, int]) -> None:
    x = cx
    for ch in "OMARCHY":
        bits = _OMARCHY_BITS[ch]
        for row, line in enumerate(bits):
            for col, bit in enumerate(line):
                if bit == "1":
                    _rect(img, x + col * scale, cy + row * scale, scale, scale, color)
        x += 3 * scale + gap


def _apply_micro_omarchy_mark(img: Image.Image) -> None:
    """Re-ink a 14×5 SNES-tier wordmark after reduction from Ultra."""

    if img.width < 16 or img.height < 16:
        return
    x0 = (img.width - 14) // 2
    y0 = (img.height - 7) // 2
    _rect(img, x0 - 1, y0 - 1, 16, 7, (12, 14, 17))
    for letter_index, ch in enumerate("OMARCHY"):
        for row, bits in enumerate(_OMARCHY_MICRO_BITS[ch]):
            for col, bit in enumerate(bits):
                if bit == "1":
                    _px(img, x0 + letter_index * 2 + col, y0 + row, LIME)


def _apply_logo_mask(
    img: Image.Image,
    logo_source: Path,
    bounds: tuple[int, int, int, int],
) -> None:
    """Composite the real OMARCHY wordmark as a bright, scale-safe inlay."""

    if not logo_source.is_file():
        return
    x, y, width, height = bounds
    source = Image.open(logo_source).convert("RGBA")
    alpha = source.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return
    alpha = alpha.crop(bbox)
    scale = min(width / max(1, alpha.width), height / max(1, alpha.height))
    target = (max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale)))
    alpha = alpha.resize(target, Image.Resampling.LANCZOS)
    mark = Image.new("RGBA", target, (*LIME, 0))
    mark.putalpha(alpha)
    img.alpha_composite(mark, (x + (width - target[0]) // 2, y + (height - target[1]) // 2))


def draw_block(size: int = 16, logo_source: Path | None = None) -> Image.Image:
    """Hardware block. `size` is source texels; it is always shown at one tile."""

    img = _new(size, size)
    _rect(img, 0, 0, size, size, BRONZE_DARK)
    _rect(img, 1, 1, size - 2, size - 2, BRONZE)
    bevel = max(1, size // 16)
    _rect(img, 1, 1, size - 2, bevel, BRONZE_LIGHT)
    _rect(img, 1, size - 1 - bevel, size - 2, bevel, (112, 72, 38))
    step = max(2, size // 10)
    for y in range(2, size - 2, step):
        for x in range(2, size - 2, step):
            _px(img, x, y, BRONZE_DARK)
            if x + 1 < size - 2:
                _px(img, x + 1, y, BRONZE_LIGHT)
            _px(img, x, y + 1, BRONZE_DARK)
    if size >= 32:
        draw = ImageDraw.Draw(img)
        inset = max(3, size // 12)
        draw.rounded_rectangle(
            [inset, inset, size - inset - 1, size - inset - 1],
            radius=max(2, size // 14),
            outline=BRONZE_LIGHT,
            width=max(1, size // 32),
        )
        rivet = max(1, size // 24)
        for x, y in ((inset, inset), (size - inset - rivet, inset), (inset, size - inset - rivet), (size - inset - rivet, size - inset - rivet)):
            draw.ellipse([x, y, x + rivet, y + rivet], fill=(238, 196, 132))
    plate_w = max(size - max(2, size // 9), 8)
    plate_h = max(round(size * 0.40), 5)
    px = (size - plate_w) // 2
    py = (size - plate_h) // 2
    _rect(img, px, py, plate_w, plate_h, (12, 12, 16))
    _rect(img, px + 1, py + 1, max(1, plate_w - 2), max(1, plate_h - 2), (24, 24, 30))
    if logo_source is not None and logo_source.is_file():
        _apply_logo_mask(img, logo_source, (px + 2, py + 2, plate_w - 4, plate_h - 4))
    else:
        scale, gap = _omarchy_glyph_size(size)
        while 7 * 3 * scale + 6 * gap > plate_w - 2 and scale > 1:
            scale -= 1
        if 7 * 3 * scale + 6 * max(0, gap - 1) > plate_w - 2:
            gap = 0
        mark_w = 7 * 3 * scale + 6 * gap
        mark_h = 5 * scale
        mx = px + max(0, (plate_w - mark_w) // 2)
        my = py + max(0, (plate_h - mark_h) // 2)
        blit_omarchy_mark(img, mx, my, scale, gap, LIME)
    return img


def draw_parallax_layer(index: int, fidelity: str, palette: str = "corrupted") -> Image.Image:
    """Authored installation scenery, not repeating rectangles."""

    w, h = 640, 180
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    palettes = {
        "corrupted": ((18, 20, 36), (36, 40, 56), (196, 132, 72), (80, 180, 220)),
        "wilderness": ((16, 28, 20), (32, 52, 36), (120, 160, 90), (200, 180, 80)),
        "front": ((28, 16, 20), (60, 28, 32), (200, 80, 90), (220, 180, 80)),
        "garden": ((16, 20, 40), (40, 48, 72), (140, 180, 220), (220, 200, 120)),
        "singularity": ((12, 8, 28), (40, 20, 60), (180, 90, 220), (220, 180, 255)),
        "goliath": ((24, 8, 8), (48, 16, 16), (220, 70, 70), (220, 180, 80)),
        "cow": ((8, 22, 28), (18, 52, 46), (158, 206, 106), (125, 207, 255)),
    }
    far, mid, accent, light = palettes.get(palette, palettes["corrupted"])
    detail = {"sixteen-bit": 0, "high": 1, "ultra": 2}.get(fidelity, 0)
    if index == 0:
        # Distant rack-line / skyline.
        x = 0
        widths = (14, 27, 19, 34, 16, 23, 41, 18, 29)
        gaps = (4, 9, 6, 13, 5, 8, 16, 7, 11)
        heights = (32, 58, 41, 76, 49, 35, 68, 44, 82)
        n = 0
        while x < w:
            ww, ht = widths[n % len(widths)], heights[(n * 5 + index) % len(heights)]
            d.rectangle([x, h - ht, min(w, x + ww), h], fill=(*far, 200))
            if detail and n % 3 == 1:
                d.rectangle([x + ww // 3, h - ht + 7, x + ww // 3 + max(2, ww // 5), h - ht + 11], fill=(*light, 90))
            x += ww + gaps[n % len(gaps)]
            n += 1
        if detail:
            for x, y in ((22, 18), (108, 25), (193, 14), (344, 28), (478, 17), (603, 31)):
                d.ellipse([x, y, x + 2, y + 2], fill=(*light, 70))
    elif index == 1:
        # Server halls and bronze lattice towers.
        towers = ((0, 31, 64), (55, 42, 92), (126, 24, 58), (179, 48, 76), (262, 34, 108), (328, 26, 70), (394, 52, 86), (485, 30, 61), (546, 58, 101), (624, 22, 72))
        for x, ww, ht in towers:
            d.rectangle([x, h - ht, x + ww, h], fill=(*mid, 210))
            d.rectangle([x, h - ht, x + ww, h - ht + 4], fill=(*accent, 180))
            if detail:
                for wy in range(h - ht + 10, h - 8, 13):
                    d.rectangle([x + 4, wy, x + min(11, ww // 2), wy + 4], fill=(*light, 80))
                    if ww > 26:
                        d.rectangle([x + ww - 11, wy, x + ww - 5, wy + 4], fill=(*light, 50))
        for x in (26, 148, 307, 462, 588):
            d.polygon([(x, h - 90), (x + 10, h - 110), (x + 20, h - 90)], fill=(*accent, 90))
    elif index == 2:
        # Cables, pipes, leftover installer chrome.
        cables = ((4, 11, -3, 16), (61, -8, 12, -2), (139, 16, 4, 23), (226, -13, -2, 8), (352, 7, 19, -7), (451, -5, 8, 14), (573, 18, -8, 6), (632, -11, 3, -16))
        for x, a, b, c in cables:
            d.line([(x, 0), (x + a, 40), (x + b, 90), (x + c, h)], fill=(*accent, 70), width=1 + detail)
        for x, y, ww in ((34, 20, 42), (178, 43, 31), (318, 16, 54), (487, 51, 38), (586, 25, 29)):
            d.rectangle([x, y, x + ww, y + 24], fill=(12, 12, 16, 160))
            d.rectangle([x + 2, y + 2, x + ww - 2, y + 22], fill=(*far, 180))
            # mini lime run
            d.rectangle([x + 6, y + 8, x + ww - 6, y + 12], fill=(158, 206, 106, 160))
        if detail >= 1:
            for x, hh in ((82, 29), (271, 44), (429, 34), (612, 51)):
                d.rectangle([x, h - hh, x + 14, h], fill=(*mid, 200))
                d.rectangle([x + 3, h - hh + 6, x + 11, h - 8], fill=(*light, 70))
    else:
        # Ultra near layer: ruined terminals and lattice cubes.
        for x, ww, hh in ((8, 25, 48), (102, 34, 63), (244, 21, 42), (331, 41, 72), (496, 27, 56), (601, 31, 45)):
            d.rectangle([x, h - hh, x + ww, h], fill=(*mid, 230))
            d.rectangle([x + 2, h - hh + 4, x + ww - 2, h - hh + 16], fill=(12, 12, 16, 220))
            d.rectangle([x + 4, h - hh + 8, x + ww - 4, h - hh + 12], fill=(245, 245, 248, 200))
            for n in range(3):
                d.rectangle([x + 4 + n * 5, h - 27, x + 7 + n * 5, h - 16], fill=(*accent, 160))
        d.arc([40, -20, 120, 40], 0, 180, fill=(*accent, 80))

    # Chapter-specific landmarks break the repeating-server-room cadence and
    # give each playfield a recognizable silhouette at every fidelity.
    if palette == "corrupted":
        if index == 0:
            d.polygon([(56, 138), (124, 62), (178, 138)], fill=(*mid, 145))
            d.rectangle([82, 84, 151, 126], fill=(10, 12, 18, 175), outline=(*accent, 150), width=1 + detail)
            d.rectangle([92, 96, 138, 101], fill=(*light, 130))
        elif index >= 2:
            d.arc([390, 34, 570, 212], 195, 342, fill=(*accent, 105), width=2 + detail)
    elif palette == "wilderness":
        if index <= 1:
            for x, y, radius in ((70, 118, 40), (255, 132, 26), (470, 108, 48)):
                d.ellipse([x - radius, y - radius, x + radius, y + radius], fill=(*mid, 115), outline=(*light, 70), width=1 + detail)
                d.rectangle([x - 5, y, x + 6, h], fill=(*far, 190))
        else:
            d.polygon([(310, 162), (354, 100), (402, 162)], fill=(*accent, 80), outline=(*light, 90))
    elif palette == "front":
        if index == 0:
            d.polygon([(0, 160), (84, 122), (152, 148), (238, 104), (330, 152), (430, 116), (540, 150), (640, 108), (640, 180), (0, 180)], fill=(*far, 210))
        elif index >= 1:
            for x, lean in ((74, -12), (286, 14), (512, -8)):
                d.line([(x, h), (x + lean, 58)], fill=(*accent, 180), width=2 + detail)
                d.polygon([(x + lean, 58), (x + lean + 34, 69), (x + lean, 82)], fill=(*light, 135))
    elif palette == "garden":
        if index <= 1:
            for x, width in ((36, 116), (232, 164), (500, 96)):
                d.arc([x, 54, x + width, 206], 180, 360, fill=(*light, 120), width=2 + detail)
                d.line([(x, 130), (x, h)], fill=(*accent, 90), width=1 + detail)
                d.line([(x + width, 130), (x + width, h)], fill=(*accent, 90), width=1 + detail)
        elif index >= 2:
            d.rounded_rectangle([390, 76, 474, 178], radius=34, outline=(*accent, 150), width=3 + detail)
            d.ellipse([426, 122, 436, 132], fill=(*light, 210))
    elif palette == "singularity":
        center = (322, 82)
        for ring in range(1 + index, 5 + index):
            rx, ry = ring * 24, ring * 11
            d.ellipse([center[0] - rx, center[1] - ry, center[0] + rx, center[1] + ry], outline=(*accent, max(25, 125 - ring * 12)), width=1 + (detail if ring % 2 == 0 else 0))
        if index >= 2:
            for x, y in ((48, 46), (154, 112), (468, 58), (582, 126)):
                d.polygon([(x, y - 8), (x + 7, y), (x, y + 8), (x - 7, y)], fill=(*light, 115))
    elif palette == "goliath":
        if index <= 1:
            d.polygon([(176, 180), (206, 58), (236, 22), (266, 180)], fill=(*mid, 185), outline=(*accent, 120))
            d.polygon([(424, 180), (452, 78), (494, 42), (530, 180)], fill=(*far, 215), outline=(*light, 75))
        else:
            for x, y in ((100, 64), (340, 40), (566, 84)):
                d.polygon([(x, y), (x + 26, y - 18), (x + 50, y + 10), (x + 18, y + 34)], fill=(*accent, 70), outline=(*light, 80))
    elif palette == "cow":
        if index <= 1:
            for x, radius in ((82, 42), (286, 31), (512, 48)):
                d.ellipse([x - radius, h - radius, x + radius, h + radius], fill=(*mid, 145), outline=(*light, 90), width=1 + detail)
        else:
            for x in (104, 338, 566):
                d.arc([x, 38, x + 72, 164], 175, 360, fill=(*accent, 135), width=2 + detail)
    scale = {"sixteen-bit": 1, "high": 2, "ultra": 3}.get(fidelity, 1)
    if scale > 1:
        img = img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
        detail_draw = ImageDraw.Draw(img, "RGBA")
        # Fine wires, indicator lamps, and specular edges exist only at the
        # denser tiers, so Ultra retains information High cannot represent.
        for x in range(18 * scale, w * scale, (54 if fidelity == "high" else 34) * scale):
            y = (20 + (x // scale * 11) % 78) * scale
            detail_draw.line(
                [(x, y), (x + 10 * scale, y + 7 * scale)],
                fill=(*light, 70 if fidelity == "high" else 110),
                width=max(1, scale - 1),
            )
            detail_draw.ellipse(
                [x - scale, y - scale, x + scale, y + scale],
                fill=(*accent, 120),
            )
        if fidelity == "ultra" and index < 2:
            img = img.filter(ImageFilter.GaussianBlur(radius=0.35 * (2 - index)))
    return img


def draw_environment_layer(
    index: int,
    palette: str,
    source: Path | None = None,
    authored_plane: Path | None = None,
) -> Image.Image:
    """Build one non-repeating band, preserving authored Ultra art verbatim."""

    if index > 0 and authored_plane is not None and authored_plane.is_file():
        return _key_generated_studio(Image.open(authored_plane))

    width = 1500 - index * 90
    height = 180
    if index == 0 and source is not None and source.is_file():
        return Image.open(source).convert("RGBA")
    if palette == "cow" and index > 0:
        # The complete generated pasture is the opaque base. Near planes are
        # intentionally fine packet/wind accents, not scaled masks cut from
        # that same image; large geometric masks obscured characters and read
        # as foreground rectangles once rasterized at Ultra density.
        accent = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(accent, "RGBA")
        if index == 1:
            for x in range(42, width, 137):
                y = 28 + (x * 17) % 72
                draw.line((x, y, x + 7, y - 2), fill=(125, 207, 255, 58), width=1)
        elif index == 2:
            for x in range(70, width, 181):
                y = 116 + (x * 11) % 34
                draw.ellipse((x, y, x + 2, y + 2), fill=(158, 206, 106, 68))
                draw.ellipse((x + 19, y - 7, x + 20, y - 6), fill=(232, 176, 64, 54))
        else:
            for x in (96, 448, 820, 1168):
                draw.arc((x, 78, x + 176, 166), 194, 338, fill=(185, 232, 214, 46), width=1)
                draw.arc((x + 20, 88, x + 190, 172), 194, 334, fill=(125, 207, 255, 38), width=1)
        return accent
    layer = draw_parallax_layer(index, "ultra", palette)
    layer = layer.resize((width, height), Image.Resampling.LANCZOS)
    if source is None or not source.is_file():
        return layer
    # Use the authored layer only as a unique silhouette/material mask. Each
    # plane samples a different vertical band of the chapter's Ultra master,
    # so near structures inherit original stone, foliage, glass, and metal
    # detail without repeating the full background bitmap.
    centering_y = {1: 0.38, 2: 0.62, 3: 0.80}.get(index, 0.5)
    texture = ImageOps.fit(
        Image.open(source).convert("RGB"),
        (width, height),
        Image.Resampling.LANCZOS,
        centering=(0.5, centering_y),
    ).convert("RGBA")
    alpha = np.array(layer.getchannel("A"), dtype=np.uint16)
    # Empty space remains transparent, but authored structures are materially
    # opaque. The prior blanket 40–60% alpha made every plane look like a
    # ghosted duplicate even when transparency served no visual purpose.
    material_alpha = np.where(alpha >= 24, 255, np.minimum(255, alpha * 10)).astype(np.uint8)
    texture.putalpha(Image.fromarray(material_alpha, "L"))
    structure = layer.copy()
    structure.putalpha(Image.fromarray((alpha * 2 // 5).astype(np.uint8), "L"))
    return Image.alpha_composite(texture, structure)


def _key_generated_studio(img: Image.Image) -> Image.Image:
    """Recover alpha from generated black, white, or checker studio plates.

    Image generation preserves the modeled scene faithfully but can flatten a
    requested transparent backdrop.  The backdrop is deliberately neutral and
    dominates the top border; chapter art is colored and materially darker.
    Keeping this cleanup in the deterministic bake means the checked-in source
    remains untouched while every runtime tier receives identical cutout edges.
    """

    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3].astype(np.int16)
    top = rgb[: max(2, img.height // 24), :, :].reshape(-1, 3)
    edge = np.concatenate(
        (
            rgb[:8].reshape(-1, 3),
            rgb[-8:].reshape(-1, 3),
            rgb[:, :8].reshape(-1, 3),
            rgb[:, -8:].reshape(-1, 3),
        )
    )
    top_spread = top.max(axis=1) - top.min(axis=1)
    edge_spread = edge.max(axis=1) - edge.min(axis=1)
    neutral_ratio = max(float(np.mean(top_spread < 26)), float(np.mean(edge_spread < 26)))
    top_neutral = top[top_spread < 26]
    edge_neutral = edge[edge_spread < 26]
    levels = [
        float(np.median(sample.mean(axis=1)))
        for sample in (top_neutral, edge_neutral)
        if sample.size
    ]
    # Some near planes intentionally hang foliage/cables from the top edge.
    # The brighter neutral border sample still identifies their light studio
    # plate, while genuinely black stages remain near zero on every edge.
    level = max(levels, default=0.0)
    full_spread = rgb.max(axis=2) - rgb.min(axis=2)
    if neutral_ratio < 0.45:
        return Image.fromarray(arr, "RGBA")
    if level < 70:
        # Dark plates surround equally dark modeled material, so no broad color
        # key can separate them safely. Build alpha from color/luma signal above
        # the sampled plate instead: checker squares and neutral haze disappear,
        # while blue, green, violet, and red structure survives without holes.
        neutral_samples = np.concatenate((top_neutral, edge_neutral))
        values = np.clip(np.rint(neutral_samples.mean(axis=1)), 0, 255).astype(np.uint8)
        plate_high = float(np.quantile(values, 0.75)) if values.size else level
        luma_floor = 4 if level < 15 else 22
        luma_signal = rgb.max(axis=2).astype(np.float32) - plate_high - luma_floor
        chroma_signal = (full_spread.astype(np.float32) - 3.0) * 2.0
        signal = np.maximum(luma_signal, chroma_signal)
        recovered_alpha = np.clip(signal * 32.0, 0, 255).astype(np.uint8)
        arr[:, :, 3] = np.minimum(arr[:, :, 3], recovered_alpha)
        return Image.fromarray(arr, "RGBA")
    if level >= 115:
        # White and light checker plates.  Both checker values satisfy this
        # broad neutral mask, so they remain one connected visual background.
        light_floor = max(82, round(level - 62))
        studio = (full_spread < 34) & (rgb.min(axis=2) > light_floor)
        fringe_limit = max(66, light_floor - 28)
        neutral_samples = np.concatenate((top_neutral, edge_neutral))
        values = np.clip(np.rint(neutral_samples.mean(axis=1)), 0, 255).astype(np.uint8)
        histogram = np.bincount(values, minlength=256)
        plate_modes = np.argsort(histogram)[-8:].astype(np.int16)
        gray = np.rint(rgb.mean(axis=2)).astype(np.int16)
        plate_distance = np.min(np.abs(gray[:, :, None] - plate_modes), axis=2)
        # Enclosed windows and archways do not connect to the image edge. Key
        # exact studio swatches globally so checker squares cannot survive in
        # those openings; the broader threshold remains edge-connected and
        # therefore preserves light stone and metal.
        enclosed_plate = (full_spread < 18) & (plate_distance <= 4)
    else:
        # Black or charcoal checker plates.  Restrict the initial removal to
        # nearly neutral pixels so violet haze and colored machine shadows stay.
        studio = (full_spread < 18) & (rgb.max(axis=2) < min(92, max(24, level + 34)))
        fringe_limit = min(118, max(42, round(level + 54)))
    # A color test alone removes neutral stone, fog, metal, and concrete inside
    # the illustration. Treat only studio-colored pixels connected to an image
    # edge as backdrop. ``fromarray`` can retain a read-only shared buffer, so
    # floodfill receives an owned writable image.
    studio_mask = Image.fromarray(np.where(studio, 255, 0).astype(np.uint8), "L").copy()
    studio_pixels = studio_mask.load()
    edge_seeds = (
        [(x, 0) for x in range(img.width)]
        + [(x, img.height - 1) for x in range(img.width)]
        + [(0, y) for y in range(1, img.height - 1)]
        + [(img.width - 1, y) for y in range(1, img.height - 1)]
    )
    for seed in edge_seeds:
        if studio_pixels[seed] == 255:
            ImageDraw.floodfill(studio_mask, seed, 128, thresh=0)
    connected_studio = np.asarray(studio_mask) == 128
    if level >= 115:
        connected_studio |= enclosed_plate
    alpha = np.where(connected_studio, 0, arr[:, :, 3]).astype(np.uint8)
    # Peel only the neutral antialias fringe touching the cleared plate.  This
    # prevents white/checker halos without globally deleting metal highlights.
    for _ in range(4):
        transparent = alpha == 0
        near = transparent.copy()
        near[1:, :] |= transparent[:-1, :]
        near[:-1, :] |= transparent[1:, :]
        near[:, 1:] |= transparent[:, :-1]
        near[:, :-1] |= transparent[:, 1:]
        if level >= 115:
            fringe = (full_spread < 38) & (rgb.min(axis=2) > fringe_limit)
        else:
            fringe = (full_spread < 26) & (rgb.max(axis=2) < fringe_limit)
        alpha = np.where(near & fringe, 0, alpha).astype(np.uint8)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def _resize_rgba_premultiplied(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize a cutout without pulling its neutral studio matte into the edge."""

    return img.convert("RGBa").resize(size, Image.Resampling.LANCZOS).convert("RGBA")


def _contain_cutout(
    img: Image.Image,
    size: tuple[int, int],
    *,
    occupancy: tuple[float, float] = (0.92, 0.90),
    bottom_align: bool = False,
    edge_fade: float = 0.0,
) -> Image.Image:
    """Contain one keyed plate with transparent safety margins on every edge."""

    keyed = _key_generated_studio(img.convert("RGBA"))
    bounds = keyed.getchannel("A").getbbox()
    if bounds:
        keyed = keyed.crop(bounds)
    max_w = max(1, round(size[0] * occupancy[0]))
    max_h = max(1, round(size[1] * occupancy[1]))
    scale = min(max_w / max(1, keyed.width), max_h / max(1, keyed.height))
    cutout = _resize_rgba_premultiplied(
        keyed,
        (max(1, round(keyed.width * scale)), max(1, round(keyed.height * scale))),
    )
    if edge_fade > 0:
        arr = np.array(cutout, dtype=np.uint8)
        alpha = arr[:, :, 3].astype(np.float32)
        fade_x = max(2, round(cutout.width * edge_fade))
        fade_y = max(2, round(cutout.height * edge_fade))
        horizontal = np.ones(cutout.width, dtype=np.float32)
        horizontal[:fade_x] = np.linspace(0.0, 1.0, fade_x)
        horizontal[-fade_x:] = np.minimum(horizontal[-fade_x:], np.linspace(1.0, 0.0, fade_x))
        vertical = np.ones(cutout.height, dtype=np.float32)
        vertical[:fade_y] = np.linspace(0.0, 1.0, fade_y)
        alpha *= vertical[:, None] * horizontal[None, :]
        arr[:, :, 3] = np.rint(alpha).astype(np.uint8)
        cutout = Image.fromarray(arr, "RGBA")
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - cutout.width) // 2
    y = size[1] - cutout.height - max(1, round(size[1] * 0.025)) if bottom_align else (size[1] - cutout.height) // 2
    canvas.alpha_composite(cutout, (x, y))
    return canvas


def _layout_authored_parallax(
    master: Image.Image,
    canvas_size: tuple[int, int],
    index: int,
) -> Image.Image:
    """Place a complete authored plane once on a long, smooth-scrolling strip.

    Earlier bakes cut every master into thirds. Even with feathering, those
    internal cuts read as seams and reduced modeled detail. A depth plane is
    now indivisible: far/mid/near assets are each used once and only their
    exterior alpha boundary is softened into the empty strip.
    """

    canvas_w, canvas_h = canvas_size
    fitted_w = max(canvas_w + 1, round(master.width * canvas_h / max(1, master.height)))
    fitted = _resize_rgba_premultiplied(master, (fitted_w, canvas_h))
    if index == 0:
        return fitted

    # Downsampling intricate cutouts can turn one-pixel modeled details into a
    # field of nearly transparent matte specks. Keep a narrow antialias band,
    # discard sub-visible residue, and restore materially solid pixels.
    fitted_alpha = np.asarray(fitted.getchannel("A")).copy()
    fitted_alpha = np.where(fitted_alpha < 48, 0, fitted_alpha)
    fitted_alpha = np.where(fitted_alpha >= 144, 255, fitted_alpha).astype(np.uint8)
    fitted.putalpha(Image.fromarray(fitted_alpha, "L"))

    strip_w = max(canvas_w + 1, round((1500 - index * 90) * canvas_h / 180))
    strip = Image.new("RGBA", (strip_w, canvas_h), (0, 0, 0, 0))
    anchors = {1: 0.0, 2: 0.5, 3: 1.0}
    anchor = anchors.get(index, 0.5)
    x = round((strip_w - fitted.width) * anchor)
    x = max(0, min(strip_w - fitted.width, x))

    alpha = np.asarray(fitted.getchannel("A"), dtype=np.float32).copy()
    edge = min(max(2, round(canvas_h / 60)), max(1, fitted.width // 12))
    if x > 0:
        alpha[:, :edge] *= np.linspace(0.0, 1.0, edge, dtype=np.float32)
    if x + fitted.width < strip_w:
        alpha[:, -edge:] *= np.linspace(1.0, 0.0, edge, dtype=np.float32)
    fitted.putalpha(Image.fromarray(np.clip(alpha, 0, 255).astype(np.uint8), "L"))
    strip.alpha_composite(fitted, (x, 0))
    return strip


def draw_penguin(size: int = 16) -> Image.Image:
    img = _new(size, size)
    s = max(1, size // 16)
    _rect(img, 4 * s, 3 * s, 8 * s, 11 * s, PENGUIN_BLACK)
    _rect(img, 6 * s, 6 * s, 5 * s, 7 * s, PENGUIN_WHITE)
    _rect(img, 6 * s, 4 * s, 2 * s, 2 * s, EYE)
    _rect(img, 9 * s, 5 * s, 3 * s, 2 * s, PENGUIN_GOLD)
    _rect(img, 4 * s, 13 * s, 3 * s, 2 * s, PENGUIN_GOLD)
    _rect(img, 10 * s, 13 * s, 3 * s, 2 * s, PENGUIN_GOLD)
    return img


def draw_tile(kind: str, size: int = 16, palette: str = "corrupted") -> Image.Image:
    if kind == "+":
        # A deck remains solid while the ladder stays visible and mountable.
        # Draw the platform behind the rails so the crossing reads immediately.
        return Image.alpha_composite(draw_tile("=", size, palette), draw_tile("L", size, palette))
    img = _new(size, size)
    palettes = {
        "corrupted": ((36, 40, 56), (24, 26, 36), BRONZE),
        "wilderness": ((42, 64, 48), (24, 40, 32), (120, 160, 90)),
        "front": ((60, 40, 48), (32, 20, 28), (200, 80, 90)),
        "garden": ((40, 48, 72), (22, 26, 40), (140, 180, 220)),
        "singularity": ((28, 24, 48), (12, 10, 24), (180, 90, 220)),
        "goliath": ((48, 24, 24), (20, 8, 8), (220, 70, 70)),
        "cow": ((28, 62, 48), (10, 28, 25), (158, 206, 106)),
    }
    ground, dark, accent = palettes.get(palette, palettes["corrupted"])
    draw = ImageDraw.Draw(img, "RGBA")
    hi = tuple(min(255, c + 42) for c in ground)
    shadow = tuple(max(0, c - 18) for c in dark)
    if kind == "#":
        for y in range(size):
            t = y / max(1, size - 1)
            color = tuple(round(ground[i] * (1.0 - t * 0.28) + shadow[i] * t * 0.28) for i in range(3))
            draw.line([(0, y), (size - 1, y)], fill=(*color, 255))
        mortar = max(1, size // 24)
        rows = max(2, size // 8)
        brick_h = max(3, size // rows)
        for y in range(brick_h, size, brick_h):
            draw.line([(0, y), (size - 1, y)], fill=(*dark, 210), width=mortar)
        brick_w = max(6, size // 3)
        for row, y in enumerate(range(0, size, brick_h)):
            offset = brick_w // 2 if row % 2 else 0
            for x in range(offset, size, brick_w):
                draw.line([(x, y), (x, min(size - 1, y + brick_h))], fill=(*dark, 190), width=mortar)
        draw.line([(0, 0), (size - 1, 0)], fill=(*accent, 255), width=max(2, size // 12))
        if size >= 32:
            draw.line([(0, max(2, size // 12)), (size - 1, max(2, size // 12))], fill=(*hi, 120), width=max(1, size // 32))
            for x in range(size // 8, size, max(5, size // 5)):
                y = size // 3 + (x * 7) % max(3, size // 2)
                draw.line([(x, y), (min(size - 1, x + size // 10), max(0, y - size // 12))], fill=(*accent, 95), width=max(1, size // 32))
    elif kind == "=":
        lip = max(3, size // 4)
        draw.rounded_rectangle([0, 0, size - 1, lip], radius=max(1, size // 14), fill=(*accent, 255))
        draw.line([(1, 1), (size - 2, 1)], fill=(*hi, 210), width=max(1, size // 24))
        draw.rectangle([size // 8, lip, size - size // 8, size - 1], fill=(*dark, 255))
        draw.rectangle([size // 4, lip, size // 4 + max(1, size // 16), size - 1], fill=(*accent, 150))
        draw.rectangle([size - size // 4, lip, size - size // 4 + max(1, size // 16), size - 1], fill=(*accent, 110))
    elif kind == "L":
        rail = max(2, size // 7)
        left = max(1, size // 8)
        right = size - left - rail
        draw.rounded_rectangle([left, 0, left + rail, size], radius=max(1, rail // 2), fill=(*BRONZE, 255), outline=(*BRONZE_LIGHT, 255))
        draw.rounded_rectangle([right, 0, right + rail, size], radius=max(1, rail // 2), fill=(*BRONZE, 255), outline=(*BRONZE_LIGHT, 255))
        rung = max(2, size // 10)
        for y in range(rung, size, max(4, size // 4)):
            draw.rounded_rectangle([left, y, right + rail, min(size - 1, y + rung)], radius=max(1, rung // 2), fill=(*BRONZE_LIGHT, 255))
            if size >= 32:
                draw.line([(left + rail, y + 1), (right, y + 1)], fill=(255, 220, 160, 180), width=max(1, size // 32))
    elif kind == "^":
        pad = max(2, size // 10)
        draw.rounded_rectangle([pad, size // 2, size - pad, size - pad], radius=max(1, size // 8), fill=(*dark, 255), outline=(*BRONZE, 255), width=max(1, size // 20))
        draw.polygon(
            [(size // 2, pad), (size - pad * 2, size // 2 + pad), (size // 2 + size // 10, size // 2 + pad), (size // 2 + size // 10, size - pad * 2), (size // 2 - size // 10, size - pad * 2), (size // 2 - size // 10, size // 2 + pad), (pad * 2, size // 2 + pad)],
            fill=(*LIME, 255),
        )
        if size >= 32:
            draw.line([(size // 2, pad * 2), (size // 2, size - pad * 2)], fill=(232, 255, 190, 210), width=max(1, size // 24))
    elif kind == "G":
        rail = max(2, size // 8)
        draw.rounded_rectangle([1, 0, size - 2, size - 1], radius=max(2, size // 10), fill=(*BRONZE_DARK, 255), outline=(*BRONZE_LIGHT, 255), width=max(1, size // 18))
        draw.rounded_rectangle([rail, rail, size - rail - 1, size - rail - 1], radius=max(1, size // 14), fill=(12, 12, 18, 255), outline=(*BRONZE, 255), width=max(1, size // 22))
        for x in range(rail * 2, size - rail, max(3, size // 5)):
            draw.line([(x, rail), (x, size - rail)], fill=(*accent, 210), width=max(1, size // 24))
        draw.ellipse([size // 2, size // 2, size // 2 + max(1, size // 12), size // 2 + max(1, size // 12)], fill=(*LIME, 255))
    elif kind == "D":
        # Optional kick-break masonry: visibly cracked and strapped, never
        # confused with traversal-critical ground.
        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=max(1, size // 16), fill=(*ground, 255), outline=(*BRONZE_LIGHT, 255), width=max(1, size // 18))
        strap = max(2, size // 8)
        draw.rectangle([0, size // 2 - strap // 2, size - 1, size // 2 + strap // 2], fill=(*BRONZE_DARK, 225))
        crack = max(1, size // 28)
        draw.line([(size // 2, 2), (size // 2 - size // 8, size // 3), (size // 2 + size // 10, size // 2), (size // 3, size - 2)], fill=(12, 12, 18, 255), width=crack)
        draw.line([(size // 2 + size // 10, size // 2), (size - size // 5, size // 3)], fill=(12, 12, 18, 230), width=crack)
        draw.ellipse([size // 2 - strap, size // 2 - strap, size // 2 + strap, size // 2 + strap], fill=(*accent, 245), outline=(*LIME, 230), width=max(1, size // 24))
    else:
        pass
    return img


def draw_ultra_material_tile(
    kind: str,
    size: int,
    palette: str,
    source: Path | None,
    material_source: Path | None = None,
    structural_sources: dict[str, Path] | None = None,
) -> Image.Image:
    """Compose a structural tile from a purpose-built Ultra source.

    The legacy material-mask path remains as a source-only fallback, but the
    production build supplies explicit ground, deck, ladder, breakable, and
    gate masters.  Crossings are composed from the same deck and ladder, so
    their traversal and visual seams stay coherent.
    """

    if structural_sources:
        if kind == "+":
            deck = draw_ultra_material_tile(
                "=", size, palette, source, material_source, structural_sources
            )
            ladder = draw_ultra_material_tile(
                "L", size, palette, source, material_source, structural_sources
            )
            return Image.alpha_composite(deck, ladder)
        authored = structural_sources.get(kind)
        if authored is not None and authored.is_file():
            return _prepare_ultra_structure(authored, kind, size, palette)

    base = draw_tile(kind, size, palette).convert("RGBA")
    seed = sum(ord(ch) for ch in f"{palette}:{kind}")
    textured = base
    if material_source is not None and material_source.is_file():
        material = Image.open(material_source).convert("RGB")
        crop_w = max(1, material.width // 4)
        crop_h = max(1, material.height // 4)
        mx = (seed * 37) % max(1, material.width - crop_w)
        my = (seed * 53) % max(1, material.height - crop_h)
        material = ImageOps.fit(
            material.crop((mx, my, mx + crop_w, my + crop_h)),
            (size, size),
            Image.Resampling.LANCZOS,
        ).convert("RGBA")
        textured = Image.blend(base, material, 0.38)
        textured.putalpha(base.getchannel("A"))
    if source is None or not source.is_file():
        return textured
    scene = Image.open(source).convert("RGB")
    # Different palette/kind combinations select different non-repeating source
    # regions; the structural mask still controls gameplay readability.
    crop_w = max(1, scene.width // 5)
    crop_h = max(1, scene.height // 3)
    x0 = seed % max(1, scene.width - crop_w)
    y0 = scene.height - crop_h - (seed % max(1, scene.height // 5))
    texture = scene.crop((x0, max(0, y0), x0 + crop_w, max(0, y0) + crop_h))
    texture = ImageOps.fit(texture, (size, size), Image.Resampling.LANCZOS).convert("RGBA")
    textured = Image.blend(textured, texture, 0.24 if kind in {"#", "=", "D"} else 0.12)
    textured.putalpha(base.getchannel("A"))
    structure = base.copy()
    structure.putalpha(base.getchannel("A").point(lambda a: a // 2))
    return Image.alpha_composite(textured, structure)


_ULTRA_TILE_ACCENTS = {
    "corrupted": (158, 206, 106),
    "wilderness": (126, 188, 92),
    "front": (62, 194, 228),
    "garden": (132, 204, 232),
    "singularity": (190, 92, 236),
    "goliath": (238, 72, 58),
    "cow": (158, 206, 106),
}


def _prepare_ultra_structure(source: Path, kind: str, size: int, palette: str) -> Image.Image:
    """Fit one generated structural master without changing its world footprint."""

    raw = Image.open(source).convert("RGBA")
    pixels = np.array(raw)
    # Generated alpha often contains a very faint studio-light veil.  Clear it
    # before reduction so it cannot become a dark rectangle around ladders and
    # decks; retain antialiased modeled edges above the conservative threshold.
    pixels[:, :, 3] = np.where(pixels[:, :, 3] < 36, 0, pixels[:, :, 3]).astype(np.uint8)
    raw = Image.fromarray(pixels, "RGBA")

    if kind == "#":
        art = ImageOps.fit(raw, (size, size), Image.Resampling.LANCZOS)
        art.putalpha(Image.new("L", art.size, 255))
    elif kind == "=":
        # The source is a long modular deck.  One central manufactured bay is
        # the repeat cell; using the entire strip would miniaturize six bays in
        # every 16-world-pixel tile and destroy the modeled detail.
        x0 = round(raw.width * 0.415)
        x1 = round(raw.width * 0.585)
        module = raw.crop((x0, 0, max(x0 + 1, x1), raw.height))
        bbox = module.getchannel("A").getbbox()
        module = module.crop(bbox) if bbox else module
        target_h = max(1, round(size * 0.82))
        scale = min(size / max(1, module.width), target_h / max(1, module.height))
        module = _resize_rgba_premultiplied(
            module,
            (max(1, round(module.width * scale)), max(1, round(module.height * scale))),
        )
        art = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        art.alpha_composite(module, ((size - module.width) // 2, 0))
    elif kind == "L":
        bbox = raw.getchannel("A").getbbox()
        ladder = raw.crop(bbox) if bbox else raw
        # A ladder is a continuous traversal surface: fill almost the full
        # tile width, then crop a repeating vertical section to the cell.
        scale = (size * 0.90) / max(1, ladder.width)
        ladder = _resize_rgba_premultiplied(
            ladder,
            (max(1, round(ladder.width * scale)), max(1, round(ladder.height * scale))),
        )
        if ladder.height < size:
            grow = size / max(1, ladder.height)
            ladder = _resize_rgba_premultiplied(
                ladder,
                (max(1, round(ladder.width * grow)), size),
            )
        crop_y = max(0, (ladder.height - size) // 2)
        ladder = ladder.crop((0, crop_y, ladder.width, crop_y + size))
        art = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        art.alpha_composite(ladder, ((size - ladder.width) // 2, (size - ladder.height) // 2))
    else:
        art = ImageOps.fit(raw, (size, size), Image.Resampling.LANCZOS)

    arr = np.array(art.convert("RGBA"))
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    energy = (g > 82) & (g * 100 > r * 118) & (g * 100 > b * 112) & (arr[:, :, 3] > 0)
    accent = _ULTRA_TILE_ACCENTS.get(palette, _ULTRA_TILE_ACCENTS["corrupted"])
    brightness = np.maximum.reduce((r, g, b)).astype(np.float32) / 255.0
    for channel, value in enumerate(accent):
        arr[:, :, channel] = np.where(
            energy,
            np.clip(value * (0.48 + brightness * 0.72), 0, 255),
            arr[:, :, channel],
        ).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def draw_boss(boss_id: str, size: int = 32) -> Image.Image:
    img = _new(size, size)
    s = max(1, size // 32)
    if boss_id == "package-bureaucrat":
        # Khaki clerk: round glasses, stamp, paper stack. Not a rectangle.
        khaki, khaki_d = (186, 168, 104), (118, 96, 58)
        paper = (236, 230, 214)
        ink = (36, 32, 28)
        _rect(img, 10 * s, 18 * s, 14 * s, 12 * s, khaki)  # torso
        _rect(img, 8 * s, 20 * s, 4 * s, 10 * s, khaki_d)  # arm
        _rect(img, 22 * s, 20 * s, 6 * s, 5 * s, paper)  # papers
        _rect(img, 24 * s, 18 * s, 4 * s, 3 * s, (180, 60, 60))  # stamp
        _rect(img, 10 * s, 8 * s, 12 * s, 10 * s, SKIN)  # head
        _rect(img, 10 * s, 6 * s, 12 * s, 3 * s, (48, 42, 38))  # hair
        _rect(img, 12 * s, 12 * s, 3 * s, 3 * s, ink)  # glasses L
        _rect(img, 18 * s, 12 * s, 3 * s, 3 * s, ink)
        _rect(img, 15 * s, 13 * s, 3 * s, 1 * s, ink)
        _rect(img, 14 * s, 16 * s, 4 * s, 2 * s, BEARD)
        return img
    if boss_id == "dogma-sprite":
        body = (168, 72, 88)
        _rect(img, 12 * s, 10 * s, 8 * s, 14 * s, body)
        _rect(img, 10 * s, 6 * s, 12 * s, 8 * s, body)
        _rect(img, 12 * s, 8 * s, 3 * s, 3 * s, (20, 20, 24))
        _rect(img, 19 * s, 8 * s, 3 * s, 3 * s, (20, 20, 24))
        _rect(img, 14 * s, 14 * s, 4 * s, 2 * s, (236, 220, 180))
        _rect(img, 22 * s, 4 * s, 8 * s, 6 * s, (236, 240, 248))  # "NO" bubble
        _rect(img, 24 * s, 6 * s, 2 * s, 3 * s, body)
        _rect(img, 27 * s, 6 * s, 2 * s, 3 * s, body)
        return img
    colors = {
        "dependency-hydra": (80, 180, 120),
        "distro-commander": (200, 80, 80),
        "garden-gatekeeper": (120, 170, 230),
        "singularity": (160, 80, 220),
        "goliath": (220, 70, 70),
    }
    fill = colors.get(boss_id, (160, 160, 160))
    if boss_id == "dependency-hydra":
        _rect(img, 8 * s, 14 * s, 16 * s, 14 * s, fill)
        _rect(img, 2 * s, 2 * s, 8 * s, 16 * s, fill)
        _rect(img, 12 * s, 0 * s, 8 * s, 16 * s, fill)
        _rect(img, 22 * s, 2 * s, 8 * s, 16 * s, fill)
        for hx in (4, 14, 24):
            _rect(img, hx * s, 6 * s, 3 * s, 3 * s, (20, 20, 24))
        return img
    if boss_id == "distro-commander":
        _rect(img, 8 * s, 12 * s, 16 * s, 16 * s, fill)
        _rect(img, 10 * s, 4 * s, 12 * s, 10 * s, SKIN)
        _rect(img, 6 * s, 2 * s, 20 * s, 4 * s, (40, 40, 80))  # beret
        _rect(img, 12 * s, 8 * s, 3 * s, 3 * s, (20, 20, 24))
        _rect(img, 18 * s, 8 * s, 3 * s, 3 * s, (20, 20, 24))
        _rect(img, 4 * s, 16 * s, 4 * s, 12 * s, (200, 180, 80))  # banner
        return img
    if boss_id == "garden-gatekeeper":
        _rect(img, 10 * s, 14 * s, 12 * s, 14 * s, fill)
        _rect(img, 8 * s, 4 * s, 16 * s, 12 * s, SKIN)
        _rect(img, 6 * s, 2 * s, 20 * s, 6 * s, (80, 140, 200))
        _rect(img, 12 * s, 8 * s, 3 * s, 3 * s, (20, 20, 24))
        _rect(img, 18 * s, 8 * s, 3 * s, 3 * s, (20, 20, 24))
        _rect(img, 14 * s, 18 * s, 4 * s, 8 * s, (220, 200, 120))  # key
        return img
    if boss_id == "singularity":
        _rect(img, 8 * s, 8 * s, 16 * s, 16 * s, fill)
        _rect(img, 12 * s, 12 * s, 8 * s, 8 * s, (12, 8, 24))
        _rect(img, 14 * s, 14 * s, 4 * s, 4 * s, (220, 180, 255))
        return img
    if boss_id == "goliath":
        _rect(img, 4 * s, 6 * s, 24 * s, 22 * s, fill)
        _rect(img, 0 * s, 10 * s, 32 * s, 4 * s, (12, 12, 16))
        _rect(img, 8 * s, 12 * s, 4 * s, 4 * s, (20, 20, 24))
        _rect(img, 20 * s, 12 * s, 4 * s, 4 * s, (20, 20, 24))
        _rect(img, 10 * s, 22 * s, 12 * s, 4 * s, BRONZE)
        return img
    _rect(img, 8 * s, 8 * s, 16 * s, 16 * s, fill)
    return img


def draw_logo_pickup(size: int = 16) -> Image.Image:
    img = _new(size, size)
    draw = ImageDraw.Draw(img, "RGBA")
    pad = max(1, size // 10)
    draw.rounded_rectangle([pad, pad * 2, size - pad - 1, size - pad * 2 - 1], radius=max(1, size // 7), fill=(10, 12, 18, 255), outline=(*BRONZE, 255), width=max(1, size // 18))
    draw.rounded_rectangle([pad * 2, pad * 3, size - pad * 2 - 1, size - pad * 3 - 1], radius=max(1, size // 10), fill=(*LIME, 255))
    draw.line([(pad * 3, size // 2), (size - pad * 3, size // 2)], fill=(232, 255, 200, 230), width=max(1, size // 14))
    if size >= 32:
        draw.ellipse([size // 2 - 2, size // 2 - 2, size // 2 + 2, size // 2 + 2], fill=(255, 255, 255, 230))
    return img


def draw_logic_bomb(size: int = 16) -> Image.Image:
    img = _new(size, size)
    draw = ImageDraw.Draw(img, "RGBA")
    pad = max(2, size // 7)
    draw.ellipse([pad, pad + size // 8, size - pad - 1, size - pad - 1], fill=(40, 98, 130, 255), outline=(125, 207, 255, 255), width=max(1, size // 18))
    draw.arc([pad + size // 5, 0, size - pad, size // 2], 190, 300, fill=(*BRONZE_LIGHT, 255), width=max(1, size // 14))
    spark = max(1, size // 12)
    cx, cy = size - pad, pad
    draw.line([(cx - spark * 2, cy), (cx + spark, cy)], fill=(*LIME, 255), width=spark)
    draw.line([(cx, cy - spark * 2), (cx, cy + spark)], fill=(*LIME, 255), width=spark)
    if size >= 32:
        draw.ellipse([pad + size // 6, pad + size // 4, pad + size // 3, pad + size // 2], fill=(210, 240, 255, 160))
        for offset in range(-1, 2):
            draw.line([(size // 2 + offset * size // 8, size // 2), (size // 2, size - pad * 2)], fill=(158, 206, 106, 150), width=max(1, size // 28))
    return img


def draw_item(item: str, size: int = 16) -> Image.Image:
    """Compact, silhouette-first inventory art for every side-view tool."""

    if item == "logic-bomb":
        return draw_logic_bomb(size)
    img = _new(size, size)
    d = ImageDraw.Draw(img, "RGBA")
    p = max(1, size // 8)
    line = max(1, size // 14)
    if item == "patch-cable":
        d.arc([p, p, size - p, size - p], 35, 330, fill=(125, 207, 255, 255), width=line * 2)
        d.rounded_rectangle([p, size // 2 - line, p * 3, size // 2 + line * 2], radius=line, fill=(*BRONZE_LIGHT, 255))
        d.rounded_rectangle([size - p * 3, p, size - p, p * 3], radius=line, fill=(*LIME, 255))
    elif item == "manifest":
        d.rounded_rectangle([p * 2, p, size - p * 2, size - p], radius=line, fill=(228, 230, 222, 255), outline=(*BRONZE, 255), width=line)
        for y in range(p * 3, size - p * 2, max(2, p * 2)):
            d.line([(p * 3, y), (size - p * 3, y)], fill=(60, 70, 90, 255), width=line)
        d.polygon([(size - p * 4, p), (size - p * 2, p), (size - p * 2, p * 3)], fill=(125, 207, 255, 255))
    elif item == "penguin-flock":
        # The fallback is a flock-control beacon, never a lone low-detail
        # penguin that could be mistaken for the ordinary penguin pickup.
        d.rounded_rectangle([p * 2, size // 2, size - p * 2, size - p], radius=line, fill=(*BRONZE_DARK, 255), outline=(*BRONZE_LIGHT, 255), width=line)
        d.line([(size // 2, size // 2), (size // 2, p * 2)], fill=(125, 207, 255, 255), width=line)
        for cx, cy in ((p * 2, p * 2), (size // 2, p), (size - p * 2, p * 2)):
            d.ellipse([cx - p, cy - p, cx + p, cy + p], fill=(28, 38, 52, 255), outline=(*LIME, 255), width=line)
    elif item == "fork-beacon":
        d.line([(size // 2, size - p), (size // 2, p * 3)], fill=(*BRONZE_LIGHT, 255), width=line * 2)
        d.line([(size // 2, p * 4), (p * 2, p)], fill=(*LIME, 255), width=line * 2)
        d.line([(size // 2, p * 4), (size - p * 2, p)], fill=(125, 207, 255, 255), width=line * 2)
        d.ellipse([size // 2 - p, size - p * 3, size // 2 + p, size - p], fill=(*BRONZE, 255))
    elif item == "checksum-key":
        d.ellipse([p, p, size // 2 + p, size // 2 + p], outline=(*LIME, 255), width=line * 2)
        d.line([(size // 2, size // 2), (size - p, size - p)], fill=(*BRONZE_LIGHT, 255), width=line * 2)
        d.line([(size - p * 3, size - p * 3), (size - p * 3, size - p)], fill=(*BRONZE_LIGHT, 255), width=line)
    elif item == "mirror-cache":
        d.polygon([(size // 2, p), (size - p, size // 2), (size // 2, size - p), (p, size // 2)], fill=(28, 42, 68, 255), outline=(125, 207, 255, 255))
        d.polygon([(size // 2, p * 2), (size - p * 2, size // 2), (size // 2, size // 2)], fill=(220, 240, 255, 190))
        d.line([(p * 2, size // 2), (size // 2, size - p * 2)], fill=(173, 142, 230, 255), width=line)
    elif item == "touch-grass-usb":
        # A tiny patch of aggressively literal portable nature. The broad USB
        # silhouette survives the derived 16-bit tier; Ultra keeps individual
        # blades, connector pins, soil, and the absurd status light.
        d.rounded_rectangle(
            [p * 2, size // 2 - p, size - p * 2, size - p],
            radius=max(1, p),
            fill=(24, 34, 30, 255),
            outline=(*BRONZE_LIGHT, 255),
            width=line,
        )
        d.rectangle([size - p * 3, size // 2, size - p, size - p * 2], fill=(184, 190, 184, 255), outline=(48, 54, 58, 255), width=line)
        for pin_y in (size // 2 + p // 2, size - p * 2 - p // 2):
            d.line([(size - p * 2, pin_y), (size - p, pin_y)], fill=(*BRONZE, 255), width=line)
        d.ellipse([p * 3, size - p * 3, p * 4, size - p * 2], fill=(125, 207, 255, 255))
        soil_y = size // 2 + p
        d.rounded_rectangle([p * 2, soil_y, size - p * 4, size - p], radius=max(1, line), fill=(82, 54, 32, 255))
        for base_x, lean in ((p * 3, -p), (size // 2, 0), (size - p * 5, p)):
            d.line([(base_x, soil_y), (base_x + lean, p)], fill=(*LIME, 255), width=max(1, line * 2))
            d.line([(base_x, soil_y), (base_x + p, p * 2)], fill=(92, 178, 86, 255), width=line)
    return img


def draw_ui_panel(w: int = 160, h: int = 48) -> Image.Image:
    img = Image.new("RGBA", (w, h), (10, 12, 20, 238))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=max(2, h // 10), outline=LIME, width=max(1, h // 32))
    draw.rounded_rectangle([3, 3, w - 4, h - 4], radius=max(1, h // 12), outline=BRONZE, width=max(1, h // 40))
    draw.line([(8, 7), (w - 9, 7)], fill=(*BRONZE_LIGHT, 110), width=max(1, h // 40))
    return img


def emit_official_wordmark(root: Path) -> None:
    """Rasterize the vendored Omarchy-family marks in the game theme color."""

    source = root / "source" / "branding" / "omarchy-logo-official.png"
    if not source.is_file():
        return
    logo = Image.open(source).convert("RGBA")
    alpha = logo.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        logo = logo.crop(bbox)
        alpha = logo.getchannel("A")
    colored = Image.new("RGBA", logo.size, (*LIME, 0))
    colored.putalpha(alpha)
    colored.thumbnail((196, 46), Image.Resampling.LANCZOS)
    colored.save(root / "ui" / "omarchy-wordmark.png")
    colored.save(root / "ui" / "omarchy-logo-hud.png")

    # The post-event brand uses oligarchy.fyi's actual block geometry, not a
    # typeface approximation. Preserve the alpha shape and apply game color.
    oligarchy_source = root / "source" / "branding" / "oligarchy-logo-official.png"
    if oligarchy_source.is_file():
        oligarchy = Image.open(oligarchy_source).convert("RGBA")
        alpha = oligarchy.getchannel("A")
        bbox = alpha.getbbox()
        if bbox:
            alpha = alpha.crop(bbox)
        oligarchy = Image.new("RGBA", alpha.size, (*LIME, 0))
        oligarchy.putalpha(alpha)
        oligarchy.thumbnail((260, 52), Image.Resampling.LANCZOS)
        oligarchy.save(root / "ui" / "oligarchy-logo-hud.png")


def emit_app_icons(root: Path) -> None:
    """Derive mask-safe runtime icons from the selected brand master."""

    source = root / "source" / "branding" / "omega-omarchy-logo-powered-artifact.png"
    if not source.is_file():
        return
    master = Image.open(source).convert("RGBA")
    bbox = master.getchannel("A").getbbox()
    if bbox:
        master = master.crop(bbox)
    for size in (32, 64, 128, 256, 512):
        safe_extent = round(size * 0.88)
        icon = master.copy()
        icon.thumbnail((safe_extent, safe_extent), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.alpha_composite(
            icon,
            ((size - icon.width) // 2, (size - icon.height) // 2),
        )
        canvas.save(root / "ui" / f"omega-omarchy-icon-{size}.png")
        if size == 256:
            canvas.save(root / "ui" / "omega-omarchy-icon.png")


def draw_exit_sign(size: tuple[int, int]) -> Image.Image:
    """North-American building-code EXIT: dark housing, red face, white copy."""

    width, height = size
    canvas = _new(width, height)
    draw = ImageDraw.Draw(canvas)
    inset = max(1, height // 7)
    draw.rounded_rectangle(
        [0, 0, width - 1, height - 1],
        radius=max(1, height // 8),
        fill=(36, 28, 24, 255),
        outline=(196, 158, 92, 255),
        width=max(1, height // 10),
    )
    draw.rounded_rectangle(
        [inset, inset, width - 1 - inset, height - 1 - inset],
        radius=max(1, height // 10),
        fill=(168, 22, 24, 255),
    )
    lamp = max(1, height // 7)
    for cx in (inset + lamp, width - inset - lamp - 1):
        draw.ellipse(
            [cx, inset + 1, cx + lamp, inset + 1 + lamp],
            fill=(255, 236, 170, 255),
        )
    font = _sign_font(max(8, height - inset * 2 - lamp))
    draw.text(
        (width // 2, height // 2 + max(0, lamp // 3)),
        "EXIT",
        font=font,
        fill=(255, 244, 232, 255),
        anchor="mm",
    )
    return canvas


def _sign_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSansCondensed-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _official_logo_strip(source: Path, size: tuple[int, int]) -> Image.Image:
    if not source.is_file():
        fallback = Image.new("RGBA", size, (0, 0, 0, 0))
        blit_omarchy_mark(fallback, 1, max(0, size[1] // 3), 1, 0, LIME)
        return fallback
    logo = Image.open(source).convert("RGBA")
    bbox = logo.getchannel("A").getbbox()
    if bbox:
        logo = logo.crop(bbox)
    colored = Image.new("RGBA", logo.size, (*LIME, 0))
    colored.putalpha(logo.getchannel("A"))
    colored.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(colored, ((size[0] - colored.width) // 2, (size[1] - colored.height) // 2))
    return canvas


def _compose_enemy_sign(
    art: Image.Image,
    enemy_id: str,
    *,
    converted: bool,
    logo_source: Path,
) -> Image.Image:
    """Composite exact small-sign copy after generation, before tier reduction."""

    if enemy_id == "justice-signaler" and not converted:
        return art
    if enemy_id not in {"justice-signaler", "detractabot"}:
        return art
    if enemy_id == "justice-signaler":
        # The source placard is nearly half the sprite height. Cover its full
        # face so no fragment of the old JUSTICE line survives below FREEDOM.
        panel_size = (238, 118)
        panel = Image.new("RGBA", panel_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(panel)
        draw.rounded_rectangle((1, 1, panel_size[0] - 2, panel_size[1] - 2), radius=8, fill=(182, 236, 104, 255), outline=(18, 26, 24, 255), width=5)
        draw.text((panel_size[0] // 2, 15), "LINUX", font=_sign_font(33), fill=(12, 18, 20, 255), anchor="mt")
        draw.text((panel_size[0] // 2, 57), "FREEDOM", font=_sign_font(31), fill=(12, 18, 20, 255), anchor="mt")
        panel = panel.rotate(-5, Image.Resampling.BICUBIC, expand=True)
        at = ((art.width - panel.width) // 2, -12)
    else:
        # Detractabot's generated placard is a dominant prop; use nearly its
        # full face so the official mark and punch line remain legible after
        # reduction to the 28px SNES floor.
        panel_size = (222, 92)
        panel = Image.new("RGBA", panel_size, (18, 19, 24, 252))
        draw = ImageDraw.Draw(panel)
        draw.rounded_rectangle((1, 1, panel_size[0] - 2, panel_size[1] - 2), radius=8, outline=(214, 156, 62, 255), width=4)
        logo = _official_logo_strip(logo_source, (204, 34))
        panel.alpha_composite(logo, (9, 6))
        copy = "4 LIFE" if converted else "SUCKS"
        draw.text((panel_size[0] // 2, 48), copy, font=_sign_font(32), fill=(232, 240, 244, 255), anchor="mt")
        panel = panel.rotate(-7, Image.Resampling.BICUBIC, expand=True)
        at = ((art.width - panel.width) // 2, 0)
    out = art.copy().convert("RGBA")
    out.alpha_composite(panel, at)
    return out


def _green_detractabot_hair(art: Image.Image) -> Image.Image:
    arr = np.array(art.convert("RGBA"))
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    purple = (r > 80) & (b > 105) & (r > g * 1.35) & (b > g * 1.45) & (arr[:, :, 3] > 0)
    light = np.maximum(r, b)
    arr[purple, 0] = np.clip(light[purple] * 0.42, 45, 130).astype(np.uint8)
    arr[purple, 1] = np.clip(light[purple] * 1.08, 145, 255).astype(np.uint8)
    arr[purple, 2] = np.clip(light[purple] * 0.34, 32, 110).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _tone(freq: float, seconds: float, volume: float = 0.18, sr: int = 22050, square: bool = True) -> np.ndarray:
    n = int(sr * seconds)
    sample = np.arange(n, dtype=np.int64)
    frequency_millihertz = int(round(freq * 1000))
    phase_period = sr * 1000
    phase = (sample * frequency_millihertz) % phase_period
    if square:
        doubled = phase * 2
        wave_q15 = np.where(
            (doubled == 0) | (doubled == phase_period),
            0,
            np.where(doubled < phase_period, 32767, -32767),
        ).astype(np.int64)
    else:
        # A four-segment integer triangle keeps the softer effect timbre without
        # relying on platform libm implementations for sine values.
        phase4 = phase * 4
        wave_q15 = np.select(
            (phase4 < phase_period, phase4 < 2 * phase_period, phase4 < 3 * phase_period),
            (
                phase4 * 32767 // phase_period,
                (2 * phase_period - phase4) * 32767 // phase_period,
                -(phase4 - 2 * phase_period) * 32767 // phase_period,
            ),
            default=-(4 * phase_period - phase4) * 32767 // phase_period,
        ).astype(np.int64)
    denominator = max(1, n - 1)
    linear_q15 = (n - 1 - sample) * 32767 // denominator
    squared_q15 = linear_q15 * linear_q15 // 32767
    envelope_q15 = (3 * linear_q15 + 2 * squared_q15) // 5
    volume_q15 = int(round(volume * 32767))
    pcm = wave_q15 * envelope_q15 // 32767
    pcm = pcm * volume_q15 // 32767
    return pcm.astype(np.int32)


def write_wav(path: Path, samples: np.ndarray, sr: int = 22050) -> None:
    data = np.clip(samples, -32767, 32767).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sr)
        handle.writeframes(data.tobytes())


def build_audio(root: Path) -> None:
    # Keep the tiny integer helpers above for their focused determinism tests,
    # but route production assets through the authored master/tier pipeline.
    from .audio_build import build_audio_assets

    build_audio_assets(root)


def emit_fidelity_art(root: Path) -> None:
    """Bake every lower tier from common Ultra composition masters."""

    from . import spritekit
    from .presentation import (
        BLOCK_ART_SIZE,
        FIDELITIES,
        PARALLAX_LAYERS,
        SPRITE_SIZE,
        TILE_ART_SIZE,
        canvas_size,
        view_scale,
    )

    src_dir = spritekit.session_images()
    fid_root = root / "fidelity"
    penguin_src = src_dir / "penguin.jpg"
    ground_src = src_dir / "corrupted-ground.jpg"
    environment_sources = {
        "corrupted": src_dir / "omega-ultra-environment-install-chamber.png",
        "wilderness": src_dir / "omega-ultra-environment-wilderness.png",
        "front": src_dir / "omega-ultra-environment-hardware.png",
        "garden": src_dir / "omega-ultra-environment-garden.png",
        "singularity": src_dir / "omega-ultra-environment-singularity.png",
        "goliath": src_dir / "omega-ultra-environment-goliath.png",
        "cow": src_dir / "omega-ultra-environment-cow-level-v1.png",
    }
    foreground_sources = {
        "front": tuple(
            src_dir
            / f"omega-ultra-overlay-hardware-plane-{index}-{'v3' if index == 4 else 'v2'}.png"
            for index in range(1, 5)
        ),
    }
    structural_sources = {
        "#": src_dir / "omega-ultra-tile-solid-v3.png",
        "=": src_dir / "omega-ultra-tile-platform-v3.png",
        "L": src_dir / "omega-ultra-tile-ladder-v3.png",
        "D": src_dir / "omega-ultra-tile-breakable-v3.png",
        "G": src_dir / "omega-ultra-tile-gate-v4.png",
    }
    parallax_sources = {
        palette: tuple(
            src_dir
            / (
                f"omega-ultra-parallax-garden-{depth}-{'v5' if depth == 'far' else 'v4'}.png"
                if palette == "garden"
                else f"omega-ultra-parallax-cow-{depth}-v4.png"
                if palette == "cow"
                else f"omega-ultra-parallax-front-{depth}-{'v4' if depth == 'near' else 'v3'}.png"
                if palette == "front"
                else f"omega-ultra-parallax-{palette}-{depth}-v3.png"
            )
            for depth in ("far", "mid", "near")
        )
        for palette in ("corrupted", "wilderness", "front", "garden", "singularity", "goliath", "cow")
    }
    corruption_effect_source = src_dir / "omega-ultra-corruption-red-code.png"
    wind_effect_source = src_dir / "omega-ultra-wind-gust.png"
    network_sources = {
        protocol: src_dir / f"omega-ultra-network-{protocol}-v1.png"
        for protocol in ("ethernet", "wifi")
    }
    network_overlay_sources = {
        protocol: src_dir
        / f"omega-ultra-network-{protocol}-overlay-{'v3' if protocol == 'wifi' else 'v2'}.png"
        for protocol in ("ethernet", "wifi")
    }
    prologue_sources = {
        "prologue-campus": src_dir / "omega-ultra-prologue-campus-v1.png",
        "prologue-transfer": src_dir / "omega-ultra-prologue-transfer-v2.png",
        "prologue-rift": src_dir / "omega-ultra-prologue-rift-v1.png",
        "stage-world-map": src_dir / "omega-ultra-stage-world-map-v1.png",
    }
    prologue_pose_sources = {
        "prologue-captured": src_dir / "david-ultra-prologue-captured-pose-v1.png",
        "prologue-transfer": src_dir / "david-ultra-prologue-transfer-pose-v1.png",
    }
    prologue_pose_masters = {
        name: spritekit.crop_subject(_key_generated_studio(Image.open(source).convert("RGBA")), pad=6)
        for name, source in prologue_pose_sources.items()
        if source.is_file()
    }
    secret_door_source = src_dir / "omega-ultra-secret-door-v1.png"
    cow_cannon_source = src_dir / "omega-ultra-cow-cannon-v1.png"
    cow_cannon_barrel_source = src_dir / "omega-ultra-cow-cannon-barrel-v2.png"
    cow_cannon_base_source = src_dir / "omega-ultra-cow-cannon-base-v2.png"
    ui_frame_src = src_dir / "omega-ultra-ui-frame.png"
    boss_sources = {
        "package-bureaucrat": src_dir / "package-bureaucrat.jpg",
        "dogma-sprite": src_dir / "dogma-sprite.jpg",
        "dependency-hydra": src_dir / "dependency-hydra.png",
        "distro-commander": src_dir / "distro-commander.png",
        "garden-gatekeeper": src_dir / "garden-gatekeeper.png",
        "singularity": src_dir / "singularity.png",
        "goliath": src_dir / "goliath.png",
        "goliath-cyborg-penguin": src_dir / "goliath-cyborg-penguin-ultra.png",
    }
    ultra_boss_sources = {
        "package-bureaucrat": src_dir / "package-bureaucrat-ultra.png",
        "dogma-sprite": src_dir / "dogma-sprite-ultra.png",
    }
    item_sources = {
        item: src_dir / f"item-{item}-ultra.png"
        for item in ("logic-bomb", "patch-cable", "manifest", "penguin-flock", "fork-beacon", "checksum-key", "mirror-cache", "touch-grass-usb")
    }
    bouncer_source = src_dir / "bouncer-ultra.png"
    for fid in FIDELITIES:
        size = SPRITE_SIZE[fid]
        characters = fid_root / fid / "characters"
        items = fid_root / fid / "items"
        enemies = fid_root / fid / "enemies"
        bosses = fid_root / fid / "bosses"
        tiles = fid_root / fid / "tiles"
        bg = fid_root / fid / "bg"
        effects = fid_root / fid / "effects"
        tier_ui = fid_root / fid / "ui"
        for folder in (characters, items, enemies, bosses, tiles, bg, effects, tier_ui):
            folder.mkdir(parents=True, exist_ok=True)
        poses = {
            "sixteen-bit": {
                "idle": src_dir / "david-ultra-idle.jpg",
                "walk-a": src_dir / "david-ultra-walk-contact-a-v5.png",
                "walk-pass-a": src_dir / "david-ultra-walk-passing-a-v5.png",
                "walk-b": src_dir / "david-ultra-walk-contact-b-v5.png",
                "walk-pass-b": src_dir / "david-ultra-walk-passing-b-v5.png",
                "jump": src_dir / "david-ultra-jump.jpg",
                "climb": src_dir / "david-ultra-climb.jpg",
                "air-action": src_dir / "david-high-jump.jpg",
                "action": src_dir / "david-ultra-kick.png",
                "throw": src_dir / "david-ultra-throw.png",
                "slide": src_dir / "david-ultra-slide-v2.png",
                "away": src_dir / "david-ultra-away.png",
                "portrait": src_dir / "david-ultra-portrait.jpg",
            },
            "high": {
                "idle": src_dir / "david-ultra-idle.jpg",
                "walk-a": src_dir / "david-ultra-walk-contact-a-v5.png",
                "walk-pass-a": src_dir / "david-ultra-walk-passing-a-v5.png",
                "walk-b": src_dir / "david-ultra-walk-contact-b-v5.png",
                "walk-pass-b": src_dir / "david-ultra-walk-passing-b-v5.png",
                "jump": src_dir / "david-ultra-jump.jpg",
                "climb": src_dir / "david-ultra-climb.jpg",
                "air-action": src_dir / "david-high-jump.jpg",
                "action": src_dir / "david-ultra-kick.png",
                "throw": src_dir / "david-ultra-throw.png",
                "slide": src_dir / "david-ultra-slide-v2.png",
                "away": src_dir / "david-ultra-away.png",
                "portrait": src_dir / "david-ultra-portrait.jpg",
            },
            "ultra": {
                "idle": src_dir / "david-ultra-idle.jpg",
                "walk-a": src_dir / "david-ultra-walk-contact-a-v5.png",
                "walk-pass-a": src_dir / "david-ultra-walk-passing-a-v5.png",
                "walk-b": src_dir / "david-ultra-walk-contact-b-v5.png",
                "walk-pass-b": src_dir / "david-ultra-walk-passing-b-v5.png",
                "jump": src_dir / "david-ultra-jump.jpg",
                "climb": src_dir / "david-ultra-climb.jpg",
                "air-action": src_dir / "david-high-jump.jpg",
                "action": src_dir / "david-ultra-kick.png",
                "throw": src_dir / "david-ultra-throw.png",
                "slide": src_dir / "david-ultra-slide-v2.png",
                "away": src_dir / "david-ultra-away.png",
                "portrait": src_dir / "david-ultra-portrait.jpg",
            },
        }.get(fid, {})
        idle_src = poses.get("idle")
        if idle_src.is_file():
            idle = spritekit.ingest_file(idle_src, characters / "david_side-idle.png", size, nes=False)
            idle = spritekit.decontaminate_magenta(idle, passes=5)
        else:
            idle = _david_side(2 if fid == "sixteen-bit" else 3, "side-idle").resize(size, Image.Resampling.LANCZOS)
            idle.save(characters / "david_side-idle.png")

        def _pose(key: str, fallback: Image.Image) -> Image.Image:
            src = poses.get(key)
            if src is not None and src.is_file():
                return spritekit.decontaminate_magenta(spritekit.prepare_file(src, size, nes=False), passes=5)
            return fallback

        walk_a = _pose("walk-a", spritekit.walk_frame(idle, 0))
        walk_pass_a = _pose("walk-pass-a", spritekit.walk_passing_frame(walk_a, 0))
        walk_b = _pose("walk-b", spritekit.walk_frame(idle, 2))
        walk_pass_b = _pose("walk-pass-b", spritekit.walk_passing_frame(walk_b, 1))
        jump = _pose("jump", spritekit.jump_frame(idle))
        climb = _pose("climb", idle)
        air_action = _pose("air-action", jump)
        action = _pose("action", walk_a)
        throw = _pose("throw", air_action)
        slide = _pose("slide", spritekit.fall_frame(spritekit.land_frame(walk_a)))
        away = _pose("away", climb)
        frames = {
            "side-idle": idle,
            "side-walk-0": walk_a,
            "side-walk-1": walk_pass_a,
            "side-walk-2": walk_b,
            "side-walk-3": walk_pass_b,
            "side-jump": jump,
            "side-fall": spritekit.fall_frame(jump),
            "side-land": spritekit.land_frame(jump),
            "side-crouch": spritekit.land_frame(idle),
            "side-slide": slide,
            "side-climb-0": spritekit.climb_frame(climb, 0),
            "side-climb-1": spritekit.climb_frame(climb, 1),
            "side-climb-2": spritekit.climb_frame(climb, 2),
            "side-climb-3": spritekit.climb_frame(climb, 3),
            "side-action": action,
            "side-air-action": air_action,
            "battle": idle,
            "side-hurt": spritekit.fall_frame(idle),
            "side-bomb": throw,
        }
        for name, frame_img in frames.items():
            frame_img = _fidelity_finish(frame_img, fid)
            frame_img.save(characters / f"david_{name}.png")
            tinted = frame_img.copy()
            arr = np.array(tinted)
            mask = (arr[:, :, 0] < 40) & (arr[:, :, 1] < 40) & (arr[:, :, 2] < 50) & (arr[:, :, 3] > 0)
            arr[mask, 1] = np.minimum(180, arr[mask, 1] + 80)
            Image.fromarray(arr).save(characters / f"custom_{name}.png")
        vs = view_scale(fid)
        prologue_pose_sizes = {
            "prologue-captured": (48 * vs, 54 * vs),
            "prologue-transfer": (84 * vs, 58 * vs),
        }
        for name, master in prologue_pose_masters.items():
            pose = spritekit.fit_scaled(master, prologue_pose_sizes[name], anchor_y="center")
            _fidelity_finish(pose, fid).save(characters / f"david_{name}.png")
        ots_size = {"sixteen-bit": (80, 96), "high": (160, 192), "ultra": (240, 288)}[fid]
        away = _fidelity_finish(away, fid)
        away.save(characters / "david_away.png")
        ots = spritekit.ots_from_back(away, ots_size)
        ots.save(characters / "david_ots.png")
        arr = np.array(ots)
        mask = (arr[:, :, 0] < 40) & (arr[:, :, 1] < 40) & (arr[:, :, 2] < 50) & (arr[:, :, 3] > 0)
        arr[mask, 1] = np.minimum(180, arr[mask, 1] + 80)
        Image.fromarray(arr).save(characters / "custom_ots.png")
        fl_size = (size[0] + 8, size[1] + 8)
        flight = spritekit.fit_scaled(spritekit.crop_subject(away), fl_size)
        flight.save(characters / "david_flight.png")
        flight.save(characters / "custom_flight.png")
        port = {"sixteen-bit": 48, "high": 64, "ultra": 96}[fid]
        port_src = poses.get("portrait")
        if port_src is not None and port_src.is_file():
            portrait = spritekit.portrait_from_source(port_src, (port, port), zoom=1.34)
        else:
            portrait = _david_portrait(max(1, port // 32)).resize((port, port), Image.Resampling.LANCZOS)
        portrait = _fidelity_finish(portrait, fid)
        portrait.save(characters / "david_portrait.png")
        portrait.save(characters / "david_turn.png")

        tile_px = TILE_ART_SIZE[fid]
        for pal in ("corrupted", "wilderness", "front", "garden", "singularity", "goliath", "cow"):
            for kind in ("#", "=", "L", "+", "^", "D", "G"):
                if kind == "^" and bouncer_source.is_file():
                    master = spritekit.prepare_file(bouncer_source, (128, 128), nes=False)
                else:
                    master = draw_ultra_material_tile(
                        kind,
                        128,
                        pal,
                        environment_sources.get(pal),
                        None,
                        structural_sources,
                    )
                tier_tile = master.resize((tile_px, tile_px), Image.Resampling.LANCZOS)
                _fidelity_finish(tier_tile, fid).save(tiles / f"{pal}_{kind}.png")

        tier_penguin = src_dir / "penguin-ultra.png" if (src_dir / "penguin-ultra.png").is_file() else penguin_src
        if tier_penguin.is_file():
            penguin = spritekit.prepare_file(tier_penguin, (tile_px, tile_px), nes=False)
            _fidelity_finish(penguin, fid).save(items / "penguin.png")
        else:
            draw_penguin(tile_px).save(items / "penguin.png")
        logo_source = root / "source" / "branding" / "omarchy-logo-official.png"
        block_master = draw_block(128, logo_source)
        solid_source = structural_sources["#"]
        if solid_source.is_file():
            block_texture = _prepare_ultra_structure(solid_source, "#", 128, "corrupted")
            alpha = block_master.getchannel("A")
            block_master = Image.blend(block_texture, block_master, 0.42)
            block_master.putalpha(alpha)
            # Material blending must not wash the identity back out. Reapply
            # the official geometry as the final luminous faceplate inlay.
            plate_w = 128 - max(2, 128 // 9)
            plate_h = round(128 * 0.40)
            plate_x = (128 - plate_w) // 2
            plate_y = (128 - plate_h) // 2
            draw = ImageDraw.Draw(block_master)
            draw.rounded_rectangle(
                [plate_x, plate_y, plate_x + plate_w - 1, plate_y + plate_h - 1],
                radius=5,
                fill=(18, 20, 24, 255),
                outline=BRONZE_LIGHT,
                width=2,
            )
            _apply_logo_mask(
                block_master,
                logo_source,
                (plate_x + 4, plate_y + 5, plate_w - 8, plate_h - 10),
            )
        tier_block = _fidelity_finish(
            block_master.resize((BLOCK_ART_SIZE[fid], BLOCK_ART_SIZE[fid]), Image.Resampling.LANCZOS),
            fid,
        )
        if fid == "sixteen-bit":
            _apply_micro_omarchy_mark(tier_block)
        tier_block.save(items / "block.png")
        logo_master = draw_logo_pickup(64)
        _fidelity_finish(logo_master.resize((tile_px, tile_px), Image.Resampling.LANCZOS), fid).save(items / "omarchy-logo.png")
        for item_name in ("logic-bomb", "patch-cable", "manifest", "penguin-flock", "fork-beacon", "checksum-key", "mirror-cache", "touch-grass-usb"):
            source = item_sources[item_name]
            if source.is_file():
                if item_name == "patch-cable":
                    keyed = spritekit.chroma_key(Image.open(source))
                    keyed = spritekit.clear_neutral_holes(keyed, ((0.5, 0.39),))
                    item_master = spritekit.fit_scaled(spritekit.crop_subject(keyed), (tile_px, tile_px), anchor_y="center")
                else:
                    item_master = spritekit.prepare_file(source, (tile_px, tile_px), nes=False)
            else:
                item_master = draw_item(item_name, tile_px)
            _fidelity_finish(item_master, fid).save(items / f"{item_name}.png")
        shoe_src = poses.get("walk-a")
        if shoe_src is not None and shoe_src.is_file():
            shoe_subject = spritekit.crop_subject(spritekit.chroma_key(Image.open(shoe_src)), pad=2)
            shoe_crop = shoe_subject.crop((shoe_subject.width // 2, int(shoe_subject.height * 0.62), shoe_subject.width, shoe_subject.height))
            shoe = spritekit.fit_scaled(shoe_crop, (tile_px, tile_px), anchor_y="center")
        else:
            shoe = draw_item("checksum-key", tile_px)
        _fidelity_finish(shoe, fid).save(items / "kick.png")
        if secret_door_source.is_file():
            door_size = {
                "sixteen-bit": (32, 48),
                "high": (64, 96),
                "ultra": (128, 192),
            }[fid]
            door = spritekit.prepare_file(secret_door_source, door_size, nes=False)
            _fidelity_finish(door, fid).save(items / "omega-door.png")
        if cow_cannon_source.is_file():
            cannon_master = spritekit.crop_subject(
                _key_generated_studio(Image.open(cow_cannon_source).convert("RGBA")),
                pad=4,
            )
            cannon_size = (152 * vs, 96 * vs)
            cannon = spritekit.fit_scaled(cannon_master, cannon_size, anchor_y="center")
            _fidelity_finish(cannon, fid).save(items / "cow-cannon.png")
        for source, filename, logical_size in (
            (cow_cannon_barrel_source, "cow-cannon-barrel.png", (152, 76)),
            (cow_cannon_base_source, "cow-cannon-base.png", (92, 76)),
        ):
            if not source.is_file():
                continue
            master = spritekit.crop_subject(
                _key_generated_studio(Image.open(source).convert("RGBA")),
                pad=4,
            )
            part = spritekit.fit_scaled(
                master,
                (logical_size[0] * vs, logical_size[1] * vs),
                anchor_y="center",
            )
            _fidelity_finish(part, fid).save(items / filename)

        if ui_frame_src.is_file():
            frame_master = Image.open(ui_frame_src).convert("RGBA")
            panel_size = (300 * {"sixteen-bit": 1, "high": 2, "ultra": 3}[fid], 146 * {"sixteen-bit": 1, "high": 2, "ultra": 3}[fid])
            panel = frame_master.resize(panel_size, Image.Resampling.LANCZOS)
            _fidelity_finish(panel, fid).save(tier_ui / "panel.png")

        boss_size = {"sixteen-bit": 48, "high": 72, "ultra": 128}[fid]
        for boss_id, source in boss_sources.items():
            dest = bosses / f"{boss_id}.png"
            target = boss_size // 2 + 8 if boss_id == "dogma-sprite" else boss_size
            source = ultra_boss_sources.get(boss_id, source) if fid == "ultra" else source
            if source.is_file():
                art = spritekit.prepare_file(source, (target, target), nes=False)
                art = _fidelity_finish(art, fid)
            else:
                art = draw_boss(boss_id, target)
            art.save(dest)
            converted = np.array(art.convert("RGBA"))
            opaque = converted[:, :, 3] > 0
            converted[opaque, 1] = np.minimum(255, converted[opaque, 1].astype(np.int16) + (72 if boss_id == "dogma-sprite" else 44))
            converted[opaque, 0] = np.maximum(0, converted[opaque, 0].astype(np.int16) - 12)
            Image.fromarray(converted.astype(np.uint8), "RGBA").save(bosses / f"{boss_id}-converted.png")

        enemy_sources = {
            enemy_id: src_dir / f"enemy-{enemy_id}-ultra.png"
            for enemy_id in (
                "cache-gremlin",
                "packet-wasp",
                "lint-launcher",
                "garden-glitch",
                "void-orbiter",
                "justice-signaler",
                "consensus-crier",
                "detractabot",
                "cow",
                "llama",
            )
        }
        enemy_sources["cow"] = src_dir / "enemy-cow-ultra-v1.png"
        enemy_sources["llama"] = src_dir / "enemy-llama-ultra-v1.png"
        enemy_size = {"sixteen-bit": 28, "high": 48, "ultra": 80}[fid]
        for enemy_id, source in enemy_sources.items():
            if source.is_file() and enemy_id in {"justice-signaler", "detractabot"}:
                master = spritekit.prepare_file(source, (240, 240), nes=False)
                art = _compose_enemy_sign(
                    master,
                    enemy_id,
                    converted=False,
                    logo_source=root / "source" / "branding" / "omarchy-logo-official.png",
                ).resize((enemy_size, enemy_size), Image.Resampling.LANCZOS)
            else:
                art = (
                    spritekit.prepare_file(source, (enemy_size, enemy_size), nes=False)
                    if source.is_file()
                    else draw_boss("dogma-sprite", enemy_size)
                )
            art = _fidelity_finish(art, fid)
            arr = np.array(art.convert("RGBA"))
            opaque = arr[:, :, 3] > 0
            art = Image.fromarray(arr.astype(np.uint8), "RGBA")
            art.save(enemies / f"{enemy_id}.png")
            if enemy_id in {"justice-signaler", "detractabot"} and source.is_file():
                converted_master = spritekit.prepare_file(source, (240, 240), nes=False)
                if enemy_id == "detractabot":
                    converted_master = _green_detractabot_hair(converted_master)
                converted_art = _compose_enemy_sign(
                    converted_master,
                    enemy_id,
                    converted=True,
                    logo_source=root / "source" / "branding" / "omarchy-logo-official.png",
                ).resize((enemy_size, enemy_size), Image.Resampling.LANCZOS)
                _fidelity_finish(converted_art, fid).save(enemies / f"{enemy_id}-converted.png")
            elif enemy_id in {"cow", "llama"}:
                # The Cow Level animals become allies without the universal
                # green conversion tint; their behavior and HUD treatment are
                # enough to communicate recruitment without recoloring them.
                art.save(enemies / f"{enemy_id}-converted.png")
            else:
                converted = np.array(art)
                converted[opaque, 1] = np.minimum(255, converted[opaque, 1].astype(np.int16) + 70)
                Image.fromarray(converted.astype(np.uint8), "RGBA").save(enemies / f"{enemy_id}-converted.png")

        layers = PARALLAX_LAYERS[fid]
        for pal in ("corrupted", "wilderness", "front", "garden", "singularity", "goliath", "cow"):
            pal_dir = bg / pal
            pal_dir.mkdir(parents=True, exist_ok=True)
            for i in range(layers):
                authored = parallax_sources.get(pal, ())
                authored_plane = authored[i - 1] if 0 < i <= len(authored) else None
                master = draw_environment_layer(i, pal, environment_sources.get(pal), authored_plane)
                layer = _layout_authored_parallax(master, canvas_size(fid), i)
                if fid != "ultra":
                    layer = _fidelity_finish(layer, fid)
                layer.save(pal_dir / f"parallax-{i}.png")
            foreground_set = foreground_sources.get(pal) or ()
            for foreground_index, foreground_source in enumerate(foreground_set, start=1):
                if not foreground_source.is_file():
                    continue
                foreground = _contain_cutout(
                    Image.open(foreground_source).convert("RGBA"),
                    canvas_size(fid),
                    occupancy=(0.94, 0.94),
                    bottom_align=True,
                    edge_fade=0.045,
                )
                if fid != "ultra":
                    foreground = _fidelity_finish(foreground, fid)
                foreground.save(pal_dir / f"foreground-{foreground_index}.png")
                if foreground_index == 1:
                    # Compatibility alias for older bundles and screenshots.
                    foreground.save(pal_dir / "foreground.png")

        for protocol, source in network_sources.items():
            if not source.is_file():
                continue
            transition = ImageOps.fit(
                Image.open(source).convert("RGBA"),
                canvas_size(fid),
                Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            if fid != "ultra":
                transition = _fidelity_finish(transition, fid)
            transition.save(tier_ui / f"network-{protocol}.png")
            overlay_source = network_overlay_sources.get(protocol)
            if overlay_source is not None and overlay_source.is_file():
                overlay = _contain_cutout(
                    Image.open(overlay_source).convert("RGBA"),
                    canvas_size(fid),
                    occupancy=(0.90, 0.84),
                )
                if fid != "ultra":
                    overlay = _fidelity_finish(overlay, fid)
                overlay.save(tier_ui / f"network-{protocol}-overlay.png")
        for name, source in prologue_sources.items():
            if not source.is_file():
                continue
            backdrop = ImageOps.fit(
                Image.open(source).convert("RGBA"),
                canvas_size(fid),
                Image.Resampling.LANCZOS,
            )
            if fid != "ultra":
                backdrop = _fidelity_finish(backdrop, fid)
            backdrop.save(tier_ui / f"{name}.png")

        divisor = {"sixteen-bit": 4, "high": 2, "ultra": 1}[fid]
        if corruption_effect_source.is_file():
            corruption = Image.open(corruption_effect_source).convert("RGBA")
            effect_size = 256 // divisor
            corruption = ImageOps.fit(
                corruption,
                (effect_size, effect_size),
                Image.Resampling.LANCZOS,
            )
            _fidelity_finish(corruption, fid).save(effects / "corruption-code.png")
        if wind_effect_source.is_file():
            wind = spritekit.crop_subject(Image.open(wind_effect_source).convert("RGBA"), pad=0)
            wind_master = ImageOps.fit(
                wind,
                (256, 768),
                Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            wind_tier = wind_master.resize(
                (256 // divisor, 768 // divisor),
                Image.Resampling.LANCZOS,
            )
            _fidelity_finish(wind_tier, fid).save(effects / "wind-column.png")


def sync_legacy_art(root: Path) -> None:
    """Refresh compatibility filenames from the new authored fidelity assets.

    Old saves still mention 8-bit/clean-pixel/CRT presets. Presentation migration
    maps them to the sixteen-bit floor, and these aliases ensure even a renderer
    fallback never exposes the retired placeholder sprites.
    """

    fidelity_for = {
        "eight-bit": "sixteen-bit",
        "sixteen-bit": "sixteen-bit",
        "clean-pixel": "sixteen-bit",
        "crt": "sixteen-bit",
        "high": "high",
        "ultra": "ultra",
    }
    characters = root / "characters"
    for preset, fidelity in fidelity_for.items():
        source = root / "fidelity" / fidelity / "characters"
        for view in VIEWS:
            src = source / f"david_{view}.png"
            if src.is_file():
                Image.open(src).save(characters / f"david_{preset}_{view}.png")
        for view in ("side-idle", "flight", "ots"):
            src = source / f"custom_{view}.png"
            if src.is_file():
                Image.open(src).save(characters / f"custom_{preset}_{view}.png")

    items = root / "items"
    item_aliases = {
        "block.png": ("sixteen-bit", "block.png"),
        "block-high.png": ("high", "block.png"),
        "penguin.png": ("sixteen-bit", "penguin.png"),
        "penguin-high.png": ("high", "penguin.png"),
        "omarchy-logo.png": ("sixteen-bit", "omarchy-logo.png"),
        "logic-bomb.png": ("sixteen-bit", "logic-bomb.png"),
    }
    for dest_name, (fidelity, source_name) in item_aliases.items():
        Image.open(root / "fidelity" / fidelity / "items" / source_name).save(items / dest_name)

    for tile in root.glob("fidelity/sixteen-bit/tiles/*.png"):
        Image.open(tile).save(root / "tiles" / tile.name)

    for boss in (
        "package-bureaucrat",
        "dependency-hydra",
        "distro-commander",
        "garden-gatekeeper",
        "singularity",
        "goliath",
        "dogma-sprite",
    ):
        Image.open(root / "fidelity" / "high" / "bosses" / f"{boss}.png").save(root / "bosses" / f"{boss}.png")
        Image.open(root / "fidelity" / "sixteen-bit" / "bosses" / f"{boss}.png").save(root / "bosses" / f"{boss}-8.png")


def build_assets(root: Path | None = None) -> Path:
    root = Path(root) if root else asset_dir()
    resolved = root.resolve()
    if resolved in _BUILT_ROOTS:
        return root
    root.mkdir(parents=True, exist_ok=True)
    characters = root / "characters"
    tiles = root / "tiles"
    items = root / "items"
    bosses = root / "bosses"
    ui = root / "ui"
    for folder in (characters, tiles, items, bosses, ui):
        folder.mkdir(parents=True, exist_ok=True)

    for preset in PRESETS:
        scale = _preset_scale(preset)
        for frame in ("side-idle", "side-walk-0", "side-walk-1", "side-walk-2", "side-jump"):
            _david_side(scale, frame).save(characters / f"david_{preset}_{frame}.png")
        _david_flight(scale).save(characters / f"david_{preset}_flight.png")
        _david_portrait(scale).save(characters / f"david_{preset}_portrait.png")
        _david_portrait(scale).save(characters / f"david_{preset}_turn.png")
        # Dedicated OTS composition at a scale appropriate to the closer camera.
        ots_scale = {"eight-bit": 1, "sixteen-bit": 2, "clean-pixel": 2, "crt": 2, "high": 3, "ultra": 4}[preset]
        _david_ots(ots_scale).save(characters / f"david_{preset}_ots.png")
        # custom-character tints reuse the same silhouette with shirt swap
        shirt_custom = _david_side(scale, "side-idle")
        shirt_custom.save(characters / f"custom_{preset}_side-idle.png")
        _david_ots(ots_scale).save(characters / f"custom_{preset}_ots.png")
        _david_flight(scale).save(characters / f"custom_{preset}_flight.png")

    draw_block(16).save(items / "block.png")
    draw_block(32).save(items / "block-high.png")
    draw_penguin(16).save(items / "penguin.png")
    draw_penguin(32).save(items / "penguin-high.png")
    draw_logo_pickup(16).save(items / "omarchy-logo.png")
    for kind in ("#", "=", "L", "+", "^", "D", "G"):
        for pal in ("corrupted", "wilderness", "front", "garden", "singularity", "goliath", "cow"):
            draw_tile(kind, 16, pal).save(tiles / f"{pal}_{kind}.png")
    for boss in ("package-bureaucrat", "dependency-hydra", "distro-commander", "garden-gatekeeper", "singularity", "goliath", "dogma-sprite"):
        draw_boss(boss, 32).save(bosses / f"{boss}.png")
        draw_boss(boss, 16).save(bosses / f"{boss}-8.png")
    draw_ui_panel().save(ui / "panel.png")
    # Secondary wordmarks remain original pixel rasters. OMARCHY itself uses
    # Basecamp's actual official geometry emitted below.
    for word, name in (("OLIGARCHY", "oligarchy"), ("Play Now", "play-now")):
        img = Image.new("RGB", (8 * len(word) + 16, 24), (14, 15, 22))
        d = ImageDraw.Draw(img)
        d.text((8, 4), word, fill=LIME)
        img.save(ui / f"{name}.png")
    emit_official_wordmark(root)
    emit_app_icons(root)
    omarchy_font = root / "source" / "fonts" / "omarchy-font.ttf"
    if omarchy_font.is_file():
        shutil.copyfile(omarchy_font, ui / "omarchy-font.ttf")
    omarchy_font_license = root / "source" / "fonts" / "OMARCHY-FONT-LICENSE.txt"
    if omarchy_font_license.is_file():
        shutil.copyfile(omarchy_font_license, ui / "OMARCHY-FONT-LICENSE.txt")
    emit_fidelity_art(root)
    from .refinement_art import emit_refinement_art

    emit_refinement_art(root)
    sync_legacy_art(root)
    from .character_build import build_agent_kit, build_builtin_characters

    build_builtin_characters(root)
    build_agent_kit(root)
    build_audio(root)
    _BUILT_ROOTS.add(resolved)
    return root
