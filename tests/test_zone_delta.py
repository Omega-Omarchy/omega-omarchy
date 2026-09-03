from omega_omarchy.generation import generate_world
from omega_omarchy.reachability import find_boss, find_spawn, validate_level
from omega_omarchy.zone_delta import apply_delta, make_delta, revert_delta


def _chapter():
    world = generate_world("omega-fixture-1", force_logo=True)
    chapter = world.chapters[0]
    return world, chapter


def test_valid_platform_apply_and_undo():
    world, chapter = _chapter()
    spawn = find_spawn(chapter["tiles"])
    ops = [{"op": "place", "x": spawn[0] + 2, "y": spawn[1] - 2, "tile": "="}]
    delta, report = make_delta(
        chapter,
        ops,
        world_digest=world.identity.digest(),
        generator_version=world.identity.generator_version,
        content_digest=world.identity.content_digest,
    )
    assert report["ok"], report["errors"]
    assert delta is not None
    applied = apply_delta(chapter, delta)
    assert applied["tiles"] != chapter["tiles"]
    restored = revert_delta(applied, chapter["tiles"])
    assert restored["tiles"] == chapter["tiles"]


def test_rejects_removing_boss_anchor():
    world, chapter = _chapter()
    bx, by = find_boss(chapter["tiles"])
    _, report = make_delta(
        chapter,
        [{"op": "remove", "x": bx, "y": by}],
        world_digest=world.identity.digest(),
        generator_version=world.identity.generator_version,
        content_digest=world.identity.content_digest,
    )
    assert not report["ok"]
    assert any("boss" in err or "anchor" in err or "cannot remove" in err for err in report["errors"])


def test_rejects_resource_abuse():
    world, chapter = _chapter()
    ops = [{"op": "place", "x": 3, "y": 3, "tile": "="} for _ in range(40)]
    _, report = make_delta(
        chapter,
        ops,
        world_digest=world.identity.digest(),
        generator_version=world.identity.generator_version,
        content_digest=world.identity.content_digest,
    )
    assert not report["ok"]
    assert any("resource-abuse" in err for err in report["errors"])


def test_rejects_blocking_boss():
    world, chapter = _chapter()
    bx, by = find_boss(chapter["tiles"])
    # wall off the boss tile's approach with solids across the row above the floor
    ops = []
    for x in range(max(0, bx - 3), min(len(chapter["tiles"][0]), bx + 4)):
        ops.append({"op": "place", "x": x, "y": by, "tile": "#"})
    _, report = make_delta(
        chapter,
        ops,
        world_digest=world.identity.digest(),
        generator_version=world.identity.generator_version,
        content_digest=world.identity.content_digest,
    )
    assert not report["ok"]
