import json

import numpy as np

from omega_omarchy.music_diagnostic import (
    Chord,
    DrumHit,
    InstrumentCandidate,
    InstrumentInventory,
    OMEGA_CHIP_PROFILES,
    SourceProvenance,
    SymbolicArrangement,
    SymbolicNote,
    SynthFingerprint,
    _classify_instrument_archetype,
    _deterministic_clusters,
    _plucked_string_note,
    _rearticulate_plucked_notes,
    _source_informed_saw_note,
    _source_wavetable,
    build_timing_grid,
    _chord_templates,
    _diatonic_states,
    infer_grid_origin,
    load_arrangement,
    load_instrument_inventory,
    load_synth_fingerprint,
    monophonic_grid,
    musical_cleanup,
    nearest_timing,
    omega_arpeggio_notes,
    quantize_time,
    save_arrangement,
    save_instrument_inventory,
    save_synth_fingerprint,
)


def test_quantize_time_uses_sixteenth_note_grid():
    assert quantize_time(0.17, 120.0) == 0.125
    assert quantize_time(0.20, 120.0) == 0.25


def test_quantize_time_respects_detected_grid_phase():
    assert quantize_time(0.11, 120.0, 0.10) == 0.10
    assert quantize_time(0.24, 120.0, 0.10) == 0.225


def test_grid_origin_ignores_clip_boundary():
    origin = infer_grid_origin(np.asarray([0.10, 0.60, 1.10, 1.60]), 120.0)
    assert origin == 0.1


def test_variable_timing_grid_preserves_detected_tempo_changes():
    grid = build_timing_grid((0.1, 0.6, 1.2), 1.8, 120.0)

    assert 0.1 in grid
    assert 0.6 in grid
    assert 1.2 in grid
    assert nearest_timing(0.59, grid) == 0.6
    assert nearest_timing(1.04, grid) == 1.05


def test_monophonic_grid_prefers_confidence_and_collapses_holds():
    notes = monophonic_grid(
        [
            (0.0, 0.5, 60, 0.7),
            (0.2, 0.35, 72, 0.2),
            (0.5, 1.0, 62, 0.8),
        ],
        role="lead",
        bpm=120.0,
        duration=1.0,
        pitch_range=(45, 88),
    )
    assert [(note.pitch, note.start, note.end) for note in notes] == [
        (60, 0.0, 0.5),
        (62, 0.5, 1.0),
    ]


def test_chord_templates_cover_major_and_minor_for_every_root():
    states, templates = _chord_templates()
    assert len(states) == 24
    assert templates.shape == (24, 12)
    assert (0, "major") in states
    assert (11, "minor") in states


def test_minor_key_allows_natural_and_harmonic_dominants():
    states = _diatonic_states(8, "minor")
    assert (8, "minor") in states  # G# minor tonic
    assert (3, "minor") in states  # D# natural-minor dominant
    assert (3, "major") in states  # D# harmonic-minor dominant
    assert (11, "minor") not in states


def test_arrangement_round_trip_preserves_editable_score(tmp_path):
    arrangement = SymbolicArrangement(
        schema_version=1,
        duration=1.0,
        bpm=120.0,
        grid_origin=0.1,
        key="C major",
        source_offset=15.0,
        source=SourceProvenance("htdemucs", "a", "b", "c", "d"),
        notes=(SymbolicNote("lead", 0.1, 0.6, 60, 90),),
        drums=(DrumHit("kick", 0.1, 100),),
        chords=(Chord(0.0, 1.0, 0, "major", 0.8),),
        timing_grid=(0.0, 0.1, 0.225, 0.35, 0.475, 0.6, 1.0),
    )
    target = save_arrangement(arrangement, tmp_path / "arrangement.json")

    assert load_arrangement(target) == arrangement
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["counts"]["leadNotes"] == 1
    assert payload["chords"][0]["name"] == "C"


def test_musical_cleanup_snaps_and_consolidates_weak_notes():
    arrangement = SymbolicArrangement(
        schema_version=1,
        duration=1.0,
        bpm=120.0,
        grid_origin=0.0,
        key="C major",
        source_offset=0.0,
        source=SourceProvenance("test", "a", "b", "c", "d"),
        notes=(
            SymbolicNote("lead", 0.0, 0.125, 61, 60),
            SymbolicNote("lead", 0.25, 0.5, 60, 90),
            SymbolicNote("bass", 0.0, 0.125, 30, 60),
            SymbolicNote("instrument-other-01-plucked-string", 0.0, 0.25, 67, 88),
        ),
        drums=(),
        chords=(Chord(0.0, 1.0, 0, "major", 0.8),),
    )

    cleaned = musical_cleanup(arrangement, style="standard-backbeat")
    lead = [note for note in cleaned.notes if note.role == "lead"]
    bass = [note for note in cleaned.notes if note.role == "bass"]
    assert [(note.pitch, note.start, note.end) for note in lead] == [(60, 0.0, 0.5)]
    assert bass[0].pitch % 12 in {0, 4, 7}
    assert any(note.role.startswith("instrument-") for note in cleaned.notes)


def test_omega_chip_profiles_share_score_but_not_mix_character():
    assert set(OMEGA_CHIP_PROFILES) == {"balanced", "vivid"}
    assert OMEGA_CHIP_PROFILES["vivid"].stereo_width > OMEGA_CHIP_PROFILES["balanced"].stereo_width
    assert OMEGA_CHIP_PROFILES["vivid"].arpeggio_gain > OMEGA_CHIP_PROFILES["balanced"].arpeggio_gain


def test_omega_arpeggio_follows_chord_and_eighth_note_grid():
    arrangement = SymbolicArrangement(
        schema_version=1,
        duration=1.0,
        bpm=120.0,
        grid_origin=0.0,
        key="C major",
        source_offset=0.0,
        source=SourceProvenance("test", "a", "b", "c", "d"),
        notes=(),
        drums=(),
        chords=(Chord(0.0, 1.0, 0, "major", 0.8),),
    )

    notes = omega_arpeggio_notes(arrangement)
    assert [note.pitch % 12 for note in notes] == [0, 4, 7, 4]
    assert [note.start for note in notes] == [0.0, 0.25, 0.5, 0.75]


def test_omega_arpeggio_yields_space_to_recovered_instruments():
    arrangement = SymbolicArrangement(
        schema_version=2,
        duration=1.0,
        bpm=120.0,
        grid_origin=0.0,
        key="C major",
        source_offset=0.0,
        source=SourceProvenance("test", "a", "b", "c", "d"),
        notes=(SymbolicNote("instrument-other-01-plucked-string", 0.0, 0.6, 67, 88),),
        drums=(),
        chords=(Chord(0.0, 1.0, 0, "major", 0.8),),
    )

    assert [note.start for note in omega_arpeggio_notes(arrangement)] == [0.75]


def test_instrument_classifier_recognizes_plucked_and_source_specific_timbres():
    plucked, plucked_confidence = _classify_instrument_archetype(
        "other",
        harmonic_ratio=0.51,
        spectral_flatness=0.004,
        onset_density=5.0,
        spectral_centroid_hz=890.0,
        stereo_width=0.4,
    )
    guitar, _ = _classify_instrument_archetype(
        "guitar",
        harmonic_ratio=0.53,
        spectral_flatness=0.002,
        onset_density=2.0,
        spectral_centroid_hz=1_270.0,
        stereo_width=1.2,
    )

    assert plucked == "plucked-string"
    assert plucked_confidence > 0.6
    assert guitar == "guitar-like"


def test_instrument_inventory_round_trip(tmp_path):
    candidate = InstrumentCandidate(
        candidate_id="other-01",
        source_stem="other",
        archetype="plucked-string",
        confidence=0.78,
        promoted=True,
        regions=((0.0, 9.5),),
        level_db=-29.0,
        harmonic_ratio=0.52,
        spectral_flatness=0.004,
        onset_density=5.0,
        spectral_centroid_hz=1_100.0,
        stereo_width=0.3,
    )
    inventory = InstrumentInventory(1, 0.0, 20.0, 1.0, 0.5, (("other", "abc"),), (candidate,))

    target = save_instrument_inventory(inventory, tmp_path / "instruments.json")

    assert load_instrument_inventory(target) == inventory


def test_instrument_clustering_is_deterministic():
    features = np.asarray(((0.1, 0.2), (0.12, 0.21), (0.8, 0.9), (0.82, 0.88)))

    first = _deterministic_clusters(features, 2)
    second = _deterministic_clusters(features, 2)

    assert np.array_equal(first, second)
    assert first[0] == first[1]
    assert first[2] == first[3]
    assert first[0] != first[2]


def test_plucked_string_patch_is_deterministic_and_decays():
    note = SymbolicNote("instrument-other-01-plucked-string", 0.0, 0.5, 69, 100)

    first = _plucked_string_note(note, 16_000)
    second = _plucked_string_note(note, 16_000)

    assert np.array_equal(first, second)
    assert np.sqrt(np.mean(first[:2_000] ** 2)) > np.sqrt(np.mean(first[-2_000:] ** 2))


def test_plucked_string_retriggers_at_detected_attacks():
    notes = [SymbolicNote("instrument-other-01-plucked-string", 0.0, 1.0, 67, 90)]

    articulated = _rearticulate_plucked_notes(
        notes,
        np.asarray((0.26, 0.51, 0.76)),
        bpm=120.0,
        timing_grid=(0.0, 0.25, 0.5, 0.75, 1.0),
    )

    assert [(note.start, note.end) for note in articulated] == [
        (0.0, 0.25),
        (0.25, 0.5),
        (0.5, 0.75),
        (0.75, 1.0),
    ]


def test_source_informed_saw_retains_even_and_odd_harmonics():
    note = SymbolicNote("bass", 0.0, 1.0, 45, 100)
    signal = _source_informed_saw_note(note, 32_000, voice="bass", fingerprint=None)
    spectrum = np.abs(np.fft.rfft(signal[:16_000] * np.hanning(16_000)))
    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    bins = [round(frequency * harmonic * 16_000 / 32_000) for harmonic in (1, 2, 3)]

    assert spectrum[bins[1]] > spectrum[bins[0]] * 0.08
    assert spectrum[bins[2]] > spectrum[bins[0]] * 0.05


def test_synth_fingerprint_round_trip(tmp_path):
    fingerprint = SynthFingerprint(
        schema_version=1,
        source_sha256="abc",
        source_offset=2.0,
        duration=20.0,
        sample_rate=32_000,
        fundamental_median_hz=220.0,
        harmonic_levels=(1.0, 0.5, 0.25),
        noise_mix=0.03,
        stereo_width=0.4,
        stereo_correlation=0.8,
        attack=0.01,
        decay=0.2,
        sustain=0.6,
        release=0.15,
        vibrato_rate_hz=5.2,
        vibrato_depth_cents=6.0,
        selected_windows=((1.0, 1.6, 0.9, 220.0),),
    )

    target = save_synth_fingerprint(fingerprint, tmp_path / "fingerprint.json")
    assert load_synth_fingerprint(target) == fingerprint


def test_source_wavetable_averages_repeating_cycles():
    rate = 32_000
    frequency = 100.0
    time = np.arange(round(rate * 0.6)) / rate
    source = np.sin(2.0 * np.pi * frequency * time)

    wavetable = _source_wavetable(source, (0.0, 0.6, 1.0, frequency), rate=rate)

    assert wavetable.shape == (256,)
    assert np.max(np.abs(wavetable)) == 1.0
    assert np.std(wavetable) > 0.6
