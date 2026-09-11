"""Local vocal-reintegration experiments for Omega Chip review renders."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import shutil

import numpy as np

from .guided_music import _load_audio, _region_envelope, _write_pcm
from .music_diagnostic import OUTPUT_RATE, _encode_review


@dataclass(frozen=True)
class VocalMixProfile:
    name: str
    source: str
    gain: float
    duck_depth: float
    sample_rate: int | None = None
    bits: int | None = None
    drive: float = 1.0


VOCAL_MIX_PROFILES = {
    "natural-vocal": VocalMixProfile("natural-vocal", "demucs", 0.72, 0.10),
    "omega-polished-vocal": VocalMixProfile(
        "omega-polished-vocal", "demucs", 0.82, 0.13, 24_000, 12, 1.10
    ),
    "omega-sampled-vocal": VocalMixProfile(
        "omega-sampled-vocal", "demucs", 0.80, 0.13, 18_000, 10, 1.18
    ),
    "roformer-consensus-vocal": VocalMixProfile(
        "roformer-consensus-vocal", "roformer", 0.66, 0.11
    ),
    "vocal-forward": VocalMixProfile("vocal-forward", "demucs", 0.96, 0.18),
}


def vocal_activity_envelope(guide: np.ndarray) -> np.ndarray:
    """Build a forgiving activity gate from an independent vocal estimate."""

    try:
        import librosa
        from scipy.ndimage import gaussian_filter1d, maximum_filter1d
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa and scipy are required for vocal reintegration") from exc

    mono = np.mean(guide, axis=0)
    hop = 256
    rms = librosa.feature.rms(y=mono, frame_length=2_048, hop_length=hop)[0]
    db = 20.0 * np.log10(np.maximum(rms, 1e-8))
    noise = float(np.percentile(db, 18))
    active = float(np.percentile(db, 72))
    lower = noise + 2.5
    upper = max(lower + 4.0, active - 1.5)
    normalized = np.clip((db - lower) / (upper - lower), 0.0, 1.0)
    smooth = normalized * normalized * (3.0 - 2.0 * normalized)
    # Preserve consonants and phrase tails: expand activity before smoothing it.
    smooth = maximum_filter1d(smooth, size=17, mode="nearest")
    smooth = gaussian_filter1d(smooth, sigma=3.0, mode="nearest")
    positions = np.arange(guide.shape[1], dtype=np.float64) / hop
    envelope = np.interp(positions, np.arange(smooth.size), smooth)
    return np.clip(envelope, 0.0, 1.0)


def shape_vocal(
    source: np.ndarray,
    *,
    sample_rate: int | None,
    bits: int | None,
    drive: float,
) -> np.ndarray:
    """Remove low-frequency leakage and optionally use a console sample channel."""

    try:
        import librosa
        from scipy.signal import butter, sosfiltfilt
    except ImportError as exc:  # pragma: no cover - local authoring environment
        raise RuntimeError("librosa and scipy are required for vocal reintegration") from exc

    highpass = butter(2, 95.0, btype="highpass", fs=OUTPUT_RATE, output="sos")
    shaped = sosfiltfilt(highpass, source, axis=1)
    if sample_rate is not None:
        reduced = librosa.resample(
            shaped,
            orig_sr=OUTPUT_RATE,
            target_sr=sample_rate,
            axis=-1,
        )
        shaped = librosa.resample(
            reduced,
            orig_sr=sample_rate,
            target_sr=OUTPUT_RATE,
            axis=-1,
        )
        shaped = np.pad(
            shaped,
            ((0, 0), (0, max(0, source.shape[1] - shaped.shape[1]))),
        )[:, : source.shape[1]]
    shaped = np.tanh(shaped * drive) / math.tanh(drive)
    if bits is not None:
        levels = float(2 ** (bits - 1) - 1)
        shaped = np.round(shaped * levels) / levels
    return shaped


def mix_vocal(
    instrumental: np.ndarray,
    vocal: np.ndarray,
    activity: np.ndarray,
    profile: VocalMixProfile,
) -> np.ndarray:
    count = min(instrumental.shape[1], vocal.shape[1], activity.size)
    presence = activity[:count, None]
    bed = instrumental[:, :count].T * (1.0 - presence * profile.duck_depth)
    mixed = bed + vocal[:, :count].T * presence * profile.gain
    # A transparent knee changes only samples that would otherwise overload.
    magnitude = np.abs(mixed)
    threshold = 0.86
    above = magnitude > threshold
    if np.any(above):
        remaining = 1.0 - threshold
        compressed = threshold + remaining * np.tanh(
            (magnitude[above] - threshold) / remaining
        )
        mixed[above] = np.sign(mixed[above]) * compressed
    return mixed


def render_vocal_review(
    *,
    instrumental: Path,
    demucs_vocal: Path,
    roformer_vocal: Path,
    output: Path,
    duration: float,
    vocal_regions: tuple[tuple[float, float], ...] = (),
) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required")
    output.mkdir(parents=True, exist_ok=True)
    bed = _load_audio(instrumental, start=0.0, duration=duration)
    sources = {
        "demucs": _load_audio(demucs_vocal, start=0.0, duration=duration),
        "roformer": _load_audio(roformer_vocal, start=0.0, duration=duration),
    }
    activity = vocal_activity_envelope(sources["demucs"])
    if vocal_regions:
        activity *= _region_envelope(
            activity.size,
            vocal_regions,
            fade_seconds=0.18,
        )
    for index, profile in enumerate(VOCAL_MIX_PROFILES.values(), start=10):
        shaped = shape_vocal(
            sources[profile.source],
            sample_rate=profile.sample_rate,
            bits=profile.bits,
            drive=profile.drive,
        )
        mixed = mix_vocal(bed, shaped, activity, profile)
        wav = output / f"{index:02d}-{profile.name}.wav"
        _write_pcm(wav, mixed)
        _encode_review(ffmpeg, wav, wav.with_suffix(".ogg"))

    manifest = {
        "schemaVersion": 1,
        "approach": "activity-gated-vocal-reintegration",
        "duration": duration,
        "activityGuide": str(demucs_vocal),
        "instrumental": str(instrumental),
        "profiles": {name: asdict(profile) for name, profile in VOCAL_MIX_PROFILES.items()},
        "sources": {"demucs": str(demucs_vocal), "roformer": str(roformer_vocal)},
        "vocalRegions": vocal_regions,
    }
    target = output / "vocal-render-manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Render vocal blends over an Omega Chip bed")
    parser.add_argument("--instrumental", type=Path, required=True)
    parser.add_argument("--demucs-vocal", type=Path, required=True)
    parser.add_argument("--roformer-vocal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=45.0)
    parser.add_argument(
        "--vocal-region",
        action="append",
        default=[],
        metavar="START:END",
        help="Limit vocal activity to an authored arrangement interval.",
    )
    args = parser.parse_args()
    vocal_regions = []
    for specification in args.vocal_region:
        try:
            raw_start, raw_end = specification.split(":", 1)
            region = (float(raw_start), float(raw_end))
        except ValueError:
            parser.error("--vocal-region must use START:END seconds")
        if region[0] < 0.0 or region[1] <= region[0]:
            parser.error("--vocal-region requires 0 <= START < END")
        vocal_regions.append(region)
    result = render_vocal_review(
        instrumental=args.instrumental,
        demucs_vocal=args.demucs_vocal,
        roformer_vocal=args.roformer_vocal,
        output=args.output,
        duration=max(1.0, args.duration),
        vocal_regions=tuple(vocal_regions),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
