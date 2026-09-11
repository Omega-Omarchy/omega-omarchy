import numpy as np

from omega_omarchy.music_diagnostic import OUTPUT_RATE
from omega_omarchy.vocal_reintegration import (
    VOCAL_MIX_PROFILES,
    mix_vocal,
    shape_vocal,
    vocal_activity_envelope,
)
from omega_omarchy.guided_music import _region_envelope


def test_activity_envelope_suppresses_quiet_separator_residue():
    count = OUTPUT_RATE * 2
    guide = np.zeros((2, count))
    time = np.arange(count - OUTPUT_RATE) / OUTPUT_RATE
    guide[:, OUTPUT_RATE:] = np.sin(2.0 * np.pi * 220.0 * time) * 0.3

    envelope = vocal_activity_envelope(guide)

    assert envelope.shape == (count,)
    assert np.mean(envelope[: OUTPUT_RATE // 2]) < 0.1
    assert np.mean(envelope[OUTPUT_RATE + OUTPUT_RATE // 4 :]) > 0.8


def test_retro_vocal_shaping_is_deterministic_and_length_preserving():
    count = OUTPUT_RATE // 2
    time = np.arange(count) / OUTPUT_RATE
    source = np.vstack((np.sin(2 * np.pi * 220 * time), np.sin(2 * np.pi * 330 * time))) * 0.2

    first = shape_vocal(source, sample_rate=18_000, bits=10, drive=1.18)
    second = shape_vocal(source, sample_rate=18_000, bits=10, drive=1.18)

    assert first.shape == source.shape
    assert np.array_equal(first, second)


def test_polished_vocal_profile_is_gentler_than_sampled_profile():
    polished = VOCAL_MIX_PROFILES["omega-polished-vocal"]
    sampled = VOCAL_MIX_PROFILES["omega-sampled-vocal"]

    assert polished.sample_rate > sampled.sample_rate
    assert polished.bits > sampled.bits
    assert polished.drive < sampled.drive


def test_vocal_mix_ducks_only_during_activity():
    count = 1_000
    bed = np.full((2, count), 0.2)
    vocal = np.full((2, count), 0.1)
    activity = np.zeros(count)
    activity[count // 2 :] = 1.0
    profile = VOCAL_MIX_PROFILES["natural-vocal"]

    mixed = mix_vocal(bed, vocal, activity, profile)

    assert mixed.shape == (count, 2)
    assert np.allclose(mixed[: count // 2], 0.2)
    assert np.all(mixed[count // 2 :] > 0.2)


def test_authored_region_removes_confident_instrument_leakage():
    activity = np.ones(OUTPUT_RATE * 2)
    activity *= _region_envelope(activity.size, ((1.0, 2.0),), fade_seconds=0.1)

    assert np.all(activity[:OUTPUT_RATE] == 0.0)
    assert activity[OUTPUT_RATE + OUTPUT_RATE // 2] == 1.0
