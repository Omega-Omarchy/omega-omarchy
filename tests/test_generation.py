from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.generation import generate_world
from omega_omarchy.reachability import (
    ladder_endpoint_issues,
    normalize_ladder_tiles,
    penguin_issues,
    validate_level,
)


def test_web_chapter_one_generation_matches_the_first_full_world_chapter():
    full = generate_world("omega-fixture-1", force_logo=True)
    web = generate_world("omega-fixture-1", force_logo=True, chapter_ids=("corrupted-install",))
    assert [chapter["chapterId"] for chapter in web.chapters] == ["corrupted-install"]
    assert web.chapters[0]["tiles"] == full.chapters[0]["tiles"]


def test_every_chapter_completable_without_rare_events():
    world = generate_world("omega-fixture-1", force_logo=True)
    assert len(world.chapters) == len(CAMPAIGN_ROSTER)
    for chapter in world.chapters:
        report = validate_level(chapter["tiles"], require_logo=False)
        assert report["ok"], (chapter["chapterId"], report["errors"])
        assert report["bossReachableWithoutRare"]
        assert not ladder_endpoint_issues(chapter["tiles"])
        assert not penguin_issues(chapter["tiles"])
        assert all(
            penguin["supported"]
            and (penguin["reachable"] or penguin["reachableAfterBreaking"])
            for penguin in report["penguins"]
        )
        assert "+" in "".join(chapter["tiles"]), "each generated chapter should exercise a ladder/deck crossing"


def test_campaign_contains_oligarchy_singularity_goliath():
    world = generate_world("omega-fixture-1", force_logo=True)
    names = [chapter["name"] for chapter in world.chapters]
    bosses = [chapter["bossId"] for chapter in world.chapters]
    events = [event for chapter in world.chapters for event in chapter["events"]]
    assert "Goliath" in names
    assert "goliath" in bosses
    assert "oligarchy" in events
    assert "singularity" in events
    assert "singularity" in bosses


def test_forced_logo_is_optional_not_required():
    world = generate_world("omega-fixture-1", force_logo=True)
    chapter = world.chapters[0]
    report = validate_level(chapter["tiles"], require_logo=False)
    assert report["bossReachableWithoutRare"]
    # logo may exist for the edit showcase but is not required to finish
    logos = report["logos"]
    assert isinstance(logos, list)


def test_chapter_one_is_large_procedural_with_optional_logo_and_secret():
    world = generate_world("omega-fixture-1", force_logo=True)
    chapter = world.chapters[0]
    tiles = chapter["tiles"]
    assert chapter["height"] >= 18
    assert chapter["width"] >= 256
    assert chapter["algorithm"] == "macro-route-v13-descent-skyways"
    assert chapter["height"] >= 60
    assert chapter["macroSectors"] >= 6
    assert chapter["recipeCount"] >= 4
    assert chapter["pitCount"] >= 1
    report = validate_level(tiles, require_logo=False)
    assert report["ok"]
    assert report["logos"], "QA seed still places the optional OMARCHY logo"
    for x, y in report["logos"]:
        assert y < chapter["height"] - 8, "logo must sit on the upper route, not the main floor"
    secrets = report["optionalSecrets"]
    assert secrets, "sealed crate should exist"
    assert any(not item["reachable"] for item in secrets)
    assert all(item["reachableAfterBreaking"] for item in report["penguins"] if item["secret"])
    joined = "".join(tiles)
    assert "B" in joined and "C" in joined and "E" in joined and "X" in joined
    assert "L" in joined and "+" in joined


def test_procedural_seeds_change_geometry_but_reproduce_exactly():
    first = generate_world("procedural-a", force_logo=True)
    repeat = generate_world("procedural-a", force_logo=True)
    other = generate_world("procedural-b", force_logo=True)
    assert first.chapters[0]["tiles"] == repeat.chapters[0]["tiles"]
    assert first.chapters[0]["tiles"] != other.chapters[0]["tiles"]
    assert all(chapter["width"] >= 256 for chapter in first.chapters)
    assert first.receipt["generatorAlgorithm"] == "macro-route-v13-descent-skyways"


def test_macro_levels_include_sparse_steps_and_low_ground_without_touching_anchors():
    world = generate_world("ground-relief-fixture", force_logo=True)
    for chapter in world.chapters:
        contours = chapter["groundContours"]
        assert chapter["groundContourCount"] == len(contours)
        assert {entry["kind"] for entry in contours} == {"step", "low"}
        floor = chapter["height"] - 4
        tiles = chapter["tiles"]
        for entry in contours:
            x0 = int(entry["x"])
            span = int(entry["width"])
            if entry["kind"] == "step":
                assert all(tiles[floor - 1][x] == "#" for x in range(x0, x0 + span))
            else:
                assert all(tiles[floor][x] == "." for x in range(x0, x0 + span))


def test_pre_oligarchy_chapters_seed_multiple_edit_flight_pickups():
    world = generate_world("edit-pickup-density", force_logo=True)
    for chapter in world.chapters[:3]:
        assert chapter["editPickupCount"] >= 3, chapter["chapterId"]
        assert sum(row.count("O") for row in chapter["tiles"]) == chapter["editPickupCount"]


def test_hardware_chapter_is_split_by_unique_ethernet_and_wifi_edges():
    world = generate_world("hardware-network-fixture", force_logo=True)
    chapter = next(item for item in world.chapters if item["chapterId"] == "distro-front")
    links = chapter["networkLinks"]
    assert chapter["hardwareSegments"] == 4
    assert len(links) == 3
    assert len(chapter["maps"]) == 4
    assert sum(row.count("S") for row in chapter["maps"][0]["tiles"]) == 1
    assert sum(row.count("X") for row in chapter["maps"][-1]["tiles"]) == 1
    assert all(len(runtime_map["tiles"][0]) < len(chapter["tiles"][0]) for runtime_map in chapter["maps"])
    assert {link["protocol"] for link in links} == {"ethernet", "wifi"}
    operations = [
        operation
        for link in links
        for operation in (link["forwardOperation"], link["reverseOperation"])
    ]
    assert len(operations) == len(set(operations)) == 6
    assert sum(row.count("N") for row in chapter["tiles"]) == 6
    assert chapter["reachability"]["bossReachableWithoutRare"]


def test_edit_pickups_have_a_two_tile_ladder_moat_and_pits_contain_corrupt_code():
    world = generate_world("spatial-invariants", force_logo=True)
    for chapter in world.chapters:
        tiles = chapter["tiles"]
        ladders = {(x, y) for y, row in enumerate(tiles) for x, cell in enumerate(row) if cell in {"L", "+"}}
        pickups = [(x, y) for y, row in enumerate(tiles) for x, cell in enumerate(row) if cell == "O"]
        assert pickups
        for x, y in pickups:
            assert all(
                (xx, yy) not in ladders
                for yy in range(max(0, y - 2), min(len(tiles), y + 3))
                for xx in range(max(0, x - 2), min(len(tiles[0]), x + 3))
            )
        assert "M" in "".join(tiles)


def test_blocks_have_direct_support_or_two_clear_cells_and_dynamic_features_vary_traversal():
    world = generate_world("traversal-feature-invariants", force_logo=True)
    supports = {"#", "=", "+", "B", "D", "G"}
    for chapter in world.chapters:
        tiles = chapter["tiles"]
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if cell != "B":
                    continue
                distance = next(
                    (dy for dy in range(1, len(tiles) - y) if tiles[y + dy][x] in supports),
                    None,
                )
                assert distance is None or distance == 1 or distance >= 3
        assert len(chapter["tiltingPlatforms"]) >= 1
        assert all(4 <= int(spec["width"]) <= 6 for spec in chapter["tiltingPlatforms"])
        assert len(chapter["movingPlatforms"]) >= 1
        assert len(chapter["windColumns"]) >= 1


def test_ladder_platform_crossings_require_a_regular_adjacent_platform():
    world = generate_world("crossing-invariant", force_logo=True)
    for chapter in world.chapters:
        tiles = chapter["tiles"]
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if cell == "+":
                    left = row[x - 1] if x > 0 else "#"
                    right = row[x + 1] if x + 1 < len(row) else "#"
                    assert "=" in {left, right}, (chapter["chapterId"], x, y)


def test_orphan_crossing_is_downgraded_to_regular_ladder():
    tiles = [".....", "..+..", "..L..", "..L..", "#####"]
    normalized = normalize_ladder_tiles(tiles)
    assert normalized[1][2] == "L"


def test_ladders_never_end_under_impassable_tiles():
    tiles = [".......", ".BDG#=.", ".LLLLL.", "======="]
    normalized = normalize_ladder_tiles(tiles)
    impassable = {"#", "=", "B", "D", "G"}
    for y, row in enumerate(normalized[1:], start=1):
        for x, cell in enumerate(row):
            if cell in {"L", "+"}:
                assert normalized[y - 1][x] not in impassable


def test_procedural_levels_include_many_safe_floating_omarchy_blocks():
    world = generate_world("floating-block-invariant", force_logo=True)
    for chapter in world.chapters:
        tiles = chapter["tiles"]
        blocks = [(x, y) for y, row in enumerate(tiles) for x, cell in enumerate(row) if cell == "B"]
        floating = [(x, y) for x, y in blocks if y + 1 < len(tiles) and tiles[y + 1][x] == "."]
        assert chapter["floatingBlockCount"] >= 8
        assert len(floating) >= 8
        assert all(y + 1 >= len(tiles) or tiles[y + 1][x] not in {"L", "+"} for x, y in blocks)
