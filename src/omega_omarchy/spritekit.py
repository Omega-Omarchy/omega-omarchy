"""Ingest generated production art and emit fidelity-specific game sprites."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .presentation import SPRITE_SIZE, TILE_ART_SIZE

MAGENTA = (255, 0, 255, 255)
NES = [
    (0, 0, 0),
    (252, 252, 252),
    (188, 188, 188),
    (124, 124, 124),
    (188, 148, 92),
    (124, 92, 60),
    (92, 60, 28),
    (220, 180, 140),
    (188, 140, 108),
    (60, 148, 212),
    (16, 16, 20),
    (48, 48, 56),
    (200, 72, 88),
    (80, 180, 88),
    (36, 40, 56),
    (196, 132, 72),
]


def chroma_key(img: Image.Image) -> Image.Image:
    """Key magenta/pink backdrop without eating warm skin.

    Magenta has min(R,B) well above G and sits on the image border. Skin is
    warm (R >> B) so it fails that test. Only background connected to the
    frame edge is cleared, then tiny interior holes are closed.
    """

    img = img.convert("RGBA")
    arr = np.array(img)
    border = np.concatenate((arr[0, :, :3], arr[-1, :, :3], arr[:, 0, :3], arr[:, -1, :3]))
    border_spread = border.max(axis=1).astype(np.int16) - border.min(axis=1).astype(np.int16)
    if float(np.mean((border_spread < 18) & (border.min(axis=1) > 215))) > 0.55:
        return key_neutral_background(img)
    original_alpha = arr[:, :, 3].copy()
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    bg = (np.minimum(r, b) > g + 25) & (np.minimum(r, b) > 110) & (np.abs(r - b) < 90)
    h, w = bg.shape
    mask = np.zeros((h, w), dtype=bool)
    mask[0, :] = bg[0, :]
    mask[-1, :] = bg[-1, :]
    mask[:, 0] = bg[:, 0]
    mask[:, -1] = bg[:, -1]
    for _ in range(max(h, w)):
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        nxt = grown & bg
        if np.array_equal(nxt, mask):
            break
        mask = nxt
    alpha = np.where(mask, 0, original_alpha).astype(np.uint8)
    # Close 1px holes punched in faces by fringe.
    opaque = alpha > 0
    filled = opaque.copy()
    filled[1:, :] |= opaque[:-1, :]
    filled[:-1, :] |= opaque[1:, :]
    filled[:, 1:] |= opaque[:, :-1]
    filled[:, :-1] |= opaque[:, 1:]
    # Only keep the dilation inside the original opaque bounding mass.
    alpha = np.where(filled & ~mask & (original_alpha > 0), original_alpha, alpha).astype(np.uint8)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr, "RGBA")


def key_neutral_background(img: Image.Image) -> Image.Image:
    """Clear a connected white/gray studio checker while preserving highlights."""

    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3].astype(np.int16)
    neutral = (rgb.max(axis=2) - rgb.min(axis=2) < 22) & (rgb.min(axis=2) > 210)
    h, w = neutral.shape
    mask = np.zeros((h, w), dtype=bool)
    mask[0, :] = neutral[0, :]
    mask[-1, :] = neutral[-1, :]
    mask[:, 0] = neutral[:, 0]
    mask[:, -1] = neutral[:, -1]
    for _ in range(max(h, w)):
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        nxt = grown & neutral
        if np.array_equal(nxt, mask):
            break
        mask = nxt
    # Peel connected near-neutral antialiasing without touching isolated eyes,
    # shirt ink, or beard highlights inside the silhouette.
    for _ in range(5):
        near = mask.copy()
        near[1:, :] |= mask[:-1, :]
        near[:-1, :] |= mask[1:, :]
        near[:, 1:] |= mask[:, :-1]
        near[:, :-1] |= mask[:, 1:]
        fringe = (rgb.max(axis=2) - rgb.min(axis=2) < 30) & (rgb.min(axis=2) > 170)
        mask |= near & fringe
    arr[:, :, 3] = np.where(mask, 0, arr[:, :, 3]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def clear_neutral_holes(
    img: Image.Image,
    seeds: tuple[tuple[float, float], ...],
) -> Image.Image:
    """Clear enclosed white/gray studio regions selected by normalized seeds.

    Edge-connected keying deliberately preserves interior highlights. Product
    art such as a coiled cable can also enclose the studio backdrop, so callers
    may identify only those known negative-space regions without erasing metal
    speculars elsewhere in the subject.
    """

    arr = np.array(img.convert("RGBA"))
    rgb = arr[:, :, :3].astype(np.int16)
    neutral = (rgb.max(axis=2) - rgb.min(axis=2) < 28) & (rgb.min(axis=2) > 205) & (arr[:, :, 3] > 0)
    h, w = neutral.shape
    mask = np.zeros((h, w), dtype=bool)
    for sx, sy in seeds:
        x = max(0, min(w - 1, round(sx * (w - 1))))
        y = max(0, min(h - 1, round(sy * (h - 1))))
        if neutral[y, x]:
            mask[y, x] = True
    for _ in range(max(h, w)):
        grown = mask.copy()
        grown[1:, :] |= mask[:-1, :]
        grown[:-1, :] |= mask[1:, :]
        grown[:, 1:] |= mask[:, :-1]
        grown[:, :-1] |= mask[:, 1:]
        nxt = grown & neutral
        if np.array_equal(nxt, mask):
            break
        mask = nxt
    # Include the softer antialias fringe immediately surrounding the keyed
    # negative space, but never disconnected neutral highlights.
    for _ in range(4):
        near = mask.copy()
        near[1:, :] |= mask[:-1, :]
        near[:-1, :] |= mask[1:, :]
        near[:, 1:] |= mask[:, :-1]
        near[:, :-1] |= mask[:, 1:]
        fringe = (rgb.max(axis=2) - rgb.min(axis=2) < 34) & (rgb.min(axis=2) > 170)
        mask |= near & fringe
    arr[:, :, 3] = np.where(mask, 0, arr[:, :, 3]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def decontaminate_magenta(img: Image.Image, *, passes: int = 3) -> Image.Image:
    """Remove keyed-backdrop color that survives as a downsampled edge fringe.

    The ordinary key is deliberately conservative for skin. Portrait cleanup
    can be stricter because it only removes magenta-like pixels adjacent to
    already transparent backdrop, preserving lips and warm facial shading.
    """

    arr = np.array(img.convert("RGBA"))
    for _ in range(max(1, passes)):
        alpha = arr[:, :, 3]
        transparent = alpha < 24
        near = transparent.copy()
        near[1:, :] |= transparent[:-1, :]
        near[:-1, :] |= transparent[1:, :]
        near[:, 1:] |= transparent[:, :-1]
        near[:, :-1] |= transparent[:, 1:]
        r = arr[:, :, 0].astype(np.int16)
        g = arr[:, :, 1].astype(np.int16)
        b = arr[:, :, 2].astype(np.int16)
        magenta = (
            (r > 105)
            & (b > 85)
            & (r > g * 1.42)
            & (b > g * 1.35)
            & (np.abs(r - b) < 105)
        )
        arr[:, :, 3] = np.where(near & magenta, 0, alpha).astype(np.uint8)
    # Generated studio backdrops can leave isolated pink islands between hair
    # strands. Their hue is much bluer than skin/lips, so remove those even
    # when an opaque strand disconnects them from the outer keyed region.
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    isolated_key = (
        (r > 105)
        & (b > 75)
        & (b * 100 > r * 54)
        & (r > g * 1.48)
        & (b > g * 1.32)
        & (np.abs(r - b) < 112)
    )
    arr[:, :, 3] = np.where(isolated_key, 0, arr[:, :, 3]).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def crop_subject(img: Image.Image, pad: int = 2) -> Image.Image:
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(img.width, x1 + pad), min(img.height, y1 + pad)
    return img.crop((x0, y0, x1, y1))


def fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    src = img.copy()
    src.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - src.width) // 2
    y = size[1] - src.height
    canvas.paste(src, (x, y), src)
    return canvas


def fit_scaled(img: Image.Image, size: tuple[int, int], *, anchor_y: str = "bottom") -> Image.Image:
    """Contain an image in ``size``, allowing enlargement for close camera art."""

    img = img.convert("RGBA")
    scale = min(size[0] / max(1, img.width), size[1] / max(1, img.height))
    fitted = img.resize(
        (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2 if anchor_y == "center" else size[1] - fitted.height
    canvas.paste(fitted, (x, y), fitted)
    return canvas


def pixel_outline(img: Image.Image, color: tuple[int, int, int, int] = (252, 252, 252, 255)) -> Image.Image:
    """1px light outline so small NES sprites stay readable on dark tiles."""

    img = img.convert("RGBA")
    w, h = img.size
    src = img.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dst = out.load()
    for y in range(h):
        for x in range(w):
            if src[x, y][3] > 16:
                dst[x, y] = src[x, y]
                continue
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3] > 16:
                    dst[x, y] = color
                    break
    return out


def nes_quantize(img: Image.Image) -> Image.Image:
    pal = Image.new("P", (1, 1))
    flat: list[int] = []
    for color in NES:
        flat.extend(color)
    flat.extend([0, 0, 0] * (256 - len(NES)))
    pal.putpalette(flat)
    rgb = img.convert("RGB")
    q = rgb.quantize(palette=pal, dither=Image.Dither.NONE)
    out = q.convert("RGBA")
    arr = np.array(out)
    src = np.array(img)
    arr[:, :, 3] = src[:, :, 3]
    return Image.fromarray(arr, "RGBA")


def walk_frame(idle: Image.Image, phase: int) -> Image.Image:
    """Cheap but distinct walk: bob + leading/trailing foot."""

    w, h = idle.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bob = (0, 1, 0, 1)[phase % 4]
    shift = (-1, 0, 1, 0)[phase % 4]
    canvas.paste(idle, (shift, -bob), idle)
    return canvas


def walk_passing_frame(contact: Image.Image, phase: int) -> Image.Image:
    """A narrow, weight-bearing passing pose between opposite contact beats."""

    subject = crop_subject(contact)
    target_w = max(1, round(subject.width * 0.82))
    passing = subject.resize((target_w, subject.height), Image.Resampling.LANCZOS)
    angle = -1.4 if phase % 2 == 0 else 1.4
    passing = passing.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = fit_scaled(passing, contact.size)
    shifted = Image.new("RGBA", contact.size, (0, 0, 0, 0))
    dx = (-1 if phase % 2 == 0 else 1) * max(1, contact.width // 80)
    shifted.paste(canvas, (dx, -max(1, contact.height // 90)), canvas)
    return shifted


def opposite_stride(contact: Image.Image) -> Image.Image:
    """Reverse arms/legs while keeping the authored head facing screen-right."""

    contact = contact.convert("RGBA")
    w, h = contact.size
    opposite = ImageOps.mirror(contact)
    # Mirroring produces the correct opposing limb silhouette but also turns
    # the face. Restore the authored head and center torso from the source,
    # leaving the outer arm and complete lower-body shapes reversed.
    hx0, hx1 = round(w * 0.22), round(w * 0.65)
    hy1 = round(h * 0.46)
    opposite.paste(Image.new("RGBA", (w, hy1), (0, 0, 0, 0)), (0, 0))
    head = contact.crop((hx0, 0, hx1, hy1))
    opposite.paste(head, (hx0, 0), head)
    x0, x1 = round(w * 0.35), round(w * 0.60)
    y0, y1 = round(h * 0.34), round(h * 0.64)
    torso = contact.crop((x0, y0, x1, y1))
    opposite.paste(torso, (x0, y0), torso)
    return opposite


def jump_frame(idle: Image.Image) -> Image.Image:
    w, h = idle.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(idle, (0, -2), idle)
    return canvas


def fall_frame(jump: Image.Image) -> Image.Image:
    """Pitch an airborne pose forward so ascent and descent read separately."""

    subject = crop_subject(jump)
    turned = subject.rotate(-5, resample=Image.Resampling.BICUBIC, expand=True)
    return fit_scaled(turned, jump.size)


def land_frame(jump: Image.Image) -> Image.Image:
    """Compress the jump pose into a brief landing anticipation frame."""

    subject = crop_subject(jump)
    squashed = subject.resize(
        (subject.width, max(1, round(subject.height * 0.78))),
        Image.Resampling.LANCZOS,
    )
    return fit_scaled(squashed, jump.size)


def climb_frame(back: Image.Image, phase: int) -> Image.Image:
    """Four readable climbing beats from a back-facing authored pose."""

    subject = crop_subject(back)
    phase %= 4
    if phase in {1, 3}:
        subject = ImageOps.mirror(subject)
    angle = (-2.4, 1.2, 2.4, -1.2)[phase]
    subject = subject.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = fit_scaled(subject, back.size)
    shifted = Image.new("RGBA", back.size, (0, 0, 0, 0))
    dx = (-1, 1, 1, -1)[phase] * max(1, back.width // 60)
    dy = (1, -2, 0, -1)[phase] * max(1, back.height // 72)
    shifted.paste(canvas, (dx, dy), canvas)
    return shifted


def ots_from_back(back: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Crop the upper back/shoulders of a facing-away sprite for the edit camera."""

    back = back.convert("RGBA")
    w, h = back.size
    crop = crop_subject(back.crop((0, 0, w, int(h * 0.72))), pad=1)
    return fit_scaled(crop, size)


def portrait_from_source(src: Path, size: tuple[int, int], *, zoom: float = 1.0) -> Image.Image:
    img = decontaminate_magenta(chroma_key(Image.open(src)), passes=5)
    img = crop_subject(img, pad=4)
    if zoom > 1.0:
        crop_w = max(1, round(img.width / zoom))
        crop_h = max(1, round(img.height / zoom))
        left = max(0, (img.width - crop_w) // 2)
        # Bias upward so every tier puts eyes and chin into the same portrait box.
        top = max(0, round((img.height - crop_h) * 0.30))
        img = img.crop((left, top, min(img.width, left + crop_w), min(img.height, top + crop_h)))
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    fitted = img.copy()
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (x, y), fitted)
    return canvas


def prepare_file(src: Path, size: tuple[int, int], *, nes: bool = False) -> Image.Image:
    """Prepare source art in memory without leaking intermediate build files."""

    img = chroma_key(Image.open(src))
    img = crop_subject(img)
    img = fit(img, size)
    if nes:
        img = nes_quantize(img.resize(size, Image.Resampling.NEAREST))
    return img


def ingest_file(src: Path, dest: Path, size: tuple[int, int], *, nes: bool = False) -> Image.Image:
    img = prepare_file(src, size, nes=nes)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)
    return img


def session_images() -> Path:
    """Versioned generated source art used by the deterministic asset build."""

    return Path(__file__).resolve().parents[2] / "assets" / "source" / "rendered"
