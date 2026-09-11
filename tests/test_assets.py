from PIL import Image
import numpy as np

from omega_omarchy.assets import _key_generated_studio, _layout_authored_parallax, _tone, asset_dir, build_assets
from omega_omarchy.physics import TILE
from omega_omarchy.presentation import CHAR_WORLD_HEIGHT, FIDELITIES, PARALLAX_LAYERS, canvas_size, view_scale


def test_square_tone_exact_crossings_are_platform_stable():
    tone = _tone(196, 0.4)
    assert tone.dtype == np.int32
    assert tone[0] == 0
    assert tone[225] == 0


def test_ots_is_separately_composed():
    root = build_assets(asset_dir())
    side = Image.open(root / "fidelity/sixteen-bit/characters/david_side-idle.png")
    ots = Image.open(root / "fidelity/sixteen-bit/characters/david_ots.png")
    assert ots.size != side.size
    assert ots.size[0] >= 40 and ots.size[1] >= 48
    blown = side.resize(ots.size, Image.NEAREST)
    assert list(ots.get_flattened_data()) != list(blown.get_flattened_data())


def test_fidelity_tiers_use_distinct_prepared_assets():
    root = build_assets(asset_dir())
    sizes = []
    hashes = []
    for fid in FIDELITIES:
        path = root / "fidelity" / fid / "characters" / "david_side-idle.png"
        assert path.is_file(), fid
        img = Image.open(path)
        sizes.append(img.size)
        hashes.append(list(img.get_flattened_data())[::17])
    assert sizes[0] != sizes[1] or sizes[1] != sizes[2]
    assert hashes[0] != hashes[1]
    assert hashes[1] != hashes[2]
    high = Image.open(root / "fidelity/high/characters/david_side-idle.png")
    sixteen = Image.open(root / "fidelity/sixteen-bit/characters/david_side-idle.png")
    blown = high.resize(sixteen.size, Image.NEAREST)
    assert list(sixteen.get_flattened_data()) != list(blown.get_flattened_data())


def test_high_david_skin_is_opaque():
    root = build_assets(asset_dir())
    img = Image.open(root / "fidelity/high/characters/david_side-idle.png").convert("RGBA")
    skin = 0
    for x in range(img.width):
        for y in range(img.height // 2):
            r, g, b, a = img.getpixel((x, y))
            if a > 200 and r > 150 and g > 90 and 60 < b < 180 and r > b:
                skin += 1
    assert skin > 20, "high-detail David should keep opaque skin"


def test_blocks_carry_readable_omarchy_mark():
    from omega_omarchy.assets import draw_block

    img = draw_block(32).convert("RGBA")
    mark = 0
    for px in img.get_flattened_data():
        if px[3] > 200 and px[1] > px[0] + 20 and px[1] > 140:
            mark += 1
    assert mark > 20, "OMARCHY plate should use lime glyph pixels"


def test_higher_fidelity_does_not_enlarge_world_footprint():
    assert [view_scale(fid) for fid in FIDELITIES] == [1, 2, 3]
    assert [canvas_size(fid) for fid in FIDELITIES] == [(320, 180), (640, 360), (960, 540)]
    for fidelity in FIDELITIES:
        raster = view_scale(fidelity)
        assert CHAR_WORLD_HEIGHT * raster / raster == CHAR_WORLD_HEIGHT
        assert TILE * raster / raster == TILE


def test_fidelity_canvases_gain_density_not_bigger_sprites_in_world_units():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    from omega_omarchy.render import Renderer
    from omega_omarchy.sim import GameSim

    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now()
    renderer = Renderer()
    sim.set_presentation(fidelity="sixteen-bit", display="clean")
    a = renderer.frame(sim)
    sim.set_presentation(fidelity="high", display="clean")
    b = renderer.frame(sim)
    sim.set_presentation(fidelity="ultra", display="clean")
    c = renderer.frame(sim)
    assert a.get_size() == (320, 180)
    assert b.get_size() == (640, 360)
    assert c.get_size() == (960, 540)
    pygame.quit()


def test_authored_animation_frames_are_distinct_and_fill_their_canvas():
    root = build_assets(asset_dir())
    for fidelity in FIDELITIES:
        folder = root / "fidelity" / fidelity / "characters"
        names = ("side-idle", "side-walk-0", "side-walk-2", "side-jump", "side-fall", "side-climb-0", "side-climb-1")
        images = {name: Image.open(folder / f"david_{name}.png").convert("RGBA") for name in names}
        assert images["side-walk-0"].tobytes() != images["side-walk-2"].tobytes(), fidelity
        assert images["side-jump"].tobytes() != images["side-fall"].tobytes(), fidelity
        assert images["side-climb-0"].tobytes() != images["side-climb-1"].tobytes(), fidelity
        assert images["side-climb-0"].tobytes() != images["side-idle"].tobytes(), fidelity
        for name in ("side-walk-0", "side-walk-2", "side-jump", "side-climb-0"):
            bbox = images[name].getchannel("A").getbbox()
            assert bbox is not None
            assert bbox[3] - bbox[1] >= images[name].height * 0.82, (fidelity, name, bbox)
        assert not list(folder.glob("_tmp_*.png"))


def test_expanded_climb_and_air_action_sets_are_authored():
    root = build_assets(asset_dir())
    for fidelity in FIDELITIES:
        folder = root / "fidelity" / fidelity / "characters"
        climbs = [Image.open(folder / f"david_side-climb-{i}.png").convert("RGBA") for i in range(4)]
        assert len({image.tobytes() for image in climbs}) == 4
        air = Image.open(folder / "david_side-air-action.png").convert("RGBA")
        jump = Image.open(folder / "david_side-jump.png").convert("RGBA")
        assert air.tobytes() != jump.tobytes()


def test_walk_cycle_has_opposite_contacts_and_non_idle_passing_poses():
    root = build_assets(asset_dir())
    for fidelity in FIDELITIES:
        folder = root / "fidelity" / fidelity / "characters"
        idle = Image.open(folder / "david_side-idle.png").convert("RGBA")
        frames = [Image.open(folder / f"david_side-walk-{i}.png").convert("RGBA") for i in range(4)]
        assert len({frame.tobytes() for frame in frames}) == 4
        assert frames[0].tobytes() != frames[2].tobytes()
        assert frames[1].tobytes() != idle.tobytes()
        assert frames[3].tobytes() != idle.tobytes()


def test_regenerated_walk_item_bouncer_and_crossing_masters_are_integrated():
    root = build_assets(asset_dir())
    source = root / "source" / "rendered"
    for name in (
        "david-ultra-walk-contact-a-v5.png",
        "david-ultra-walk-passing-a-v5.png",
        "david-ultra-walk-contact-b-v5.png",
        "david-ultra-walk-passing-b-v5.png",
        "david-ultra-slide-v2.png",
        "david-ultra-throw.png",
        "bouncer-ultra.png",
        "item-penguin-flock-ultra.png",
    ):
        assert (source / name).is_file(), name
    for fidelity in FIDELITIES:
        tier = root / "fidelity" / fidelity
        assert (tier / "tiles" / "corrupted_+.png").is_file()
        assert (tier / "tiles" / "corrupted_^.png").is_file()
        flock = Image.open(tier / "items" / "penguin-flock.png").convert("RGBA")
        penguin = Image.open(tier / "items" / "penguin.png").convert("RGBA")
        assert flock.tobytes() != penguin.tobytes(), fidelity


def test_oligarchy_hud_uses_vendored_block_geometry():
    root = build_assets(asset_dir())
    source = Image.open(root / "source" / "branding" / "oligarchy-logo-official.png").convert("RGBA")
    hud = Image.open(root / "ui" / "oligarchy-logo-hud.png").convert("RGBA")
    assert source.width / source.height > 5
    assert hud.width / hud.height > 5
    assert hud.getchannel("A").getbbox() is not None


def test_portraits_have_matching_coverage_and_no_chroma_fringe():
    root = build_assets(asset_dir())
    coverage = []
    for fidelity in FIDELITIES:
        image = Image.open(root / "fidelity" / fidelity / "characters" / "david_portrait.png").convert("RGBA")
        bbox = image.getchannel("A").getbbox()
        assert bbox is not None
        coverage.append(((bbox[2] - bbox[0]) / image.width, (bbox[3] - bbox[1]) / image.height))
        keyed = 0
        for r, g, b, a in image.get_flattened_data():
            if a > 32 and r > 120 and b > 85 and r > g * 1.5 and b > g * 1.35 and abs(r - b) < 105:
                keyed += 1
        assert keyed == 0, (fidelity, keyed)
    assert max(value[0] for value in coverage) - min(value[0] for value in coverage) < 0.22
    assert max(value[1] for value in coverage) - min(value[1] for value in coverage) < 0.22


def test_dedicated_event_model_items_and_enemy_motifs_ship_at_every_tier():
    root = build_assets(asset_dir())
    enemy_ids = (
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
    item_ids = ("logic-bomb", "patch-cable", "manifest", "penguin-flock", "fork-beacon", "checksum-key", "mirror-cache", "touch-grass-usb", "kick")
    for fidelity in FIDELITIES:
        tier = root / "fidelity" / fidelity
        away = Image.open(tier / "characters" / "david_away.png").convert("RGBA")
        climb = Image.open(tier / "characters" / "david_side-climb-0.png").convert("RGBA")
        assert away.tobytes() != climb.tobytes()
        for item in item_ids:
            assert (tier / "items" / f"{item}.png").is_file()
        for enemy in enemy_ids:
            assert (tier / "enemies" / f"{enemy}.png").is_file()
            assert (tier / "enemies" / f"{enemy}-converted.png").is_file()


def test_patch_cable_negative_space_and_companion_variants_are_authored():
    root = build_assets(asset_dir())
    for fidelity in FIDELITIES:
        patch = Image.open(root / "fidelity" / fidelity / "items" / "patch-cable.png").convert("RGBA")
        assert patch.getpixel((patch.width // 2, patch.height // 3))[3] == 0, fidelity

        detractor = np.array(Image.open(root / "fidelity" / fidelity / "enemies" / "detractabot.png").convert("RGBA"))
        converted = np.array(Image.open(root / "fidelity" / fidelity / "enemies" / "detractabot-converted.png").convert("RGBA"))
        assert detractor.tobytes() != converted.tobytes(), fidelity
        if fidelity == "ultra":
            purple = (detractor[:, :, 0] > 80) & (detractor[:, :, 2] > 100) & (detractor[:, :, 1] < detractor[:, :, 0] * 0.75)
            converted_purple = (converted[:, :, 0] > 80) & (converted[:, :, 2] > 100) & (converted[:, :, 1] < converted[:, :, 0] * 0.75)
            ordinary_green = (detractor[:, :, 1] > detractor[:, :, 0] * 1.35) & (detractor[:, :, 1] > detractor[:, :, 2] * 1.25)
            green = (converted[:, :, 1] > converted[:, :, 0] * 1.35) & (converted[:, :, 1] > converted[:, :, 2] * 1.25)
            assert int(purple.sum()) > 8
            assert int(green.sum()) > 20
            assert int(purple.sum()) > int(converted_purple.sum())
            assert int(green.sum()) > int(ordinary_green.sum())
            sign_alpha = detractor[: detractor.shape[0] // 2, :, 3] > 24
            sign_columns = np.where(sign_alpha.any(axis=0))[0]
            assert sign_columns.size / detractor.shape[1] >= 0.9

        justice = Image.open(root / "fidelity" / fidelity / "enemies" / "justice-signaler-converted.png").convert("RGBA")
        ordinary = Image.open(root / "fidelity" / fidelity / "enemies" / "justice-signaler.png").convert("RGBA")
        assert justice.tobytes() != ordinary.tobytes(), fidelity


def test_pause_portraits_and_full_boss_roster_follow_fidelity():
    root = build_assets(asset_dir())
    boss_ids = (
        "package-bureaucrat",
        "dependency-hydra",
        "distro-commander",
        "garden-gatekeeper",
        "singularity",
        "goliath",
        "goliath-cyborg-penguin",
        "dogma-sprite",
    )
    portrait_sizes = []
    boss_sizes = []
    for fidelity in FIDELITIES:
        tier = root / "fidelity" / fidelity
        portrait = Image.open(tier / "characters" / "david_portrait.png")
        cyborg_penguin = Image.open(
            tier / "bosses" / "goliath-cyborg-penguin.png"
        ).convert("RGBA")
        portrait_sizes.append(portrait.size)
        boss_sizes.append(Image.open(tier / "bosses" / "goliath.png").size)
        assert cyborg_penguin.getchannel("A").getextrema() == (0, 255)
        assert cyborg_penguin.getchannel("A").getbbox() is not None
        for boss_id in boss_ids:
            assert (tier / "bosses" / f"{boss_id}.png").is_file()
            assert (tier / "bosses" / f"{boss_id}-converted.png").is_file()
    assert portrait_sizes == [(48, 48), (64, 64), (96, 96)]
    assert boss_sizes[0][0] < boss_sizes[1][0] < boss_sizes[2][0]


def test_generated_source_art_is_versioned_in_the_repo():
    from omega_omarchy.spritekit import session_images

    source = session_images()
    assert source == asset_dir() / "source" / "rendered"
    assert (source / "david-ultra-walk-contact-a-v2.png").is_file()
    assert (source / "david-ultra-walk-contact-b-v2.png").is_file()
    assert (source / "david-ultra-kick.png").is_file()
    assert (source / "omega-ultra-environment-panorama.png").is_file()
    assert (source / "omega-ultra-environment-install-chamber.png").is_file()
    assert (source / "omega-ultra-environment-hardware.png").is_file()
    overlay = Image.open(source / "omega-ultra-overlay-hardware.png").convert("RGBA")
    assert overlay.getchannel("A").getextrema()[0] == 0
    for index in range(1, 5):
        dedicated = Image.open(
            source / f"omega-ultra-overlay-hardware-island-{index}-v1.png"
        ).convert("RGBA")
        assert dedicated.getchannel("A").getextrema()[0] == 0
    for chapter in ("wilderness", "front", "garden", "singularity", "goliath"):
        assert (source / f"omega-ultra-environment-{chapter}.png").is_file()
    assert (source / "omega-ultra-ui-frame.png").is_file()
    assert (source / "goliath.png").is_file()
    assert (source / "goliath-cyborg-penguin-ultra.png").is_file()
    for name in (
        "enemy-cow-ultra-v1.png",
        "enemy-llama-ultra-v1.png",
        "omega-ultra-environment-cow-level-v1.png",
        "omega-ultra-prologue-campus-v1.png",
        "omega-ultra-prologue-transfer-v1.png",
        "omega-ultra-prologue-rift-v1.png",
        "omega-ultra-stage-world-map-v1.png",
        "omega-ultra-secret-door-v1.png",
        "david-ultra-prologue-captured-pose-v1.png",
        "david-ultra-prologue-transfer-pose-v1.png",
        "omega-ultra-network-wifi-overlay-v3.png",
        "omega-ultra-overlay-hardware-plane-4-v3.png",
        "omega-ultra-parallax-front-near-v4.png",
        "omega-ultra-parallax-garden-far-v4.png",
        "omega-ultra-parallax-garden-far-v5.png",
        "omega-ultra-parallax-garden-mid-v4.png",
        "omega-ultra-parallax-garden-near-v4.png",
    ):
        assert (source / name).is_file()


def test_snes_floor_keeps_modeled_color_and_panorama_layers_never_duplicate():
    root = build_assets(asset_dir())
    tile = Image.open(root / "fidelity/sixteen-bit/tiles/wilderness_#.png").convert("RGBA")
    colors = {pixel for pixel in tile.get_flattened_data() if pixel[3]}
    assert len(colors) >= 24, "16-bit tiles should retain SNES-class material shading"
    palettes = ("corrupted", "wilderness", "front", "garden", "singularity", "goliath", "cow")
    for fidelity in FIDELITIES:
        first_layers = []
        for palette in palettes:
            folder = root / "fidelity" / fidelity / "bg" / palette
            layers = [Image.open(path).convert("RGBA") for path in sorted(folder.glob("parallax-*.png"))]
            assert len({layer.tobytes() for layer in layers}) == len(layers), (fidelity, palette)
            assert all(layer.width > 320 * view_scale(fidelity) for layer in layers)
            first_layers.append(layers[0].resize((64, 32)).tobytes())
        assert len(set(first_layers)) == len(palettes), fidelity
        foregrounds = [
            Image.open(root / "fidelity" / fidelity / "bg/front" / f"foreground-{index}.png").convert("RGBA")
            for index in range(1, 5)
        ]
        assert len({foreground.tobytes() for foreground in foregrounds}) == 4
        assert all(foreground.getchannel("A").getextrema()[0] == 0 for foreground in foregrounds)
        assert all(foreground.size == canvas_size(fidelity) for foreground in foregrounds)


def test_ultra_effect_masters_and_opaque_parallax_derive_all_fidelity_tiers():
    root = build_assets(asset_dir())
    sizes = []
    for fidelity in FIDELITIES:
        effects = root / "fidelity" / fidelity / "effects"
        corruption = Image.open(effects / "corruption-code.png").convert("RGBA")
        wind = Image.open(effects / "wind-column.png").convert("RGBA")
        sizes.append((corruption.size, wind.size))
        rgb = np.asarray(corruption)[:, :, :3]
        assert float(rgb[:, :, 0].mean()) > float(rgb[:, :, 1].mean()) * 1.8
        assert wind.getchannel("A").getextrema() == (0, 255)
    assert sizes[0][0][0] < sizes[1][0][0] < sizes[2][0][0]
    assert sizes[0][1][1] < sizes[1][1][1] < sizes[2][1][1]

    near = Image.open(root / "fidelity/ultra/bg/corrupted/parallax-1.png").convert("RGBA")
    alpha = np.asarray(near.getchannel("A"))
    visible = alpha[alpha > 0]
    assert visible.size
    assert float((visible >= 240).mean()) > 0.80, "visible structures should be opaque, not blanket-faded"


def test_authored_parallax_plane_is_never_chopped_into_internal_pieces():
    master = Image.new("RGBA", (240, 100), (30, 90, 140, 255))
    strip = _layout_authored_parallax(master, (320, 180), 2)
    alpha = np.asarray(strip.getchannel("A"))
    occupied = np.any(alpha > 0, axis=0)
    runs = int(occupied[0]) + int(np.count_nonzero(occupied[1:] & ~occupied[:-1]))
    assert runs == 1


def test_branded_blocks_and_network_interstitials_derive_from_ultra_masters():
    root = build_assets(asset_dir())
    source = root / "source" / "rendered"
    for protocol in ("ethernet", "wifi"):
        assert (source / f"omega-ultra-network-{protocol}-v1.png").is_file()
        assert (source / f"omega-ultra-network-{protocol}-overlay-v2.png").is_file()
        for fidelity in FIDELITIES:
            frame = Image.open(root / "fidelity" / fidelity / "ui" / f"network-{protocol}.png")
            overlay = Image.open(
                root / "fidelity" / fidelity / "ui" / f"network-{protocol}-overlay.png"
            ).convert("RGBA")
            assert frame.size == canvas_size(fidelity)
            assert overlay.size == canvas_size(fidelity)
            assert overlay.getchannel("A").getextrema() == (0, 255)
            alpha = np.asarray(overlay.getchannel("A"))
            assert not alpha[0].any() and not alpha[-1].any()
            assert not alpha[:, 0].any() and not alpha[:, -1].any()

    minimum_width = {"sixteen-bit": 9, "high": 20, "ultra": 40}
    for fidelity in FIDELITIES:
        block = np.asarray(Image.open(root / "fidelity" / fidelity / "items" / "block.png").convert("RGBA"))
        mark = (block[:, :, 1] > block[:, :, 0] * 1.12) & (block[:, :, 1] > block[:, :, 2] * 1.12) & (block[:, :, 3] > 64)
        ys, xs = np.where(mark)
        assert xs.size, fidelity
        assert int(xs.max() - xs.min() + 1) >= minimum_width[fidelity]


def test_exit_sign_reads_as_a_lit_building_code_plaque():
    from omega_omarchy.assets import draw_exit_sign

    sign = draw_exit_sign((56, 18))
    pixels = np.asarray(sign.convert("RGBA"))
    red = (pixels[:, :, 0] > 120) & (pixels[:, :, 1] < 90) & (pixels[:, :, 3] > 200)
    assert red.any()
    assert pixels[0, 0, 3] > 0 or pixels[9, 28, 3] > 0


def test_cow_level_door_and_prologue_art_derive_for_every_fidelity():
    root = build_assets(asset_dir())
    sizes = []
    for fidelity in FIDELITIES:
        tier = root / "fidelity" / fidelity
        door = Image.open(tier / "items" / "omega-door.png").convert("RGBA")
        cow = Image.open(tier / "enemies" / "cow.png").convert("RGBA")
        llama = Image.open(tier / "enemies" / "llama.png").convert("RGBA")
        campus = Image.open(tier / "ui" / "prologue-campus.png").convert("RGBA")
        transfer = Image.open(tier / "ui" / "prologue-transfer.png").convert("RGBA")
        rift = Image.open(tier / "ui" / "prologue-rift.png").convert("RGBA")
        world_map = Image.open(tier / "ui" / "stage-world-map.png").convert("RGBA")
        captured_pose = Image.open(tier / "characters" / "david_prologue-captured.png").convert("RGBA")
        transfer_pose = Image.open(tier / "characters" / "david_prologue-transfer.png").convert("RGBA")
        assert door.getchannel("A").getextrema()[0] == 0
        assert cow.getchannel("A").getextrema()[0] == 0
        assert llama.getchannel("A").getextrema()[0] == 0
        assert campus.size == canvas_size(fidelity)
        assert transfer.size == canvas_size(fidelity)
        assert rift.size == canvas_size(fidelity)
        assert world_map.size == canvas_size(fidelity)
        assert captured_pose.getchannel("A").getextrema() == (0, 255)
        assert transfer_pose.getchannel("A").getextrema() == (0, 255)
        assert len(list((tier / "bg" / "cow").glob("parallax-*.png"))) == PARALLAX_LAYERS[fidelity]
        sizes.append(door.size)
    assert sizes[0][0] < sizes[1][0] < sizes[2][0]


def test_cow_and_hardware_use_complete_dedicated_transparent_planes():
    root = build_assets(asset_dir())
    source = root / "source" / "rendered"
    for depth in ("far", "mid", "near"):
        assert (source / f"omega-ultra-parallax-cow-{depth}-v4.png").is_file()
    for index in range(1, 5):
        master = Image.open(
            source / f"omega-ultra-overlay-hardware-plane-{index}-v2.png"
        ).convert("RGBA")
        assert master.getchannel("A").getextrema() == (0, 255)
    cow_layers = [
        Image.open(root / "fidelity" / "ultra" / "bg" / "cow" / f"parallax-{index}.png").convert("RGBA")
        for index in range(1, 4)
    ]
    assert len({layer.tobytes() for layer in cow_layers}) == 3
    assert all(layer.getchannel("A").getextrema()[0] == 0 for layer in cow_layers)


def test_map_title_font_is_vendored_into_runtime_assets():
    root = build_assets(asset_dir())
    assert (root / "source" / "fonts" / "omarchy-font.ttf").stat().st_size == 7744
    assert (root / "ui" / "omarchy-font.ttf").read_bytes() == (
        root / "source" / "fonts" / "omarchy-font.ttf"
    ).read_bytes()
    assert (root / "ui" / "OMARCHY-FONT-LICENSE.txt").read_bytes() == (
        root / "source" / "fonts" / "OMARCHY-FONT-LICENSE.txt"
    ).read_bytes()


def test_powered_artifact_is_the_selected_mask_safe_application_icon(tmp_path):
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame

    from omega_omarchy.app import _set_window_icon
    from omega_omarchy.web_build import stage_web

    root = build_assets(asset_dir())
    branding = root / "source" / "branding"
    assert (branding / "omega-omarchy-logo-powered-artifact.png").read_bytes() == (
        branding / "omega-omarchy-logo-concepts" / "variant-02-powered-artifact.png"
    ).read_bytes()
    for size in (32, 64, 128, 256, 512):
        icon = Image.open(root / "ui" / f"omega-omarchy-icon-{size}.png").convert("RGBA")
        assert icon.size == (size, size)
        assert icon.getchannel("A").getextrema() == (0, 255)
        bbox = icon.getchannel("A").getbbox()
        assert bbox is not None
        assert min(bbox[0], bbox[1], size - bbox[2], size - bbox[3]) >= size // 25
    assert (root / "ui" / "omega-omarchy-icon.png").read_bytes() == (
        root / "ui" / "omega-omarchy-icon-256.png"
    ).read_bytes()

    pygame.init()
    pygame.display.set_mode((32, 32))
    assert _set_window_icon()
    pygame.quit()

    web = stage_web(tmp_path / "web")
    assert "run_game_async" in (web / "main.py").read_text(encoding="utf-8")
    assert (web / "favicon.png").read_bytes() == (
        root / "ui" / "omega-omarchy-icon-256.png"
    ).read_bytes()


def test_cow_level_animals_keep_their_authored_colors_after_conversion():
    root = build_assets(asset_dir())
    for fidelity in FIDELITIES:
        enemies = root / "fidelity" / fidelity / "enemies"
        for animal in ("cow", "llama"):
            ordinary = Image.open(enemies / f"{animal}.png").convert("RGBA")
            converted = Image.open(enemies / f"{animal}-converted.png").convert("RGBA")
            assert ordinary.tobytes() == converted.tobytes(), (fidelity, animal)


def test_cow_cannon_and_full_height_gate_derive_from_new_ultra_masters():
    root = build_assets(asset_dir())
    source = root / "source" / "rendered"
    assert (source / "omega-ultra-cow-cannon-v1.png").is_file()
    assert (source / "omega-ultra-cow-cannon-barrel-v2.png").is_file()
    assert (source / "omega-ultra-cow-cannon-base-v2.png").is_file()
    assert (source / "omega-ultra-tile-gate-v4.png").is_file()
    widths = []
    for fidelity in FIDELITIES:
        barrel = Image.open(root / "fidelity" / fidelity / "items" / "cow-cannon-barrel.png").convert("RGBA")
        base = Image.open(root / "fidelity" / fidelity / "items" / "cow-cannon-base.png").convert("RGBA")
        gate = Image.open(root / "fidelity" / fidelity / "tiles" / "cow_G.png").convert("RGBA")
        assert barrel.getchannel("A").getextrema() == (0, 255)
        assert base.getchannel("A").getextrema() == (0, 255)
        assert gate.getchannel("A").getextrema()[1] == 255
        assert barrel.width > base.width
        widths.append(barrel.width)
    assert widths[0] < widths[1] < widths[2]


def test_studio_key_only_removes_edge_connected_neutral_backdrop():
    plate = Image.new("RGBA", (40, 28), (238, 238, 238, 255))
    pixels = np.asarray(plate).copy()
    pixels[5:23, 7:33, :3] = (24, 80, 116)
    pixels[9:19, 12:28, :3] = (150, 150, 150)
    keyed = _key_generated_studio(Image.fromarray(pixels, "RGBA"))
    alpha = np.asarray(keyed.getchannel("A"))
    assert alpha[0, 0] == 0
    assert alpha[14, 20] == 255, "enclosed neutral material is artwork, not studio matte"

    black_plate = Image.new("RGBA", (24, 18), (0, 0, 0, 255))
    dark_pixels = np.asarray(black_plate).copy()
    dark_pixels[4:15, 5:20, :3] = (10, 14, 20)
    dark_alpha = np.asarray(
        _key_generated_studio(Image.fromarray(dark_pixels, "RGBA")).getchannel("A")
    )
    assert dark_alpha[0, 0] == 0
    assert dark_alpha[9, 12] == 255, "dark modeled material must survive a black plate"


def test_explicit_ultra_structure_and_chapter_parallax_masters_drive_the_bake():
    root = build_assets(asset_dir())
    source = root / "source" / "rendered"
    structural = {
        "#": "solid",
        "=": "platform",
        "L": "ladder",
        "D": "breakable",
        "G": "gate",
    }
    for kind, name in structural.items():
        master = source / f"omega-ultra-tile-{name}-v3.png"
        assert master.is_file(), master.name
        tile = Image.open(root / "fidelity" / "ultra" / "tiles" / f"corrupted_{kind}.png").convert("RGBA")
        assert tile.size == (64, 64)
        assert len({pixel for pixel in tile.get_flattened_data() if pixel[3]}) > 128
    ladder = Image.open(root / "fidelity" / "ultra" / "tiles" / "corrupted_L.png").convert("RGBA")
    platform = Image.open(root / "fidelity" / "ultra" / "tiles" / "corrupted_=.png").convert("RGBA")
    assert ladder.getchannel("A").getextrema() == (0, 255)
    assert platform.getchannel("A").getpixel((32, 63)) == 0
    assert ladder.getchannel("A").getbbox()[2] - ladder.getchannel("A").getbbox()[0] >= 54
    assert platform.getchannel("A").getbbox()[3] >= 48

    for palette in ("corrupted", "wilderness", "front", "garden", "singularity", "goliath"):
        for index, depth in enumerate(("far", "mid", "near"), start=1):
            master = Image.open(source / f"omega-ultra-parallax-{palette}-{depth}-v3.png").convert("RGBA")
            ultra = Image.open(
                root / "fidelity" / "ultra" / "bg" / palette / f"parallax-{index}.png"
            ).convert("RGBA")
            ultra_canvas = canvas_size("ultra")
            expected_ultra_width = round((1500 - index * 90) * ultra_canvas[1] / 180)
            assert ultra.size == (expected_ultra_width, ultra_canvas[1]), (palette, depth)
            alpha = np.asarray(ultra.getchannel("A"))
            assert float((alpha == 0).mean()) > 0.04, (palette, depth)
            visible = alpha[alpha > 0]
            assert float((visible >= 240).mean()) > 0.65, (palette, depth)
            assert float(((alpha > 0) & (alpha < 240)).mean()) < 0.03, (palette, depth)
            for fidelity in ("high", "sixteen-bit"):
                if index >= PARALLAX_LAYERS[fidelity]:
                    continue
                derived = Image.open(
                    root / "fidelity" / fidelity / "bg" / palette / f"parallax-{index}.png"
                )
                tier_canvas = canvas_size(fidelity)
                expected_width = round((1500 - index * 90) * tier_canvas[1] / 180)
                assert derived.size == (expected_width, tier_canvas[1])


def test_hud_uses_official_wide_logo_geometry():
    root = build_assets(asset_dir())
    logo = Image.open(root / "ui/omarchy-logo-hud.png").convert("RGBA")
    bbox = logo.getchannel("A").getbbox()
    assert bbox is not None
    assert (bbox[2] - bbox[0]) / (bbox[3] - bbox[1]) > 4.0
