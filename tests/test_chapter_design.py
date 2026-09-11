"""Player-facing variety and traversal contracts for the Chapter 1 grammar."""

from copy import deepcopy

import pytest

from omega_omarchy.chapter_design import plan_chapter_one
from omega_omarchy.content import load_content
from omega_omarchy.generation import _paint_macro_level, assemble_chapter
from omega_omarchy.reachability import find_spawn, reachable_from, validate_level
from omega_omarchy.rng import Streams


@pytest.fixture(scope="module", params=[(seed, difficulty) for seed in range(4) for difficulty in ("casual", "standard", "precise")])
def chapter(request):
    seed, difficulty = request.param
    return assemble_chapter(
        load_content(), "corrupted-install", Streams(f"chapter-variety-{seed}"),
        difficulty=difficulty, include_optional=True, force_logo=True,
    )


def test_main_route_has_varied_decisions_and_uninterrupted_seams(chapter):
    sections = chapter["placements"]
    routes = [section["route"] for section in sections]
    assert len(set(routes)) >= 5
    assert all(a != b for a, b in zip(routes, routes[1:]))
    assert len({section["width"] for section in sections}) >= 3
    assert sections[0]["x"] == 20
    assert sections[-1]["x"] + sections[-1]["width"] == chapter["width"] - 24
    floor = chapter["height"] - 4
    for left, right in zip(sections, sections[1:]):
        assert left["x"] + left["width"] == right["x"]
        seam = right["x"]
        assert all(chapter["tiles"][floor][x] == "#" for x in range(seam - 1, seam + 2))


def test_opening_and_breather_have_no_hazards_or_moving_toys(chapter):
    sections = chapter["placements"]
    assert sections[0]["beat"] == "arrival"
    assert sections[1]["beat"] == "discovery"
    assert sections[-1]["beat"] == "climax"
    assert sum(s["beat"] == "breather" for s in sections) == 1
    for section in sections:
        if section["beat"] not in {"arrival", "breather"}:
            continue
        x0, end = section["x"], section["x"] + section["width"]
        assert not set("ME^") & set("".join(row[x0:end] for row in chapter["tiles"]))
        for key in ("movingPlatforms", "tiltingPlatforms", "windColumns"):
            for feature in chapter[key]:
                travel = feature.get("range", 0) if feature.get("axis") == "horizontal" else 0
                left = feature["x"] - travel
                right = feature["x"] + feature["width"] + travel
                assert right <= x0 or left >= end


def test_optional_rewards_are_supported_reachable_and_spread_through_chapter(chapter):
    tiles = chapter["tiles"]
    reached = reachable_from(tiles, find_spawn(tiles))
    logos = [(x, y) for y, row in enumerate(tiles) for x, glyph in enumerate(row) if glyph == "O"]
    assert len(logos) >= 3
    assert min(x for x, _ in logos) < chapter["width"] * 0.25
    assert max(x for x, _ in logos) > chapter["width"] * 0.75
    for x, y in logos:
        assert (x, y) in reached
        assert tiles[y + 1][x] in {"=", "+"}
    assert chapter["reachability"]["bossReachableWithoutRare"]
    assert chapter["attempt"] == 0


def test_no_consecutive_tower_or_staircase_reward_routes(chapter):
    family = {"sky-well": "tower", "twin-towers": "tower", "switchback": "stairs", "archive-stacks": "stairs"}
    branches = [family.get(s["branchRecipe"], "chain") for s in chapter["placements"] if s["branchRecipe"]]
    assert all(a != b for a, b in zip(branches, branches[1:]))


def test_moving_platforms_have_clear_travel_and_headroom(chapter):
    assert chapter["movingPlatforms"]
    for feature in chapter["movingPlatforms"]:
        dx = feature["range"] if feature["axis"] == "horizontal" else 0
        dy = feature["range"] if feature["axis"] == "vertical" else 0
        for y in range(feature["y"] - dy - 2, feature["y"] + dy + 2):
            for x in range(feature["x"] - dx, feature["x"] + feature["width"] + dx):
                assert chapter["tiles"][y][x] == ".", (feature, x, y)


def test_seed_changes_route_order_and_spacing_not_only_decoration():
    profile = load_content().chapter_profile("corrupted-install")["generation"]
    signatures = set()
    for seed in range(12):
        sections = plan_chapter_one(
            288, 32, tuple(profile["recipes"]), tuple(profile["sectorMotifs"]),
            Streams(f"plan-{seed}")["layout"], include_optional=True,
        )
        signatures.add(tuple((s["width"], s["route"], s["branchRecipe"], s["mirrored"]) for s in sections))
    assert len(signatures) == 12


@pytest.mark.parametrize("width,height,sector_width,optional", [(160, 32, 64, False), (160, 32, 20, True), (512, 96, 64, True), (256, 60, 32, False)])
def test_small_large_and_optional_free_content_profiles_still_complete(width, height, sector_width, optional):
    profile = deepcopy(load_content().chapter_profile("corrupted-install"))
    profile["generation"].update(widthBase=dict.fromkeys(("casual", "standard", "precise"), width), heightBase=height, sectorWidth=sector_width)
    c = _paint_macro_level(
        "corrupted-install", 0, Streams("profile-bounds"), difficulty="standard",
        include_optional=optional, force_logo=False, attempt=0, profile=profile,
    )
    report = validate_level(c["tiles"], require_all_logos=True)
    assert report["ok"], report["errors"]
    assert c["editPickupCount"] >= 3


def test_cosmetic_rng_draws_cannot_rewrite_chapter_one_collision():
    profile = load_content().chapter_profile("corrupted-install")
    first, changed = Streams("cosmetic-isolation"), Streams("cosmetic-isolation")
    for _ in range(31):
        changed["cosmetics"].random()
    options = dict(difficulty="standard", include_optional=True, force_logo=True, attempt=0, profile=profile)
    assert _paint_macro_level("corrupted-install", 0, first, **options)["tiles"] == _paint_macro_level("corrupted-install", 0, changed, **options)["tiles"]


def test_stranded_edit_reward_is_rejected_even_when_the_boss_is_reachable(chapter):
    tiles = list(chapter["tiles"])
    tiles[1] = tiles[1][:2] + "O" + tiles[1][3:]
    report = validate_level(tiles, require_all_logos=True)
    assert report["bossReachableWithoutRare"]
    assert not report["ok"]
    assert "logo-unreachable:2:1" in report["errors"]
