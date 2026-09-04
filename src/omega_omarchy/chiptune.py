"""Deterministic polyphonic-audio to console-style chiptune conversion.

This is an offline authoring tool, never a runtime dependency.  It performs a
lightweight transcription of an arbitrary mixed recording onto a tempo-locked
note grid, then resynthesizes those notes without mixing the source recording
back in.  The result is an editable first arrangement pass, not a substitute
for a musician reviewing the transcription.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np


ANALYSIS_RATE = 12_000
OUTPUT_RATE = 32_000
FFT_SIZE = 2_048
HOP_SIZE = 512
SUPPORTED_STYLES = ("snes", "genesis")
_MIDI_NOTES = np.arange(36, 97, dtype=np.int16)
_NOTE_FREQUENCIES = 440.0 * np.power(2.0, (_MIDI_NOTES.astype(np.float64) - 69.0) / 12.0)


@dataclass(frozen=True)
class ConversionReport:
    style: str
    duration_seconds: float
    analysis_rate: int
    output_rate: int
    tempo_bpm: float
    step_seconds: float
    pitched_voices: int
    note_events: int
    percussion_events: int
    source_mix_retained: bool = False


@dataclass(frozen=True)
class _Cell:
    notes: tuple[tuple[int, float], ...]
    energy: float
    onset: float
    bass_ratio: float


def _run(command: list[str], *, binary: bool = False) -> bytes | str:
    process = subprocess.run(command, check=False, capture_output=True)
    if process.returncode:
        message = process.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(message or "audio conversion command failed")
    return process.stdout if binary else process.stdout.decode("utf-8", "replace")


def _decode_mono(
    ffmpeg: str,
    source: Path,
    *,
    start: float,
    end: float | None,
) -> np.ndarray:
    trim = f"atrim=start={max(0.0, start):.6f}"
    if end is not None:
        trim += f":end={max(start + 0.001, end):.6f}"
    payload = _run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-af",
            f"{trim},asetpts=PTS-STARTPTS",
            "-ac",
            "1",
            "-ar",
            str(ANALYSIS_RATE),
            "-f",
            "f32le",
            "pipe:1",
        ],
        binary=True,
    )
    samples = np.frombuffer(payload, dtype="<f4").astype(np.float64)
    if samples.size < FFT_SIZE:
        raise RuntimeError("music source is too short for chiptune transcription")
    samples -= float(np.mean(samples))
    peak = float(np.percentile(np.abs(samples), 99.5))
    if peak > 1e-8:
        samples /= peak
    return np.clip(samples, -1.25, 1.25)


def _interpolated_bins(magnitude: np.ndarray, positions: np.ndarray) -> np.ndarray:
    valid = (positions >= 0.0) & (positions < magnitude.size - 1)
    clipped = np.clip(positions, 0.0, magnitude.size - 1.000001)
    low = np.floor(clipped).astype(np.int32)
    high = np.minimum(low + 1, magnitude.size - 1)
    fraction = clipped - low
    values = magnitude[low] * (1.0 - fraction) + magnitude[high] * fraction
    return np.where(valid, values, 0.0)


def _tempo_from_onsets(onsets: np.ndarray) -> tuple[int, float]:
    centered = onsets - float(np.mean(onsets))
    frames_per_second = ANALYSIS_RATE / HOP_SIZE
    candidates: list[tuple[float, int]] = []
    for lag in range(
        max(2, round(frames_per_second * 60.0 / 190.0)),
        round(frames_per_second * 60.0 / 62.0) + 1,
    ):
        left = centered[:-lag]
        right = centered[lag:]
        denominator = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
        correlation = float(np.dot(left, right)) / denominator if denominator > 1e-12 else 0.0
        bpm = 60.0 * frames_per_second / lag
        # Resolve common half/double-time ambiguity gently toward a game-music
        # pulse without overriding a materially stronger autocorrelation peak.
        prior = math.exp(-((bpm - 122.0) / 62.0) ** 2) * 0.08
        candidates.append((correlation + prior, lag))
    beat_frames = max(candidates)[1] if candidates else round(frames_per_second * 0.5)
    return beat_frames, 60.0 * frames_per_second / beat_frames


def _analyse(samples: np.ndarray, *, pitched_voices: int) -> tuple[list[_Cell], float, float]:
    frame_count = 1 + math.ceil(max(0, samples.size - FFT_SIZE) / HOP_SIZE)
    window = np.hanning(FFT_SIZE)
    harmonics = np.asarray((1.0, 2.0, 3.0, 4.0), dtype=np.float64)
    weights = np.asarray((1.0, 0.52, 0.29, 0.16), dtype=np.float64)
    note_bins = _NOTE_FREQUENCIES[:, None] * harmonics[None, :] * FFT_SIZE / ANALYSIS_RATE
    note_scores = np.zeros((frame_count, _MIDI_NOTES.size), dtype=np.float32)
    energies = np.zeros(frame_count, dtype=np.float32)
    onsets = np.zeros(frame_count, dtype=np.float32)
    bass_ratios = np.zeros(frame_count, dtype=np.float32)
    previous = np.zeros(FFT_SIZE // 2 + 1, dtype=np.float64)
    frequencies = np.fft.rfftfreq(FFT_SIZE, 1.0 / ANALYSIS_RATE)
    bass_mask = frequencies <= 220.0

    for frame_index in range(frame_count):
        offset = frame_index * HOP_SIZE
        frame = np.zeros(FFT_SIZE, dtype=np.float64)
        available = samples[offset : offset + FFT_SIZE]
        frame[: available.size] = available
        energies[frame_index] = math.sqrt(float(np.mean(frame * frame)))
        magnitude = np.abs(np.fft.rfft(frame * window))
        total = float(np.sum(magnitude)) + 1e-12
        positive_flux = np.maximum(0.0, magnitude - previous)
        onsets[frame_index] = float(np.sum(positive_flux)) / total
        bass_ratios[frame_index] = float(np.sum(magnitude[bass_mask])) / total
        interpolated = _interpolated_bins(magnitude, note_bins)
        scores = np.sum(interpolated * weights[None, :], axis=1)
        # A harmonic is not automatically a second note. Penalizing energy at
        # half the candidate frequency reduces octave ghosts while retaining
        # genuinely strong octave parts.
        subharmonic_bins = _NOTE_FREQUENCIES * 0.5 * FFT_SIZE / ANALYSIS_RATE
        scores -= 0.20 * _interpolated_bins(magnitude, subharmonic_bins)
        note_scores[frame_index] = np.maximum(0.0, scores).astype(np.float32)
        previous = magnitude

    beat_frames, tempo_bpm = _tempo_from_onsets(onsets)
    step_frames = max(2, round(beat_frames / 4.0))
    step_seconds = step_frames * HOP_SIZE / ANALYSIS_RATE
    energy_reference = max(1e-7, float(np.percentile(energies, 92.0)))
    onset_reference = max(1e-7, float(np.percentile(onsets, 86.0)))
    cells: list[_Cell] = []

    for first in range(0, frame_count, step_frames):
        last = min(frame_count, first + step_frames)
        score = np.mean(note_scores[first:last], axis=0, dtype=np.float64)
        energy = min(1.0, float(np.mean(energies[first:last])) / energy_reference)
        onset = min(1.5, float(np.max(onsets[first:last])) / onset_reference)
        bass_ratio = float(np.mean(bass_ratios[first:last]))
        if energy < 0.025 or float(np.max(score)) <= 1e-8:
            cells.append(_Cell((), energy, onset, bass_ratio))
            continue

        chosen: list[tuple[int, float]] = []
        maximum = float(np.max(score))
        bass_limit = int(np.searchsorted(_MIDI_NOTES, 60))
        bass_index = int(np.argmax(score[:bass_limit]))
        if float(score[bass_index]) >= maximum * 0.24:
            chosen.append((int(_MIDI_NOTES[bass_index]), float(score[bass_index])))

        for index in np.argsort(score)[::-1]:
            midi = int(_MIDI_NOTES[index])
            value = float(score[index])
            if value < maximum * 0.28:
                break
            if any(abs(midi - existing) < 3 for existing, _ in chosen):
                continue
            if any(midi > existing and (midi - existing) % 12 == 0 and prior >= value * 0.78 for existing, prior in chosen):
                continue
            chosen.append((midi, value))
            if len(chosen) >= pitched_voices:
                break
        chosen.sort(key=lambda item: item[0])
        scale = max(value for _, value in chosen) if chosen else 1.0
        notes = tuple(
            (midi, min(1.0, math.sqrt(value / scale) * (0.40 + 0.60 * energy)))
            for midi, value in chosen
        )
        cells.append(_Cell(notes, energy, onset, bass_ratio))
    return cells, tempo_bpm, step_seconds


def _assign_voices(cells: list[_Cell], voice_count: int) -> list[tuple[tuple[int | None, float], ...]]:
    previous: list[int | None] = [None] * voice_count
    arrangement: list[tuple[tuple[int | None, float], ...]] = []
    for cell in cells:
        assigned: list[tuple[int | None, float]] = [(None, 0.0) for _ in range(voice_count)]
        candidates = list(cell.notes)
        if candidates:
            assigned[0] = candidates.pop(0)  # dedicated bass/sample voice
        # Preserve melodic continuity before filling idle channels. This is a
        # small but important distinction from merely playing the loudest FFT
        # bins independently on every frame.
        for voice in range(1, voice_count):
            if previous[voice] is None or not candidates:
                continue
            index = min(range(len(candidates)), key=lambda item: abs(candidates[item][0] - int(previous[voice])))
            if abs(candidates[index][0] - int(previous[voice])) <= 8:
                assigned[voice] = candidates.pop(index)
        for voice in range(1, voice_count):
            if assigned[voice][0] is None and candidates:
                # High and low parts alternate across the available voices,
                # producing a more stable lead/chord split.
                index = -1 if voice % 2 else 0
                assigned[voice] = candidates.pop(index)
        previous = [note for note, _ in assigned]
        arrangement.append(tuple(assigned))
    return arrangement


def _snes_tables() -> tuple[np.ndarray, ...]:
    phase = np.arange(256, dtype=np.float64) / 256.0
    triangle = 2.0 * np.abs(2.0 * (phase - np.floor(phase + 0.5))) - 1.0
    sine = np.sin(2.0 * np.pi * phase)
    saw = 2.0 * phase - 1.0
    square = np.where(phase < 0.5, 1.0, -1.0)
    pulse = np.where(phase < 0.25, 1.0, -1.0)
    waves = (
        0.82 * triangle + 0.18 * sine,
        0.62 * sine + 0.38 * saw,
        0.76 * sine + 0.24 * triangle,
        0.56 * pulse + 0.44 * sine,
        0.48 * square + 0.52 * triangle,
        0.70 * saw + 0.30 * sine,
        0.84 * sine + 0.16 * square,
    )
    # Small, quantized, single-cycle samples are deliberately used as the
    # instrument palette; this is closer to the S-DSP model than oscillator
    # effects applied to the finished recording.
    return tuple((np.round(np.clip(wave, -1.0, 1.0) * 101.0) / 101.0).astype(np.float32) for wave in waves)


def _sample_wave(table: np.ndarray, phase: float, frequency: float, count: int) -> tuple[np.ndarray, float]:
    positions = phase + np.arange(count, dtype=np.float64) * frequency / OUTPUT_RATE
    indexes = np.floor((positions % 1.0) * table.size).astype(np.int32)
    return table[indexes].astype(np.float64), float((phase + count * frequency / OUTPUT_RATE) % 1.0)


def _fm_wave(voice: int, phase: float, frequency: float, count: int) -> tuple[np.ndarray, float]:
    positions = phase + np.arange(count, dtype=np.float64) * frequency / OUTPUT_RATE
    carrier = 2.0 * np.pi * positions
    ratios = (2.0, 2.0, 3.0, 1.0, 4.0, 1.5)
    depths = (1.15, 2.65, 1.75, 3.20, 0.90, 2.10)
    ratio = ratios[voice % len(ratios)]
    depth = depths[voice % len(depths)]
    operator_two = np.sin(carrier * ratio * 2.0) * depth * 0.22
    operator_one = np.sin(carrier * ratio + operator_two) * depth
    wave = np.sin(carrier + operator_one)
    return wave, float((phase + count * frequency / OUTPUT_RATE) % 1.0)


def _write_arrangement(
    target: Path,
    cells: list[_Cell],
    arrangement: list[tuple[tuple[int | None, float], ...]],
    *,
    style: str,
    step_seconds: float,
    duration_seconds: float,
) -> tuple[int, int]:
    total_samples = max(1, round(duration_seconds * OUTPUT_RATE))
    output = np.zeros((total_samples, 2), dtype=np.float32)
    voice_count = len(arrangement[0]) if arrangement else (7 if style == "snes" else 6)
    phases = [0.0] * voice_count
    prior_notes: list[int | None] = [None] * voice_count
    prior_amplitudes = [0.0] * voice_count
    pans = np.linspace(-0.72, 0.72, voice_count)
    voice_gain = np.linspace(0.21, 0.14, voice_count)
    tables = _snes_tables()
    rng = np.random.default_rng(0x4F4D4547)
    note_events = 0
    percussion_events = 0
    onset_floor = 0.92

    for cell_index, (cell, voices) in enumerate(zip(cells, arrangement, strict=True)):
        first = round(cell_index * step_seconds * OUTPUT_RATE)
        last = min(total_samples, round((cell_index + 1) * step_seconds * OUTPUT_RATE))
        if first >= total_samples or last <= first:
            continue
        count = last - first
        for voice, (note, velocity) in enumerate(voices):
            changed = note != prior_notes[voice]
            if note is None:
                if prior_notes[voice] is None or prior_amplitudes[voice] <= 1e-5:
                    prior_amplitudes[voice] = 0.0
                    continue
                active_note = int(prior_notes[voice])
                target_amplitude = 0.0
            else:
                active_note = int(note)
                target_amplitude = float(velocity) * float(voice_gain[voice])
                if changed:
                    phases[voice] = 0.0
                    note_events += 1
            frequency = 440.0 * 2.0 ** ((active_note - 69.0) / 12.0)
            if style == "snes":
                wave_data, phases[voice] = _sample_wave(
                    tables[voice % len(tables)], phases[voice], frequency, count
                )
            else:
                wave_data, phases[voice] = _fm_wave(voice, phases[voice], frequency, count)
            if changed and note is not None:
                attack = min(count, round(OUTPUT_RATE * (0.010 if style == "snes" else 0.006)))
                envelope = np.full(count, target_amplitude, dtype=np.float64)
                envelope[:attack] = np.linspace(0.0, target_amplitude, attack, endpoint=False)
            else:
                envelope = np.linspace(prior_amplitudes[voice], target_amplitude, count, endpoint=False)
            signal = wave_data * envelope
            pan = float(pans[voice])
            output[first:last, 0] += signal * math.sqrt((1.0 - pan) * 0.5)
            output[first:last, 1] += signal * math.sqrt((1.0 + pan) * 0.5)
            prior_amplitudes[voice] = target_amplitude
            prior_notes[voice] = note

        if cell.onset >= onset_floor:
            percussion_events += 1
            time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
            if cell.bass_ratio >= 0.23:
                frequency = 92.0 - 48.0 * np.minimum(1.0, time / max(0.03, step_seconds))
                phase = 2.0 * np.pi * np.cumsum(frequency) / OUTPUT_RATE
                percussion = np.sin(phase) * np.exp(-time * 17.0) * 0.24
            else:
                noise = rng.integers(-32768, 32768, count, dtype=np.int32).astype(np.float64) / 32768.0
                decay = 31.0 if style == "snes" else 42.0
                percussion = noise * np.exp(-time * decay) * 0.15
            output[first:last, 0] += percussion
            output[first:last, 1] += percussion

    if style == "snes":
        # One modest shared echo approximates the S-DSP's global echo path.
        delay = round(OUTPUT_RATE * 0.096)
        for index in range(delay, total_samples):
            output[index] += output[index - delay] * 0.17
        # Gaussian interpolation is not emulated sample-for-sample, but this
        # short FIR removes the modern hard edges from the tiny PCM tables.
        output[1:-1] = output[:-2] * 0.22 + output[1:-1] * 0.56 + output[2:] * 0.22
    else:
        # The YM2612's character is represented by discrete FM operators and a
        # restrained DAC ladder quantization, not a bitcrusher over source audio.
        output = np.round(output * 768.0) / 768.0

    peak = float(np.max(np.abs(output)))
    if peak > 1e-8:
        output *= min(1.0, 0.88 / peak)
    pcm = np.round(np.clip(output, -1.0, 1.0) * 32767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(OUTPUT_RATE)
        stream.writeframes(pcm.tobytes())
    return note_events, percussion_events


def convert_to_chiptune(
    source: Path,
    target: Path,
    *,
    style: str = "snes",
    start: float = 0.0,
    end: float | None = None,
    ffmpeg: str | None = None,
) -> ConversionReport:
    """Transcribe ``source`` and render a standalone console-style WAV."""

    if style not in SUPPORTED_STYLES:
        raise ValueError(f"unsupported chiptune style: {style}")
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg is required for chiptune source decoding")
    source = Path(source)
    target = Path(target)
    samples = _decode_mono(executable, source, start=start, end=end)
    duration_seconds = samples.size / ANALYSIS_RATE
    pitched_voices = 7 if style == "snes" else 6
    cells, tempo_bpm, step_seconds = _analyse(samples, pitched_voices=pitched_voices)
    arrangement = _assign_voices(cells, pitched_voices)
    note_events, percussion_events = _write_arrangement(
        target,
        cells,
        arrangement,
        style=style,
        step_seconds=step_seconds,
        duration_seconds=duration_seconds,
    )
    return ConversionReport(
        style=style,
        duration_seconds=round(duration_seconds, 6),
        analysis_rate=ANALYSIS_RATE,
        output_rate=OUTPUT_RATE,
        tempo_bpm=round(tempo_bpm, 3),
        step_seconds=round(step_seconds, 6),
        pitched_voices=pitched_voices,
        note_events=note_events,
        percussion_events=percussion_events,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe mixed music into a console-style arrangement")
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--style", choices=SUPPORTED_STYLES, default="snes")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    end = args.start + args.duration if args.duration is not None else None
    report = convert_to_chiptune(args.source, args.target, style=args.style, start=args.start, end=end)
    payload = json.dumps(asdict(report), indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
