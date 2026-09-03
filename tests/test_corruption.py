import pytest

from omega_omarchy.generation import generate_world
from omega_omarchy.identity import WorldIdentity
from omega_omarchy.omega_codes import OmegaCodeError, decode_text
from omega_omarchy.save import SaveError, make_save, validate_save


def test_truncated_identity_rejected():
    with pytest.raises(ValueError):
        WorldIdentity.from_record({"seed": "x"})


def test_unknown_difficulty_rejected():
    with pytest.raises(ValueError):
        generate_world("omega-fixture-1", difficulty="legendary")


def test_empty_omega_code_rejected():
    with pytest.raises(OmegaCodeError):
        decode_text("")


def test_save_missing_digest_rejected():
    world = generate_world("omega-fixture-1", force_logo=True)
    record = make_save(world.to_record(), {})
    del record["saveDigest"]
    with pytest.raises(SaveError):
        validate_save(record)
