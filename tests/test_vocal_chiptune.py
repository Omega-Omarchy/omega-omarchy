import numpy as np

from omega_omarchy.music_diagnostic import OUTPUT_RATE
from omega_omarchy.music_diagnostic import SourceProvenance, SymbolicArrangement, SymbolicNote
from omega_omarchy.vocal_chiptune import (
    VOCAL_CHIP_PROFILES,
    anchor_frequency_to_symbolic_lead,
    enhance_bed_delivery,
    quantize_frequency,
    recover_vocal_sustain,
    strengthen_vocal_amplitude,
    synthesize_vocal_chip,
)


def test_frequency_quantization_moves_contour_to_semitone_centers():
    frequency = np.asarray([438.0, 442.0])

    raw = quantize_frequency(frequency, 0.0)
    crisp = quantize_frequency(frequency, 1.0)

    assert np.allclose(raw, frequency)
    assert np.allclose(crisp, 440.0)


def test_vocal_chip_is_deterministic_and_source_gated():
    count = OUTPUT_RATE // 2
    frequency = np.linspace(220.0, 246.94, count)
    amplitude = np.ones(count)
    amplitude[: count // 4] = 0.0

    first = synthesize_vocal_chip(frequency, amplitude, tone="pulse-triangle")
    second = synthesize_vocal_chip(frequency, amplitude, tone="pulse-triangle")

    assert first.shape == (count, 2)
    assert np.array_equal(first, second)
    assert np.max(np.abs(first[: count // 4])) == 0.0
    assert np.max(np.abs(first[count // 3 :])) > 0.1


def test_octave_profile_is_an_accent_not_a_replacement():
    profile = VOCAL_CHIP_PROFILES["octave-spark"]

    assert 0.0 < profile.octave_mix < 0.5
    assert profile.pitch_quantization > 0.9


def test_strength_curve_raises_active_notes_without_filling_silence():
    amplitude = np.asarray([0.0, 0.02, 0.10, 0.25, 0.75, 1.0])
    lifted = strengthen_vocal_amplitude(
        amplitude,
        active_floor=0.58,
        compression_gamma=0.46,
        gate_knee=0.10,
    )

    assert lifted[0] == 0.0
    assert lifted[2] > amplitude[2]
    assert lifted[3] > amplitude[3] * 2.0
    assert lifted[-1] == 1.0


def test_assertive_profile_has_a_stronger_active_floor_than_lifted():
    assert VOCAL_CHIP_PROFILES["saw-assertive"].active_floor > VOCAL_CHIP_PROFILES["saw-lifted"].active_floor


def test_wispy_profile_preserves_boundaries_and_restrains_soft_delivery():
    amplitude = np.asarray([0.0, 0.02, 0.10, 0.25, 0.75, 1.0])
    profile = VOCAL_CHIP_PROFILES["saw-wispy"]
    shaped = strengthen_vocal_amplitude(
        amplitude,
        active_floor=profile.active_floor,
        compression_gamma=profile.compression_gamma,
        gate_knee=profile.gate_knee,
    )

    assert shaped[0] == 0.0
    assert shaped[1] < amplitude[1]
    assert shaped[3] < amplitude[3]
    assert shaped[-1] == 1.0
    assert profile.gain < VOCAL_CHIP_PROFILES["saw-expressive"].gain


def test_air_channel_is_deterministic_and_uses_the_same_articulation_gate():
    count = OUTPUT_RATE // 2
    frequency = np.full(count, 440.0)
    amplitude = np.ones(count)
    amplitude[: count // 3] = 0.0

    first = synthesize_vocal_chip(frequency, amplitude, tone="saw-air")
    second = synthesize_vocal_chip(frequency, amplitude, tone="saw-air")

    assert np.array_equal(first, second)
    assert np.max(np.abs(first[: count // 3 - 3])) == 0.0
    assert not np.array_equal(
        first,
        synthesize_vocal_chip(frequency, amplitude, tone="saw"),
    )


def test_sustain_recovery_bridges_unvoiced_energy_but_preserves_stutter_gap():
    count = OUTPUT_RATE * 2
    time = np.arange(count) / OUTPUT_RATE
    vocal = np.zeros(count)
    vocal[: OUTPUT_RATE // 2] = np.sin(2.0 * np.pi * 440.0 * time[: OUTPUT_RATE // 2]) * 0.2
    vocal[OUTPUT_RATE * 3 // 4 : OUTPUT_RATE] = (
        np.sin(2.0 * np.pi * 440.0 * time[OUTPUT_RATE * 3 // 4 : OUTPUT_RATE]) * 0.2
    )
    amplitude = np.zeros(count)
    amplitude[: OUTPUT_RATE // 8] = 0.4
    amplitude[OUTPUT_RATE * 3 // 4 : OUTPUT_RATE * 7 // 8] = 0.4

    recovered = recover_vocal_sustain(
        amplitude,
        vocal,
        strength=0.8,
        proximity_seconds=0.4,
    )

    assert np.mean(recovered[OUTPUT_RATE // 4 : OUTPUT_RATE * 3 // 8]) > 0.05
    assert np.max(recovered[OUTPUT_RATE * 19 // 32 : OUTPUT_RATE * 21 // 32]) == 0.0
    assert np.max(recovered[OUTPUT_RATE + OUTPUT_RATE // 16 :]) == 0.0


def test_symbolic_pitch_anchor_corrects_wrong_center_without_erasing_bend():
    source = SourceProvenance("test", "mix", "vocals", "bass", "drums")
    arrangement = SymbolicArrangement(
        schema_version=1,
        duration=1.0,
        bpm=120.0,
        grid_origin=0.0,
        key="F major",
        source_offset=0.0,
        source=source,
        notes=(SymbolicNote("lead", 0.25, 0.75, 69, 90),),
        drums=(),
        chords=(),
    )
    count = OUTPUT_RATE
    source_midi = np.linspace(40.5, 41.5, count)
    frequency = 440.0 * 2.0 ** ((source_midi - 69.0) / 12.0)
    amplitude = np.ones(count)

    anchored = anchor_frequency_to_symbolic_lead(
        frequency,
        amplitude,
        arrangement,
        amount=1.0,
    )
    anchored_midi = 69.0 + 12.0 * np.log2(anchored / 440.0)

    assert np.allclose(anchored_midi[: OUTPUT_RATE // 4], source_midi[: OUTPUT_RATE // 4])
    assert np.isclose(np.median(anchored_midi[OUTPUT_RATE // 4 : OUTPUT_RATE * 3 // 4]), 69.0)
    assert np.ptp(anchored_midi[OUTPUT_RATE // 4 : OUTPUT_RATE * 3 // 4]) > 0.1


def test_bed_delivery_lifts_quiet_active_music_without_filling_source_silence():
    candidate = np.zeros((OUTPUT_RATE * 4, 2))
    reference = np.zeros_like(candidate)
    candidate[:OUTPUT_RATE] = 0.05
    candidate[OUTPUT_RATE : OUTPUT_RATE * 2] = 0.4
    candidate[OUTPUT_RATE * 3 :] = 0.05
    reference[: OUTPUT_RATE * 2] = 0.25

    enhanced = enhance_bed_delivery(candidate, reference)

    assert np.mean(np.abs(enhanced[OUTPUT_RATE // 4 : OUTPUT_RATE * 3 // 4])) > 0.06
    assert np.allclose(
        enhanced[OUTPUT_RATE + OUTPUT_RATE // 4 : OUTPUT_RATE * 2 - OUTPUT_RATE // 4],
        0.4,
        atol=0.01,
    )
    assert np.max(np.abs(enhanced[OUTPUT_RATE * 2 : OUTPUT_RATE * 3])) == 0.0
    assert np.allclose(enhanced[OUTPUT_RATE * 3 + OUTPUT_RATE // 2 :], 0.05)
