"""Offline extraction of registered boss animation and articulated prop parts."""

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from .campaign import BOSSES
from .character_build import _isolate_atlas_cell, _key_atlas
from .presentation import FIDELITIES, view_scale
from .spritekit import fit_scaled

BOSS_POSES = ("idle", "active", "defeated")
ROBOT_PARTS = {
    "body": (30, 44), "upper": (36, 10), "fore": (32, 9),
    "claw-open": (22, 18), "claw-closed": (22, 18), "joint": (9, 9),
}


def _cyan_key(image: Image.Image) -> Image.Image:
    array = np.array(image.convert("RGBA"))
    r, g, b = [array[:, :, channel].astype(np.int16) for channel in range(3)]
    key = (np.minimum(g, b) - r > 90) & (g > 150) & (b > 150) & (abs(g - b) < 75)
    array[key, 3] = 0
    # Remove cyan spill only at the outer edge, preserving costume colors.
    from PIL import ImageFilter
    edge = np.array(Image.fromarray(key.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0
    spill = edge & ~key & (np.minimum(g, b) > r + 25)
    array[spill, 1] = np.minimum(array[spill, 1], array[spill, 0] + 25)
    array[spill, 2] = np.minimum(array[spill, 2], array[spill, 0] + 25)
    return Image.fromarray(array)


@lru_cache(maxsize=14)
def boss_masters(path: str) -> tuple[Image.Image, ...]:
    sheet = _cyan_key(Image.open(path))
    cells = []
    for index in range(3):
        left, right = round(index * sheet.width / 3), round((index + 1) * sheet.width / 3)
        if "dependency-hydra" in path:
            left, right = max(0, left - 32), min(sheet.width, right + 32)
        cell = sheet.crop((left, 0, right, sheet.height))
        if "dependency-hydra" in path:
            cell = _isolate_atlas_cell(cell)
        bounds = cell.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"Missing boss pose: {path}, {index}")
        cells.append(cell.crop(bounds))
    # One scale for the entire sheet. Kneeling frames stay shorter and action
    # poses retain head size instead of independently filling the square.
    scale = min(122 / max(im.width for im in cells), 122 / max(im.height for im in cells))
    result = []
    for cell in cells:
        image = cell.resize((round(cell.width * scale), round(cell.height * scale)), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (128, 128))
        canvas.alpha_composite(image, ((128 - image.width) // 2, 126 - image.height))
        result.append(canvas)
    return tuple(result)


def emit_refinement_art(root: Path) -> None:
    from .assets import _fidelity_finish

    source = root / "source/refinement"
    portal = Image.open(source / "ring-portal-v1.png").convert("RGBA")
    portal_parts = [portal.crop((round(i * portal.width / 2), 0, round((i + 1) * portal.width / 2), portal.height)) for i in range(2)]
    sign = Image.open(source / "exit-sign-v1.png").convert("RGBA")
    robot = _key_atlas(Image.open(source / "custodian-parts-keyed-v2.png"))
    parts = {}
    for index, name in enumerate(ROBOT_PARTS):
        x, y = index % 3, index // 3
        cell = robot.crop((round(x * robot.width / 3), round(y * robot.height / 2),
                           round((x + 1) * robot.width / 3), round((y + 1) * robot.height / 2)))
        parts[name] = cell.crop(cell.getchannel("A").getbbox())
    for fid in FIDELITIES:
        folder = root / "fidelity" / fid
        for sub in ("bosses", "items", "ui"):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        vs = view_scale(fid)
        for boss_id in (*BOSSES, "goliath-cyborg-penguin"):
            target = {"sixteen-bit": 48, "high": 72, "ultra": 128}[fid]
            for pose, master in zip(BOSS_POSES, boss_masters(str(source / f"{boss_id}-v1.png"))):
                image = _fidelity_finish(master.resize((target, target), Image.Resampling.LANCZOS), fid)
                suffix = "" if pose == "idle" else "-" + pose
                image.save(folder / "bosses" / f"{boss_id}{suffix}.png")
                if pose == "defeated":
                    image.save(folder / "bosses" / f"{boss_id}-converted.png")
        for part, size in ROBOT_PARTS.items():
            # Compact, fixed canvases: rig sockets are measured in these
            # logical dimensions and don't drift with image bounding boxes.
            image = parts[part].resize((size[0] * vs, size[1] * vs), Image.Resampling.LANCZOS)
            _fidelity_finish(image, fid).save(folder / "ui" / f"custodian-{part}.png")
        for master, name, size in ((sign, "exit-sign", (56, 18)),
                                   (portal_parts[0], "ring-pad", (32, 12)),
                                   (portal_parts[1], "ring-portal", (32, 12))):
            # Generated cutouts can contain nearly transparent pixels well
            # outside the prop. Exclude that haze from registration bounds.
            master = master.copy()
            master.putalpha(master.getchannel("A").point(lambda alpha: alpha if alpha > 16 else 0))
            master = master.crop(master.getchannel("A").getbbox())
            image = fit_scaled(master, (size[0] * vs, size[1] * vs), anchor_y="bottom")
            _fidelity_finish(image, fid).save(folder / "items" / f"{name}.png")
