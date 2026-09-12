"""Rendering optimizations must preserve alpha edges and asset registration."""

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from omega_omarchy.render import Renderer
from omega_omarchy.runtime_assets import asset_dir


@pytest.mark.parametrize("position", [(0, 0), (-28, -19), (63, 45), (-70, 4)])
@pytest.mark.parametrize("metadata", ["valid", "missing", "wrong-size", "invalid-bounds"])
def test_parallax_padding_crop_preserves_every_pixel(tmp_path, position, metadata):
    pygame.init()
    pygame.display.set_mode((96, 64))
    image = pygame.Surface((180, 100), pygame.SRCALPHA)
    image.fill((95, 23, 44, 0))
    pygame.draw.rect(image, (80, 150, 60, 1), (30, 20, 75, 48))
    pygame.draw.rect(image, (150, 70, 200, 173), (32, 24, 60, 39))
    data = {"parallax-0.png": {"size": [180, 100], "bounds": [30, 20, 75, 48]}}
    if metadata == "wrong-size":
        data["parallax-0.png"]["size"] = [90, 50]
    if metadata == "invalid-bounds":
        data["parallax-0.png"]["bounds"] = [30, 20, 500, 100]
    directory = tmp_path / "bg"
    directory.mkdir()
    if metadata != "missing":
        (directory / "parallax-bounds.json").write_text(json.dumps(data))
    renderer = Renderer(ensure_assets=False)
    renderer.root = tmp_path
    bounds = renderer._parallax_bounds(image, "bg/parallax-0.png")
    reference = pygame.Surface((96, 64))
    reference.fill((12, 24, 59))
    cropped = reference.copy()
    reference.blit(image, position)
    cropped.blit(image, (position[0] + bounds.x, position[1] + bounds.y), bounds)
    assert pygame.image.tobytes(reference, "RGB") == pygame.image.tobytes(cropped, "RGB")
    pygame.quit()


def test_shipped_parallax_bounds_match_all_nontransparent_pixels():
    pygame.init()
    pygame.display.set_mode((1, 1))
    metadata_files = list((asset_dir() / "fidelity").glob("*/bg/**/parallax-bounds.json"))
    assert metadata_files
    for metadata_file in metadata_files:
        entries = json.loads(metadata_file.read_text())
        assert set(entries) == {path.name for path in metadata_file.parent.glob("parallax-*.png")}
        for name, entry in entries.items():
            image = pygame.image.load(str(metadata_file.parent / name))
            assert entry["size"] == list(image.get_size())
            assert entry["bounds"] == list(image.get_bounding_rect(min_alpha=1)), str(metadata_file / name)
    pygame.quit()
