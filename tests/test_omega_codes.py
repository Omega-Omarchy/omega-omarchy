from omega_omarchy.generation import generate_world
from omega_omarchy.omega_codes import decode_text, encode_text, render_qr, seed_payload
from omega_omarchy.sharing import encode_character_ref, encode_challenge, encode_ghost, encode_replay, GhostFrame


def test_seed_code_round_trip():
    world = generate_world("omega-fixture-1", force_logo=True)
    payload = seed_payload(world.identity.seed, world.identity.to_record())
    text = encode_text(payload)
    back = decode_text(text)
    assert back["kind"] == "seed"
    assert back["body"]["seed"] == "omega-fixture-1"
    assert back["body"]["identityDigest"] == world.identity.digest()
    image = render_qr(payload)
    assert image.size[0] > 16 and image.size[1] > 16


def test_character_challenge_replay_ghost_payloads():
    world = generate_world("omega-fixture-1", force_logo=True)
    digest = world.identity.digest()
    for payload in (
        encode_character_ref({"name": "Ada", "hair": "bun"}),
        encode_challenge("daily", "omega-fixture-1", digest, {"no-logic-bombs": True}),
        encode_replay("omega-fixture-1", digest, [{"tick": 0, "jump": True}]),
        encode_ghost("omega-fixture-1", digest, [GhostFrame(0, 1.0, 2.0, 1)]),
    ):
        assert decode_text(encode_text(payload))["kind"] == payload["kind"]


def test_corrupt_code_rejected():
    from omega_omarchy.omega_codes import OmegaCodeError
    import pytest

    with pytest.raises(OmegaCodeError):
        decode_text("{not-json")
    with pytest.raises(OmegaCodeError):
        decode_text('{"schema":"nope","kind":"seed","body":{},"digest":"sha256:00"}')
