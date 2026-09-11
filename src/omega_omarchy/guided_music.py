"""CatchyTune-guided local experiments for the Omega Chip renderer.

This module intentionally produces review artifacts rather than runtime assets.
It tests a hybrid transcription strategy: symbolic voices retain the authored
retro arrangement, continuous stem-conditioned oscillators retain performed
pitch and dynamics, and retro sample playback retains the source drum groove.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import shutil
import wave

import numpy as np

from .music_diagnostic import (
    OMEGA_CHIP_PROFILES,
    OUTPUT_RATE,
    InstrumentInventory,
    OmegaChipProfile,
    SymbolicArrangement,
    SymbolicNote,
    SynthFingerprint,
    _adsr,
    _cross_echo,
    _encode_review,
    _instrument_archetype,
    _omega_chip_note,
    _safe_instrument_label,
    _stable_instrument_pan,
    _triangle,
    load_arrangement,
    load_instrument_inventory,
    load_synth_fingerprint,
    omega_arpeggio_notes,
)


@dataclass(frozen=True)
class GuidedMixProfile:
    name: str
    symbolic_gain: float
    bass_gain: float
    synth_gain: float
    lead_gain: float
    drum_gain: float
    sampled_instrument_gain: float
    symbolic_pluck: bool
    symbolic_lead: bool
    drive: float
    lead_pitch_bend_depth: float = 0.0
    lead_articulation_depth: float = 0.0


GUIDED_MIX_PROFILES = {
    "balanced-guided": GuidedMixProfile(
        "balanced-guided", 0.72, 0.32, 0.29, 0.0, 0.82, 0.0, True, True, 1.16
    ),
    "rhythm-locked": GuidedMixProfile(
        "rhythm-locked", 0.62, 0.31, 0.25, 0.0, 0.94, 0.0, True, True, 1.13
    ),
    "saw-led": GuidedMixProfile(
        "saw-led", 0.62, 0.38, 0.34, 0.0, 0.80, 0.0, True, True, 1.20
    ),
    "phrase-balanced": GuidedMixProfile(
        "phrase-balanced", 0.72, 0.32, 0.29, 0.0, 0.82, 0.0, True, True, 1.16, 0.45, 0.60
    ),
    "phrase-bend": GuidedMixProfile(
        "phrase-bend", 0.72, 0.32, 0.29, 0.0, 0.82, 0.0, True, True, 1.16, 0.50, 0.0
    ),
}


def _load_audio(source: Path, *, start: float, duration: float) -> np.ndarray:
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for guided music experiments") from exc

    values, _ = librosa.load(
        source,
        sr=OUTPUT_RATE,
        mono=False,
        offset=max(0.0, start),
        duration=duration,
    )
    if values.ndim == 1:
        values = np.vstack((values, values))
    values = values[:2].astype(np.float64)
    expected = round(duration * OUTPUT_RATE)
    if values.shape[1] < expected:
        values = np.pad(values, ((0, 0), (0, expected - values.shape[1])))
    return values[:, :expected]


def _smooth_frames(values: np.ndarray, radius: int = 2) -> np.ndarray:
    if radius <= 0 or values.size < 3:
        return values.copy()
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.asarray(
        [np.median(padded[index : index + radius * 2 + 1]) for index in range(values.size)],
        dtype=np.float64,
    )


def normalize_activity_presence(
    amplitude: np.ndarray,
    *,
    target_level: float,
    max_boost: float,
    window_seconds: float = 1.5,
    min_activity: float = 0.025,
    hop: int = 256,
) -> np.ndarray:
    """Lift quiet performed phrases without turning isolated leakage into notes.

    Global peak normalization makes a softly delivered phrase disappear beside
    a later strong phrase. This automatic gain control measures only already
    active pitch frames, so silence remains silence, and requires sustained
    local activity before applying its full boost.
    """

    values = np.clip(np.asarray(amplitude, dtype=np.float64), 0.0, 1.35)
    if values.size == 0 or target_level <= 0.0 or max_boost <= 1.0:
        return values.copy()
    hop = max(1, int(hop))
    frames = values[::hop]
    active = (frames > 0.005).astype(np.float64)
    window = max(3, round(window_seconds * OUTPUT_RATE / hop))
    window = min(window, max(1, frames.size))
    if window > 1 and window % 2 == 0:
        window -= 1
    kernel = np.hanning(window) if window > 2 else np.ones(window)
    kernel /= max(1e-9, float(np.sum(kernel)))
    density_kernel = np.ones(window, dtype=np.float64) / window
    pad = window // 2

    def smooth(source: np.ndarray, weights: np.ndarray = kernel) -> np.ndarray:
        if window == 1:
            return source.copy()
        padded = np.pad(source, (pad, pad), mode="edge")
        return np.convolve(padded, weights, mode="valid")[: source.size]

    density = smooth(active, density_kernel)
    weighted_density = smooth(active)
    active_mean = smooth(frames * active) / np.maximum(1e-6, weighted_density)
    requested = np.clip(target_level / np.maximum(active_mean, 1e-6), 1.0, max_boost)
    confidence = np.clip(
        (density - min_activity) / max(1e-6, min_activity * 1.5), 0.0, 1.0
    )
    confidence = confidence * confidence * (3.0 - 2.0 * confidence)
    frame_gain = 1.0 + (requested - 1.0) * confidence
    sample_gain = np.interp(
        np.arange(values.size),
        np.arange(frames.size) * hop,
        frame_gain,
    )
    return np.clip(values * sample_gain, 0.0, 1.35)


def _pitch_and_amplitude_contours(
    mono: np.ndarray,
    *,
    voice: str,
    pitch_quantization: float = 0.82,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Recover continuous pitch and performance energy without note segmentation."""

    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for guided music experiments") from exc

    ranges = {
        "bass": (25.0, 165.0, 4_096, 0.08),
        "synth": (65.0, 1_400.0, 2_048, 0.16),
        "lead": (80.0, 1_400.0, 2_048, 0.18),
    }
    minimum, maximum, frame_length, threshold = ranges[voice]
    hop = 256
    harmonic = librosa.effects.harmonic(mono, margin=2.0)
    f0, voiced, probability = librosa.pyin(
        harmonic,
        fmin=minimum,
        fmax=maximum,
        sr=OUTPUT_RATE,
        frame_length=frame_length,
        hop_length=hop,
    )
    probability = np.nan_to_num(probability, nan=0.0)
    rms = librosa.feature.rms(y=mono, frame_length=2_048, hop_length=hop)[0]
    frame_count = min(len(f0), len(rms))
    f0 = f0[:frame_count]
    probability = probability[:frame_count]
    voiced = np.asarray(voiced[:frame_count], dtype=bool)
    level_floor = max(1e-7, float(np.percentile(rms[:frame_count], 30)))
    valid = np.isfinite(f0) & (probability >= threshold) & voiced & (rms[:frame_count] > level_floor)
    if np.count_nonzero(valid) < 2:
        zeros = np.zeros(mono.size, dtype=np.float64)
        return np.full(mono.size, 55.0), zeros, {"voiced_fraction": 0.0, "median_pitch_hz": 0.0}

    indexes = np.arange(frame_count)
    midi = librosa.hz_to_midi(np.interp(indexes, indexes[valid], f0[valid]))
    midi = _smooth_frames(midi, 2)
    # Retain small performed bends while pulling uncertain estimates toward a
    # console-like pitch center. This avoids hard re-segmentation and timing loss.
    quantization = float(np.clip(pitch_quantization, 0.0, 1.0))
    midi = np.round(midi) * quantization + midi * (1.0 - quantization)
    frequency_frames = librosa.midi_to_hz(midi)

    reference = max(1e-7, float(np.percentile(rms[:frame_count], 95)))
    level = np.clip(rms[:frame_count] / reference, 0.0, 1.35)
    confidence = np.clip((probability - threshold) / max(0.1, 1.0 - threshold), 0.0, 1.0)
    gate = valid.astype(np.float64) * confidence
    gate = np.convolve(gate, np.ones(5) / 5.0, mode="same")
    amplitude_frames = np.sqrt(level) * np.clip(gate * 1.45, 0.0, 1.0)

    sample_positions = np.arange(mono.size, dtype=np.float64) / hop
    frequency = np.interp(sample_positions, indexes, frequency_frames)
    amplitude = np.interp(sample_positions, indexes, amplitude_frames)
    details = {
        "voiced_fraction": round(float(np.mean(valid)), 6),
        "median_pitch_hz": round(float(np.median(f0[valid])), 4),
        "median_confidence": round(float(np.median(probability[valid])), 6),
    }
    return frequency, amplitude, details


def _harmonic_levels(fingerprint: SynthFingerprint | None, voice: str) -> np.ndarray:
    default = np.asarray([1.0 / harmonic for harmonic in range(1, 13)], dtype=np.float64)
    if fingerprint is None or not fingerprint.harmonic_levels:
        measured = default
    else:
        measured = np.asarray(fingerprint.harmonic_levels[:12], dtype=np.float64)
        if measured.size < default.size:
            measured = np.pad(measured, (0, default.size - measured.size), constant_values=0.0)
        measured = measured * 0.62 + default * 0.38
    rolloff = np.exp(-np.arange(1, 13) / (6.8 if voice == "bass" else 10.5))
    levels = measured * rolloff
    return levels / max(1e-9, float(np.sum(levels)))


def synthesize_conditioned_saw(
    frequency: np.ndarray,
    amplitude: np.ndarray,
    *,
    voice: str,
    fingerprint: SynthFingerprint | None,
) -> np.ndarray:
    """Drive an alias-limited saw family from continuous source contours."""

    phase = 2.0 * np.pi * np.cumsum(frequency) / OUTPUT_RATE
    levels = _harmonic_levels(fingerprint, voice)

    def oscillator(detune_cents: float) -> np.ndarray:
        detune = 2.0 ** (detune_cents / 1_200.0)
        result = np.zeros(frequency.size, dtype=np.float64)
        for harmonic, level in enumerate(levels, start=1):
            below_nyquist = frequency * harmonic * detune < OUTPUT_RATE * 0.46
            polarity = 1.0 if harmonic % 2 else -1.0
            result += (
                np.sin(phase * harmonic * detune + harmonic * 0.071)
                * below_nyquist
                * level
                * polarity
            )
        return result

    center = oscillator(0.0)
    if voice == "bass":
        sub = np.sin(phase * 0.5) * 0.18
        biased = center + sub + 0.055
        shaped = np.tanh(biased * 2.35) - math.tanh(0.055 * 2.35)
        mono = (center * 0.24 + shaped * 0.76) * amplitude
        return np.column_stack((mono, mono))

    width = fingerprint.stereo_width if fingerprint else 0.7
    detune = (
        1.4 + min(2.8, width * 2.2)
        if voice == "lead"
        else 2.6 + min(5.4, width * 4.0)
    )
    left = (center * 0.44 + oscillator(-detune) * 0.56) * amplitude
    right = (center * 0.44 + oscillator(detune) * 0.56) * amplitude
    return np.tanh(np.column_stack((left, right)) * 1.45)


def synthesize_performance_guided_lead(
    note: SymbolicNote,
    count: int,
    *,
    source_frequency: np.ndarray,
    source_amplitude: np.ndarray,
    pitch_bend_depth: float,
    articulation_depth: float,
    pulse_mix: float,
) -> np.ndarray:
    """Retain a symbolic note while borrowing expression from its source phrase.

    Absolute source pitches are deliberately discarded: separation artifacts can
    put a harmonic in the wrong octave.  The stable symbolic pitch remains the
    center, while only a tightly bounded relative contour and performance gate
    survive.  This gives the retro voice phrasing without turning stem noise into
    a new melody.
    """

    if count <= 0:
        return np.zeros(0, dtype=np.float64)
    frequency = np.asarray(source_frequency[:count], dtype=np.float64)
    amplitude = np.asarray(source_amplitude[:count], dtype=np.float64)
    if frequency.size < count:
        frequency = np.pad(frequency, (0, count - frequency.size), mode="edge")
    if amplitude.size < count:
        amplitude = np.pad(amplitude, (0, count - amplitude.size))

    base_frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    valid = np.isfinite(frequency) & (frequency > 20.0) & (amplitude > 0.04)
    if np.count_nonzero(valid) >= 4 and pitch_bend_depth > 0.0:
        source_midi = 69.0 + 12.0 * np.log2(np.maximum(frequency, 20.0) / 440.0)
        center = float(np.median(source_midi[valid]))
        relative = np.clip(_smooth_frames(source_midi - center, 4), -1.5, 1.5)
        guided_frequency = base_frequency * 2.0 ** (relative * pitch_bend_depth / 12.0)
    else:
        guided_frequency = np.full(count, base_frequency, dtype=np.float64)

    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    phase = 2.0 * np.pi * np.cumsum(guided_frequency) / OUTPUT_RATE
    phase += np.sin(2.0 * np.pi * 5.35 * time) * 0.052
    width = 0.42 + np.sin(2.0 * np.pi * 0.72 * time) * 0.055
    pulse = np.where(np.mod(phase / (2.0 * np.pi), 1.0) < width, 1.0, -1.0)
    signal = _triangle(phase) * 0.58 + np.sin(phase * 2.0) * 0.16 + pulse * pulse_mix

    note_envelope = _adsr(
        count,
        OUTPUT_RATE,
        attack=0.009,
        decay=0.14,
        sustain=0.73,
        release=0.14,
    )
    performance = np.sqrt(np.clip(amplitude, 0.0, 1.0))
    performance = 0.28 + performance * 0.72
    expression = 1.0 + (performance - 1.0) * np.clip(articulation_depth, 0.0, 1.0)
    return np.tanh(signal * 1.08) * note_envelope * expression * (note.velocity / 127.0)


def _conditioned_saw_components(
    source: Path,
    *,
    start: float,
    duration: float,
    voice: str,
    fingerprint: SynthFingerprint | None,
    presence_target: float = 0.0,
    presence_max_boost: float = 1.0,
) -> tuple[np.ndarray, dict[str, float], np.ndarray, np.ndarray]:
    stereo = _load_audio(source, start=start, duration=duration)
    frequency, amplitude, details = _pitch_and_amplitude_contours(np.mean(stereo, axis=0), voice=voice)
    if presence_target > 0.0 and presence_max_boost > 1.0:
        amplitude = normalize_activity_presence(
            amplitude,
            target_level=presence_target,
            max_boost=presence_max_boost,
            min_activity=0.04 if voice in {"bass", "synth"} else 0.025,
        )
    output = synthesize_conditioned_saw(
        frequency,
        amplitude,
        voice=voice,
        fingerprint=fingerprint,
    )
    peak = float(np.max(np.abs(output)))
    if peak > 1e-9:
        output *= min(1.0, 0.86 / peak)
    return output, details, frequency, amplitude


def conditioned_saw_bus(
    source: Path,
    *,
    start: float,
    duration: float,
    voice: str,
    fingerprint: SynthFingerprint | None,
    presence_target: float = 0.0,
    presence_max_boost: float = 1.0,
) -> tuple[np.ndarray, dict[str, float]]:
    output, details, _, _ = _conditioned_saw_components(
        source,
        start=start,
        duration=duration,
        voice=voice,
        fingerprint=fingerprint,
        presence_target=presence_target,
        presence_max_boost=presence_max_boost,
    )
    return output, details


def retro_sample_bus(
    source: Path,
    *,
    start: float,
    duration: float,
    sample_rate: int,
    bits: int,
    drive: float,
) -> np.ndarray:
    """Convert an isolated performance into deliberate early-console sample playback."""

    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for guided music experiments") from exc

    audio = _load_audio(source, start=start, duration=duration)
    reduced = librosa.resample(audio, orig_sr=OUTPUT_RATE, target_sr=sample_rate, axis=-1)
    restored = librosa.resample(reduced, orig_sr=sample_rate, target_sr=OUTPUT_RATE, axis=-1)
    expected = audio.shape[1]
    restored = np.pad(restored, ((0, 0), (0, max(0, expected - restored.shape[1]))))[:, :expected]
    restored = np.tanh(restored * drive) / math.tanh(drive)
    levels = float(2 ** (bits - 1) - 1)
    restored = np.round(restored * levels) / levels
    # Return sample-major stereo to match the synthesis buses.
    return restored.T


def _symbolic_premix(
    arrangement: SymbolicArrangement,
    *,
    duration: float,
    profile: OmegaChipProfile,
    voice_fingerprints: dict[str, SynthFingerprint],
    include_plucked: bool = True,
    include_lead: bool = True,
    lead_frequency_contour: np.ndarray | None = None,
    lead_amplitude_contour: np.ndarray | None = None,
    lead_pitch_bend_depth: float = 0.0,
    lead_articulation_depth: float = 0.0,
    lead_guidance_regions: tuple[tuple[float, float], ...] = (),
) -> np.ndarray:
    total = max(1, round(duration * OUTPUT_RATE))
    buses = {
        name: np.zeros((total, 2), dtype=np.float64)
        for name in ("lead", "harmony", "arpeggio", "instrument")
    }
    notes = (*arrangement.notes, *omega_arpeggio_notes(arrangement))
    harmony_pans = {"harmony-1": -0.72, "harmony-2": 0.10, "harmony-3": 0.66}
    previous_by_role: dict[str, SymbolicNote] = {}
    for note_index, note in enumerate(notes):
        archetype = _instrument_archetype(note.role)
        if (
            note.role == "bass"
            or (note.role == "lead" and not include_lead)
            or archetype == "sustained-synth"
            or (archetype == "plucked-string" and not include_plucked)
            or note.start >= duration
        ):
            continue
        bus_name = (
            "harmony"
            if note.role.startswith("harmony")
            else "instrument"
            if note.role.startswith("instrument-")
            else note.role
        )
        if bus_name not in buses:
            continue
        first = max(0, round(note.start * OUTPUT_RATE))
        release = 0.20 if bus_name == "harmony" else 0.15
        last = min(total, round((note.end + release) * OUTPUT_RATE))
        if last <= first:
            continue
        previous = previous_by_role.get(note.role)
        previous_pitch = previous.pitch if previous and note.start - previous.end <= 0.14 else None
        if (
            note.role == "lead"
            and lead_frequency_contour is not None
            and lead_amplitude_contour is not None
            and (
                not lead_guidance_regions
                or any(start < note.end and note.start < end for start, end in lead_guidance_regions)
            )
        ):
            signal = synthesize_performance_guided_lead(
                note,
                last - first,
                source_frequency=lead_frequency_contour[first:last],
                source_amplitude=lead_amplitude_contour[first:last],
                pitch_bend_depth=lead_pitch_bend_depth,
                articulation_depth=lead_articulation_depth,
                pulse_mix=profile.pulse_mix,
            )
        else:
            signal = _omega_chip_note(
                note,
                last - first,
                profile,
                voice_fingerprints,
                previous_pitch,
            )
        previous_by_role[note.role] = note
        if note.role == "lead":
            pan = -0.10 * profile.stereo_width
        elif note.role == "arpeggio":
            pan = (-0.48 if note_index % 2 else 0.48) * profile.stereo_width
        elif note.role.startswith("instrument-"):
            pan = _stable_instrument_pan(note.role) * profile.stereo_width
        else:
            pan = harmony_pans.get(note.role, 0.0) * profile.stereo_width
        buses[bus_name][first:last, 0] += signal * math.sqrt((1.0 - pan) * 0.5)
        buses[bus_name][first:last, 1] += signal * math.sqrt((1.0 + pan) * 0.5)

    lead = _cross_echo(buses["lead"], 0.096, profile.echo_gain * 0.72)
    harmony = _cross_echo(buses["harmony"], 0.168, profile.echo_gain * 0.48)
    arpeggio = _cross_echo(buses["arpeggio"], 0.073, profile.echo_gain * 0.34)
    instrument = _cross_echo(buses["instrument"], 0.118, profile.echo_gain * 0.28)
    output = lead * profile.lead_gain
    output += harmony * profile.harmony_gain * 0.76
    output += arpeggio * profile.arpeggio_gain * 0.72
    output += instrument * 0.31
    return output


def _region_envelope(
    total: int,
    regions: tuple[tuple[float, float], ...],
    *,
    source_start: float = 0.0,
    fade_seconds: float = 0.045,
) -> np.ndarray:
    envelope = np.zeros(total, dtype=np.float64)
    fade = max(1, round(fade_seconds * OUTPUT_RATE))
    for start, end in regions:
        first = max(0, min(total, round((start - source_start) * OUTPUT_RATE)))
        last = max(first, min(total, round((end - source_start) * OUTPUT_RATE)))
        if last <= first:
            continue
        envelope[first:last] = 1.0
        fade_in_last = min(last, first + fade)
        if fade_in_last > first:
            progress = np.linspace(0.0, 1.0, fade_in_last - first)
            envelope[first:fade_in_last] *= progress * progress * (3.0 - 2.0 * progress)
        fade_out_first = max(first, last - fade)
        if last > fade_out_first:
            progress = np.linspace(1.0, 0.0, last - fade_out_first)
            envelope[fade_out_first:last] *= progress * progress * (3.0 - 2.0 * progress)
    return envelope


def _inventory_regions(
    inventory: InstrumentInventory | None,
    archetype: str,
    duration: float,
    source_start: float = 0.0,
) -> tuple[tuple[float, float], ...]:
    if inventory is None:
        return ((source_start, source_start + duration),)
    offset = inventory.source_offset
    regions = [
        (offset + start, offset + end)
        for candidate in inventory.candidates
        if candidate.promoted and candidate.archetype == archetype
        for start, end in candidate.regions
        if offset + start < source_start + duration and offset + end > source_start
    ]
    return tuple(sorted(regions))


def _write_pcm(target: Path, audio: np.ndarray) -> None:
    peak = float(np.max(np.abs(audio)))
    if peak > 1e-9:
        audio = audio * min(1.0, 0.92 / peak)
    pcm = np.round(np.clip(audio, -1.0, 1.0) * 32_767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(OUTPUT_RATE)
        stream.writeframes(pcm.tobytes())


def render_guided_set(
    *,
    arrangement: SymbolicArrangement,
    lead_stem: Path,
    bass_stem: Path,
    synth_stem: Path,
    drum_stem: Path,
    sampled_instrument_stem: Path | None,
    instrument_inventory: InstrumentInventory | None,
    output: Path,
    duration: float,
    source_start: float = 0.0,
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
    lead_guidance_regions: tuple[tuple[float, float], ...] = (),
    adaptive_presence: bool = False,
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    output.mkdir(parents=True, exist_ok=True)
    fingerprints = voice_fingerprints or {}
    profile = OMEGA_CHIP_PROFILES["balanced"]
    symbolic_variants = {
        (include_pluck, include_lead): _symbolic_premix(
            arrangement,
            duration=duration,
            profile=profile,
            voice_fingerprints=fingerprints,
            include_plucked=include_pluck,
            include_lead=include_lead,
        )
        for include_pluck in (False, True)
        for include_lead in (False, True)
    }
    symbolic_with_pluck = symbolic_variants[(True, True)]
    lead, lead_details, lead_frequency, lead_amplitude = _conditioned_saw_components(
        lead_stem,
        start=source_start,
        duration=duration,
        voice="lead",
        fingerprint=fingerprints.get("lead"),
        presence_target=0.42 if adaptive_presence else 0.0,
        presence_max_boost=4.0 if adaptive_presence else 1.0,
    )
    bass, bass_details = conditioned_saw_bus(
        bass_stem,
        start=source_start,
        duration=duration,
        voice="bass",
        fingerprint=fingerprints.get("bass"),
        presence_target=0.34 if adaptive_presence else 0.0,
        presence_max_boost=2.6 if adaptive_presence else 1.0,
    )
    synth, synth_details = conditioned_saw_bus(
        synth_stem,
        start=source_start,
        duration=duration,
        voice="synth",
        fingerprint=fingerprints.get("synth"),
        presence_target=0.30 if adaptive_presence else 0.0,
        presence_max_boost=2.6 if adaptive_presence else 1.0,
    )
    drums = retro_sample_bus(
        drum_stem,
        start=source_start,
        duration=duration,
        sample_rate=16_000,
        bits=10,
        drive=1.36,
    )
    sampled = (
        retro_sample_bus(
            sampled_instrument_stem,
            start=source_start,
            duration=duration,
            sample_rate=14_000,
            bits=9,
            drive=1.18,
        )
        if sampled_instrument_stem
        else np.zeros_like(symbolic_with_pluck)
    )

    total = symbolic_with_pluck.shape[0]
    synth_regions = _inventory_regions(
        instrument_inventory, "sustained-synth", duration, source_start
    )
    pluck_regions = _inventory_regions(
        instrument_inventory, "plucked-string", duration, source_start
    )
    synth *= _region_envelope(total, synth_regions, source_start=source_start)[:, None]
    sampled *= _region_envelope(total, pluck_regions, source_start=source_start)[:, None]

    buses = {
        "00-conditioned-lead": lead,
        "01-conditioned-bass": bass,
        "02-conditioned-synth": synth,
        "03-retro-source-drums": drums,
        "04-symbolic-remainder": symbolic_with_pluck,
    }
    for name, audio in buses.items():
        wav = output / f"{name}.wav"
        _write_pcm(wav, audio)
        _encode_review(ffmpeg, wav, wav.with_suffix(".ogg"))

    rendered_profiles = [
        value
        for value in GUIDED_MIX_PROFILES.values()
        if lead_guidance_regions
        or (value.lead_pitch_bend_depth == 0.0 and value.lead_articulation_depth == 0.0)
    ]
    for index, mix_profile in enumerate(rendered_profiles, start=10):
        if mix_profile.lead_pitch_bend_depth or mix_profile.lead_articulation_depth:
            symbolic = _symbolic_premix(
                arrangement,
                duration=duration,
                profile=profile,
                voice_fingerprints=fingerprints,
                include_plucked=mix_profile.symbolic_pluck,
                include_lead=mix_profile.symbolic_lead,
                lead_frequency_contour=lead_frequency,
                lead_amplitude_contour=lead_amplitude,
                lead_pitch_bend_depth=mix_profile.lead_pitch_bend_depth,
                lead_articulation_depth=mix_profile.lead_articulation_depth,
                lead_guidance_regions=lead_guidance_regions,
            )
        else:
            symbolic = symbolic_variants[(mix_profile.symbolic_pluck, mix_profile.symbolic_lead)]
        mix = symbolic * mix_profile.symbolic_gain
        mix += lead * mix_profile.lead_gain
        mix += bass * mix_profile.bass_gain
        mix += synth * mix_profile.synth_gain
        mix += drums * mix_profile.drum_gain
        mix += sampled * mix_profile.sampled_instrument_gain
        mix = np.tanh(mix * mix_profile.drive) / math.tanh(mix_profile.drive)
        mix = np.round(mix * 8_192.0) / 8_192.0
        wav = output / f"{index:02d}-{mix_profile.name}.wav"
        _write_pcm(wav, mix)
        _encode_review(ffmpeg, wav, wav.with_suffix(".ogg"))

    manifest = {
        "schemaVersion": 1,
        "approach": "symbolic-plus-continuous-stem-conditioned-resynthesis",
        "duration": duration,
        "sourceStart": source_start,
        "profiles": {value.name: asdict(value) for value in rendered_profiles},
        "leadGuidanceRegions": lead_guidance_regions,
        "analysis": {"lead": lead_details, "bass": bass_details, "synth": synth_details},
        "regions": {"sustainedSynth": synth_regions, "pluckedString": pluck_regions},
        "sources": {
            "arrangement": str(arrangement.source.mix_sha256),
            "lead": str(lead_stem),
            "bass": str(bass_stem),
            "synth": str(synth_stem),
            "drums": str(drum_stem),
            "sampledInstrument": str(sampled_instrument_stem) if sampled_instrument_stem else None,
        },
        "voiceFingerprints": sorted(fingerprints),
        "adaptivePresence": adaptive_presence,
    }
    target = output / "guided-render-manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Render CatchyTune-guided Omega Chip experiments")
    parser.add_argument("--arrangement", type=Path, required=True)
    parser.add_argument("--lead-stem", type=Path, required=True)
    parser.add_argument("--bass-stem", type=Path, required=True)
    parser.add_argument("--synth-stem", type=Path, required=True)
    parser.add_argument("--drum-stem", type=Path, required=True)
    parser.add_argument("--sampled-instrument-stem", type=Path)
    parser.add_argument("--instrument-inventory", type=Path)
    parser.add_argument("--voice-fingerprint", action="append", default=[], metavar="ROLE=PATH")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=45.0)
    parser.add_argument("--source-start", type=float, default=0.0)
    parser.add_argument(
        "--adaptive-presence",
        action="store_true",
        help="Lift sustained quiet phrases while preserving silence and sparse leakage.",
    )
    parser.add_argument(
        "--lead-guidance-region",
        action="append",
        default=[],
        metavar="START:END",
        help="Apply source phrasing to symbolic lead notes overlapping this interval.",
    )
    args = parser.parse_args()

    fingerprints: dict[str, SynthFingerprint] = {}
    for specification in args.voice_fingerprint:
        if "=" not in specification:
            parser.error("--voice-fingerprint must use ROLE=PATH")
        role, raw_path = specification.split("=", 1)
        role = role.strip()
        if not role or role in fingerprints:
            parser.error("--voice-fingerprint roles must be non-empty and unique")
        fingerprints[role] = load_synth_fingerprint(Path(raw_path))

    arrangement = load_arrangement(args.arrangement)
    guidance_regions = []
    for specification in args.lead_guidance_region:
        try:
            raw_start, raw_end = specification.split(":", 1)
            region = (float(raw_start), float(raw_end))
        except ValueError:
            parser.error("--lead-guidance-region must use START:END seconds")
        if region[0] < 0.0 or region[1] <= region[0]:
            parser.error("--lead-guidance-region requires 0 <= START < END")
        guidance_regions.append(region)
    result = render_guided_set(
        arrangement=arrangement,
        lead_stem=args.lead_stem,
        bass_stem=args.bass_stem,
        synth_stem=args.synth_stem,
        drum_stem=args.drum_stem,
        sampled_instrument_stem=args.sampled_instrument_stem,
        instrument_inventory=(
            load_instrument_inventory(args.instrument_inventory)
            if args.instrument_inventory
            else None
        ),
        output=args.output,
        duration=max(1.0, min(args.duration, arrangement.duration)),
        source_start=max(0.0, args.source_start),
        voice_fingerprints=fingerprints,
        lead_guidance_regions=tuple(guidance_regions),
        adaptive_presence=args.adaptive_presence,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
