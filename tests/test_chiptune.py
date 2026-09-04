from pathlib import Path
import shutil
import wave

import numpy as np
import pytest

from omega_omarchy.chiptune import (
    ANALYSIS_RATE,
    OUTPUT_RATE,
    _assign_voices,
    _Cell,
    _constrain_arrangement,
    _stabilize_monophonic,
    convert_to_chiptune,
)


def test_voice_assignment_preserves_bass_and_nearby_melodic_parts():
    cells = [
        _Cell(((40, 0.8), (60, 0.7), (72, 0.9)), 0.8, 1.0, 0.4),
        _Cell(((41, 0.8), (62, 0.7), (74, 0.9)), 0.8, 0.5, 0.4),
    ]
    arrangement = _assign_voices(cells, 3)
    assert arrangement[0][0][0] == 40
    assert arrangement[1][0][0] == 41
    assert {voice[0] for voice in arrangement[1][1:]} == {62, 74}


def test_monophonic_stabilizer_removes_single_cell_pitch_chatter():
    cells = [
        _Cell(((60, 0.8),), 0.8, 0.3, 0.1),
        _Cell(((72, 0.7),), 0.8, 0.3, 0.1),
        _Cell(((60, 0.8),), 0.8, 0.3, 0.1),
    ]
    assert [cell.notes[0][0] for cell in _stabilize_monophonic(cells)] == [60, 60, 60]


def test_arrangement_constraint_snaps_pitch_set_and_suppresses_short_jumps():
    arrangement = [
        ((60, 0.8), (64, 0.7)),
        ((72, 0.8), (71, 0.7)),
        ((61, 0.8), (64, 0.7)),
        ((60, 0.8), (64, 0.7)),
    ]
    constrained, key = _constrain_arrangement(arrangement, minimum_hold=2)
    assert key is not None
    assert constrained[1][0][0] == 60
    assert abs(int(constrained[2][0][0]) - int(constrained[1][0][0])) <= 2


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is required")
@pytest.mark.parametrize("style, voices", [("snes", 7), ("genesis", 6)])
def test_converter_removes_source_mix_and_emits_console_rate(tmp_path: Path, style: str, voices: int):
    source = tmp_path / "source.wav"
    time = np.arange(ANALYSIS_RATE * 2, dtype=np.float64) / ANALYSIS_RATE
    signal = (np.sin(time * 2.0 * np.pi * 220.0) * 0.35 * 32767.0).astype("<i2")
    with wave.open(str(source), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(ANALYSIS_RATE)
        stream.writeframes(signal.tobytes())

    target = tmp_path / f"{style}.wav"
    report = convert_to_chiptune(source, target, style=style)

    assert report.source_mix_retained is False
    assert report.pitched_voices == voices
    assert report.note_events > 0
    with wave.open(str(target), "rb") as stream:
        assert stream.getframerate() == OUTPUT_RATE
        assert stream.getnchannels() == 2
        assert stream.getnframes() == pytest.approx(OUTPUT_RATE * 2, abs=OUTPUT_RATE // 10)
