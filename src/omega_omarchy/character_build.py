"""Offline character authoring, fidelity derivation, and portable agent kits."""

from __future__ import annotations

from hashlib import sha256
from collections import deque
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

import numpy as np
from PIL import Image, ImageEnhance

from .canonical import sha256_json
from .character_pack import BUILTIN_NAMES, POSES, _metadata, pose_size, validate_pack
from .presentation import FIDELITIES

ATLAS_POSES = (
    "side-idle", "side-walk-0", "side-walk-1", "side-walk-2", "side-walk-3",
    "side-jump", "side-climb-0", "side-climb-1", "side-climb-2", "side-climb-3",
    "side-action", "side-air-action", "side-bomb", "side-slide", "away",
    "portrait", "prologue-captured", "prologue-transfer", "ots", "flight",
)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_source(source: Path) -> tuple[dict, dict[str, Image.Image]]:
    source = Path(source)
    manifest = source / "character.json"
    if manifest.stat().st_size > 64 * 1024:
        raise ValueError("Character source manifest is too large.")
    record = json.loads(manifest.read_text(encoding="utf-8"))
    _metadata(record)
    frames = record.get("frames")
    if not isinstance(frames, dict) or set(frames) != set(POSES):
        raise ValueError("Supply exactly the 26 named frames; no implicit David fallback is allowed.")
    images = {}
    for pose, filename in frames.items():
        if not isinstance(filename, str) or Path(filename).is_absolute():
            raise ValueError(f"Invalid source path for {pose}.")
        path = source / filename
        if path.is_symlink() or not path.resolve().is_relative_to(source.resolve()) or path.stat().st_size > 1024 * 1024:
            raise ValueError(f"Invalid source file for {pose}.")
        with Image.open(path) as image:
            if image.format != "PNG" or image.mode != "RGBA" or image.size != pose_size(pose, "ultra"):
                raise ValueError(f"{pose}: expected transparent RGBA PNG, {pose_size(pose, 'ultra')} pixels.")
            image.load()
            low, high = image.getchannel("A").getextrema()
            if low != 0 or high < 200:
                raise ValueError(f"{pose}: needs transparent background and an opaque visible character.")
            images[pose] = image.copy()
    return record, images


def _tier(image: Image.Image, fidelity: str, size: tuple[int, int]) -> Image.Image:
    image = image.resize(size, Image.Resampling.LANCZOS)
    if fidelity == "ultra":
        return image
    alpha = image.getchannel("A")
    colors = 64 if fidelity == "sixteen-bit" else 256
    image = ImageEnhance.Contrast(image.convert("RGB")).enhance(1.06 if colors == 64 else 1.025)
    image = image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGBA")
    image.putalpha(alpha)
    return image


def build_pack(source: Path, destination: Path) -> Path:
    """Build all tiers without changing source registration or gameplay rules."""
    record, images = validate_source(source)
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Choose an empty output directory for the character build.")
    destination.mkdir(parents=True, exist_ok=True)
    files = {}
    for fid in FIDELITIES:
        (destination / fid).mkdir(exist_ok=True)
        for pose, image in images.items():
            relative = f"{fid}/{pose}.png"
            path = destination / relative
            tier = _tier(image, fid, pose_size(pose, fid))
            if pose == "side-slide":
                # The renderer lowers this canvas by six world pixels. Match
                # David's actual alpha baseline, including tier resampling.
                bottom = {"sixteen-bit": 29, "high": 58, "ultra": 87}[fid]
                bounds = tier.getchannel("A").getbbox()
                aligned = Image.new("RGBA", tier.size)
                aligned.alpha_composite(tier, (0, bottom - bounds[3]))
                tier = aligned
            tier.save(path)
            files[relative] = "sha256:" + sha256(path.read_bytes()).hexdigest()
    manifest = {key: record[key] for key in ("schemaVersion", "id", "name", "author", "license")}
    manifest["files"] = files
    manifest["digest"] = sha256_json(manifest)
    _write_json(destination / "manifest.json", manifest)
    validate_pack(destination)
    return destination


def zip_pack(source: Path, destination: Path) -> Path:
    record = validate_pack(source)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in ["manifest.json", *sorted(record["files"])]:
            entry = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (source / relative).read_bytes())
    return destination


def contract_document() -> str:
    rows = "\n".join(f"| `{pose}` | {pose_size(pose, 'ultra')[0]} × {pose_size(pose, 'ultra')[1]} | {description} |" for pose, description in POSES.items())
    return f'''# Create an Omega Omarchy character with your agent

Give this entire folder to any agent with image creation and filesystem tools.
Tell it your character's appearance and name. A photograph is optional; the
game never sends one to an image service. Choose your own agent and provider.

## Message to the agent

Create a complete playable character for Omega Omarchy using my description.
Read contract.json and this brief. Use reference/ only to understand pose,
canvas registration, and game art style. Maintain my chosen identity, outfit,
hair, proportions, and accessories in every frame. Do not leave David artwork
in the deliverable. Generate the art with your image tool, inspect all poses,
and replace every path in character.json with the finished 26 PNGs.

This is a visual replacement. Do not alter collisions, speed, jump, abilities,
map generation, or game code. Keep descriptive metadata honest, including the
author and license; do not assume reference art transfers its license to new art.

## Delivery contract (version 1)

- Author **Ultra only** as the exact canvas sizes below; the compiler derives
  High and Sixteen-bit from the same artwork. All files are 8-bit RGBA PNGs
  (noninterlaced) with genuine transparency, an opaque subject, and no baked backdrop,
  checkerboard, ground shadow, labels, HUD, trails, projectiles, or machinery.
- Ordinary character canvases are 120 × 108. They render as 40 × 36 world
  pixels, centered horizontally on the player's feet and anchored at their
  bottom edge. Grounded feet should meet y=107, with body center around x=60.
  Keep consistent head scale and support-foot placement through the walk cycle.
  Do not independently enlarge a kick or crouch to fill its whole canvas.
- Collision stays **10 × 18 world pixels**, below the visible shoulders/head.
  TILE stays 16. Crowns, hair, capes, and weapons grant no extra reach.
- Right-facing side poses are flipped at runtime for left travel. Climbing,
  away, flight, and OTS are rear views. Portrait/turn face the viewer.
- A slide uses the normal 120 × 108 canvas and is lowered by six world pixels
  at runtime. Its lowest visible pixel is y=86, matching David (28 in
  Sixteen-bit, 57 in High). The compiler registers this baseline in each tier.
- Prologue poses are centered compositions fitted to their dedicated canvases.
  Captured sits upright facing right. Transfer matches the reference's diagonal
  three-quarter perspective: boots in the lower-left foreground, head in the
  upper-right background, face visible from above, lying supine. Do not use
  a horizontal side profile. Furniture and restraint effects come from the game.
- OTS is a dedicated rear view from head to upper thighs with both hands,
  composed against the bottom of its
  240 × 288 canvas. The edit grid is to its right. No face looking back.
- Portrait matches David's facial registration: on the 96 × 96 Ultra canvas,
  eye centers are roughly (31, 40) and (59, 40), with the mouth around y=68.
  Match face scale and placement before framing hair, crowns or shoulders.
  Distinctive headwear may extend beyond the crop.
- Keep a readable silhouette against dark scenery, and avoid tiny details
  that vanish at 36 pixels tall. Preserve alpha while downsampling.
- Reusing your own idle for battle and portrait for turn is allowed. All 26
  files must exist. No undeclared fallback or missing view is accepted.
- Maximum source PNG size: 1 MiB per frame. Compiled pack: 12 MiB expanded;
  distributable ZIP: 4 MiB for browser import. PNG files and JSON only.

| Frame/file stem | Ultra pixels | Required view or action |
| --- | --- | --- |
{rows}

## Compile, inspect, install

From the Omega Omarchy repository (Python and game dependencies installed):

```sh
./scripts/omega validate-character-source /path/to/this-folder
./scripts/omega build-character /path/to/this-folder --out /path/to/my-character-pack
./scripts/omega validate-character /path/to/my-character-pack
./scripts/omega install-character /path/to/my-character-pack
```

`build-character` also writes a sibling `.zip` for sharing/import. Installing
copies a complete validated version into game-owned local storage. It never
overwrites David or another saved version. Return to character setup (or move
its selection once) to refresh the list, select the installed character, and
start a new world. Existing saves retain their chosen appearance and name.
Built-in King/Queen characters receive the game's framing and animation fixes;
their stored digest records the version at creation. Custom packs remain pinned
to the exact installed digest and never silently select different artwork.

In the browser, use **Import character ZIP** below the game, then select it in
character setup. Import is local, with no upload to a server. Browser storage
attempts to retain the pack; keep your ZIP in case storage is cleared or full.
To bundle a custom character into a browser build, pass `--character-pack` to
the `web` command. World sharing does not distribute character art: share its
ZIP separately. A missing saved pack produces one consistent David fallback
and a visible message, never a mixture of characters between scenes.

Review every frame on dark and light backgrounds. Check right/left walking,
jumping, sliding, climbing, throwing, battle, portrait/turn, both prologue
poses, flight in/out, OTS, and the left-behind ghost at all three fidelities.
Check that crowns/hair are not clipped, feet do not drift, limbs alternate,
and no checkerboard or chroma-key color survives. Validation proves coverage,
dimensions and integrity; visual quality and animation still require review.
'''


def export_kit(destination: Path, assets: Path) -> Path:
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Choose an empty directory for the agent kit.")
    (destination / "reference").mkdir(parents=True, exist_ok=True)
    (destination / "frames").mkdir()
    _write_json(destination / "character.json", {
        "schemaVersion": 1, "id": "my-character", "name": "My Character",
        "author": "Your name or handle", "license": "Describe the permission for your new artwork",
        "frames": {pose: f"frames/{pose}.png" for pose in POSES},
    })
    _write_json(destination / "contract.json", {
        "schemaVersion": 1, "worldTilePixels": 16, "collisionPixels": [10, 18],
        "visualWorldHeight": 36, "groundAnchor": "bottom-center", "sideFacing": "right",
        "png": {"bitDepth": 8, "colorMode": "RGBA", "interlaced": False},
        "poses": {pose: {"description": description, "sizes": {fid: list(pose_size(pose, fid)) for fid in FIDELITIES}}
                  for pose, description in POSES.items()},
    })
    (destination / "AGENT-BRIEF.md").write_text(contract_document(), encoding="utf-8")
    for pose in POSES:
        shutil.copyfile(assets / "fidelity/ultra/characters" / f"david_{pose}.png", destination / "reference" / f"{pose}.png")
    return destination


def _key_atlas(image: Image.Image) -> Image.Image:
    """The built-in atlas explicitly uses green, absent from either costume."""
    array = np.array(image.convert("RGBA"))
    rgb = array[:, :, :3].astype(np.int16)
    spill = rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])
    mask = (spill > 45) & (rgb[:, :, 1] > 100)
    array[mask, 3] = 0
    # De-spill antialiased edge texels, keeping original alpha for the subject.
    fringe = (spill > 0) & (spill <= 45)
    array[fringe, 1] = np.maximum(array[fringe, 0], array[fringe, 2])
    return Image.fromarray(array)


def _contain(image: Image.Image, size: tuple[int, int], *, scale: float | None = None, center: bool = False) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if not bbox:
        raise ValueError("Empty atlas cell.")
    image = image.crop(bbox)
    ratio = min((size[0] - 4) / image.width, (size[1] - 2) / image.height)
    ratio = min(ratio, scale) if scale is not None else ratio
    image = image.resize((max(1, round(image.width * ratio)), max(1, round(image.height * ratio))), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", size)
    result.alpha_composite(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2 if center else size[1] - image.height))
    return result


def _isolate_atlas_cell(image: Image.Image) -> Image.Image:
    """Discard fragments of adjacent poses that cross a generative grid edge."""
    array = np.array(image)
    opaque = array[:, :, 3] > 8
    visited = np.zeros(opaque.shape, dtype=bool)
    largest = []
    h, w = opaque.shape
    for y, x in zip(*np.nonzero(opaque)):
        if visited[y, x]:
            continue
        component = []
        queue = deque([(int(y), int(x))])
        visited[y, x] = True
        while queue:
            cy, cx = queue.popleft()
            component.append((cy, cx))
            for dy, dx in ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < h and 0 <= nx < w and opaque[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))
        if len(component) > len(largest):
            largest = component
    keep = np.zeros(opaque.shape, dtype=bool)
    for y, x in largest:
        keep[y, x] = True
    # Keep antialiased edge pixels immediately adjacent to the chosen subject.
    from PIL import ImageFilter
    edge = np.array(Image.fromarray(keep.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))) > 0
    array[~edge, 3] = 0
    return Image.fromarray(array)


def build_builtin_characters(assets: Path) -> None:
    from .spritekit import fall_frame

    for pack_id, name in BUILTIN_NAMES.items():
        source = assets / "source/characters" / pack_id
        atlas_path = source / "atlas-keyed-v2.png"
        if not atlas_path.is_file():
            raise ValueError(f"Missing built-in character atlas: {atlas_path}")
        atlas = _key_atlas(Image.open(atlas_path))
        cells = {}
        for index, pose in enumerate(ATLAS_POSES):
            column, row = index % 5, index // 5
            # Generative grids have small spacing deviations. Insets use the
            # observed horizontal bands, kept with the source metadata.
            bands = [0, 290, 560, 830, atlas.height] if pack_id == "omarch-king" else [0, 305, 590, 855, atlas.height]
            left, right = round(column * atlas.width / 5), round((column + 1) * atlas.width / 5)
            if pose == "prologue-transfer":
                left -= 20
            cells[pose] = _isolate_atlas_cell(atlas.crop((left, bands[row], right, bands[row + 1])))
        correction = _key_atlas(Image.open(source / "pose-corrections-v3.png"))
        # Observed gutters in the generated sheet, independent of nominal
        # grid thirds. Queen's reclining crown overlaps the portrait's x band
        # but remains a disconnected silhouette, so isolate that component.
        cuts = [0, 811, 1510, correction.width] if pack_id == "omarch-king" else [0, 750, 1316, correction.width]
        for index, pose in enumerate(("prologue-transfer", "portrait", "ots")):
            cell = correction.crop((cuts[index], 0, cuts[index + 1], correction.height))
            if pose == "prologue-transfer":
                cell = _isolate_atlas_cell(cell)
            elif pose == "portrait":
                # Face-sized registration; the crown and shoulders are not
                # allowed to shrink the eyes/mouth back into a distant bust.
                # Measured eye centers match David at roughly (31, 40) and
                # (59, 40) on the 96px Ultra portrait. Keep the crop fixed:
                # alpha-bounds fitting would undo the face registration.
                box = (78, 37, 678, 637) if pack_id == "omarch-king" else (-14, 88, 586, 688)
                cell = cell.crop(box)
            cells[pose] = cell
        # The source sheet repeated the raised arm on the second contact.
        # Rear-facing costumes are symmetric, so mirror the opposite half
        # of the climb cycle to give real alternating hands and knees.
        cells["side-climb-2"] = cells["side-climb-0"].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        cells["side-climb-3"] = cells["side-climb-1"].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        idle_height = cells["side-idle"].getchannel("A").getbbox()[3] - cells["side-idle"].getchannel("A").getbbox()[1]
        master_scale = 106 / idle_height
        frames = {}
        for pose, cell in cells.items():
            normal = pose.startswith("side-") or pose == "away"
            if pose == "portrait":
                frames[pose] = cell.resize(pose_size(pose, "ultra"), Image.Resampling.LANCZOS)
                continue
            frames[pose] = _contain(cell, pose_size(pose, "ultra"), scale=master_scale if normal else None,
                                    center=pose.startswith("prologue-") or pose == "portrait")
        frames["side-fall"] = fall_frame(frames["side-jump"])
        frames["side-hurt"] = fall_frame(frames["side-idle"])
        for pose, base in (("side-land", "side-jump"), ("side-crouch", "side-idle")):
            image = frames[base]
            compressed = image.resize((image.width, round(image.height * .78)), Image.Resampling.LANCZOS)
            frames[pose] = Image.new("RGBA", image.size)
            frames[pose].alpha_composite(compressed, (0, image.height - compressed.height))
        frames["battle"] = frames["side-idle"].copy()
        frames["turn"] = frames["portrait"].copy()
        with tempfile.TemporaryDirectory(prefix="omega-character-build-") as temporary:
            stage = Path(temporary) / "source"
            (stage / "frames").mkdir(parents=True)
            for pose, image in frames.items():
                image.save(stage / "frames" / f"{pose}.png")
            _write_json(stage / "character.json", {
                "schemaVersion": 1, "id": pack_id, "name": name,
                "author": "Omega Omarchy · generated from maintainer-supplied Omarch concepts",
                "license": "Project artwork; see ASSET-LICENSE.md and source provenance",
                "frames": {pose: f"frames/{pose}.png" for pose in POSES},
            })
            compiled = build_pack(stage, Path(temporary) / "compiled")
            destination = assets / "character-packs" / pack_id
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(compiled, destination)


def build_agent_kit(assets: Path) -> Path:
    output = assets / "character-creation"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="omega-agent-kit-") as temporary:
        kit = export_kit(Path(temporary) / "kit", assets)
        destination = output / "agent-kit.zip"
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(kit.rglob("*")):
                if path.is_file():
                    entry = zipfile.ZipInfo(path.relative_to(kit).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(entry, path.read_bytes())
    (output / "AGENT-BRIEF.md").write_text(contract_document(), encoding="utf-8")
    return destination
