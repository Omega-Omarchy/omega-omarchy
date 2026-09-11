"""Turn an isolated vocal performance into a source-timed Omega Chip lead."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import shutil

import numpy as np

from .guided_music import (
    _load_audio,
    _pitch_and_amplitude_contours,
    _region_envelope,
    _symbolic_premix,
    _write_pcm,
    normalize_activity_presence,
    synthesize_conditioned_saw,
)
from .music_diagnostic import (
    OMEGA_CHIP_PROFILES,
    OUTPUT_RATE,
    SymbolicArrangement,
    SynthFingerprint,
    _encode_review,
    load_arrangement,
    load_synth_fingerprint,
)


@dataclass(frozen=True)
class VocalChipProfile:
    name: str
    tone: str
    gain: float
    pitch_quantization: float
    octave_mix: float = 0.0
    active_floor: float = 0.0
    compression_gamma: float = 1.0
    gate_knee: float = 0.12
    sustain_recovery: float = 0.0
    sustain_proximity_seconds: float = 0.0
    symbolic_pitch_anchor: float = 0.0


VOCAL_CHIP_PROFILES = {
    "saw-expressive": VocalChipProfile("saw-expressive", "saw", 0.30, 0.82),
    "saw-articulated": VocalChipProfile(
        "saw-articulated", "saw", 0.24, 0.82, compression_gamma=1.25, gate_knee=0.12
    ),
    "saw-wispy": VocalChipProfile(
        "saw-wispy", "saw", 0.22, 0.82, compression_gamma=1.55, gate_knee=0.10
    ),
    "air-channel": VocalChipProfile(
        "air-channel", "saw-air", 0.23, 0.82, compression_gamma=1.40, gate_knee=0.10
    ),
    "air-sustain": VocalChipProfile(
        "air-sustain",
        "saw-air",
        0.23,
        0.82,
        compression_gamma=1.40,
        gate_knee=0.10,
        sustain_recovery=0.72,
        sustain_proximity_seconds=0.22,
    ),
    "air-long-sustain": VocalChipProfile(
        "air-long-sustain",
        "saw-air",
        0.22,
        0.82,
        compression_gamma=1.48,
        gate_knee=0.10,
        sustain_recovery=1.0,
        sustain_proximity_seconds=0.38,
    ),
    "guided-saw-sustain": VocalChipProfile(
        "guided-saw-sustain",
        "saw",
        0.24,
        0.82,
        compression_gamma=1.25,
        gate_knee=0.12,
        sustain_recovery=0.72,
        sustain_proximity_seconds=0.22,
        symbolic_pitch_anchor=1.0,
    ),
    "guided-tonal-air": VocalChipProfile(
        "guided-tonal-air",
        "tonal-air",
        0.23,
        0.82,
        compression_gamma=1.38,
        gate_knee=0.10,
        sustain_recovery=0.72,
        sustain_proximity_seconds=0.22,
        symbolic_pitch_anchor=1.0,
    ),
    "saw-lifted": VocalChipProfile(
        "saw-lifted", "saw", 0.30, 0.82, active_floor=0.42, compression_gamma=0.60
    ),
    "saw-assertive": VocalChipProfile(
        "saw-assertive",
        "saw",
        0.30,
        0.82,
        active_floor=0.58,
        compression_gamma=0.46,
        gate_knee=0.10,
    ),
    "saw-arcade": VocalChipProfile(
        "saw-arcade",
        "saw",
        0.30,
        0.82,
        active_floor=0.70,
        compression_gamma=0.35,
        gate_knee=0.08,
    ),
    "saw-crisp": VocalChipProfile("saw-crisp", "saw", 0.30, 1.0),
    "pulse-triangle": VocalChipProfile("pulse-triangle", "pulse-triangle", 0.32, 0.94),
    "octave-spark": VocalChipProfile("octave-spark", "pulse-triangle", 0.30, 0.94, 0.24),
}


def quantize_frequency(frequency: np.ndarray, amount: float, *, hop: int = 256) -> np.ndarray:
    frequency = np.asarray(frequency, dtype=np.float64)
    amount = float(np.clip(amount, 0.0, 1.0))
    if frequency.size <= hop:
        midi = 69.0 + 12.0 * np.log2(np.maximum(frequency, 20.0) / 440.0)
        midi = np.round(midi) * amount + midi * (1.0 - amount)
        return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)
    # Quantize on the analysis frames, then interpolate. Quantizing after
    # sample interpolation creates artificial portamento between every frame.
    frame_indexes = np.arange(0, frequency.size, hop)
    frame_midi = 69.0 + 12.0 * np.log2(
        np.maximum(frequency[frame_indexes], 20.0) / 440.0
    )
    frame_midi = np.round(frame_midi) * amount + frame_midi * (1.0 - amount)
    frame_frequency = 440.0 * 2.0 ** ((frame_midi - 69.0) / 12.0)
    return np.interp(np.arange(frequency.size), frame_indexes, frame_frequency)


def strengthen_vocal_amplitude(
    amplitude: np.ndarray,
    *,
    active_floor: float,
    compression_gamma: float,
    gate_knee: float,
) -> np.ndarray:
    """Raise voiced-note strength without filling intentional phrase gaps."""

    amplitude = np.clip(np.asarray(amplitude, dtype=np.float64), 0.0, 1.0)
    if active_floor <= 0.0 and compression_gamma == 1.0:
        return amplitude.copy()
    knee = max(1e-4, gate_knee)
    gate = np.clip(amplitude / knee, 0.0, 1.0)
    gate = gate * gate * (3.0 - 2.0 * gate)
    compressed = np.power(amplitude, max(0.05, compression_gamma))
    level = np.clip(active_floor, 0.0, 0.95) + (1.0 - active_floor) * compressed
    return gate * level


def recover_vocal_sustain(
    amplitude: np.ndarray,
    vocal: np.ndarray,
    *,
    strength: float,
    proximity_seconds: float,
    hop: int = 256,
) -> np.ndarray:
    """Bridge pitch-confidence dropouts only while vocal energy remains audible."""

    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for vocal sustain recovery") from exc

    values = np.clip(np.asarray(amplitude, dtype=np.float64), 0.0, 1.35)
    mono = np.asarray(vocal, dtype=np.float64)
    if values.size == 0 or strength <= 0.0 or proximity_seconds <= 0.0:
        return values.copy()
    hop = max(1, int(hop))
    frames = values[::hop]
    rms = librosa.feature.rms(y=mono, frame_length=1_024, hop_length=hop)[0]
    count = min(frames.size, rms.size)
    frames = frames[:count]
    rms = rms[:count]
    noise = float(np.percentile(rms, 20))
    active = float(np.percentile(rms, 75))
    energy = np.clip((rms - noise) / max(1e-8, active - noise), 0.0, 1.0)
    energy = energy * energy * (3.0 - 2.0 * energy)

    pitched = frames > 0.005
    radius = max(1, round(proximity_seconds * OUTPUT_RATE / hop))
    nearby = np.convolve(
        np.pad(pitched.astype(np.float64), (radius, radius)),
        np.ones(radius * 2 + 1),
        mode="valid",
    ) > 0.0
    pitched_energy = energy[pitched]
    pitched_amplitude = frames[pitched]
    if pitched_energy.size == 0:
        return values.copy()
    scale = float(np.median(pitched_amplitude)) / max(
        1e-6, float(np.median(pitched_energy))
    )
    scale = float(np.clip(scale, 0.45, 1.6))
    recovered = energy * nearby * scale * float(np.clip(strength, 0.0, 1.0))
    merged = np.maximum(frames, recovered)
    sample_values = np.interp(
        np.arange(values.size),
        np.arange(count) * hop,
        merged,
    )
    # Multiplication by the measured energy envelope ensures a true stutter gap
    # remains zero even when reliable pitch frames exist on both sides.
    sample_energy = np.interp(
        np.arange(values.size),
        np.arange(count) * hop,
        energy,
    )
    extended_only = values <= 0.005
    sample_values[extended_only] *= sample_energy[extended_only] > 1e-4
    return np.clip(np.maximum(values, sample_values), 0.0, 1.35)


def anchor_frequency_to_symbolic_lead(
    frequency: np.ndarray,
    amplitude: np.ndarray,
    arrangement: SymbolicArrangement,
    *,
    amount: float,
    bend_depth: float = 0.24,
) -> np.ndarray:
    """Use symbolic lead notes as pitch centers while retaining performed bends."""

    source = np.asarray(frequency, dtype=np.float64)
    level = np.asarray(amplitude, dtype=np.float64)
    anchored = source.copy()
    blend = float(np.clip(amount, 0.0, 1.0))
    if source.size == 0 or blend <= 0.0:
        return anchored
    source_midi = 69.0 + 12.0 * np.log2(np.maximum(source, 20.0) / 440.0)
    total = source.size
    for note in arrangement.notes:
        if note.role != "lead" or note.start >= arrangement.duration:
            continue
        first = max(0, min(total, round(note.start * OUTPUT_RATE)))
        last = max(first, min(total, round(note.end * OUTPUT_RATE)))
        if last <= first:
            continue
        note_source = source_midi[first:last]
        valid = level[first:last] > 0.005
        center = float(np.median(note_source[valid])) if np.any(valid) else float(np.median(note_source))
        relative = np.clip(note_source - center, -1.5, 1.5) * bend_depth
        target_midi = note.pitch + relative
        mixed_midi = source_midi[first:last] * (1.0 - blend) + target_midi * blend
        anchored[first:last] = 440.0 * 2.0 ** ((mixed_midi - 69.0) / 12.0)
    return anchored


def enhance_bed_delivery(
    audio: np.ndarray,
    reference: np.ndarray,
    *,
    compression_gamma: float = 0.68,
    max_boost_db: float = 4.5,
    frame_seconds: float = 0.05,
    smoothing_seconds: float = 0.45,
) -> np.ndarray:
    """Apply source-gated upward compression to a softly delivered music bed."""

    candidate = np.asarray(audio, dtype=np.float64)
    source = np.asarray(reference, dtype=np.float64)
    if candidate.ndim != 2 or source.ndim != 2:
        raise ValueError("audio and reference must be sample-major stereo arrays")
    total = min(candidate.shape[0], source.shape[0])
    if total == 0:
        return candidate.copy()
    candidate = candidate[:total]
    source = source[:total]
    frame = max(1, round(frame_seconds * OUTPUT_RATE))
    frames = math.ceil(total / frame)
    padded = frames * frame

    def rms(values: np.ndarray) -> np.ndarray:
        values = np.pad(values, ((0, padded - total), (0, 0)))
        return np.sqrt(np.mean(values.reshape(frames, frame, 2) ** 2, axis=(1, 2)))

    candidate_rms = rms(candidate)
    source_rms = rms(source)
    source_anchor = max(1e-7, float(np.percentile(source_rms, 85)))
    threshold = source_anchor * 0.025
    activity = np.clip((source_rms - threshold) / max(1e-7, threshold * 3.0), 0.0, 1.0)
    activity = activity * activity * (3.0 - 2.0 * activity)
    measured = candidate_rms[(activity > 0.25) & (candidate_rms > 1e-7)]
    if measured.size == 0:
        return candidate.copy()
    anchor = max(1e-7, float(np.percentile(measured, 70)))
    gamma = float(np.clip(compression_gamma, 0.1, 1.0))
    desired = anchor * np.power(np.maximum(candidate_rms, 1e-7) / anchor, gamma)
    requested = np.maximum(1.0, desired / np.maximum(candidate_rms, 1e-7))
    maximum = 10.0 ** (max(0.0, max_boost_db) / 20.0)
    frame_gain = 1.0 + (np.clip(requested, 1.0, maximum) - 1.0) * activity

    smooth_frames = min(frames, max(1, round(smoothing_seconds / frame_seconds)))
    if smooth_frames > 1:
        if smooth_frames % 2 == 0:
            smooth_frames -= 1
        kernel = np.hanning(smooth_frames)
        kernel /= max(1e-9, float(np.sum(kernel)))
        pad = smooth_frames // 2
        frame_gain = np.convolve(np.pad(frame_gain, (pad, pad), mode="edge"), kernel, mode="valid")
    sample_gain = np.interp(
        np.arange(total),
        np.minimum(np.arange(frames) * frame + frame // 2, total - 1),
        frame_gain,
    )
    return candidate * sample_gain[:, None]


def synthesize_vocal_chip(
    frequency: np.ndarray,
    amplitude: np.ndarray,
    *,
    tone: str,
    octave_mix: float = 0.0,
) -> np.ndarray:
    """Render a cleaned vocal contour as an oscillator melody, never as speech."""

    if tone in {"saw", "saw-air", "tonal-air"}:
        base = synthesize_conditioned_saw(
            frequency,
            amplitude,
            voice="lead",
            fingerprint=None,
        )
        if tone == "saw-air":
            # A deterministic low-rate noise channel lets breathy performances
            # remain airy instead of forcing every syllable into a solid saw.
            stride = max(1, OUTPUT_RATE // 8_000)
            count = math.ceil(frequency.size / stride)
            noise = np.random.default_rng(0x0A3EA).uniform(-1.0, 1.0, count)
            noise = np.repeat(noise, stride)[: frequency.size]
            noise = noise - np.concatenate(([0.0], noise[:-1])) * 0.58
            air = np.column_stack((noise, np.roll(noise, 3))) * amplitude[:, None]
            base = base * 0.72 + air * 0.18
        elif tone == "tonal-air":
            phase = 2.0 * np.pi * np.cumsum(frequency) / OUTPUT_RATE
            shimmer = np.column_stack(
                (np.sin(phase * 2.002), np.sin(phase * 1.998 + 0.17))
            ) * amplitude[:, None]
            stride = max(1, OUTPUT_RATE // 6_000)
            count = math.ceil(frequency.size / stride)
            noise = np.random.default_rng(0x70A1A).uniform(-1.0, 1.0, count)
            noise = np.repeat(noise, stride)[: frequency.size]
            air = np.column_stack((noise, np.roll(noise, 5))) * amplitude[:, None]
            base = base * 0.86 + shimmer * 0.09 + air * 0.035
    elif tone == "pulse-triangle":
        phase = 2.0 * np.pi * np.cumsum(frequency) / OUTPUT_RATE
        triangle = (2.0 / np.pi) * np.arcsin(np.sin(phase))
        width = 0.43 + np.sin(np.arange(frequency.size) / OUTPUT_RATE * 2.0 * np.pi * 0.61) * 0.045
        pulse = np.where(np.mod(phase / (2.0 * np.pi), 1.0) < width, 1.0, -1.0)
        center = triangle * 0.62 + pulse * 0.22 + np.sin(phase * 2.0) * 0.13
        detuned = np.sin(phase * 1.0022) * 0.10
        left = (center + detuned) * amplitude
        right = (center - detuned) * amplitude
        base = np.tanh(np.column_stack((left, right)) * 1.12)
    else:
        raise ValueError(f"unsupported vocal chip tone: {tone}")

    if octave_mix > 0.0:
        upper = synthesize_conditioned_saw(
            frequency * 2.0,
            amplitude,
            voice="lead",
            fingerprint=None,
        )
        base = base * (1.0 - octave_mix) + upper * octave_mix
    peak = float(np.max(np.abs(base)))
    if peak > 1e-9:
        base *= min(1.0, 0.86 / peak)
    return base


def _master(audio: np.ndarray, drive: float) -> np.ndarray:
    audio = np.tanh(audio * drive) / math.tanh(drive)
    return np.round(audio * 8_192.0) / 8_192.0


def render_vocal_chip_review(
    *,
    arrangement_path: Path,
    vocal_stem: Path,
    bass_bus: Path,
    synth_bus: Path,
    drum_bus: Path,
    output: Path,
    duration: float,
    vocal_regions: tuple[tuple[float, float], ...],
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
    adaptive_presence: bool = False,
    reference_bed_stems: tuple[Path, ...] = (),
    enhance_delivery: bool = False,
    profile_names: tuple[str, ...] = (),
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    output.mkdir(parents=True, exist_ok=True)
    arrangement = load_arrangement(arrangement_path)
    fingerprints = voice_fingerprints or {}
    omega_profile = OMEGA_CHIP_PROFILES["balanced"]
    symbolic = _symbolic_premix(
        arrangement,
        duration=duration,
        profile=omega_profile,
        voice_fingerprints=fingerprints,
        include_plucked=True,
        include_lead=False,
    )
    bass = _load_audio(bass_bus, start=0.0, duration=duration).T
    synth = _load_audio(synth_bus, start=0.0, duration=duration).T
    drums = _load_audio(drum_bus, start=0.0, duration=duration).T
    bed = symbolic * 0.72 + bass * 0.32 + synth * 0.29 + drums * 0.82
    if enhance_delivery:
        if not reference_bed_stems:
            raise ValueError("enhance_delivery requires at least one reference bed stem")
        reference_bed = np.zeros_like(bed)
        for source in reference_bed_stems:
            reference_bed += _load_audio(source, start=0.0, duration=duration).T
        bed = enhance_bed_delivery(bed, reference_bed)

    vocal = _load_audio(vocal_stem, start=0.0, duration=duration)
    vocal_mono = np.mean(vocal, axis=0)
    raw_frequency, amplitude, details = _pitch_and_amplitude_contours(
        vocal_mono,
        voice="lead",
        pitch_quantization=0.0,
    )
    activity = _region_envelope(amplitude.size, vocal_regions, fade_seconds=0.12)
    amplitude *= activity
    if adaptive_presence:
        amplitude = normalize_activity_presence(
            amplitude,
            target_level=0.42,
            max_boost=4.0,
            min_activity=0.025,
        )

    selected_profiles = [
        (index, profile)
        for index, profile in enumerate(VOCAL_CHIP_PROFILES.values(), start=10)
        if not profile_names or profile.name in profile_names
    ]
    for index, profile in selected_profiles:
        profiled_amplitude = amplitude
        if profile.sustain_recovery > 0.0:
            profiled_amplitude = recover_vocal_sustain(
                amplitude,
                vocal_mono,
                strength=profile.sustain_recovery,
                proximity_seconds=profile.sustain_proximity_seconds,
            )
        profiled_frequency = raw_frequency
        if profile.symbolic_pitch_anchor > 0.0:
            profiled_frequency = anchor_frequency_to_symbolic_lead(
                raw_frequency,
                profiled_amplitude,
                arrangement,
                amount=profile.symbolic_pitch_anchor,
            )
        frequency = quantize_frequency(profiled_frequency, profile.pitch_quantization)
        strengthened = strengthen_vocal_amplitude(
            profiled_amplitude,
            active_floor=profile.active_floor,
            compression_gamma=profile.compression_gamma,
            gate_knee=profile.gate_knee,
        )
        lead = synthesize_vocal_chip(
            frequency,
            strengthened,
            tone=profile.tone,
            octave_mix=profile.octave_mix,
        )
        _write_pcm(output / "buses" / f"{profile.name}.wav", lead)
        mixed = _master(bed + lead * profile.gain, 1.16)
        wav = output / f"{index:02d}-{profile.name}.wav"
        _write_pcm(wav, mixed)
        _encode_review(ffmpeg, wav, wav.with_suffix(".ogg"))

    manifest = {
        "schemaVersion": 1,
        "approach": "source-timed-vocal-to-chip-melody",
        "arrangement": str(arrangement_path),
        "duration": duration,
        "profiles": {profile.name: asdict(profile) for _, profile in selected_profiles},
        "vocalAnalysis": details,
        "vocalRegions": vocal_regions,
        "vocalStem": str(vocal_stem),
        "adaptivePresence": adaptive_presence,
        "enhancedBedDelivery": enhance_delivery,
        "referenceBedStems": [str(source) for source in reference_bed_stems],
    }
    target = output / "vocal-chip-manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a performed vocal as an Omega Chip melody")
    parser.add_argument("--arrangement", type=Path, required=True)
    parser.add_argument("--vocal-stem", type=Path, required=True)
    parser.add_argument("--bass-bus", type=Path, required=True)
    parser.add_argument("--synth-bus", type=Path, required=True)
    parser.add_argument("--drum-bus", type=Path, required=True)
    parser.add_argument("--voice-fingerprint", action="append", default=[], metavar="ROLE=PATH")
    parser.add_argument("--vocal-region", action="append", default=[], metavar="START:END")
    parser.add_argument(
        "--adaptive-presence",
        action="store_true",
        help="Lift sustained quiet vocal phrases without filling silent gaps.",
    )
    parser.add_argument(
        "--reference-bed-stem",
        action="append",
        default=[],
        type=Path,
        help="Original non-vocal stem used to gate bed delivery enhancement; repeatable.",
    )
    parser.add_argument(
        "--enhance-bed-delivery",
        action="store_true",
        help="Apply source-gated upward compression to the retro music bed.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=45.0)
    parser.add_argument(
        "--profile",
        action="append",
        choices=tuple(VOCAL_CHIP_PROFILES),
        default=[],
        help="Render only the named profile; repeatable. Defaults to every profile.",
    )
    args = parser.parse_args()

    fingerprints = {}
    for specification in args.voice_fingerprint:
        if "=" not in specification:
            parser.error("--voice-fingerprint must use ROLE=PATH")
        role, raw_path = specification.split("=", 1)
        fingerprints[role] = load_synth_fingerprint(Path(raw_path))
    regions = []
    for specification in args.vocal_region:
        try:
            raw_start, raw_end = specification.split(":", 1)
            region = (float(raw_start), float(raw_end))
        except ValueError:
            parser.error("--vocal-region must use START:END seconds")
        if region[0] < 0.0 or region[1] <= region[0]:
            parser.error("--vocal-region requires 0 <= START < END")
        regions.append(region)
    if not regions:
        regions.append((0.0, max(1.0, args.duration)))

    result = render_vocal_chip_review(
        arrangement_path=args.arrangement,
        vocal_stem=args.vocal_stem,
        bass_bus=args.bass_bus,
        synth_bus=args.synth_bus,
        drum_bus=args.drum_bus,
        output=args.output,
        duration=max(1.0, args.duration),
        vocal_regions=tuple(regions),
        voice_fingerprints=fingerprints,
        adaptive_presence=args.adaptive_presence,
        reference_bed_stems=tuple(args.reference_bed_stem),
        enhance_delivery=args.enhance_bed_delivery,
        profile_names=tuple(args.profile),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
