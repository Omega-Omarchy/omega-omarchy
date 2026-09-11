import numpy as np

from omega_omarchy.guided_music import (
    GUIDED_MIX_PROFILES,
    _region_envelope,
    _symbolic_premix,
    normalize_activity_presence,
    synthesize_conditioned_saw,
    synthesize_performance_guided_lead,
)
from omega_omarchy.music_diagnostic import (
    OUTPUT_RATE,
    OMEGA_CHIP_PROFILES,
    SourceProvenance,
    SymbolicArrangement,
    SymbolicNote,
    SynthFingerprint,
)


def _fingerprint() -> SynthFingerprint:
    return SynthFingerprint(
        schema_version=1,
        source_sha256="test",
        source_offset=0.0,
        duration=1.0,
        sample_rate=OUTPUT_RATE,
        fundamental_median_hz=110.0,
        harmonic_levels=(1.0, 0.48, 0.29, 0.18, 0.12, 0.08),
        noise_mix=0.01,
        stereo_width=0.8,
        stereo_correlation=0.2,
        attack=0.01,
        decay=0.2,
        sustain=0.6,
        release=0.1,
        vibrato_rate_hz=5.0,
        vibrato_depth_cents=4.0,
        selected_windows=(),
    )


def test_guided_profiles_test_distinct_sources_of_fidelity():
    assert set(GUIDED_MIX_PROFILES) == {
        "balanced-guided",
        "rhythm-locked",
        "saw-led",
        "phrase-balanced",
        "phrase-bend",
    }
    assert all(profile.symbolic_lead for profile in GUIDED_MIX_PROFILES.values())
    assert all(profile.lead_gain == 0 for profile in GUIDED_MIX_PROFILES.values())
    assert GUIDED_MIX_PROFILES["rhythm-locked"].drum_gain > GUIDED_MIX_PROFILES["balanced-guided"].drum_gain
    assert GUIDED_MIX_PROFILES["saw-led"].bass_gain > GUIDED_MIX_PROFILES["balanced-guided"].bass_gain
    assert GUIDED_MIX_PROFILES["saw-led"].synth_gain > GUIDED_MIX_PROFILES["balanced-guided"].synth_gain
    assert GUIDED_MIX_PROFILES["phrase-balanced"].lead_articulation_depth > 0
    assert GUIDED_MIX_PROFILES["phrase-bend"].lead_pitch_bend_depth > 0


def test_conditioned_saw_is_deterministic_and_source_gated():
    count = OUTPUT_RATE // 2
    frequency = np.linspace(110.0, 146.83, count)
    amplitude = np.ones(count)
    amplitude[: count // 4] = 0.0

    first = synthesize_conditioned_saw(
        frequency, amplitude, voice="synth", fingerprint=_fingerprint()
    )
    second = synthesize_conditioned_saw(
        frequency, amplitude, voice="synth", fingerprint=_fingerprint()
    )

    assert first.shape == (count, 2)
    assert np.array_equal(first, second)
    assert np.max(np.abs(first[: count // 4])) == 0.0
    assert np.max(np.abs(first[count // 3 :])) > 0.1
    assert not np.array_equal(first[:, 0], first[:, 1])


def test_adaptive_presence_lifts_phrases_but_not_silence_or_sparse_leakage():
    amplitude = np.zeros(OUTPUT_RATE * 4)
    amplitude[OUTPUT_RATE // 2 : OUTPUT_RATE] = 0.05
    amplitude[OUTPUT_RATE : OUTPUT_RATE * 2] = 0.8
    amplitude[OUTPUT_RATE * 3 : OUTPUT_RATE * 3 + OUTPUT_RATE // 50] = 0.05

    adjusted = normalize_activity_presence(
        amplitude,
        target_level=0.42,
        max_boost=4.0,
        window_seconds=0.5,
        min_activity=0.05,
    )

    assert np.max(adjusted[: OUTPUT_RATE // 2]) == 0.0
    assert np.median(adjusted[OUTPUT_RATE * 3 // 4 : OUTPUT_RATE]) > 0.12
    assert np.allclose(adjusted[OUTPUT_RATE : OUTPUT_RATE * 2], 0.8)
    assert np.max(adjusted[OUTPUT_RATE * 3 : OUTPUT_RATE * 3 + OUTPUT_RATE // 50]) < 0.075


def test_region_envelope_uses_bounded_smooth_edges():
    envelope = _region_envelope(OUTPUT_RATE * 2, ((0.5, 1.5),))

    assert np.all(envelope[: OUTPUT_RATE // 2] == 0.0)
    assert 0.0 < envelope[OUTPUT_RATE // 2 + 1] < 1.0
    assert envelope[OUTPUT_RATE] == 1.0
    assert 0.0 < envelope[OUTPUT_RATE + OUTPUT_RATE // 2 - 2] < 1.0
    assert envelope[-1] == 0.0


def test_performance_guided_lead_keeps_symbolic_center_and_source_expression():
    count = OUTPUT_RATE // 2
    source_frequency = np.linspace(432.0, 448.0, count)
    source_amplitude = np.ones(count)
    source_amplitude[count // 3 : count // 2] = 0.0
    note = SymbolicNote("lead", 0.0, 0.5, 70, 88)

    guided = synthesize_performance_guided_lead(
        note,
        count,
        source_frequency=source_frequency,
        source_amplitude=source_amplitude,
        pitch_bend_depth=0.5,
        articulation_depth=0.8,
        pulse_mix=0.1,
    )
    repeated = synthesize_performance_guided_lead(
        note,
        count,
        source_frequency=source_frequency,
        source_amplitude=source_amplitude,
        pitch_bend_depth=0.5,
        articulation_depth=0.8,
        pulse_mix=0.1,
    )

    assert guided.shape == (count,)
    assert np.array_equal(guided, repeated)
    assert np.max(np.abs(guided[count // 3 : count // 2])) < np.max(np.abs(guided[: count // 3]))


def test_symbolic_guidance_can_be_limited_to_problem_regions():
    source = SourceProvenance("test", "mix", "vocals", "bass", "drums")
    arrangement = SymbolicArrangement(
        schema_version=1,
        duration=2.0,
        bpm=100.0,
        grid_origin=0.0,
        key="C major",
        source_offset=0.0,
        source=source,
        notes=(
            SymbolicNote("lead", 0.0, 0.7, 60, 88),
            SymbolicNote("lead", 1.0, 1.7, 62, 88),
        ),
        drums=(),
        chords=(),
    )
    count = round(arrangement.duration * OUTPUT_RATE)
    frequency = np.linspace(430.0, 450.0, count)
    amplitude = np.zeros(count)
    baseline = _symbolic_premix(
        arrangement,
        duration=arrangement.duration,
        profile=OMEGA_CHIP_PROFILES["balanced"],
        voice_fingerprints={},
    )
    guided = _symbolic_premix(
        arrangement,
        duration=arrangement.duration,
        profile=OMEGA_CHIP_PROFILES["balanced"],
        voice_fingerprints={},
        lead_frequency_contour=frequency,
        lead_amplitude_contour=amplitude,
        lead_pitch_bend_depth=0.5,
        lead_articulation_depth=0.8,
        lead_guidance_regions=((1.0, 2.0),),
    )

    assert np.array_equal(guided[: round(0.85 * OUTPUT_RATE)], baseline[: round(0.85 * OUTPUT_RATE)])
    assert not np.array_equal(guided[OUTPUT_RATE:], baseline[OUTPUT_RATE:])
