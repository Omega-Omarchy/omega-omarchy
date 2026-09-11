from omega_omarchy.music_diagnostic import (
    SymbolicArrangement, SymbolicNote, DrumHit, SourceProvenance,
    musical_cleanup, performance_notes,
)


def test_default_cleanup_preserves_chromatic_note_and_offbeat_snare():
    arrangement = SymbolicArrangement(1, 4, 120, 0, 'C major', 0,
        SourceProvenance('synthetic', 'x', 'x', 'x', 'x'),
        (SymbolicNote('lead', 0, .125, 61, 100),),
        (DrumHit('snare', .125, 100),), ())
    assert musical_cleanup(arrangement) == arrangement


def test_event_transcription_preserves_attacks_bends_and_confidence():
    notes = performance_notes([
        (.013, .4, 61, .9, [0, 1, 3]),
        (.1, .2, 73, .2, None),
        (.4, .55, 61, .8, None),
        (.575, .63, 62, .7, None),
    ], role='lead', duration=1)
    assert [(n.start, n.end, n.pitch) for n in notes] == [(.013, .4, 61), (.4, .55, 61), (.575, .63, 62)]
    assert notes[0].pitch_curve[-1] == (1.0, 100.0)
    assert notes[0].confidence == .9
    assert notes[1].velocity == notes[0].velocity  # confidence is not volume
