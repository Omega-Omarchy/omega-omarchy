"""Offline symbolic music-transcription and console-render diagnostic.

This is deliberately an authoring tool, not a game or web dependency.  It
turns separated lead/bass/drum analysis tracks plus the original mix into one
auditable symbolic arrangement, then renders the *same events* through a
neutral GM reference, a sample-bank SNES proxy, and a four-operator FM
Genesis proxy.  Its purpose is to distinguish transcription failures from
instrument/rendering failures before any generated music enters the game.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave

import numpy as np


OUTPUT_RATE = 32_000
_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


@dataclass(frozen=True)
class SymbolicNote:
    role: str
    start: float
    end: float
    pitch: int
    velocity: int
    confidence: float | None = None
    pitch_curve: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class DrumHit:
    kind: str
    time: float
    velocity: int


@dataclass(frozen=True)
class Chord:
    start: float
    end: float
    root: int
    quality: str
    confidence: float

    @property
    def name(self) -> str:
        return f"{_NOTE_NAMES[self.root]}{'m' if self.quality == 'minor' else ''}"


@dataclass(frozen=True)
class SourceProvenance:
    separator: str
    mix_sha256: str
    vocals_sha256: str
    bass_sha256: str
    drums_sha256: str
    other_sha256: str = "unavailable"
    instrument_sha256: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SymbolicArrangement:
    schema_version: int
    duration: float
    bpm: float
    grid_origin: float
    key: str
    source_offset: float
    source: SourceProvenance
    notes: tuple[SymbolicNote, ...]
    drums: tuple[DrumHit, ...]
    chords: tuple[Chord, ...]
    timing_grid: tuple[float, ...] = ()


@dataclass(frozen=True)
class OmegaChipProfile:
    name: str
    lead_gain: float
    bass_gain: float
    harmony_gain: float
    drum_gain: float
    pulse_mix: float
    arpeggio_gain: float
    stereo_width: float
    echo_gain: float
    drive: float


@dataclass(frozen=True)
class SynthFingerprint:
    schema_version: int
    source_sha256: str
    source_offset: float
    duration: float
    sample_rate: int
    fundamental_median_hz: float
    harmonic_levels: tuple[float, ...]
    noise_mix: float
    stereo_width: float
    stereo_correlation: float
    attack: float
    decay: float
    sustain: float
    release: float
    vibrato_rate_hz: float
    vibrato_depth_cents: float
    selected_windows: tuple[tuple[float, float, float, float], ...]


@dataclass(frozen=True)
class InstrumentCandidate:
    """One recurring timbral identity recovered from an otherwise-unused stem."""

    candidate_id: str
    source_stem: str
    archetype: str
    confidence: float
    promoted: bool
    regions: tuple[tuple[float, float], ...]
    level_db: float
    harmonic_ratio: float
    spectral_flatness: float
    onset_density: float
    spectral_centroid_hz: float
    stereo_width: float


@dataclass(frozen=True)
class InstrumentInventory:
    schema_version: int
    source_offset: float
    duration: float
    window_seconds: float
    hop_seconds: float
    sources: tuple[tuple[str, str], ...]
    candidates: tuple[InstrumentCandidate, ...]


OMEGA_CHIP_PROFILES = {
    "balanced": OmegaChipProfile("balanced", 0.27, 0.35, 0.21, 0.84, 0.12, 0.068, 0.72, 0.13, 1.24),
    "vivid": OmegaChipProfile("vivid", 0.29, 0.33, 0.23, 0.88, 0.20, 0.105, 0.92, 0.19, 1.38),
}


def _run(command: list[str]) -> None:
    process = subprocess.run(command, check=False, capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or "music diagnostic command failed")


def _sha256(source: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def arrangement_payload(arrangement: SymbolicArrangement) -> dict[str, object]:
    payload = asdict(arrangement)
    payload["chords"] = [dict(asdict(chord), name=chord.name) for chord in arrangement.chords]
    payload["counts"] = {
        "leadNotes": sum(note.role == "lead" for note in arrangement.notes),
        "bassNotes": sum(note.role == "bass" for note in arrangement.notes),
        "harmonyNotes": sum(note.role.startswith("harmony") for note in arrangement.notes),
        "recoveredInstrumentNotes": sum(note.role.startswith("instrument-") for note in arrangement.notes),
        "drumHits": len(arrangement.drums),
        "chordChanges": len(arrangement.chords),
    }
    return payload


def save_arrangement(arrangement: SymbolicArrangement, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(arrangement_payload(arrangement), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_arrangement(source: Path) -> SymbolicArrangement:
    """Load an editable arrangement, including pre-schema diagnostic files."""

    payload = json.loads(source.read_text(encoding="utf-8"))
    raw_source = payload.get("source", {})
    provenance = SourceProvenance(
        separator=str(raw_source.get("separator", "unspecified")),
        mix_sha256=str(raw_source.get("mix_sha256", "unavailable")),
        vocals_sha256=str(raw_source.get("vocals_sha256", "unavailable")),
        bass_sha256=str(raw_source.get("bass_sha256", "unavailable")),
        drums_sha256=str(raw_source.get("drums_sha256", "unavailable")),
        other_sha256=str(raw_source.get("other_sha256", "unavailable")),
        instrument_sha256=tuple(
            (str(label), str(digest)) for label, digest in raw_source.get("instrument_sha256", ())
        ),
    )
    chords = tuple(
        Chord(
            start=float(chord["start"]),
            end=float(chord["end"]),
            root=int(chord["root"]),
            quality=str(chord["quality"]),
            confidence=float(chord["confidence"]),
        )
        for chord in payload["chords"]
    )
    return SymbolicArrangement(
        schema_version=int(payload.get("schema_version", 1)),
        duration=float(payload["duration"]),
        bpm=float(payload["bpm"]),
        grid_origin=float(payload.get("grid_origin", 0.0)),
        key=str(payload["key"]),
        source_offset=float(payload["source_offset"]),
        source=provenance,
        notes=tuple(SymbolicNote(**{**note, "pitch_curve": tuple(tuple(p) for p in note.get("pitch_curve", ()))})
                    for note in payload["notes"]),
        drums=tuple(DrumHit(**hit) for hit in payload["drums"]),
        chords=chords,
        timing_grid=tuple(float(time) for time in payload.get("timing_grid", ())),
    )


def save_synth_fingerprint(fingerprint: SynthFingerprint, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(fingerprint), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_synth_fingerprint(source: Path) -> SynthFingerprint:
    payload = json.loads(source.read_text(encoding="utf-8"))
    return SynthFingerprint(
        schema_version=int(payload["schema_version"]),
        source_sha256=str(payload["source_sha256"]),
        source_offset=float(payload["source_offset"]),
        duration=float(payload["duration"]),
        sample_rate=int(payload["sample_rate"]),
        fundamental_median_hz=float(payload["fundamental_median_hz"]),
        harmonic_levels=tuple(float(level) for level in payload["harmonic_levels"]),
        noise_mix=float(payload["noise_mix"]),
        stereo_width=float(payload["stereo_width"]),
        stereo_correlation=float(payload["stereo_correlation"]),
        attack=float(payload["attack"]),
        decay=float(payload["decay"]),
        sustain=float(payload["sustain"]),
        release=float(payload["release"]),
        vibrato_rate_hz=float(payload["vibrato_rate_hz"]),
        vibrato_depth_cents=float(payload["vibrato_depth_cents"]),
        selected_windows=tuple(tuple(float(value) for value in window) for window in payload["selected_windows"]),
    )


def save_instrument_inventory(inventory: InstrumentInventory, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(inventory), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_instrument_inventory(source: Path) -> InstrumentInventory:
    payload = json.loads(source.read_text(encoding="utf-8"))
    return InstrumentInventory(
        schema_version=int(payload["schema_version"]),
        source_offset=float(payload["source_offset"]),
        duration=float(payload["duration"]),
        window_seconds=float(payload["window_seconds"]),
        hop_seconds=float(payload["hop_seconds"]),
        sources=tuple((str(label), str(digest)) for label, digest in payload["sources"]),
        candidates=tuple(
            InstrumentCandidate(
                candidate_id=str(candidate["candidate_id"]),
                source_stem=str(candidate["source_stem"]),
                archetype=str(candidate["archetype"]),
                confidence=float(candidate["confidence"]),
                promoted=bool(candidate["promoted"]),
                regions=tuple((float(start), float(end)) for start, end in candidate["regions"]),
                level_db=float(candidate["level_db"]),
                harmonic_ratio=float(candidate["harmonic_ratio"]),
                spectral_flatness=float(candidate["spectral_flatness"]),
                onset_density=float(candidate["onset_density"]),
                spectral_centroid_hz=float(candidate["spectral_centroid_hz"]),
                stereo_width=float(candidate["stereo_width"]),
            )
            for candidate in payload["candidates"]
        ),
    )


def _safe_instrument_label(label: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in label.strip())
    return "-".join(part for part in cleaned.split("-") if part) or "stem"


def _deterministic_clusters(features: np.ndarray, count: int) -> np.ndarray:
    """Small dependency-free k-means for offline timbre grouping."""

    if len(features) == 0:
        return np.zeros(0, dtype=np.int16)
    count = max(1, min(count, len(features)))
    median = np.median(features, axis=0)
    spread = np.percentile(features, 75, axis=0) - np.percentile(features, 25, axis=0)
    normalized = (features - median) / np.maximum(spread, 0.08)
    centers = [normalized[int(np.argmin(np.sum(normalized * normalized, axis=1)))]]
    while len(centers) < count:
        distances = np.min(
            np.stack([np.sum((normalized - center) ** 2, axis=1) for center in centers]),
            axis=0,
        )
        centers.append(normalized[int(np.argmax(distances))])
    centers_array = np.asarray(centers)
    assignments = np.zeros(len(features), dtype=np.int16)
    for _ in range(24):
        distances = np.stack(
            [np.sum((normalized - center) ** 2, axis=1) for center in centers_array],
            axis=1,
        )
        updated = np.argmin(distances, axis=1).astype(np.int16)
        if np.array_equal(updated, assignments) and _:
            break
        assignments = updated
        for cluster in range(count):
            members = normalized[assignments == cluster]
            if len(members):
                centers_array[cluster] = np.mean(members, axis=0)
    return assignments


def _classify_instrument_archetype(
    source_stem: str,
    *,
    harmonic_ratio: float,
    spectral_flatness: float,
    onset_density: float,
    spectral_centroid_hz: float,
    stereo_width: float,
) -> tuple[str, float]:
    """Propose a patch family without pretending that separation proves identity."""

    label = source_stem.lower()
    tonal = harmonic_ratio >= 0.38 and spectral_flatness <= 0.075
    if tonal and onset_density >= 2.7 and spectral_centroid_hz >= 700.0:
        score = 0.46 + harmonic_ratio * 0.32 + min(0.18, onset_density / 35.0)
        return "plucked-string", min(0.96, score)
    if tonal and ("guitar" in label or "string" in label):
        return "guitar-like", min(0.88, 0.42 + harmonic_ratio * 0.42)
    if tonal and ("piano" in label or "keys" in label):
        return "keys-like", min(0.88, 0.42 + harmonic_ratio * 0.42)
    if tonal and onset_density <= 2.8 and (stereo_width >= 0.08 or "other" in label):
        score = 0.43 + harmonic_ratio * 0.32 + min(0.16, stereo_width * 0.45)
        return "sustained-synth", min(0.93, score)
    if tonal:
        return "melodic-residual", min(0.82, 0.38 + harmonic_ratio * 0.42)
    if onset_density >= 3.2 and (spectral_flatness >= 0.06 or harmonic_ratio < 0.30):
        return "percussive-texture", min(0.84, 0.42 + min(0.24, onset_density / 28.0))
    return "diffuse-residual", min(0.72, 0.34 + harmonic_ratio * 0.22)


def _merge_activity_regions(
    windows: list[tuple[float, float]],
    *,
    maximum_gap: float,
) -> tuple[tuple[float, float], ...]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1] + maximum_gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return tuple((round(start, 6), round(end, 6)) for start, end in merged)


def discover_instrument_candidates(
    source: Path,
    *,
    source_stem: str,
    duration: float,
    window_seconds: float = 1.0,
    hop_seconds: float = 0.5,
) -> tuple[InstrumentCandidate, ...]:
    """Segment and group coherent instrument-like material in a separated stem."""

    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for instrument discovery") from exc

    rate = 22_050
    stereo, _ = librosa.load(source, sr=rate, mono=False, duration=duration)
    if stereo.ndim == 1:
        stereo = np.vstack((stereo, stereo))
    stereo = stereo[:2]
    mono = np.mean(stereo, axis=0)
    harmonic, _ = librosa.effects.hpss(mono, margin=2.0)
    onset_times = librosa.onset.onset_detect(y=mono, sr=rate, units="time", backtrack=False)
    size = max(256, round(window_seconds * rate))
    hop = max(128, round(hop_seconds * rate))
    raw_windows: list[dict[str, float]] = []
    for first in range(0, max(1, len(mono) - size + 1), hop):
        last = min(len(mono), first + size)
        window = mono[first:last]
        harmonic_window = harmonic[first:last]
        if window.size < 256:
            continue
        power = float(np.mean(window * window)) + 1e-12
        level_db = 10.0 * math.log10(power)
        spectrum = np.abs(np.fft.rfft(window * np.hanning(window.size))) ** 2 + 1e-12
        frequencies = np.fft.rfftfreq(window.size, 1.0 / rate)
        start_time = first / rate
        end_time = last / rate
        left = stereo[0, first:last]
        right = stereo[1, first:last]
        middle = (left + right) * 0.5
        side = (left - right) * 0.5
        raw_windows.append(
            {
                "start": start_time,
                "end": end_time,
                "level_db": level_db,
                "harmonic_ratio": min(1.0, float(np.mean(harmonic_window * harmonic_window)) / power),
                "spectral_flatness": float(np.exp(np.mean(np.log(spectrum))) / np.mean(spectrum)),
                "onset_density": float(np.sum((onset_times >= start_time) & (onset_times < end_time)))
                / max(0.1, end_time - start_time),
                "spectral_centroid_hz": float(np.sum(spectrum * frequencies) / np.sum(spectrum)),
                "stereo_width": min(
                    2.0,
                    float(np.sqrt(np.mean(side * side)) / (np.sqrt(np.mean(middle * middle)) + 1e-9)),
                ),
            }
        )
    if not raw_windows:
        return ()
    peak_db = max(window["level_db"] for window in raw_windows)
    activity_threshold = max(-50.0, peak_db - 22.0)
    active = [window for window in raw_windows if window["level_db"] >= activity_threshold]
    if not active:
        return ()
    feature_names = (
        "harmonic_ratio",
        "spectral_flatness",
        "onset_density",
        "spectral_centroid_hz",
        "stereo_width",
    )
    features = np.asarray([[window[name] for name in feature_names] for window in active], dtype=np.float64)
    features[:, 2] /= 8.0
    features[:, 3] /= 4_000.0
    cluster_count = min(4, max(1, 1 + int(math.sqrt(len(active) / 24.0))))
    assignments = _deterministic_clusters(features, cluster_count)
    candidates: list[InstrumentCandidate] = []
    safe_label = _safe_instrument_label(source_stem)
    for cluster in range(cluster_count):
        members = [window for window, assignment in zip(active, assignments, strict=True) if assignment == cluster]
        if not members:
            continue
        metrics = {
            name: float(np.median([window[name] for window in members]))
            for name in ("level_db", *feature_names)
        }
        archetype, semantic_confidence = _classify_instrument_archetype(
            source_stem,
            harmonic_ratio=metrics["harmonic_ratio"],
            spectral_flatness=metrics["spectral_flatness"],
            onset_density=metrics["onset_density"],
            spectral_centroid_hz=metrics["spectral_centroid_hz"],
            stereo_width=metrics["stereo_width"],
        )
        regions = _merge_activity_regions(
            [(window["start"], window["end"]) for window in members],
            maximum_gap=hop_seconds * 1.05,
        )
        active_seconds = sum(end - start for start, end in regions)
        level_confidence = max(0.0, min(1.0, (metrics["level_db"] - activity_threshold + 4.0) / 14.0))
        confidence = semantic_confidence * (0.72 + level_confidence * 0.28)
        promoted = (
            active_seconds >= 3.0
            and confidence >= 0.52
            and archetype not in {"percussive-texture", "diffuse-residual"}
        )
        candidates.append(
            InstrumentCandidate(
                candidate_id=f"{safe_label}-{cluster + 1:02d}",
                source_stem=source_stem,
                archetype=archetype,
                confidence=round(confidence, 6),
                promoted=promoted,
                regions=regions,
                level_db=round(metrics["level_db"], 4),
                harmonic_ratio=round(metrics["harmonic_ratio"], 6),
                spectral_flatness=round(metrics["spectral_flatness"], 6),
                onset_density=round(metrics["onset_density"], 4),
                spectral_centroid_hz=round(metrics["spectral_centroid_hz"], 2),
                stereo_width=round(metrics["stereo_width"], 6),
            )
        )
    return tuple(sorted(candidates, key=lambda item: (-item.confidence, item.candidate_id)))


def discover_instrument_inventory(
    sources: dict[str, Path],
    *,
    source_offset: float,
    duration: float,
    source_hashes: dict[str, str] | None = None,
) -> InstrumentInventory:
    candidates = []
    for label, source in sorted(sources.items()):
        candidates.extend(
            discover_instrument_candidates(source, source_stem=label, duration=duration)
        )
    hashes = source_hashes or {label: _sha256(source) for label, source in sources.items()}
    return InstrumentInventory(
        schema_version=1,
        source_offset=round(source_offset, 6),
        duration=round(duration, 6),
        window_seconds=1.0,
        hop_seconds=0.5,
        sources=tuple(sorted(hashes.items())),
        candidates=tuple(sorted(candidates, key=lambda item: (item.source_stem, item.candidate_id))),
    )


def _quantum(bpm: float) -> float:
    return 60.0 / max(1.0, bpm) / 4.0


def quantize_time(value: float, bpm: float, grid_origin: float = 0.0) -> float:
    step = _quantum(bpm)
    snapped = grid_origin + round((max(0.0, value) - grid_origin) / step) * step
    return round(max(0.0, snapped), 6)


def infer_grid_origin(beat_times: np.ndarray, bpm: float) -> float:
    """Return the beat phase within one beat, robust to the clip boundary."""

    if beat_times.size == 0:
        return 0.0
    beat = 60.0 / bpm
    phases = np.mod(np.asarray(beat_times, dtype=np.float64), beat)
    vectors = np.exp(2j * np.pi * phases / beat)
    mean = np.mean(vectors)
    if abs(mean) < 0.25:
        return 0.0
    phase = float(np.angle(mean) % (2.0 * np.pi)) * beat / (2.0 * np.pi)
    return round(phase, 6)


def estimate_timing(
    source: Path,
    requested_bpm: float | None,
    duration: float,
) -> tuple[float, float, tuple[float, ...]]:
    """Estimate tempo and grid phase from an isolated drum stem."""

    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for tempo analysis") from exc

    audio, rate = librosa.load(source, sr=22_050, mono=True, duration=duration)
    hop = 256
    envelope = librosa.onset.onset_strength(y=audio, sr=rate, hop_length=hop)
    kwargs = {"bpm": requested_bpm} if requested_bpm is not None else {}
    tempo, frames = librosa.beat.beat_track(
        onset_envelope=envelope,
        sr=rate,
        hop_length=hop,
        trim=False,
        **kwargs,
    )
    detected = float(np.asarray(tempo).reshape(-1)[0])
    bpm = float(requested_bpm if requested_bpm is not None else detected)
    while bpm < 70.0:
        bpm *= 2.0
    while bpm > 180.0:
        bpm /= 2.0
    beat_times = librosa.frames_to_time(frames, sr=rate, hop_length=hop)
    phase_sample = np.asarray(beat_times[: min(64, len(beat_times))])
    return round(bpm, 4), infer_grid_origin(phase_sample, bpm), tuple(float(time) for time in beat_times)


def beat_boundaries(beat_times: tuple[float, ...], duration: float, bpm: float) -> tuple[float, ...]:
    """Extend detected beats across sparse edges while preserving local tempo."""

    if len(beat_times) < 2:
        beat = 60.0 / bpm
        return tuple(round(min(duration, index * beat), 6) for index in range(math.ceil(duration / beat) + 1))
    beats = list(beat_times)
    differences = np.diff(np.asarray(beats))
    opening = float(np.median(differences[: min(32, len(differences))]))
    closing = float(np.median(differences[-min(32, len(differences)) :]))
    while beats[0] > 0.0:
        beats.insert(0, beats[0] - opening)
    while beats[-1] < duration:
        beats.append(beats[-1] + closing)
    inside = [time for time in beats if 0.0 < time < duration]
    return tuple(round(time, 6) for time in (0.0, *inside, duration))


def build_timing_grid(beat_times: tuple[float, ...], duration: float, bpm: float) -> tuple[float, ...]:
    boundaries = beat_boundaries(beat_times, duration, bpm)
    points = [0.0]
    for first, last in zip(boundaries, boundaries[1:]):
        for subdivision in range(1, 5):
            points.append(first + (last - first) * subdivision / 4.0)
    points[-1] = duration
    return tuple(round(time, 6) for time in points)


def nearest_timing(value: float, timing_grid: tuple[float, ...]) -> float:
    if not timing_grid:
        return value
    index = int(np.searchsorted(timing_grid, value))
    candidates = timing_grid[max(0, index - 1) : min(len(timing_grid), index + 1)]
    return min(candidates, key=lambda time: abs(time - value))


def _grid_zero(bpm: float, grid_origin: float) -> float:
    step = _quantum(bpm)
    phase = grid_origin % step
    return 0.0 if phase < 1e-9 else phase - step


def _window_flatness(audio: np.ndarray) -> float:
    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size))) ** 2 + 1e-12
    return float(np.exp(np.mean(np.log(spectrum))) / np.mean(spectrum))


def _synth_windows(
    audio: np.ndarray,
    harmonic: np.ndarray,
    f0: np.ndarray,
    voiced_probability: np.ndarray,
    *,
    rate: int,
    pitch_hop: int,
    voiced_threshold: float = 0.52,
) -> list[tuple[float, float, float, float]]:
    size = round(rate * 0.60)
    hop = round(rate * 0.25)
    candidates: list[tuple[float, float, float, float]] = []
    for first in range(0, max(1, len(audio) - size + 1), hop):
        last = min(len(audio), first + size)
        window = audio[first:last]
        harmonic_window = harmonic[first:last]
        power = float(np.mean(window * window)) + 1e-12
        level_db = 10.0 * math.log10(power)
        if level_db < -58.0:
            continue
        harmonic_ratio = min(1.0, float(np.mean(harmonic_window * harmonic_window)) / power)
        flatness = _window_flatness(window)
        frame_first = max(0, round(first / pitch_hop))
        frame_last = min(len(f0), max(frame_first + 1, round(last / pitch_hop)))
        local_f0 = f0[frame_first:frame_last]
        local_probability = voiced_probability[frame_first:frame_last]
        valid = np.isfinite(local_f0) & (local_probability >= voiced_threshold)
        if np.mean(valid) < 0.35:
            continue
        pitches = local_f0[valid]
        median_f0 = float(np.median(pitches))
        cents = 1_200.0 * np.log2(pitches / median_f0)
        stability = math.exp(-float(np.median(np.abs(cents))) / 115.0)
        activity = min(1.0, 10.0 ** ((level_db + 42.0) / 20.0))
        score = harmonic_ratio * (1.0 - min(0.9, flatness * 8.0)) * stability * (0.45 + 0.55 * activity)
        candidates.append((first / rate, last / rate, score, median_f0))

    selected: list[tuple[float, float, float, float]] = []
    for candidate in sorted(candidates, key=lambda item: item[2], reverse=True):
        center = (candidate[0] + candidate[1]) * 0.5
        if any(abs(center - (prior[0] + prior[1]) * 0.5) < 0.70 for prior in selected):
            continue
        selected.append(candidate)
        if len(selected) == 8:
            break
    return selected


def _harmonic_fingerprint(
    harmonic: np.ndarray,
    windows: list[tuple[float, float, float, float]],
    *,
    rate: int,
) -> tuple[float, ...]:
    observations: list[np.ndarray] = []
    size = 8_192
    frequencies = np.fft.rfftfreq(size, 1.0 / rate)
    for start, end, _, fundamental in windows:
        center = round((start + end) * 0.5 * rate)
        first = max(0, min(len(harmonic) - size, center - size // 2))
        window = harmonic[first : first + size]
        if window.size != size:
            continue
        spectrum = np.abs(np.fft.rfft(window * np.hanning(size)))
        levels = []
        for multiple in range(1, 13):
            target = fundamental * multiple
            if target >= rate * 0.47:
                levels.append(0.0)
                continue
            index = int(np.searchsorted(frequencies, target))
            levels.append(float(np.max(spectrum[max(0, index - 2) : index + 3])))
        values = np.asarray(levels, dtype=np.float64)
        reference = max(1e-9, float(np.max(values[:4])))
        observations.append(np.clip(values / reference, 1e-5, 1.5))
    if not observations:
        return (1.0, 0.42, 0.24, 0.16, 0.11, 0.08, 0.06, 0.045, 0.035, 0.028, 0.022, 0.018)
    levels = np.exp(np.median(np.log(np.asarray(observations)), axis=0))
    log_levels = np.log(np.maximum(levels, 1e-5))
    smoothed = log_levels.copy()
    smoothed[1:-1] = log_levels[:-2] * 0.18 + log_levels[1:-1] * 0.64 + log_levels[2:] * 0.18
    levels = np.exp(smoothed)
    levels /= max(1e-9, float(np.max(levels)))
    return tuple(round(float(level), 6) for level in levels)


def _vibrato_fingerprint(
    f0: np.ndarray,
    voiced_probability: np.ndarray,
    windows: list[tuple[float, float, float, float]],
    *,
    rate: int,
    hop: int,
    voiced_threshold: float = 0.52,
) -> tuple[float, float]:
    rates: list[float] = []
    depths: list[float] = []
    frame_rate = rate / hop
    for start, end, _, _ in windows:
        first = max(0, round(start * frame_rate))
        last = min(len(f0), round(end * frame_rate))
        values = f0[first:last]
        valid = np.isfinite(values) & (voiced_probability[first:last] >= voiced_threshold)
        if np.sum(valid) < 12:
            continue
        indexes = np.arange(values.size)
        interpolated = np.interp(indexes, indexes[valid], values[valid])
        cents = 1_200.0 * np.log2(interpolated / np.median(interpolated))
        trend = np.polyval(np.polyfit(indexes, cents, 1), indexes)
        residual = np.clip(cents - trend, -80.0, 80.0)
        depths.append(float(np.std(residual)))
        spectrum = np.abs(np.fft.rfft(residual * np.hanning(residual.size)))
        frequencies = np.fft.rfftfreq(residual.size, 1.0 / frame_rate)
        mask = (frequencies >= 3.0) & (frequencies <= 8.0)
        if np.any(mask):
            rates.append(float(frequencies[mask][np.argmax(spectrum[mask])]))
    rate_hz = float(np.median(rates)) if rates else 5.2
    depth = float(np.median(depths)) if depths else 7.0
    return round(max(3.0, min(8.0, rate_hz)), 4), round(max(1.5, min(28.0, depth)), 4)


def _source_wavetable(
    harmonic: np.ndarray,
    window: tuple[float, float, float, float],
    *,
    rate: int,
    size: int = 256,
) -> np.ndarray:
    start, end, _, fundamental = window
    segment = harmonic[round(start * rate) : round(end * rate)]
    cycle = max(8, round(rate / fundamental))
    crossings = np.flatnonzero((segment[:-1] <= 0.0) & (segment[1:] > 0.0))
    waves = []
    for crossing in crossings:
        if crossing + cycle >= len(segment):
            continue
        source = segment[crossing : crossing + cycle]
        waves.append(np.interp(np.linspace(0, cycle - 1, size, endpoint=False), np.arange(cycle), source))
        if len(waves) == 24:
            break
    if not waves:
        return np.sin(np.linspace(0.0, 2.0 * np.pi, size, endpoint=False))
    table = np.mean(waves, axis=0)
    table -= np.mean(table)
    table = np.roll(table, 1) * 0.2 + table * 0.6 + np.roll(table, -1) * 0.2
    peak = float(np.max(np.abs(table)))
    return table / max(1e-9, peak)


def extract_synth_fingerprint(
    source: Path,
    *,
    start: float,
    duration: float,
    minimum_frequency: float = 65.4,
    maximum_frequency: float = 2_093.0,
    voiced_threshold: float = 0.52,
) -> tuple[SynthFingerprint, np.ndarray]:
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for synth fingerprint extraction") from exc

    rate = OUTPUT_RATE
    stereo, _ = librosa.load(source, sr=rate, mono=False, offset=start, duration=duration)
    if stereo.ndim == 1:
        stereo = np.vstack((stereo, stereo))
    mono = np.mean(stereo[:2], axis=0)
    harmonic, _ = librosa.effects.hpss(mono, margin=2.0)
    pitch_hop = 256
    f0, _, probability = librosa.pyin(
        harmonic,
        fmin=minimum_frequency,
        fmax=maximum_frequency,
        sr=rate,
        frame_length=2_048,
        hop_length=pitch_hop,
    )
    probability = np.nan_to_num(probability, nan=0.0)
    windows = _synth_windows(
        mono,
        harmonic,
        f0,
        probability,
        rate=rate,
        pitch_hop=pitch_hop,
        voiced_threshold=voiced_threshold,
    )
    if not windows:
        raise RuntimeError("no stable harmonic windows found in the synth candidate")
    harmonic_levels = _harmonic_fingerprint(harmonic, windows, rate=rate)
    vibrato_rate, vibrato_depth = _vibrato_fingerprint(
        f0,
        probability,
        windows,
        rate=rate,
        hop=pitch_hop,
        voiced_threshold=voiced_threshold,
    )
    flatness = float(np.median([_window_flatness(mono[round(a * rate) : round(b * rate)]) for a, b, _, _ in windows]))
    selected = np.concatenate([stereo[:2, round(a * rate) : round(b * rate)] for a, b, _, _ in windows], axis=1)
    middle = (selected[0] + selected[1]) * 0.5
    side = (selected[0] - selected[1]) * 0.5
    width = float(np.sqrt(np.mean(side * side)) / (np.sqrt(np.mean(middle * middle)) + 1e-9))
    correlation = float(np.corrcoef(selected[0], selected[1])[0, 1])
    rms = librosa.feature.rms(y=harmonic, frame_length=1_024, hop_length=256)[0]
    sustain = float(np.percentile(rms, 50) / max(1e-9, np.percentile(rms, 90)))
    sustain = max(0.38, min(0.76, sustain))
    fingerprint = SynthFingerprint(
        schema_version=1,
        source_sha256=_sha256(source),
        source_offset=round(start, 6),
        duration=round(duration, 6),
        sample_rate=rate,
        fundamental_median_hz=round(float(np.median([window[3] for window in windows])), 4),
        harmonic_levels=harmonic_levels,
        noise_mix=round(max(0.01, min(0.16, flatness * 7.0)), 6),
        stereo_width=round(max(0.0, min(1.4, width)), 6),
        stereo_correlation=round(max(-1.0, min(1.0, correlation)), 6),
        attack=0.012,
        decay=round(0.12 + (1.0 - sustain) * 0.20, 6),
        sustain=round(sustain, 6),
        release=0.16,
        vibrato_rate_hz=vibrato_rate,
        vibrato_depth_cents=vibrato_depth,
        selected_windows=tuple(
            (round(a, 6), round(b, 6), round(score, 6), round(frequency, 4))
            for a, b, score, frequency in windows
        ),
    )
    return fingerprint, _source_wavetable(harmonic, windows[0], rate=rate)


def _fold_pitch(pitch: int, minimum: int, maximum: int) -> int:
    while pitch < minimum:
        pitch += 12
    while pitch > maximum:
        pitch -= 12
    return max(minimum, min(maximum, pitch))


def monophonic_grid(
    events: list[tuple[float, float, int, float]],
    *,
    role: str,
    bpm: float,
    duration: float,
    pitch_range: tuple[int, int],
    grid_origin: float = 0.0,
    timing_grid: tuple[float, ...] = (),
) -> list[SymbolicNote]:
    """Select one confidence-weighted note per sixteenth-note cell."""

    step = _quantum(bpm)
    if timing_grid:
        points = timing_grid
        zero = 0.0
        cell_count = len(points) - 1
    else:
        zero = _grid_zero(bpm, grid_origin)
        cell_count = max(1, math.ceil((duration - zero) / step))
        points = tuple(round(zero + index * step, 6) for index in range(cell_count + 1))
    point_array = np.asarray(points)
    cells: list[tuple[int, float] | None] = [None] * cell_count
    minimum, maximum = pitch_range
    for start, end, raw_pitch, confidence in events:
        pitch = _fold_pitch(int(raw_pitch), minimum, maximum)
        if timing_grid:
            first = max(0, min(cell_count - 1, int(np.argmin(np.abs(point_array - max(0.0, start))))))
            last = max(first + 1, min(cell_count, int(np.argmin(np.abs(point_array - end)))))
        else:
            first = max(0, min(cell_count - 1, round((max(0.0, start) - zero) / step)))
            last = max(first + 1, min(cell_count, round((max(start + step, end) - zero) / step)))
        for index in range(first, last):
            prior = cells[index]
            if prior is None or confidence > prior[1]:
                cells[index] = (pitch, float(confidence))

    # Remove isolated octave/harmonic guesses before collapsing held notes.
    for index in range(1, cell_count - 1):
        previous = cells[index - 1]
        current = cells[index]
        following = cells[index + 1]
        if previous is None or current is None or following is None:
            continue
        if previous[0] == following[0] and abs(current[0] - previous[0]) >= 7:
            cells[index] = (previous[0], max(previous[1], following[1]) * 0.9)

    # Basic Pitch can briefly lock onto a vocal or bass harmonic. A one-cell
    # leap surrounded by nearby evidence is an analysis artifact far more
    # often than an intentional sixteenth-note octave jump.
    runs: list[tuple[int, int]] = []
    first = 0
    while first < cell_count:
        if cells[first] is None:
            first += 1
            continue
        last = first + 1
        while last < cell_count and cells[last] is not None and cells[last][0] == cells[first][0]:
            last += 1
        runs.append((first, last))
        first = last
    for first, last in runs:
        if last - first != 1 or cells[first] is None:
            continue
        prior = next(
            (cells[index] for index in range(first - 1, max(-1, first - 3), -1) if cells[index] is not None),
            None,
        )
        following = next(
            (cells[index] for index in range(last, min(cell_count, last + 2)) if cells[index] is not None),
            None,
        )
        pitch, confidence = cells[first]
        neighbors = [item for item in (prior, following) if item is not None]
        if len(neighbors) == 2 and all(abs(pitch - item[0]) >= 7 for item in neighbors):
            replacement = min(neighbors, key=lambda item: abs(item[0] - pitch))
            cells[first] = (replacement[0], max(confidence, replacement[1] * 0.82))

    notes: list[SymbolicNote] = []
    index = 0
    while index < cell_count:
        current = cells[index]
        if current is None:
            index += 1
            continue
        pitch, confidence = current
        last = index + 1
        confidences = [confidence]
        while last < cell_count and cells[last] is not None and cells[last][0] == pitch:
            confidences.append(cells[last][1])
            last += 1
        mean_confidence = float(np.mean(confidences))
        notes.append(
            SymbolicNote(
                role=role,
                start=round(max(0.0, points[index]), 6),
                end=round(min(duration, max(points[index + 1], points[last])), 6),
                pitch=pitch,
                velocity=max(36, min(112, round(42 + mean_confidence * 76))),
            )
        )
        index = last
    # Finally octave-fold very short notes toward nearby phrases. This keeps
    # genuine contour while removing isolated harmonic detections that would
    # otherwise become conspicuous console chirps.
    corrected: list[SymbolicNote] = []
    for note_index, note in enumerate(notes):
        if note.end - note.start > step * 1.15:
            corrected.append(note)
            continue
        neighbors = []
        if note_index > 0 and note.start - notes[note_index - 1].end <= 60.0 / bpm:
            neighbors.append(notes[note_index - 1].pitch)
        if note_index + 1 < len(notes) and notes[note_index + 1].start - note.end <= 60.0 / bpm:
            neighbors.append(notes[note_index + 1].pitch)
        if not neighbors:
            corrected.append(note)
            continue
        target = float(np.median(neighbors))
        candidates = [note.pitch + shift for shift in (-24, -12, 0, 12, 24)]
        candidates = [pitch for pitch in candidates if minimum <= pitch <= maximum]
        folded = min(candidates, key=lambda pitch: (abs(pitch - target), abs(pitch - note.pitch)))
        corrected.append(
            SymbolicNote(note.role, note.start, note.end, folded, note.velocity)
            if abs(folded - target) + 5 < abs(note.pitch - target)
            else note
        )
    notes = corrected
    return notes


def _clip_audio(ffmpeg: str, source: Path, target: Path, start: float, duration: float) -> None:
    _run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.6f}",
            "-t",
            f"{duration:.6f}",
            "-i",
            str(source),
            "-vn",
            "-map_metadata",
            "-1",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-c:a",
            "pcm_s16le",
            str(target),
        ]
    )


def performance_notes(events: list, *, role: str, duration: float,
                      contour_bins_per_semitone: int = 3) -> list[SymbolicNote]:
    """Resolve overlaps without imposing a grid, scale, octave, or articulation.

    An event boundary remains a possible attack even when adjacent pitches match.
    Basic Pitch bend values are contour-bin offsets, not MIDI wheel values.
    Confidence remains evidence and no longer stands in for played velocity.
    """
    import heapq
    candidates = []
    for index, event in enumerate(events):
        start, end, pitch, strength, bends = event
        start, end = max(0.0, float(start)), min(duration, float(end))
        if end <= start or not 0 <= int(pitch) <= 127:
            continue
        candidates.append((start, end, int(pitch), float(np.clip(strength, 0, 1)), bends, index))
    changes = {}
    for index, event in enumerate(candidates):
        changes.setdefault(event[0], []).append(index)
        changes.setdefault(event[1], [])
    points = sorted(changes)
    active = []
    segments = []
    for first, last in zip(points, points[1:]):
        for index in changes[first]:
            event = candidates[index]
            heapq.heappush(active, (-event[3], event[5], index))
        while active and candidates[active[0][2]][1] <= first:
            heapq.heappop(active)
        if not active:
            continue
        winner = active[0][2]
        if segments and segments[-1][2] == winner and segments[-1][1] == first:
            segments[-1] = (segments[-1][0], last, winner)
        else:
            segments.append((first, last, winner))
    result = []
    for start, end, index in segments:
        raw_start, raw_end, pitch, confidence, bends, _ = candidates[index]
        curve = ()
        if bends is not None and len(bends):
            count = min(2048, max(2, len(bends)))
            at = np.linspace(start, end, count)
            values = np.interp(at, np.linspace(raw_start, raw_end, len(bends)), bends)
            curve = tuple((round(float(pos), 7), round(float(value * 100 / contour_bins_per_semitone), 4))
                          for pos, value in zip(np.linspace(0, 1, count), values))
        result.append(SymbolicNote(role, start, end, pitch, 90, confidence, curve))
    return result


def _transcribe_pitched(
    source: Path,
    *,
    model: object,
    role: str,
    bpm: float,
    duration: float,
    grid_origin: float,
    timing_grid: tuple[float, ...] = (),
) -> list[SymbolicNote]:
    try:
        from basic_pitch.inference import predict
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("Basic Pitch is required for symbolic transcription") from exc

    ranges = {"lead": (45, 88), "bass": (28, 60)}
    frequencies = {
        "lead": (110.0, 1_318.5),
        "bass": (27.5, 261.7),
    }
    low, high = frequencies[role]
    _, _, raw_events = predict(
        source,
        model,
        onset_threshold=0.48 if role == "lead" else 0.42,
        frame_threshold=0.28 if role == "lead" else 0.24,
        minimum_note_length=90.0,
        minimum_frequency=low,
        maximum_frequency=high,
        melodia_trick=True,
    )
    from basic_pitch.constants import CONTOURS_BINS_PER_SEMITONE
    return performance_notes(raw_events, role=role, duration=duration,
                             contour_bins_per_semitone=CONTOURS_BINS_PER_SEMITONE)


def instrument_role(candidate: InstrumentCandidate) -> str:
    return f"instrument-{candidate.candidate_id}-{candidate.archetype}"


def _instrument_archetype(role: str) -> str | None:
    if not role.startswith("instrument-"):
        return None
    return next(
        (
            archetype
            for archetype in (
                "plucked-string",
                "sustained-synth",
                "guitar-like",
                "keys-like",
                "melodic-residual",
            )
            if role.endswith(f"-{archetype}")
        ),
        "melodic-residual",
    )


def _inside_regions(time: float, regions: tuple[tuple[float, float], ...]) -> bool:
    return any(start <= time <= end for start, end in regions)


def _rearticulate_plucked_notes(
    notes: list[SymbolicNote],
    onset_times: np.ndarray,
    *,
    bpm: float,
    timing_grid: tuple[float, ...],
) -> list[SymbolicNote]:
    """Split held pitch estimates at real attacks so plucks retrigger."""

    minimum_spacing = 60.0 / bpm / 5.0
    articulated: list[SymbolicNote] = []
    for note in notes:
        boundaries = [note.start]
        for onset in onset_times:
            snapped = nearest_timing(float(onset), timing_grid) if timing_grid else float(onset)
            if note.start + minimum_spacing < snapped < note.end - minimum_spacing:
                if snapped - boundaries[-1] >= minimum_spacing:
                    boundaries.append(snapped)
        boundaries.append(note.end)
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
            articulated.append(
                replace(
                    note,
                    start=round(start, 6),
                    end=round(end, 6),
                    velocity=max(36, note.velocity - min(8, index * 2)),
                )
            )
    return articulated


def transcribe_discovered_instruments(
    sources: dict[str, Path],
    inventory: InstrumentInventory,
    *,
    model: object,
    bpm: float,
    duration: float,
    grid_origin: float,
    timing_grid: tuple[float, ...] = (),
) -> list[SymbolicNote]:
    """Transcribe promoted timbre clusters while retaining rejected clusters in inventory."""

    try:
        from basic_pitch.inference import predict
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("Basic Pitch is required for symbolic transcription") from exc

    promoted = [candidate for candidate in inventory.candidates if candidate.promoted]
    notes_by_candidate: dict[str, list[SymbolicNote]] = {}
    candidate_scores = {instrument_role(candidate): candidate.confidence for candidate in promoted}
    for label, source in sorted(sources.items()):
        local_candidates = sorted(
            (candidate for candidate in promoted if candidate.source_stem == label),
            key=lambda candidate: (-candidate.confidence, candidate.candidate_id),
        )
        if not local_candidates:
            continue
        _, _, raw_events = predict(
            source,
            model,
            onset_threshold=0.40,
            frame_threshold=0.24,
            minimum_note_length=60.0,
            minimum_frequency=55.0,
            maximum_frequency=2_093.0,
            melodia_trick=True,
        )
        source_audio, source_rate = librosa.load(source, sr=22_050, mono=True, duration=duration)
        onset_times = librosa.onset.onset_detect(
            y=source_audio,
            sr=source_rate,
            units="time",
            backtrack=False,
            pre_max=3,
            post_max=3,
            pre_avg=8,
            post_avg=8,
            delta=0.12,
            wait=2,
        )
        assigned: dict[str, list[tuple[float, float, int, float]]] = {
            instrument_role(candidate): [] for candidate in local_candidates
        }
        for start, end, pitch, confidence, _ in raw_events:
            midpoint = (float(start) + float(end)) * 0.5
            candidate = next(
                (item for item in local_candidates if _inside_regions(midpoint, item.regions)),
                None,
            )
            if candidate is None:
                continue
            role = instrument_role(candidate)
            assigned[role].append((float(start), float(end), int(pitch), float(confidence)))
        for candidate in local_candidates:
            role = instrument_role(candidate)
            ranges = {
                "plucked-string": (48, 96),
                "sustained-synth": (40, 96),
                "guitar-like": (40, 88),
                "keys-like": (36, 96),
                "melodic-residual": (45, 92),
            }
            candidate_notes = monophonic_grid(
                assigned[role],
                role=role,
                bpm=bpm,
                duration=duration,
                pitch_range=ranges[candidate.archetype],
                grid_origin=grid_origin,
                timing_grid=timing_grid,
            )
            if candidate.archetype == "plucked-string":
                candidate_notes = _rearticulate_plucked_notes(
                    candidate_notes,
                    onset_times,
                    bpm=bpm,
                    timing_grid=timing_grid,
                )
            notes_by_candidate[role] = candidate_notes

    # Separators commonly leak the same event into adjacent source stems.
    # Collapse only virtually identical detections, preserving real unisons.
    retained: list[SymbolicNote] = []
    for role in sorted(notes_by_candidate, key=lambda item: (-candidate_scores[item], item)):
        for note in notes_by_candidate[role]:
            duplicate = any(
                prior.pitch == note.pitch
                and abs(prior.start - note.start) <= 0.055
                and abs(prior.end - note.end) <= 0.085
                for prior in retained
                if prior.role.startswith("instrument-")
            )
            if not duplicate:
                retained.append(note)
    return sorted(retained, key=lambda note: (note.start, note.role, note.pitch))


def save_instrument_extracts(
    inventory: InstrumentInventory,
    sources: dict[str, Path],
    target: Path,
    *,
    ffmpeg: str,
) -> Path:
    """Write source-faithful audition clips for every discovered candidate."""

    for candidate in inventory.candidates:
        source = sources[candidate.source_stem]
        candidate_root = target / candidate.candidate_id
        candidate_root.mkdir(parents=True, exist_ok=True)
        for index, (start, end) in enumerate(candidate.regions, start=1):
            _clip_audio(
                ffmpeg,
                source,
                candidate_root / f"region-{index:02d}.wav",
                inventory.source_offset + start,
                max(0.05, end - start),
            )
    return target


def _analyse_drums(
    source: Path,
    *,
    bpm: float,
    duration: float,
    grid_origin: float,
    timing_grid: tuple[float, ...] = (),
) -> list[DrumHit]:
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for drum transcription") from exc

    audio, rate = librosa.load(source, sr=22_050, mono=True, duration=duration)
    hop = 256
    onset_envelope = librosa.onset.onset_strength(y=audio, sr=rate, hop_length=hop)
    frames = librosa.onset.onset_detect(
        onset_envelope=onset_envelope,
        sr=rate,
        hop_length=hop,
        backtrack=False,
        pre_max=3,
        post_max=3,
        pre_avg=8,
        post_avg=8,
        delta=0.16,
        wait=2,
    )
    strengths = onset_envelope[frames] if len(frames) else np.zeros(0)
    reference = max(1e-8, float(np.percentile(strengths, 92))) if len(strengths) else 1.0
    seen: dict[tuple[str, float], DrumHit] = {}
    for frame, strength in zip(frames, strengths, strict=True):
        center = int(frame * hop)
        first = max(0, center - round(rate * 0.025))
        last = min(len(audio), center + round(rate * 0.085))
        window = audio[first:last]
        if window.size < 64:
            continue
        spectrum = np.abs(np.fft.rfft(window * np.hanning(window.size))) ** 2
        frequencies = np.fft.rfftfreq(window.size, 1.0 / rate)
        low = float(np.sum(spectrum[frequencies < 180.0]))
        middle = float(np.sum(spectrum[(frequencies >= 180.0) & (frequencies < 3_200.0)]))
        high = float(np.sum(spectrum[frequencies >= 3_200.0]))
        total = low + middle + high + 1e-12
        if low / total >= 0.47:
            kind = "kick"
        elif high / total >= 0.42:
            kind = "hat"
        else:
            kind = "snare"
        raw_time = float(center) / rate
        time = min(
            duration,
            nearest_timing(raw_time, timing_grid)
            if timing_grid
            else quantize_time(raw_time, bpm, grid_origin),
        )
        velocity = max(40, min(120, round(42 + 72 * min(1.0, float(strength) / reference))))
        key = (kind, time)
        hit = DrumHit(kind, time, velocity)
        if key not in seen or velocity > seen[key].velocity:
            seen[key] = hit
    ordered = sorted(seen.values(), key=lambda hit: (hit.time, hit.kind))
    # A console arrangement should preserve the pulse, not reproduce every
    # low-frequency micro-transient. Keep the strongest kick/snare in each
    # eighth-note cell; hats retain sixteenth-note resolution.
    beat = 60.0 / bpm
    selected: list[DrumHit] = []
    for kind in ("kick", "snare", "hat"):
        kind_hits = [hit for hit in ordered if hit.kind == kind]
        retained: list[DrumHit] = []
        for hit in kind_hits:
            spacing = beat / 2.0 if kind in {"kick", "snare"} else beat / 4.0
            if retained and hit.time - retained[-1].time < spacing - 1e-6:
                if hit.velocity > retained[-1].velocity:
                    retained[-1] = hit
                continue
            retained.append(hit)
        selected.extend(retained)
    return sorted(selected, key=lambda hit: (hit.time, hit.kind))


def _chord_templates() -> tuple[list[tuple[int, str]], np.ndarray]:
    states: list[tuple[int, str]] = []
    templates: list[np.ndarray] = []
    for root in range(12):
        for quality, third in (("major", 4), ("minor", 3)):
            template = np.full(12, -0.16, dtype=np.float64)
            template[root] = 1.0
            template[(root + third) % 12] = 0.76
            template[(root + 7) % 12] = 0.86
            states.append((root, quality))
            templates.append(template)
    return states, np.asarray(templates)


def _infer_key(chroma: np.ndarray) -> tuple[int, str]:
    major_profile = np.asarray((6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88))
    minor_profile = np.asarray((6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17))
    mean = np.mean(chroma, axis=1)
    candidates = []
    for root in range(12):
        for mode, profile in (("major", major_profile), ("minor", minor_profile)):
            score = float(np.corrcoef(mean, np.roll(profile, root))[0, 1])
            candidates.append((score, -root, mode))
    _, negative_root, mode = max(candidates)
    return -negative_root, mode


def _diatonic_states(root: int, mode: str) -> set[tuple[int, str]]:
    if mode == "major":
        degrees = ((0, "major"), (2, "minor"), (4, "minor"), (5, "major"), (7, "major"), (9, "minor"))
    else:
        degrees = ((0, "minor"), (3, "major"), (5, "minor"), (7, "minor"), (8, "major"), (10, "major"))
        # Include the common harmonic-minor dominant alongside natural minor.
        degrees += ((7, "major"),)
    return {((root + interval) % 12, quality) for interval, quality in degrees}


def infer_chords(
    source: Path,
    *,
    bpm: float,
    duration: float,
    grid_origin: float = 0.0,
    beat_times: tuple[float, ...] = (),
) -> tuple[list[Chord], str]:
    try:
        import librosa
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa is required for chord analysis") from exc

    audio, rate = librosa.load(source, sr=22_050, mono=True, duration=duration)
    harmonic = librosa.effects.harmonic(audio, margin=3.0)
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=harmonic, sr=rate, hop_length=hop)
    all_states, all_templates = _chord_templates()
    key_root, key_mode = _infer_key(chroma)
    allowed = _diatonic_states(key_root, key_mode)
    indexes = [index for index, state in enumerate(all_states) if state in allowed]
    states = [all_states[index] for index in indexes]
    templates = all_templates[indexes]
    beat_seconds = 60.0 / bpm
    if beat_times:
        boundaries = list(beat_boundaries(beat_times, duration, bpm))
    else:
        # Keep the partial material before the first detected beat with the
        # first complete beat instead of treating it as a tiny chord region.
        boundaries = [0.0]
        next_boundary = grid_origin + beat_seconds
        while next_boundary < duration - 1e-6:
            boundaries.append(next_boundary)
            next_boundary += beat_seconds
        boundaries.append(duration)
    count = len(boundaries) - 1
    emissions = np.zeros((count, len(states)), dtype=np.float64)
    confidences = np.zeros(count, dtype=np.float64)
    for beat in range(count):
        first = round(boundaries[beat] * rate / hop)
        last = max(first + 1, round(boundaries[beat + 1] * rate / hop))
        vector = np.mean(chroma[:, first:min(last, chroma.shape[1])], axis=1)
        norm = float(np.linalg.norm(vector))
        if norm > 1e-9:
            vector /= norm
        emissions[beat] = templates @ vector
        ordered = np.sort(emissions[beat])
        confidences[beat] = max(0.0, float(ordered[-1] - ordered[-2])) if ordered.size > 1 else 0.0

    # Viterbi smoothing prevents noisy frame-wise chord changes. Relative and
    # parallel key movements are less expensive than unrelated jumps.
    scores = np.full_like(emissions, -1e9)
    back = np.zeros_like(emissions, dtype=np.int16)
    scores[0] = emissions[0]
    for beat in range(1, count):
        for current, (root, quality) in enumerate(states):
            transitions = np.empty(len(states), dtype=np.float64)
            for previous, (prior_root, prior_quality) in enumerate(states):
                if previous == current:
                    penalty = 0.0
                elif root == prior_root or (root - prior_root) % 12 in {5, 7}:
                    penalty = 0.12
                elif quality != prior_quality and (root - prior_root) % 12 in {0, 3, 4, 8, 9}:
                    penalty = 0.18
                else:
                    penalty = 0.34
                transitions[previous] = scores[beat - 1, previous] - penalty
            winner = int(np.argmax(transitions))
            scores[beat, current] = transitions[winner] + emissions[beat, current]
            back[beat, current] = winner
    path = [int(np.argmax(scores[-1]))]
    for beat in range(count - 1, 0, -1):
        path.append(int(back[beat, path[-1]]))
    path.reverse()

    chords: list[Chord] = []
    first = 0
    for beat in range(1, count + 1):
        if beat < count and path[beat] == path[first]:
            continue
        root, quality = states[path[first]]
        chords.append(
            Chord(
                start=round(boundaries[first], 6),
                end=round(boundaries[beat], 6),
                root=root,
                quality=quality,
                confidence=round(float(np.mean(confidences[first:beat])), 4),
            )
        )
        first = beat
    return chords, f"{_NOTE_NAMES[key_root]} {key_mode}"


def _harmony_notes(
    chords: list[Chord],
    *,
    bpm: float,
    grid_origin: float = 0.0,
    timing_grid: tuple[float, ...] = (),
) -> list[SymbolicNote]:
    notes: list[SymbolicNote] = []
    previous = (60, 64, 67)
    for chord in chords:
        third = 3 if chord.quality == "minor" else 4
        base = 60 + chord.root
        candidates = []
        for inversion in range(3):
            triad = [base, base + third, base + 7]
            for index in range(inversion):
                triad[index] += 12
            for shift in (-12, 0, 12):
                voiced = tuple(note + shift for note in triad)
                if min(voiced) >= 48 and max(voiced) <= 84:
                    candidates.append(voiced)
        voiced = min(candidates, key=lambda item: sum(abs(a - b) for a, b in zip(item, previous)))
        previous = voiced
        for voice, pitch in enumerate(voiced):
            start = (
                nearest_timing(chord.start, timing_grid)
                if timing_grid
                else quantize_time(chord.start, bpm, grid_origin)
            )
            end = (
                nearest_timing(chord.end, timing_grid)
                if timing_grid
                else quantize_time(chord.end, bpm, grid_origin)
            )
            notes.append(
                SymbolicNote(
                    role=f"harmony-{voice + 1}",
                    start=start,
                    end=max(start + _quantum(bpm), end),
                    pitch=int(pitch),
                    velocity=48 if voice else 52,
                )
            )
    return notes


def _merge_matching_notes(notes: list[SymbolicNote], *, maximum_gap: float) -> list[SymbolicNote]:
    merged: list[SymbolicNote] = []
    for note in sorted(notes, key=lambda item: (item.start, item.pitch)):
        if merged and note.pitch == merged[-1].pitch and note.start - merged[-1].end <= maximum_gap + 1e-6:
            previous = merged[-1]
            merged[-1] = SymbolicNote(
                previous.role,
                previous.start,
                max(previous.end, note.end),
                previous.pitch,
                round((previous.velocity + note.velocity) / 2),
            )
        else:
            merged.append(note)
    return merged


def _snap_pitch_class(pitch: int, allowed: set[int], preferred: float) -> int:
    candidates = [candidate for candidate in range(pitch - 3, pitch + 4) if candidate % 12 in allowed]
    if not candidates:
        return pitch
    return min(candidates, key=lambda candidate: (abs(candidate - pitch), abs(candidate - preferred)))


def _cleanup_lead(notes: list[SymbolicNote], arrangement: SymbolicArrangement) -> list[SymbolicNote]:
    root_name, mode = arrangement.key.rsplit(" ", 1)
    root = _NOTE_NAMES.index(root_name)
    intervals = {0, 2, 4, 5, 7, 9, 11} if mode == "major" else {0, 2, 3, 5, 7, 8, 10, 11}
    scale = {(root + interval) % 12 for interval in intervals}
    step = _quantum(arrangement.bpm)
    corrected: list[SymbolicNote] = []
    for index, note in enumerate(notes):
        neighbors = []
        if index:
            neighbors.append(notes[index - 1].pitch)
        if index + 1 < len(notes):
            neighbors.append(notes[index + 1].pitch)
        preferred = float(np.median(neighbors)) if neighbors else float(note.pitch)
        weak_or_brief = note.velocity < 88 or note.end - note.start <= step * 2.05
        pitch = _snap_pitch_class(note.pitch, scale, preferred) if weak_or_brief else note.pitch
        corrected.append(replace(note, pitch=pitch))
    return _merge_matching_notes(corrected, maximum_gap=step * 1.05)


def _chord_at(chords: tuple[Chord, ...], time: float) -> Chord | None:
    return next((chord for chord in chords if chord.start <= time < chord.end), chords[-1] if chords else None)


def _cleanup_bass(notes: list[SymbolicNote], arrangement: SymbolicArrangement) -> list[SymbolicNote]:
    step = _quantum(arrangement.bpm)
    corrected: list[SymbolicNote] = []
    for index, note in enumerate(notes):
        chord = _chord_at(arrangement.chords, (note.start + note.end) * 0.5)
        if chord is None:
            corrected.append(note)
            continue
        third = 3 if chord.quality == "minor" else 4
        chord_tones = {chord.root, (chord.root + third) % 12, (chord.root + 7) % 12}
        duration = note.end - note.start
        if duration <= 60.0 / arrangement.bpm or note.velocity < 80:
            neighbors = [item.pitch for item in notes[max(0, index - 1) : index + 2] if item is not note]
            preferred = float(np.median(neighbors)) if neighbors else float(note.pitch)
            corrected.append(replace(note, pitch=_snap_pitch_class(note.pitch, chord_tones, preferred)))
        else:
            corrected.append(note)
    return _merge_matching_notes(corrected, maximum_gap=step * 0.55)


def _cleanup_drums(arrangement: SymbolicArrangement) -> list[DrumHit]:
    """Turn transient detections into a stable console-style groove."""

    step = _quantum(arrangement.bpm)
    origin = arrangement.grid_origin
    timing = arrangement.timing_grid
    timing_array = np.asarray(timing) if timing else np.zeros(0)
    by_bar: dict[int, list[tuple[int, DrumHit]]] = {}
    for hit in arrangement.drums:
        absolute_slot = (
            int(np.argmin(np.abs(timing_array - hit.time)))
            if timing
            else max(0, round((hit.time - origin) / step))
        )
        bar, slot = divmod(absolute_slot, 16)
        if hit.kind == "snare":
            snapped = min((4, 12), key=lambda candidate: abs(candidate - slot))
        else:
            snapped = min(range(0, 16, 2), key=lambda candidate: abs(candidate - slot))
        by_bar.setdefault(bar, []).append((snapped, hit))

    selected: dict[tuple[int, str], DrumHit] = {}
    for bar, entries in by_bar.items():
        for kind in ("kick", "snare", "hat"):
            candidates: dict[int, DrumHit] = {}
            for slot, hit in entries:
                if hit.kind != kind:
                    continue
                prior = candidates.get(slot)
                if prior is None or hit.velocity > prior.velocity:
                    candidates[slot] = hit
            limit = 5 if kind == "kick" else 2 if kind == "snare" else 8
            strongest = sorted(candidates.items(), key=lambda item: item[1].velocity, reverse=True)[:limit]
            for slot, hit in strongest:
                absolute_slot = bar * 16 + slot
                time = (
                    timing[min(absolute_slot, len(timing) - 1)]
                    if timing
                    else round(min(arrangement.duration, origin + absolute_slot * step), 6)
                )
                selected[(absolute_slot, kind)] = DrumHit(kind, time, hit.velocity)

        # Dense source bars receive a steady, restrained eighth-note hat pulse.
        if len(entries) >= 5:
            for slot in range(0, 16, 2):
                absolute_slot = bar * 16 + slot
                time = (
                    timing[min(absolute_slot, len(timing) - 1)]
                    if timing
                    else origin + absolute_slot * step
                )
                if time >= arrangement.duration:
                    continue
                key = (absolute_slot, "hat")
                selected.setdefault(
                    key,
                    DrumHit("hat", round(time, 6), 48 + (6 if slot % 4 == 0 else 0)),
                )
    return sorted(selected.values(), key=lambda hit: (hit.time, hit.kind))


def musical_cleanup(arrangement: SymbolicArrangement, *, style: str = "preserve") -> SymbolicArrangement:
    """Preserve observed expression; conventionalization requires an explicit style."""

    if style == "preserve":
        return replace(arrangement,
                       notes=tuple(sorted(arrangement.notes, key=lambda note: (note.start, note.role, note.pitch))),
                       drums=tuple(sorted(arrangement.drums, key=lambda hit: (hit.time, hit.kind))))
    if style != "standard-backbeat":
        raise ValueError("cleanup style must be preserve or standard-backbeat")

    lead = _cleanup_lead([note for note in arrangement.notes if note.role == "lead"], arrangement)
    bass = _cleanup_bass([note for note in arrangement.notes if note.role == "bass"], arrangement)
    harmony = [note for note in arrangement.notes if note.role.startswith("harmony")]
    recovered = [note for note in arrangement.notes if note.role.startswith("instrument-")]
    return replace(
        arrangement,
        notes=tuple(
            sorted((*lead, *bass, *harmony, *recovered), key=lambda note: (note.start, note.role, note.pitch))
        ),
        drums=tuple(_cleanup_drums(arrangement)),
    )


def _write_midi(arrangement: SymbolicArrangement, target: Path, *, profile: str) -> None:
    try:
        import pretty_midi
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("pretty_midi is required for diagnostic rendering") from exc

    programs = {
        "reference": {"lead": 73, "bass": 33, "harmony": 0},
        "snes": {"lead": 80, "bass": 38, "harmony": 48},
    }[profile]
    midi = pretty_midi.PrettyMIDI(initial_tempo=arrangement.bpm)
    groups: dict[str, object] = {}
    for group, program in programs.items():
        instrument = pretty_midi.Instrument(program=program, name=group)
        groups[group] = instrument
        midi.instruments.append(instrument)
    for note in arrangement.notes:
        group = "harmony" if note.role.startswith("harmony") else note.role
        if group not in groups:
            archetype = _instrument_archetype(note.role)
            program = {
                "plucked-string": 105,
                "sustained-synth": 81,
                "guitar-like": 25,
                "keys-like": 4,
                "melodic-residual": 84,
            }.get(archetype, 81)
            instrument = pretty_midi.Instrument(program=program, name=group)
            groups[group] = instrument
            midi.instruments.append(instrument)
        groups[group].notes.append(
            pretty_midi.Note(
                velocity=note.velocity,
                pitch=note.pitch,
                start=note.start,
                end=max(note.start + 0.03, note.end),
            )
        )
    drums = pretty_midi.Instrument(program=0, is_drum=True, name="drums")
    drum_pitches = {"kick": 36, "snare": 38, "hat": 42}
    for hit in arrangement.drums:
        drums.notes.append(
            pretty_midi.Note(
                velocity=hit.velocity,
                pitch=drum_pitches[hit.kind],
                start=hit.time,
                end=min(arrangement.duration, hit.time + 0.10),
            )
        )
    midi.instruments.append(drums)
    target.parent.mkdir(parents=True, exist_ok=True)
    midi.write(str(target))


def _render_soundfont(
    fluidsynth: str,
    ffmpeg: str,
    midi: Path,
    soundfont: Path,
    target: Path,
    *,
    duration: float,
    profile: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix="omega-midi-render-") as temporary:
        raw = Path(temporary) / "raw.wav"
        _run(
            [
                fluidsynth,
                "-ni",
                "-g",
                "0.72",
                "-F",
                str(raw),
                "-r",
                "44100",
                str(soundfont),
                str(midi),
            ]
        )
        if profile == "reference":
            audio_filter = f"atrim=duration={duration:.6f},apad=pad_dur=0.1,alimiter=limit=0.94"
            sample_rate = "44100"
        else:
            audio_filter = (
                f"atrim=duration={duration:.6f},apad=pad_dur=0.1,"
                "aresample=32000,lowpass=f=14200,"
                "aecho=0.84:0.72:92:0.18,acompressor=threshold=0.22:ratio=1.7:attack=9:release=110,"
                "alimiter=limit=0.92"
            )
            sample_rate = str(OUTPUT_RATE)
        _run(
            [
                ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(raw),
                "-af",
                audio_filter,
                "-ar",
                sample_rate,
                "-c:a",
                "pcm_s16le",
                str(target),
            ]
        )


def _adsr(
    count: int,
    rate: int,
    *,
    attack: float,
    decay: float,
    sustain: float,
    release: float,
) -> np.ndarray:
    envelope = np.full(count, sustain, dtype=np.float64)
    attack_count = min(count, max(1, round(attack * rate)))
    envelope[:attack_count] = np.linspace(0.0, 1.0, attack_count, endpoint=False)
    decay_count = min(count - attack_count, max(1, round(decay * rate)))
    if decay_count:
        envelope[attack_count : attack_count + decay_count] = np.linspace(1.0, sustain, decay_count, endpoint=False)
    release_count = min(count, max(1, round(release * rate)))
    envelope[-release_count:] *= np.linspace(1.0, 0.0, release_count)
    return envelope


def _plucked_string_note(note: SymbolicNote, count: int) -> np.ndarray:
    """Bright, short-decay Omega Chip string voice suitable for banjo/mandolin roles."""

    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    phase = 2.0 * np.pi * frequency * time
    signal = np.zeros(count, dtype=np.float64)
    for harmonic, level in enumerate((1.0, 0.78, 0.52, 0.36, 0.23, 0.14, 0.08), start=1):
        stretched = harmonic * (1.0 + 0.00072 * harmonic * harmonic)
        decay = np.exp(-time * (2.8 + harmonic * 1.65))
        signal += np.sin(phase * stretched + harmonic * 0.21) * level * decay
    signal /= 2.55
    # A brief deterministic pick transient supplies articulation without
    # copying source samples into the distributable patch.
    seed = (round(note.start * 1_000_000) ^ (note.pitch << 13) ^ 0x42414E4A4F) & 0xFFFFFFFF
    noise = np.random.default_rng(seed).uniform(-1.0, 1.0, count)
    pick = np.concatenate(([noise[0]], np.diff(noise))) * np.exp(-time * 105.0) * 0.12
    body = np.sin(2.0 * np.pi * 440.0 * time + phase * 0.016) * np.exp(-time * 13.0) * 0.055
    envelope = _adsr(count, OUTPUT_RATE, attack=0.0018, decay=0.24, sustain=0.16, release=0.075)
    return np.tanh((signal + pick + body) * 1.24) * envelope * (note.velocity / 127.0)


def _source_informed_saw_note(
    note: SymbolicNote,
    count: int,
    *,
    voice: str,
    fingerprint: SynthFingerprint | None,
    previous_pitch: int | None = None,
) -> np.ndarray:
    """Band-limited saw family shaped by a source fingerprint, not a pulse proxy."""

    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    frequencies = np.full(count, frequency, dtype=np.float64)
    if previous_pitch is not None and previous_pitch != note.pitch:
        prior_frequency = 440.0 * 2.0 ** ((previous_pitch - 69) / 12.0)
        glide_seconds = 0.042 if voice == "bass" else 0.068
        glide_count = min(count, max(1, round(glide_seconds * OUTPUT_RATE)))
        progress = np.linspace(0.0, 1.0, glide_count)
        progress = progress * progress * (3.0 - 2.0 * progress)
        frequencies[:glide_count] = prior_frequency * (frequency / prior_frequency) ** progress
    if fingerprint is not None:
        depth_limit = 3.0 if voice == "bass" else 10.0
        depth = min(depth_limit, fingerprint.vibrato_depth_cents)
        modulation = np.sin(2.0 * np.pi * fingerprint.vibrato_rate_hz * time)
        frequencies *= 2.0 ** (depth * modulation / 1_200.0)
    phase = 2.0 * np.pi * np.cumsum(frequencies) / OUTPUT_RATE
    maximum_harmonic = max(1, min(16, int(OUTPUT_RATE * 0.46 / frequency)))
    measured = fingerprint.harmonic_levels if fingerprint is not None else ()
    measured_peak = max(measured, default=1.0)
    if voice == "bass":
        cutoff = 4.8 + 2.9 * np.exp(-time * 5.2) + np.sin(2.0 * np.pi * 0.34 * time) * 0.38
        detune_cents = 0.0
    else:
        cutoff = 8.2 + 4.8 * np.exp(-time * 2.6) + np.sin(2.0 * np.pi * 0.41 * time) * 1.15
        width = fingerprint.stereo_width if fingerprint is not None else 0.7
        detune_cents = 3.8 + min(6.2, width * 5.0)
    signal = np.zeros(count, dtype=np.float64)
    for harmonic in range(1, maximum_harmonic + 1):
        source_shape = (
            measured[harmonic - 1] / measured_peak
            if harmonic <= len(measured)
            else 1.0 / harmonic
        )
        amplitude = 0.80 / harmonic + 0.20 * source_shape
        amplitude *= np.exp(-harmonic / np.maximum(1.5, cutoff))
        polarity = 1.0 if harmonic % 2 else -1.0
        if detune_cents:
            ratio = 2.0 ** (detune_cents / 1_200.0)
            partial = np.sin(phase * harmonic / ratio + harmonic * 0.07)
            partial += np.sin(phase * harmonic * ratio - harmonic * 0.11)
            partial *= 0.5
        else:
            partial = np.sin(phase * harmonic + harmonic * 0.05)
        signal += partial * amplitude * polarity
    signal /= 1.65 if voice == "bass" else 1.85
    velocity = note.velocity / 127.0
    if voice == "bass":
        signal += np.sin(phase * 0.5) * 0.18
        biased = signal + 0.075
        driven = np.tanh(biased * 2.75) - math.tanh(0.075 * 2.75)
        signal = signal * 0.20 + driven * 0.80
        envelope = _adsr(
            count,
            OUTPUT_RATE,
            attack=fingerprint.attack if fingerprint else 0.004,
            decay=fingerprint.decay if fingerprint else 0.20,
            sustain=fingerprint.sustain if fingerprint else 0.61,
            release=fingerprint.release if fingerprint else 0.11,
        )
    else:
        signal = np.tanh(signal * 1.48)
        envelope = _adsr(
            count,
            OUTPUT_RATE,
            attack=fingerprint.attack if fingerprint else 0.014,
            decay=fingerprint.decay if fingerprint else 0.24,
            sustain=max(0.44, fingerprint.sustain) if fingerprint else 0.58,
            release=fingerprint.release if fingerprint else 0.18,
        )
    return signal * envelope * velocity


def _recovered_instrument_note(
    note: SymbolicNote,
    count: int,
    profile: OmegaChipProfile,
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
    previous_pitch: int | None = None,
) -> np.ndarray:
    archetype = _instrument_archetype(note.role)
    if archetype == "plucked-string":
        return _plucked_string_note(note, count)
    if archetype == "sustained-synth":
        fingerprints = voice_fingerprints or {}
        fingerprint = fingerprints.get(note.role) or fingerprints.get("sustained-synth")
        return _source_informed_saw_note(
            note,
            count,
            voice="synth",
            fingerprint=fingerprint,
            previous_pitch=previous_pitch,
        )
    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    phase = 2.0 * np.pi * frequency * time
    velocity = note.velocity / 127.0
    if archetype == "guitar-like":
        envelope = _adsr(count, OUTPUT_RATE, attack=0.004, decay=0.31, sustain=0.30, release=0.11)
        signal = _triangle(phase) * 0.48 + np.sin(phase * 2.01) * 0.24 + np.sin(phase * 3.0) * 0.10
    elif archetype == "keys-like":
        envelope = _adsr(count, OUTPUT_RATE, attack=0.005, decay=0.44, sustain=0.34, release=0.18)
        signal = np.sin(phase) * 0.52 + np.sin(phase * 2.0) * 0.17
        signal += np.sin(phase * 3.98) * np.exp(-time * 5.5) * 0.14
    else:
        envelope = _adsr(count, OUTPUT_RATE, attack=0.018, decay=0.28, sustain=0.45, release=0.17)
        signal = _triangle(phase) * 0.42 + np.sin(phase * 2.0) * 0.22 + np.sin(phase) * 0.22
    return np.tanh(signal * 1.10) * envelope * velocity


def _four_operator_note(note: SymbolicNote, count: int) -> np.ndarray:
    if _instrument_archetype(note.role) == "plucked-string":
        return _plucked_string_note(note, count)
    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    phase = 2.0 * np.pi * frequency * time
    if note.role == "bass":
        ratios, indexes = (1.0, 1.0, 2.0, 0.5), (1.0, 1.8, 1.1)
        envelope = _adsr(count, OUTPUT_RATE, attack=0.006, decay=0.15, sustain=0.58, release=0.08)
        op4 = np.sin(phase * ratios[3]) * indexes[2] * envelope
        op3 = np.sin(phase * ratios[2] + op4) * indexes[1] * envelope
        op2 = np.sin(phase * ratios[1] + op3) * indexes[0] * envelope
        signal = np.sin(phase * ratios[0] + op2) * envelope
    elif note.role == "lead":
        ratios, indexes = (1.0, 2.0, 3.0, 5.0), (2.2, 1.45, 0.72)
        envelope = _adsr(count, OUTPUT_RATE, attack=0.012, decay=0.11, sustain=0.70, release=0.10)
        vibrato = np.sin(2.0 * np.pi * 5.3 * time) * 0.018
        carrier = phase + vibrato
        op4 = np.sin(carrier * ratios[3]) * indexes[2] * envelope
        op3 = np.sin(carrier * ratios[2] + op4) * indexes[1] * envelope
        op2 = np.sin(carrier * ratios[1] + op3) * indexes[0] * envelope
        signal = np.sin(carrier * ratios[0] + op2) * envelope
    else:
        ratios, indexes = (1.0, 2.0, 1.0, 3.0), (1.35, 0.65, 0.48)
        envelope = _adsr(count, OUTPUT_RATE, attack=0.018, decay=0.30, sustain=0.44, release=0.16)
        op4 = np.sin(phase * ratios[3]) * indexes[2] * envelope
        op3 = np.sin(phase * ratios[2] + op4) * indexes[1] * envelope
        carrier_a = np.sin(phase * ratios[0] + op3 * indexes[0])
        carrier_b = np.sin(phase * ratios[1] + op4 * indexes[1])
        signal = (carrier_a * 0.66 + carrier_b * 0.34) * envelope
    return signal * (note.velocity / 127.0)


def _render_genesis(arrangement: SymbolicArrangement, target: Path) -> None:
    total = max(1, round((arrangement.duration + 0.1) * OUTPUT_RATE))
    output = np.zeros((total, 2), dtype=np.float64)
    pans = {"lead": -0.22, "bass": 0.0, "harmony-1": -0.58, "harmony-2": 0.24, "harmony-3": 0.62}
    gains = {"lead": 0.25, "bass": 0.24, "harmony-1": 0.11, "harmony-2": 0.10, "harmony-3": 0.10}
    for note in arrangement.notes:
        first = max(0, round(note.start * OUTPUT_RATE))
        last = min(total, round((note.end + 0.12) * OUTPUT_RATE))
        if last <= first:
            continue
        instrument = note.role.startswith("instrument-")
        signal = _four_operator_note(note, last - first) * gains.get(note.role, 0.145 if instrument else 0.10)
        pan = pans.get(note.role, _stable_instrument_pan(note.role) if instrument else 0.0)
        output[first:last, 0] += signal * math.sqrt((1.0 - pan) * 0.5)
        output[first:last, 1] += signal * math.sqrt((1.0 + pan) * 0.5)

    rng = np.random.default_rng(0x4F4D454741)
    for hit in arrangement.drums:
        first = max(0, round(hit.time * OUTPUT_RATE))
        count = min(round(0.22 * OUTPUT_RATE), total - first)
        if count <= 0:
            continue
        time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
        amount = hit.velocity / 127.0
        if hit.kind == "kick":
            frequency = 132.0 * np.exp(-time * 18.0) + 43.0
            phase = 2.0 * np.pi * np.cumsum(frequency) / OUTPUT_RATE
            signal = np.sin(phase) * np.exp(-time * 19.0) * 0.40 * amount
        elif hit.kind == "snare":
            noise = rng.choice((-1.0, 1.0), count)
            signal = (noise * 0.30 + np.sin(2.0 * np.pi * 188.0 * time) * 0.14) * np.exp(-time * 24.0) * amount
        else:
            noise = rng.choice((-1.0, 1.0), count)
            signal = np.concatenate(([noise[0]], np.diff(noise))) * np.exp(-time * 46.0) * 0.15 * amount
        output[first : first + count] += signal[:, None]

    output = np.round(output * 1_024.0) / 1_024.0
    peak = float(np.max(np.abs(output)))
    if peak > 1e-9:
        output *= min(1.0, 0.90 / peak)
    pcm = np.round(np.clip(output, -1.0, 1.0) * 32767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(OUTPUT_RATE)
        stream.writeframes(pcm.tobytes())


def _enhanced_console_note(note: SymbolicNote, count: int) -> np.ndarray:
    """Render a deliberately era-flavored voice without hardware-exact limits."""

    if note.role.startswith("instrument-"):
        return _recovered_instrument_note(note, count, OMEGA_CHIP_PROFILES["balanced"])
    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    phase = 2.0 * np.pi * frequency * time
    triangle = lambda angle: (2.0 / np.pi) * np.arcsin(np.sin(angle))
    if note.role == "lead":
        modulated = phase + np.sin(2.0 * np.pi * 5.15 * time) * 0.065
        envelope = _adsr(count, OUTPUT_RATE, attack=0.010, decay=0.12, sustain=0.72, release=0.13)
        signal = triangle(modulated) * 0.58 + np.sin(modulated * 2.0) * 0.17
        signal += np.where(np.sin(modulated) >= 0.0, 1.0, -1.0) * 0.11
    elif note.role == "bass":
        envelope = _adsr(count, OUTPUT_RATE, attack=0.005, decay=0.18, sustain=0.62, release=0.10)
        signal = triangle(phase) * 0.48 + np.sin(phase * 0.5) * 0.34
        signal += np.sin(phase * 2.0) * 0.10 + np.sin(phase * 3.0) * 0.05
    else:
        envelope = _adsr(count, OUTPUT_RATE, attack=0.035, decay=0.34, sustain=0.48, release=0.20)
        signal = np.sin(phase * 0.997) * 0.34 + np.sin(phase * 1.003) * 0.34
        signal += triangle(phase) * 0.22
    return np.tanh(signal * 1.1) * envelope * (note.velocity / 127.0)


def _render_enhanced_console(arrangement: SymbolicArrangement, target: Path) -> None:
    """Hybrid sample/FM/wavetable interpretation with a classic-console feel."""

    total = max(1, round((arrangement.duration + 0.2) * OUTPUT_RATE))
    output = np.zeros((total, 2), dtype=np.float64)
    pans = {"lead": -0.14, "bass": 0.0, "harmony-1": -0.64, "harmony-2": 0.12, "harmony-3": 0.58}
    gains = {"lead": 0.26, "bass": 0.28, "harmony-1": 0.105, "harmony-2": 0.095, "harmony-3": 0.095}
    for note in arrangement.notes:
        first = max(0, round(note.start * OUTPUT_RATE))
        last = min(total, round((note.end + 0.16) * OUTPUT_RATE))
        if last <= first:
            continue
        instrument = note.role.startswith("instrument-")
        signal = _enhanced_console_note(note, last - first) * gains.get(note.role, 0.165 if instrument else 0.10)
        pan = pans.get(note.role, _stable_instrument_pan(note.role) if instrument else 0.0)
        output[first:last, 0] += signal * math.sqrt((1.0 - pan) * 0.5)
        output[first:last, 1] += signal * math.sqrt((1.0 + pan) * 0.5)

    rng = np.random.default_rng(0x4F4D4547415F4348)
    for hit in arrangement.drums:
        first = max(0, round(hit.time * OUTPUT_RATE))
        count = min(round(0.24 * OUTPUT_RATE), total - first)
        if count <= 0:
            continue
        time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
        amount = hit.velocity / 127.0
        if hit.kind == "kick":
            frequency = 116.0 * np.exp(-time * 20.0) + 46.0
            phase = 2.0 * np.pi * np.cumsum(frequency) / OUTPUT_RATE
            signal = (np.sin(phase) + np.sin(phase * 0.5) * 0.28) * np.exp(-time * 17.0) * 0.36
        elif hit.kind == "snare":
            noise = rng.uniform(-1.0, 1.0, count)
            tone = np.sin(2.0 * np.pi * 196.0 * time) + np.sin(2.0 * np.pi * 322.0 * time) * 0.4
            signal = (noise * 0.27 + tone * 0.12) * np.exp(-time * 21.0)
        else:
            noise = rng.choice((-1.0, 1.0), count)
            bright = np.concatenate(([noise[0]], np.diff(noise)))
            signal = bright * np.exp(-time * 53.0) * 0.095
        output[first : first + count] += (signal * amount)[:, None]

    # A short cross-channel echo supplies the recognizable console-space feel
    # without imposing a historical DSP or voice-count ceiling.
    for seconds, gain in ((0.092, 0.15), (0.184, 0.075)):
        delay = round(seconds * OUTPUT_RATE)
        dry = output.copy()
        output[delay:, 0] += dry[:-delay, 1] * gain
        output[delay:, 1] += dry[:-delay, 0] * gain
    output = np.tanh(output * 1.32) / np.tanh(1.32)
    output = np.round(output * 2_048.0) / 2_048.0
    peak = float(np.max(np.abs(output)))
    if peak > 1e-9:
        output *= min(1.0, 0.91 / peak)
    pcm = np.round(np.clip(output, -1.0, 1.0) * 32767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(OUTPUT_RATE)
        stream.writeframes(pcm.tobytes())


def _triangle(angle: np.ndarray) -> np.ndarray:
    return (2.0 / np.pi) * np.arcsin(np.sin(angle))


def _stable_instrument_pan(role: str) -> float:
    digest = hashlib.sha256(role.encode("utf-8")).digest()
    if _instrument_archetype(role) == "sustained-synth":
        direction = -1.0 if digest[0] & 1 else 1.0
        return direction * (0.36 + digest[1] / 255.0 * 0.18)
    value = int.from_bytes(digest[:2], "big") / 65_535.0
    return (value * 2.0 - 1.0) * 0.42


def _omega_chip_note(
    note: SymbolicNote,
    count: int,
    profile: OmegaChipProfile,
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
    previous_pitch: int | None = None,
) -> np.ndarray:
    if note.role.startswith("instrument-"):
        return _recovered_instrument_note(
            note,
            count,
            profile,
            voice_fingerprints,
            previous_pitch,
        )
    frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    phase = 2.0 * np.pi * frequency * time
    velocity = note.velocity / 127.0
    if note.role == "lead":
        phase += np.sin(2.0 * np.pi * 5.35 * time) * 0.052
        width = 0.42 + np.sin(2.0 * np.pi * 0.72 * time) * 0.055
        pulse = np.where(np.mod(phase / (2.0 * np.pi), 1.0) < width, 1.0, -1.0)
        envelope = _adsr(count, OUTPUT_RATE, attack=0.009, decay=0.14, sustain=0.73, release=0.14)
        signal = _triangle(phase) * 0.58 + np.sin(phase * 2.0) * 0.16 + pulse * profile.pulse_mix
    elif note.role == "bass":
        fingerprint = (voice_fingerprints or {}).get("bass")
        return _source_informed_saw_note(
            note,
            count,
            voice="bass",
            fingerprint=fingerprint,
            previous_pitch=previous_pitch,
        )
    elif note.role == "arpeggio":
        envelope = _adsr(count, OUTPUT_RATE, attack=0.003, decay=0.09, sustain=0.40, release=0.08)
        signal = _triangle(phase) * 0.46 + np.sin(phase * 2.0) * 0.20 + np.sin(phase * 4.0) * 0.07
    else:
        detune = 0.0028 if profile.name == "balanced" else 0.0042
        envelope = _adsr(count, OUTPUT_RATE, attack=0.040, decay=0.36, sustain=0.50, release=0.22)
        signal = np.sin(phase * (1.0 - detune)) * 0.32 + np.sin(phase * (1.0 + detune)) * 0.32
        signal += _triangle(phase) * 0.21
    return np.tanh(signal * 1.08) * envelope * velocity


def omega_arpeggio_notes(arrangement: SymbolicArrangement) -> tuple[SymbolicNote, ...]:
    """Build a restrained eighth-note sparkle voice from the chord track."""

    step = 60.0 / arrangement.bpm / 2.0
    notes: list[SymbolicNote] = []
    recovered = [note for note in arrangement.notes if note.role.startswith("instrument-")]
    for chord in arrangement.chords:
        third = 3 if chord.quality == "minor" else 4
        pitches = (72 + chord.root, 72 + chord.root + third, 72 + chord.root + 7, 72 + chord.root + third)
        while max(pitches) > 91:
            pitches = tuple(pitch - 12 for pitch in pitches)
        if arrangement.timing_grid:
            starts = [
                time
                for grid_index, time in enumerate(arrangement.timing_grid)
                if grid_index % 2 == 0 and chord.start <= time < chord.end - 1e-6
            ]
        else:
            starts = []
            time = chord.start
            while time < chord.end - 1e-6:
                starts.append(time)
                time += step
        for index, time in enumerate(starts):
            if any(note.start - 0.05 <= time < note.end + 0.05 for note in recovered):
                continue
            if arrangement.timing_grid:
                grid_index = arrangement.timing_grid.index(time)
                next_index = min(len(arrangement.timing_grid) - 1, grid_index + 2)
                local_step = arrangement.timing_grid[next_index] - time
            else:
                local_step = step
            end = min(chord.end, time + local_step * 0.68)
            notes.append(SymbolicNote("arpeggio", round(time, 6), round(end, 6), pitches[index % 4], 50))
    return tuple(notes)


def _omega_chip_drums(arrangement: SymbolicArrangement, total: int) -> np.ndarray:
    output = np.zeros((total, 2), dtype=np.float64)
    rng = np.random.default_rng(0x4F4D4547415F43484950)
    for hit in arrangement.drums:
        first = max(0, round(hit.time * OUTPUT_RATE))
        count = min(round(0.25 * OUTPUT_RATE), total - first)
        if count <= 0:
            continue
        time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
        amount = hit.velocity / 127.0
        if hit.kind == "kick":
            frequency = 128.0 * np.exp(-time * 22.0) + 43.0
            phase = 2.0 * np.pi * np.cumsum(frequency) / OUTPUT_RATE
            click = np.exp(-time * 72.0) * rng.uniform(-1.0, 1.0, count) * 0.055
            signal = (np.sin(phase) + np.sin(phase * 0.5) * 0.24) * np.exp(-time * 18.0) * 0.39 + click
        elif hit.kind == "snare":
            noise = rng.uniform(-1.0, 1.0, count)
            body = np.sin(2.0 * np.pi * 188.0 * time) + np.sin(2.0 * np.pi * 337.0 * time) * 0.36
            signal = (noise * 0.29 + body * 0.12) * np.exp(-time * 22.0)
        else:
            noise = rng.choice((-1.0, 1.0), count)
            bright = np.concatenate(([noise[0]], np.diff(noise)))
            metallic = np.sin(2.0 * np.pi * 6_421.0 * time) * 0.025
            signal = (bright * 0.085 + metallic) * np.exp(-time * 56.0)
        output[first : first + count] += (signal * amount)[:, None]
    return output


def _cross_echo(source: np.ndarray, seconds: float, gain: float) -> np.ndarray:
    output = source.copy()
    delay = round(seconds * OUTPUT_RATE)
    output[delay:, 0] += source[:-delay, 1] * gain
    output[delay:, 1] += source[:-delay, 0] * gain
    return output


def _render_omega_chip(
    arrangement: SymbolicArrangement,
    target: Path,
    *,
    profile: OmegaChipProfile,
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
) -> None:
    """Render the project's own flexible retro-console synthesis identity."""

    total = max(1, round((arrangement.duration + 0.25) * OUTPUT_RATE))
    buses = {
        name: np.zeros((total, 2), dtype=np.float64)
        for name in ("lead", "bass", "harmony", "arpeggio", "instrument")
    }
    notes = (*arrangement.notes, *omega_arpeggio_notes(arrangement))
    harmony_pans = {"harmony-1": -0.72, "harmony-2": 0.10, "harmony-3": 0.66}
    previous_by_role: dict[str, SymbolicNote] = {}
    for note_index, note in enumerate(notes):
        bus_name = (
            "harmony"
            if note.role.startswith("harmony")
            else "instrument"
            if note.role.startswith("instrument-")
            else note.role
        )
        first = max(0, round(note.start * OUTPUT_RATE))
        release = 0.20 if bus_name == "harmony" else 0.15
        last = min(total, round((note.end + release) * OUTPUT_RATE))
        if last <= first:
            continue
        previous = previous_by_role.get(note.role)
        previous_pitch = (
            previous.pitch if previous is not None and note.start - previous.end <= 0.14 else None
        )
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
        elif note.role == "bass":
            pan = 0.0
        elif note.role == "arpeggio":
            pan = (-0.48 if note_index % 2 else 0.48) * profile.stereo_width
        elif note.role.startswith("instrument-"):
            pan = _stable_instrument_pan(note.role) * profile.stereo_width
        else:
            pan = harmony_pans.get(note.role, 0.0) * profile.stereo_width
        buses[bus_name][first:last, 0] += signal * math.sqrt((1.0 - pan) * 0.5)
        buses[bus_name][first:last, 1] += signal * math.sqrt((1.0 + pan) * 0.5)

    lead = _cross_echo(buses["lead"], 0.096, profile.echo_gain)
    harmony = _cross_echo(buses["harmony"], 0.168, profile.echo_gain * 0.72)
    arpeggio = _cross_echo(buses["arpeggio"], 0.073, profile.echo_gain * 0.52)
    instrument = _cross_echo(buses["instrument"], 0.118, profile.echo_gain * 0.38)
    drums = _omega_chip_drums(arrangement, total)
    output = lead * profile.lead_gain
    output += buses["bass"] * profile.bass_gain
    output += harmony * profile.harmony_gain
    output += arpeggio * profile.arpeggio_gain
    output += instrument * (0.285 if profile.name == "balanced" else 0.305)
    output += drums * profile.drum_gain
    output = np.tanh(output * profile.drive) / np.tanh(profile.drive)
    output = np.round(output * 4_096.0) / 4_096.0
    peak = float(np.max(np.abs(output)))
    if peak > 1e-9:
        output *= min(1.0, 0.92 / peak)
    pcm = np.round(np.clip(output, -1.0, 1.0) * 32767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(OUTPUT_RATE)
        stream.writeframes(pcm.tobytes())


def _fingerprint_note(
    note: SymbolicNote,
    count: int,
    fingerprint: SynthFingerprint,
    wavetable: np.ndarray | None,
) -> np.ndarray:
    base_frequency = 440.0 * 2.0 ** ((note.pitch - 69) / 12.0)
    time = np.arange(count, dtype=np.float64) / OUTPUT_RATE
    modulation = np.sin(2.0 * np.pi * fingerprint.vibrato_rate_hz * time)
    frequencies = base_frequency * 2.0 ** (fingerprint.vibrato_depth_cents * modulation / 1_200.0)
    phase = 2.0 * np.pi * np.cumsum(frequencies) / OUTPUT_RATE
    signal = np.zeros(count, dtype=np.float64)
    included = 0.0
    for harmonic, level in enumerate(fingerprint.harmonic_levels, start=1):
        if base_frequency * harmonic >= OUTPUT_RATE * 0.47:
            break
        signal += np.sin(phase * harmonic + harmonic * 0.173) * level
        included += level
    signal /= max(1e-9, included)
    seed = (round(note.start * 1_000_000) ^ (note.pitch << 16) ^ 0x4F4D4547) & 0xFFFFFFFF
    noise = np.random.default_rng(seed).uniform(-1.0, 1.0, count)
    noise = np.roll(noise, 1) * 0.22 + noise * 0.56 + np.roll(noise, -1) * 0.22
    signal = signal * (1.0 - fingerprint.noise_mix) + noise * fingerprint.noise_mix
    if wavetable is not None and wavetable.size >= 8:
        position = np.mod(phase / (2.0 * np.pi), 1.0) * wavetable.size
        indexes = np.floor(position).astype(np.int64)
        fraction = position - indexes
        table_signal = wavetable[indexes % wavetable.size] * (1.0 - fraction)
        table_signal += wavetable[(indexes + 1) % wavetable.size] * fraction
        signal = signal * 0.68 + table_signal * 0.32
    envelope = _adsr(
        count,
        OUTPUT_RATE,
        attack=fingerprint.attack,
        decay=fingerprint.decay,
        sustain=fingerprint.sustain,
        release=fingerprint.release,
    )
    return np.tanh(signal * 1.16) * envelope * (note.velocity / 127.0)


def _render_fingerprint_chip(
    arrangement: SymbolicArrangement,
    target: Path,
    *,
    fingerprint: SynthFingerprint,
    wavetable: np.ndarray | None,
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
) -> None:
    profile = OMEGA_CHIP_PROFILES["balanced"]
    total = max(1, round((arrangement.duration + 0.25) * OUTPUT_RATE))
    buses = {
        name: np.zeros((total, 2), dtype=np.float64)
        for name in ("lead", "bass", "harmony", "arpeggio", "instrument")
    }
    notes = (*arrangement.notes, *omega_arpeggio_notes(arrangement))
    source_width = max(0.45, min(1.05, 0.62 + fingerprint.stereo_width * 0.38))
    harmony_pans = {"harmony-1": -0.70, "harmony-2": 0.08, "harmony-3": 0.64}
    previous_by_role: dict[str, SymbolicNote] = {}
    for note_index, note in enumerate(notes):
        bus_name = (
            "harmony"
            if note.role.startswith("harmony")
            else "instrument"
            if note.role.startswith("instrument-")
            else note.role
        )
        first = max(0, round(note.start * OUTPUT_RATE))
        last = min(total, round((note.end + fingerprint.release) * OUTPUT_RATE))
        if last <= first:
            continue
        previous = previous_by_role.get(note.role)
        previous_pitch = (
            previous.pitch if previous is not None and note.start - previous.end <= 0.14 else None
        )
        omega_signal = _omega_chip_note(
            note,
            last - first,
            profile,
            voice_fingerprints,
            previous_pitch,
        )
        previous_by_role[note.role] = note
        if note.role == "bass" or note.role.startswith("instrument-"):
            signal = omega_signal
        else:
            source_signal = _fingerprint_note(note, last - first, fingerprint, wavetable)
            source_mix = 0.58 if note.role == "lead" else 0.76
            signal = omega_signal * (1.0 - source_mix) + source_signal * source_mix
        if note.role == "lead":
            pan = -0.08 * source_width
        elif note.role == "bass":
            pan = 0.0
        elif note.role == "arpeggio":
            pan = (-0.46 if note_index % 2 else 0.46) * source_width
        elif note.role.startswith("instrument-"):
            pan = _stable_instrument_pan(note.role) * source_width
        else:
            pan = harmony_pans.get(note.role, 0.0) * source_width
        buses[bus_name][first:last, 0] += signal * math.sqrt((1.0 - pan) * 0.5)
        buses[bus_name][first:last, 1] += signal * math.sqrt((1.0 + pan) * 0.5)

    echo = 0.105 + max(0.0, 1.0 - fingerprint.stereo_correlation) * 0.035
    lead = _cross_echo(buses["lead"], 0.096, echo)
    harmony = _cross_echo(buses["harmony"], 0.168, echo * 0.70)
    arpeggio = _cross_echo(buses["arpeggio"], 0.073, echo * 0.50)
    instrument = _cross_echo(buses["instrument"], 0.118, echo * 0.38)
    output = lead * 0.28 + buses["bass"] * 0.35
    output += harmony * 0.245 + arpeggio * 0.072
    output += instrument * 0.285
    output += _omega_chip_drums(arrangement, total) * 0.86
    output = np.tanh(output * 1.25) / np.tanh(1.25)
    output = np.round(output * 4_096.0) / 4_096.0
    peak = float(np.max(np.abs(output)))
    if peak > 1e-9:
        output *= min(1.0, 0.92 / peak)
    pcm = np.round(np.clip(output, -1.0, 1.0) * 32767.0).astype("<i2")
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(OUTPUT_RATE)
        stream.writeframes(pcm.tobytes())


def _write_wavetable_preview(
    wavetable: np.ndarray,
    fingerprint: SynthFingerprint,
    target: Path,
) -> None:
    count = OUTPUT_RATE
    phase = np.arange(count, dtype=np.float64) * fingerprint.fundamental_median_hz / OUTPUT_RATE
    position = np.mod(phase, 1.0) * wavetable.size
    indexes = np.floor(position).astype(np.int64)
    fraction = position - indexes
    signal = wavetable[indexes % wavetable.size] * (1.0 - fraction)
    signal += wavetable[(indexes + 1) % wavetable.size] * fraction
    envelope = _adsr(count, OUTPUT_RATE, attack=0.02, decay=0.10, sustain=0.72, release=0.16)
    pcm = np.round(np.clip(signal * envelope * 0.55, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(target), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(OUTPUT_RATE)
        stream.writeframes(pcm.tobytes())


def _encode_review(ffmpeg: str, source: Path, target: Path) -> None:
    _run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            "loudnorm=I=-15:TP=-1.5:LRA=11",
            "-c:a",
            "libvorbis",
            "-q:a",
            "6",
            str(target),
        ]
    )


def render_diagnostic(
    *,
    arrangement: SymbolicArrangement,
    output: Path,
    soundfont: Path,
    synth_fingerprint: SynthFingerprint | None = None,
    source_wavetable: np.ndarray | None = None,
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    fluidsynth = shutil.which("fluidsynth")
    if not ffmpeg or not fluidsynth:
        raise RuntimeError("ffmpeg and fluidsynth are required")
    if not soundfont.is_file():
        raise RuntimeError(f"soundfont is missing: {soundfont}")

    output.mkdir(parents=True, exist_ok=True)
    for role, fingerprint in sorted((voice_fingerprints or {}).items()):
        save_synth_fingerprint(
            fingerprint,
            output / f"voice-fingerprint-{_safe_instrument_label(role)}.json",
        )
    target = save_arrangement(arrangement, output / "arrangement.json")
    reference_midi = output / "01-symbolic-reference.mid"
    snes_midi = output / "02-snes-sample-bank.mid"
    _write_midi(arrangement, reference_midi, profile="reference")
    _write_midi(arrangement, snes_midi, profile="snes")
    reference_wav = output / "01-symbolic-reference.wav"
    snes_wav = output / "02-snes-sample-bank.wav"
    genesis_wav = output / "03-genesis-four-op.wav"
    enhanced_wav = output / "04-enhanced-console-hybrid.wav"
    omega_balanced_wav = output / "05-omega-chip-balanced.wav"
    omega_vivid_wav = output / "06-omega-chip-vivid.wav"
    _render_soundfont(
        fluidsynth,
        ffmpeg,
        reference_midi,
        soundfont,
        reference_wav,
        duration=arrangement.duration,
        profile="reference",
    )
    _render_soundfont(
        fluidsynth,
        ffmpeg,
        snes_midi,
        soundfont,
        snes_wav,
        duration=arrangement.duration,
        profile="snes",
    )
    _render_genesis(arrangement, genesis_wav)
    _render_enhanced_console(arrangement, enhanced_wav)
    _render_omega_chip(
        arrangement,
        omega_balanced_wav,
        profile=OMEGA_CHIP_PROFILES["balanced"],
        voice_fingerprints=voice_fingerprints,
    )
    _render_omega_chip(
        arrangement,
        omega_vivid_wav,
        profile=OMEGA_CHIP_PROFILES["vivid"],
        voice_fingerprints=voice_fingerprints,
    )
    renders = [
        reference_wav,
        snes_wav,
        genesis_wav,
        enhanced_wav,
        omega_balanced_wav,
        omega_vivid_wav,
    ]
    if synth_fingerprint is not None:
        save_synth_fingerprint(synth_fingerprint, output / "synth-fingerprint.json")
        fingerprint_wav = output / "07-omega-chip-source-fingerprint.wav"
        _render_fingerprint_chip(
            arrangement,
            fingerprint_wav,
            fingerprint=synth_fingerprint,
            wavetable=None,
            voice_fingerprints=voice_fingerprints,
        )
        renders.append(fingerprint_wav)
        if source_wavetable is not None:
            np.save(output / "source-wavetable.npy", source_wavetable)
            hybrid_wav = output / "08-omega-chip-source-wavetable-hybrid.wav"
            _render_fingerprint_chip(
                arrangement,
                hybrid_wav,
                fingerprint=synth_fingerprint,
                wavetable=source_wavetable,
                voice_fingerprints=voice_fingerprints,
            )
            renders.append(hybrid_wav)
            preview_wav = output / "source-wavetable-preview.wav"
            _write_wavetable_preview(source_wavetable, synth_fingerprint, preview_wav)
            _encode_review(ffmpeg, preview_wav, preview_wav.with_suffix(".ogg"))
    for wav in renders:
        _encode_review(ffmpeg, wav, wav.with_suffix(".ogg"))
    return target


def render_omega_review(
    *,
    arrangement: SymbolicArrangement,
    output: Path,
    synth_fingerprint: SynthFingerprint | None = None,
    source_wavetable: np.ndarray | None = None,
    voice_fingerprints: dict[str, SynthFingerprint] | None = None,
) -> Path:
    """Fast listening render that skips unrelated MIDI and legacy proxies."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    output.mkdir(parents=True, exist_ok=True)
    for role, fingerprint in sorted((voice_fingerprints or {}).items()):
        save_synth_fingerprint(
            fingerprint,
            output / f"voice-fingerprint-{_safe_instrument_label(role)}.json",
        )
    target = save_arrangement(arrangement, output / "arrangement.json")
    renders = []
    balanced = output / "05-omega-chip-balanced.wav"
    _render_omega_chip(
        arrangement,
        balanced,
        profile=OMEGA_CHIP_PROFILES["balanced"],
        voice_fingerprints=voice_fingerprints,
    )
    renders.append(balanced)
    if synth_fingerprint is not None:
        save_synth_fingerprint(synth_fingerprint, output / "synth-fingerprint.json")
        fingerprint_target = output / "07-omega-chip-source-fingerprint.wav"
        _render_fingerprint_chip(
            arrangement,
            fingerprint_target,
            fingerprint=synth_fingerprint,
            wavetable=None,
            voice_fingerprints=voice_fingerprints,
        )
        renders.append(fingerprint_target)
        if source_wavetable is not None:
            np.save(output / "source-wavetable.npy", source_wavetable)
            hybrid_target = output / "08-omega-chip-source-wavetable-hybrid.wav"
            _render_fingerprint_chip(
                arrangement,
                hybrid_target,
                fingerprint=synth_fingerprint,
                wavetable=source_wavetable,
                voice_fingerprints=voice_fingerprints,
            )
            renders.append(hybrid_target)
    for wav in renders:
        _encode_review(ffmpeg, wav, wav.with_suffix(".ogg"))
    return target


def enrich_arrangement_with_instruments(
    arrangement: SymbolicArrangement,
    instrument_sources: dict[str, Path],
    *,
    output: Path,
    apply_cleanup: bool = False,
    cleanup_style: str = "preserve",
) -> SymbolicArrangement:
    """Recover additional parts without repeating the core stem analysis."""

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    try:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("Basic Pitch with an ONNX runtime is required") from exc

    output.mkdir(parents=True, exist_ok=True)
    hashes = {label: _sha256(source) for label, source in instrument_sources.items()}
    with tempfile.TemporaryDirectory(prefix="omega-instrument-discovery-") as temporary:
        temporary_root = Path(temporary)
        clips = {}
        for label, source in sorted(instrument_sources.items()):
            target = temporary_root / f"instrument-{_safe_instrument_label(label)}.wav"
            _clip_audio(
                ffmpeg,
                source,
                target,
                arrangement.source_offset,
                arrangement.duration,
            )
            clips[label] = target
        inventory = discover_instrument_inventory(
            clips,
            source_offset=arrangement.source_offset,
            duration=arrangement.duration,
            source_hashes=hashes,
        )
        recovered = transcribe_discovered_instruments(
            clips,
            inventory,
            model=Model(ICASSP_2022_MODEL_PATH),
            bpm=arrangement.bpm,
            duration=arrangement.duration,
            grid_origin=arrangement.grid_origin,
            timing_grid=arrangement.timing_grid,
        )

    existing = [note for note in arrangement.notes if not note.role.startswith("instrument-")]
    provenance = replace(
        arrangement.source,
        other_sha256=hashes.get("other", arrangement.source.other_sha256),
        instrument_sha256=tuple(sorted(hashes.items())),
    )
    enriched = replace(
        arrangement,
        schema_version=max(2, arrangement.schema_version),
        source=provenance,
        notes=tuple(sorted((*existing, *recovered), key=lambda note: (note.start, note.role, note.pitch))),
    )
    if apply_cleanup:
        enriched = musical_cleanup(enriched, style=cleanup_style)
    save_instrument_inventory(inventory, output / "instrument-inventory.json")
    save_instrument_extracts(
        inventory,
        instrument_sources,
        output / "instrument-extracts",
        ffmpeg=ffmpeg,
    )
    save_arrangement(enriched, output / "arrangement.json")
    return enriched


def build_diagnostic(
    *,
    mix: Path,
    vocals: Path,
    bass: Path,
    drums: Path,
    output: Path,
    start: float,
    duration: float,
    bpm: float | None,
    soundfont: Path,
    separator: str = "unspecified",
    apply_cleanup: bool = False,
    cleanup_style: str = "preserve",
    analysis_only: bool = False,
    instrument_stems: dict[str, Path] | None = None,
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")

    try:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import Model
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("Basic Pitch with an ONNX runtime is required") from exc

    output.mkdir(parents=True, exist_ok=True)
    instrument_sources = instrument_stems or {}
    inventory: InstrumentInventory | None = None
    with tempfile.TemporaryDirectory(prefix="omega-symbolic-") as temporary:
        temporary_root = Path(temporary)
        clips = {}
        for role, source in (("mix", mix), ("vocals", vocals), ("bass", bass), ("drums", drums)):
            target = temporary_root / f"{role}.wav"
            _clip_audio(ffmpeg, source, target, start, duration)
            clips[role] = target
        instrument_clips: dict[str, Path] = {}
        for label, source in sorted(instrument_sources.items()):
            target = temporary_root / f"instrument-{_safe_instrument_label(label)}.wav"
            _clip_audio(ffmpeg, source, target, start, duration)
            instrument_clips[label] = target

        detected_bpm, grid_origin, beat_times = estimate_timing(clips["drums"], bpm, duration)
        timing_grid = build_timing_grid(beat_times, duration, detected_bpm)
        model = Model(ICASSP_2022_MODEL_PATH)
        lead_notes = _transcribe_pitched(
            clips["vocals"],
            model=model,
            role="lead",
            bpm=detected_bpm,
            duration=duration,
            grid_origin=grid_origin,
            timing_grid=timing_grid,
        )
        bass_notes = _transcribe_pitched(
            clips["bass"],
            model=model,
            role="bass",
            bpm=detected_bpm,
            duration=duration,
            grid_origin=grid_origin,
            timing_grid=timing_grid,
        )
        drum_hits = _analyse_drums(
            clips["drums"],
            bpm=detected_bpm,
            duration=duration,
            grid_origin=grid_origin,
            timing_grid=timing_grid,
        )
        chords, key = infer_chords(
            clips["mix"],
            bpm=detected_bpm,
            duration=duration,
            grid_origin=grid_origin,
            beat_times=beat_times,
        )
        harmony = _harmony_notes(
            chords,
            bpm=detected_bpm,
            grid_origin=grid_origin,
            timing_grid=timing_grid,
        )
        recovered = []
        if instrument_clips:
            source_hashes = {label: _sha256(source) for label, source in instrument_sources.items()}
            inventory = discover_instrument_inventory(
                instrument_clips,
                source_offset=start,
                duration=duration,
                source_hashes=source_hashes,
            )
            recovered = transcribe_discovered_instruments(
                instrument_clips,
                inventory,
                model=model,
                bpm=detected_bpm,
                duration=duration,
                grid_origin=grid_origin,
                timing_grid=timing_grid,
            )
        arrangement = SymbolicArrangement(
            schema_version=2 if inventory else 1,
            duration=round(duration, 6),
            bpm=detected_bpm,
            grid_origin=grid_origin,
            key=key,
            source_offset=round(start, 6),
            source=SourceProvenance(
                separator=separator,
                mix_sha256=_sha256(mix),
                vocals_sha256=_sha256(vocals),
                bass_sha256=_sha256(bass),
                drums_sha256=_sha256(drums),
                other_sha256=(
                    _sha256(instrument_sources["other"])
                    if "other" in instrument_sources
                    else "unavailable"
                ),
                instrument_sha256=inventory.sources if inventory else (),
            ),
            notes=tuple(
                sorted((*lead_notes, *bass_notes, *harmony, *recovered), key=lambda note: (note.start, note.role))
            ),
            drums=tuple(drum_hits),
            chords=tuple(chords),
            timing_grid=timing_grid,
        )
        if apply_cleanup:
            arrangement = musical_cleanup(arrangement, style=cleanup_style)

    if inventory is not None:
        save_instrument_inventory(inventory, output / "instrument-inventory.json")
        save_instrument_extracts(
            inventory,
            instrument_sources,
            output / "instrument-extracts",
            ffmpeg=ffmpeg,
        )
    if analysis_only:
        return save_arrangement(arrangement, output / "arrangement.json")
    return render_diagnostic(arrangement=arrangement, output=output, soundfont=soundfont)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a transcription-versus-rendering diagnostic")
    parser.add_argument("--mix", type=Path)
    parser.add_argument("--vocals", type=Path)
    parser.add_argument("--bass", type=Path)
    parser.add_argument("--drums", type=Path)
    parser.add_argument(
        "--instrument-stem",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="repeat for separated stems whose instruments would otherwise be discarded",
    )
    parser.add_argument("--arrangement", type=Path, help="render an existing editable arrangement without ML")
    parser.add_argument("--musical-cleanup", action="store_true", help="apply the selected score cleanup policy")
    parser.add_argument("--cleanup-style", choices=("preserve", "standard-backbeat"), default="preserve",
                        help="with --musical-cleanup: preserve source timing/pitches, or explicitly regularize the score")
    parser.add_argument("--analysis-only", action="store_true", help="write the arrangement without rendering audio")
    parser.add_argument(
        "--omega-review",
        action="store_true",
        help="render only the current Omega Chip comparisons for faster iteration",
    )
    synth_group = parser.add_mutually_exclusive_group()
    synth_group.add_argument("--synth-candidate", type=Path, help="isolated synth candidate to fingerprint")
    synth_group.add_argument("--synth-fingerprint", type=Path, help="reuse a saved synth fingerprint")
    parser.add_argument("--source-wavetable", type=Path, help="private source-derived .npy wavetable")
    parser.add_argument(
        "--voice-fingerprint",
        action="append",
        default=[],
        metavar="ROLE=PATH",
        help="repeat to shape bass or recovered archetypes from source analysis",
    )
    parser.add_argument("--synth-start", type=float, default=0.0)
    parser.add_argument("--separator-label", default="unspecified")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--bpm", type=float, help="tempo override; by default it is inferred from the drum stem")
    parser.add_argument("--soundfont", type=Path, default=Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"))
    args = parser.parse_args()
    if args.cleanup_style != "preserve" and not args.musical_cleanup:
        parser.error("--cleanup-style requires --musical-cleanup")
    instrument_stems: dict[str, Path] = {}
    for specification in args.instrument_stem:
        if "=" not in specification:
            parser.error("--instrument-stem must use LABEL=PATH")
        label, raw_path = specification.split("=", 1)
        label = label.strip()
        if not label or label in instrument_stems:
            parser.error("--instrument-stem labels must be non-empty and unique")
        instrument_stems[label] = Path(raw_path)
    voice_fingerprints: dict[str, SynthFingerprint] = {}
    for specification in args.voice_fingerprint:
        if "=" not in specification:
            parser.error("--voice-fingerprint must use ROLE=PATH")
        role, raw_path = specification.split("=", 1)
        role = role.strip()
        if not role or role in voice_fingerprints:
            parser.error("--voice-fingerprint roles must be non-empty and unique")
        voice_fingerprints[role] = load_synth_fingerprint(Path(raw_path))
    if args.analysis_only and args.arrangement and not instrument_stems:
        parser.error("--analysis-only with --arrangement requires at least one --instrument-stem")
    if args.omega_review and not args.arrangement:
        parser.error("--omega-review requires --arrangement")
    if voice_fingerprints and not args.arrangement:
        parser.error("--voice-fingerprint requires --arrangement")
    if args.omega_review and args.analysis_only:
        parser.error("--omega-review cannot be combined with --analysis-only")
    if args.source_wavetable and not args.synth_fingerprint:
        parser.error("--source-wavetable requires --synth-fingerprint")
    if args.arrangement:
        arrangement = load_arrangement(args.arrangement)
        if instrument_stems:
            arrangement = enrich_arrangement_with_instruments(
                arrangement,
                instrument_stems,
                output=args.output,
                apply_cleanup=args.musical_cleanup,
                cleanup_style=args.cleanup_style,
            )
        elif args.musical_cleanup:
            arrangement = musical_cleanup(arrangement, style=args.cleanup_style)
        if args.analysis_only:
            print(args.output / "arrangement.json")
            return 0
        fingerprint = None
        wavetable = None
        if args.synth_candidate:
            fingerprint, wavetable = extract_synth_fingerprint(
                args.synth_candidate,
                start=max(0.0, args.synth_start),
                duration=arrangement.duration,
            )
        elif args.synth_fingerprint:
            fingerprint = load_synth_fingerprint(args.synth_fingerprint)
            if args.source_wavetable:
                wavetable = np.load(args.source_wavetable)
        if args.omega_review:
            result = render_omega_review(
                arrangement=arrangement,
                output=args.output,
                synth_fingerprint=fingerprint,
                source_wavetable=wavetable,
                voice_fingerprints=voice_fingerprints,
            )
        else:
            result = render_diagnostic(
                arrangement=arrangement,
                output=args.output,
                soundfont=args.soundfont,
                synth_fingerprint=fingerprint,
                source_wavetable=wavetable,
                voice_fingerprints=voice_fingerprints,
            )
    else:
        if args.synth_candidate or args.synth_fingerprint or args.source_wavetable:
            parser.error("synth fingerprint rendering currently requires --arrangement")
        missing = [name for name in ("mix", "vocals", "bass", "drums") if getattr(args, name) is None]
        if missing:
            parser.error("transcription requires " + ", ".join(f"--{name}" for name in missing))
        bpm = None if args.bpm is None else max(30.0, min(240.0, args.bpm))
        result = build_diagnostic(
            mix=args.mix,
            vocals=args.vocals,
            bass=args.bass,
            drums=args.drums,
            output=args.output,
            start=max(0.0, args.start),
            duration=max(1.0, args.duration),
            bpm=bpm,
            soundfont=args.soundfont,
            separator=args.separator_label,
            apply_cleanup=args.musical_cleanup,
            cleanup_style=args.cleanup_style,
            analysis_only=args.analysis_only,
            instrument_stems=instrument_stems,
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
