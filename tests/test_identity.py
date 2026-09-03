from omega_omarchy.generation import generate_world
from omega_omarchy.identity import WorldIdentity

SEED = "omega-fixture-1"


def test_fixture_identity_reproduces_across_clean_runs():
    first = generate_world(SEED, force_logo=True)
    second = generate_world(SEED, force_logo=True)
    assert first.identity.digest() == second.identity.digest()
    assert first.identity.to_record() == second.identity.to_record()
    assert first.seal_digest() == second.seal_digest()
    assert first.chapters[0]["tiles"] == second.chapters[0]["tiles"]


def test_identity_binds_seed_generator_schema_and_content():
    world = generate_world(SEED, force_logo=True)
    rec = world.identity.to_record()
    assert rec["seed"] == SEED
    assert rec["generatorVersion"] == "3.8.0"
    assert rec["schemaVersion"] == "1.0.0"
    assert rec["contentPackIds"] == ["omega-core-1"]
    assert rec["contentDigest"].startswith("sha256:")
    rebuilt = WorldIdentity.from_record(rec)
    assert rebuilt.digest() == world.identity.digest()


def test_different_seed_changes_identity():
    a = generate_world("alpha-seed", force_logo=True)
    b = generate_world("beta-seed", force_logo=True)
    assert a.identity.digest() != b.identity.digest()
