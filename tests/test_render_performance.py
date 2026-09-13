"""Rendering optimizations must preserve alpha edges and asset registration."""

import json
import os
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
from PIL import Image

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
            with Image.open(metadata_file.parent / name) as source:
                assert entry["opaque"] == (source.convert("RGBA").getchannel("A").getextrema() == (255, 255))
    pygame.quit()


@pytest.mark.parametrize("position", [(3, 4), (-4, -3), (70, 40)])
@pytest.mark.parametrize("scale", [1, 2, 3])
@pytest.mark.parametrize("alpha_target", [False, True])
def test_cached_panel_preserves_fill_frame_and_clipping(position, scale, alpha_target):
    pygame.init()
    pygame.display.set_mode((96, 64))
    renderer = Renderer(ensure_assets=False)
    renderer._vs = scale
    frame = pygame.Surface((47, 29), pygame.SRCALPHA)
    frame.fill((120, 90, 60, 72))
    pygame.draw.rect(frame, (220, 100, 40, 190), (0, 0, 47, 29), 3)
    pygame.draw.rect(frame, (0, 0, 0, 0), (8, 8, 20, 10))
    renderer._load = lambda _path: frame
    rect = (*position, 28, 19)
    for fill in ((7, 9, 18), (30, 70, 110), (7, 9, 18)):
        target = pygame.Surface((96, 64), pygame.SRCALPHA if alpha_target else 0)
        target.fill((70, 120, 160, 110))
        target.set_clip((2, 1, 88, 58))
        reference = target.copy()
        reference.set_clip(target.get_clip())
        pygame.draw.rect(reference, fill, renderer._lr(*rect))
        reference.blit(renderer._fit(frame, (28 * scale, 19 * scale)), renderer._lp(*position))
        renderer._panel(target, rect, fill=fill)
        assert pygame.image.tobytes(target, "RGBA") == pygame.image.tobytes(reference, "RGBA")
    pygame.quit()


def test_character_fit_cache_distinguishes_sources_without_mutating_them():
    pygame.init()
    renderer = Renderer(ensure_assets=False)
    sources = [pygame.Surface((8, 8), pygame.SRCALPHA) for _ in range(2)]
    sources[0].fill((120, 60, 10, 150))
    sources[1].fill((10, 180, 240, 100))
    for source in sources:
        original = pygame.image.tobytes(source, "RGBA")
        expected = renderer._fit(source, (14, 20))
        for _ in range(2):
            fitted = renderer._fit_character(source, (14, 20))
            assert pygame.image.tobytes(fitted, "RGBA") == pygame.image.tobytes(expected, "RGBA")
            assert pygame.image.tobytes(source, "RGBA") == original
    pygame.quit()


@pytest.mark.parametrize("atlas_available", [True, False])
def test_wordmark_pulse_preserves_rgba_for_a_complete_sweep(atlas_available):
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    base = renderer._load("ui/omarchy-wordmark.png")
    original = pygame.image.tobytes(base, "RGBA")
    if not atlas_available:
        renderer._load = lambda _path: (_ for _ in ()).throw(FileNotFoundError())
    # All positions, including the low-alpha antialiasing and offscreen edges.
    for tick in range(base.get_width() + 20):
        expected = base.copy()
        center = (tick * 2) % (base.get_width() + 20) - 10
        for x in range(max(0, center - 10), min(base.get_width(), center + 10)):
            falloff = 1.0 - abs(x - center) / 10
            for y in range(base.get_height()):
                color = base.get_at((x, y))
                if color.a >= 16:
                    expected.set_at((x, y), tuple(int(c + (t - c) * falloff)
                                    for c, t in zip(color[:3], (125, 207, 255))) + (color.a,))
        actual = renderer._wordmark_pulse(base, tick)
        assert pygame.image.tobytes(actual, "RGBA") == pygame.image.tobytes(expected, "RGBA"), tick
        assert pygame.image.tobytes(base, "RGBA") == original
    pygame.quit()


def test_shipped_scene_metadata_matches_opacity_and_size():
    manifests = list((asset_dir() / "fidelity").glob("*/ui/scene-backgrounds.json"))
    assert len(manifests) == 3
    for manifest in manifests:
        entries = json.loads(manifest.read_text())
        assert len(entries) == 4
        for name, entry in entries.items():
            with Image.open(manifest.parent / name) as image:
                assert entry["size"] == list(image.size)
                assert entry["opaque"] == (image.convert("RGBA").getchannel("A").getextrema() == (255, 255))


@pytest.mark.parametrize("metadata", ["opaque", "missing", "wrong-size", "transparent", "missing-art"])
@pytest.mark.parametrize("scale", [1, 2, 3])
def test_scene_background_cache_preserves_shading_and_fallback(tmp_path, metadata, scale):
    pygame.init()
    pygame.display.set_mode((96, 64))
    renderer = Renderer(ensure_assets=False)
    renderer.root = tmp_path
    renderer._iw, renderer._ih = 48 * scale, 32 * scale
    size = (renderer._iw, renderer._ih)
    source = pygame.Surface((48, 32), pygame.SRCALPHA)
    source.fill((37, 95, 150, 110 if metadata == "transparent" else 255))
    pygame.draw.rect(source, (231, 175, 80, 255), (8, 3, 22, 18))
    renderer._fid = lambda _sim, _rel: source
    directory = tmp_path / "ui"
    directory.mkdir()
    if metadata != "missing":
        (directory / "scene-backgrounds.json").write_text(json.dumps({"scene.png": {
            "size": [1, 1] if metadata == "wrong-size" else [48, 32], "opaque": metadata != "transparent"}}))
    if metadata == "missing-art":
        renderer._fid = lambda *_args: (_ for _ in ()).throw(FileNotFoundError())
    for shade in ((0, 0, 10, 44), (0, 0, 10, 92), (0, 0, 10, 44)):
        expected = pygame.Surface(size)
        expected.fill((100, 45, 16))
        actual = expected.copy()
        if metadata == "missing-art":
            expected.fill((8, 14, 24))
        else:
            expected.blit(pygame.transform.smoothscale(source, size), (0, 0))
        overlay = pygame.Surface(size, pygame.SRCALPHA)
        overlay.fill(shade)
        expected.blit(overlay, (0, 0))
        renderer._scene_background(actual, None, "ui/scene.png", shade, (8, 14, 24))
        assert pygame.image.tobytes(actual, "RGB") == pygame.image.tobytes(expected, "RGB")
    pygame.quit()


def test_prologue_hero_cache_preserves_pose_alpha_and_character_changes():
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    sources = [pygame.Surface((15, 24), pygame.SRCALPHA) for _ in range(2)]
    sources[0].fill((160, 210, 45, 120))
    sources[1].fill((75, 45, 180, 200))
    renderer._character_sprite = lambda sim, _pose: sources[sim.kind]
    for scale in (1, 3, 1):
        renderer._vs = scale
        for kind, flip, angle, alpha in ((0, False, -13.0, 255), (1, True, -5.0, 80),
                                         (0, False, -13.0, 90), (0, False, -13.0, 255)):
            source = sources[kind]
            expected = pygame.Surface((320 * scale, 180 * scale))
            expected.fill((8, 14, 24))
            actual = expected.copy()
            height = 45 * scale
            hero = renderer._fit(source, (round(source.get_width() / source.get_height() * height), height))
            if flip:
                hero = pygame.transform.flip(hero, True, False)
            hero = pygame.transform.rotozoom(hero, angle, 1.0)
            if alpha < 255:
                hero = hero.copy()
                hero.set_alpha(alpha)
            expected.blit(hero, hero.get_rect(center=(160 * scale, round((116 - 45 / 2) * scale))))
            renderer._prologue_hero(actual, SimpleNamespace(kind=kind), "prologue-transfer", 160, 116, 45,
                                   flip=flip, angle=angle, alpha=alpha)
            assert pygame.image.tobytes(actual, "RGB") == pygame.image.tobytes(expected, "RGB")
    pygame.quit()


@pytest.mark.parametrize("uniform_alpha", [False, True])
@pytest.mark.parametrize("kind", ["bomb", "convert", "penguin", "combat", "unknown"])
def test_flash_preserves_color_opacity_and_coverage(uniform_alpha, kind):
    pygame.init()
    pygame.display.set_mode((256, 256))
    renderer = Renderer(ensure_assets=False)
    renderer._use_surface_alpha_flash = uniform_alpha
    for size in ((256, 256), (512, 256), (256, 256)):
        renderer._iw, renderer._ih = size
        base = pygame.Surface(size)
        for x in range(size[0]):
            pygame.draw.line(base, (x % 256, (x * 3) % 256, 255 - x % 256), (x, 0), (x, size[1]))
        for tick in range(19):
            alpha = min(90, tick * 8)
            rgb = {"bomb": (125, 207, 255), "convert": (158, 206, 106),
                   "penguin": (232, 176, 64), "combat": (247, 118, 142)}.get(kind, (255, 255, 255))
            expected, actual = base.copy(), base.copy()
            overlay = pygame.Surface(size, pygame.SRCALPHA)
            overlay.fill((*rgb, alpha))
            expected.blit(overlay, (0, 0))
            renderer._flash(actual, SimpleNamespace(flash_kind=kind, flash_ticks=tick))
            tolerance = int(uniform_alpha)
            assert pygame.transform.threshold(None, actual, None, (tolerance, tolerance, tolerance, 255),
                                              set_behavior=0, search_surf=expected) == size[0] * size[1]
            if uniform_alpha:
                assert renderer._flash_overlay.get_masks()[3] == 0
                assert renderer._flash_overlay.get_alpha() == alpha
    pygame.quit()
