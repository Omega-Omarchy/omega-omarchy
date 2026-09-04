"""Deterministic offline rendering of tiered music and sound effects.

This module is intentionally excluded from browser staging. Runtime code only
needs ``audio.py`` and the generated JSON/Ogg files.
"""

from __future__ import annotations

from array import array
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
import wave
from typing import Any


BUILD_VERSION = "omega-audio-render/7"
TIERS = ("sixteen-bit", "high", "ultra")
TIER_FILTERS = {
    "ultra": "aresample=44100,alimiter=limit=0.95",
    "high": (
        "aresample=32000,lowpass=f=14000,"
        "stereotools=mlev=1.0:slev=0.72,"
        "acompressor=threshold=0.20:ratio=1.8:attack=12:release=120,"
        "volume=1.12,alimiter=limit=0.93"
    ),
    "sixteen-bit": (
        "aresample=22050,lowpass=f=9800,"
        "stereotools=mlev=1.0:slev=0.42,"
        "acompressor=threshold=0.18:ratio=2.4:attack=8:release=95,"
        "acrusher=bits=12:mode=lin:aa=0.85:samples=1:mix=0.16,"
        "aecho=0.82:0.88:37:0.08,volume=1.55,alimiter=limit=0.91"
    ),
}
TIER_QUALITY = {"sixteen-bit": "4", "high": "5", "ultra": "7"}
_CUE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _oscillator(
    frequency: float,
    seconds: float,
    *,
    volume: float,
    sample_rate: int = 48_000,
    waveform: str = "triangle",
    attack: float = 0.008,
) -> list[int]:
    count = max(1, round(seconds * sample_rate))
    period = sample_rate * 1000
    frequency_millihertz = round(frequency * 1000)
    attack_samples = max(1, round(attack * sample_rate))
    result: list[int] = []
    for index in range(count):
        phase = (index * frequency_millihertz) % period
        if waveform == "square":
            value = 32767 if phase < period // 2 else -32767
        else:
            quarter = phase * 4
            if quarter < period:
                value = quarter * 32767 // period
            elif quarter < 2 * period:
                value = (2 * period - quarter) * 32767 // period
            elif quarter < 3 * period:
                value = -(quarter - 2 * period) * 32767 // period
            else:
                value = -(4 * period - quarter) * 32767 // period
        fade_in = min(32767, index * 32767 // attack_samples)
        remaining = count - 1 - index
        fade_out = max(0, remaining * 32767 // max(1, count - 1))
        envelope = min(fade_in, fade_out)
        result.append(value * envelope * round(volume * 32767) // (32767 * 32767))
    return result


def _sweep(
    start: float,
    end: float,
    seconds: float,
    *,
    volume: float,
    sample_rate: int = 48_000,
) -> list[int]:
    count = max(1, round(seconds * sample_rate))
    phase = 0
    period_scale = sample_rate * 1000
    output: list[int] = []
    for index in range(count):
        frequency = round((start + (end - start) * index / max(1, count - 1)) * 1000)
        phase = (phase + frequency) % period_scale
        quarter = phase * 4
        if quarter < period_scale:
            value = quarter * 32767 // period_scale
        elif quarter < 2 * period_scale:
            value = (2 * period_scale - quarter) * 32767 // period_scale
        elif quarter < 3 * period_scale:
            value = -(quarter - 2 * period_scale) * 32767 // period_scale
        else:
            value = -(4 * period_scale - quarter) * 32767 // period_scale
        remaining = count - 1 - index
        envelope = remaining * remaining * 32767 // max(1, (count - 1) ** 2)
        output.append(value * envelope * round(volume * 32767) // (32767 * 32767))
    return output


def _noise(seconds: float, *, volume: float, sample_rate: int = 48_000) -> list[int]:
    count = max(1, round(seconds * sample_rate))
    state = 0x4F4D4547
    output = []
    for index in range(count):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        raw = ((state >> 16) & 0xFFFF) - 32768
        remaining = count - 1 - index
        envelope = remaining * remaining * 32767 // max(1, (count - 1) ** 2)
        output.append(raw * envelope * round(volume * 32767) // (32767 * 32767))
    return output


def _mix(*layers: tuple[list[int], int]) -> list[int]:
    length = max((offset + len(samples) for samples, offset in layers), default=1)
    result = [0] * length
    for samples, offset in layers:
        for index, sample in enumerate(samples):
            result[index + offset] += sample
    return [max(-32767, min(32767, sample)) for sample in result]


def _stereo(samples: list[int], *, width: float = 0.18, delay: int = 73) -> array:
    pcm = array("h")
    side = round(max(0.0, min(0.45, width)) * 1000)
    for index, sample in enumerate(samples):
        delayed = samples[index - delay] if index >= delay else 0
        left = sample + (sample - delayed) * side // 1000
        right = sample - (sample - delayed) * side // 1000
        pcm.extend((max(-32767, min(32767, left)), max(-32767, min(32767, right))))
    return pcm


def _write_wav(path: Path, samples: list[int], *, width: float = 0.18) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(48_000)
        target.writeframes(_stereo(samples, width=width).tobytes())


def _emit_sfx_masters(source_root: Path) -> None:
    sr = 48_000
    ms = lambda value: round(sr * value / 1000)
    masters = {
        "ui": _mix((_oscillator(720, 0.060, volume=0.20, waveform="square"), 0)),
        "logo": _mix(
            (_oscillator(392, 0.46, volume=0.16), 0),
            (_oscillator(523.25, 0.38, volume=0.14), ms(55)),
            (_oscillator(659.25, 0.30, volume=0.12), ms(115)),
        ),
        "jump": _mix(
            (_sweep(270, 620, 0.19, volume=0.22), 0),
            (_oscillator(880, 0.08, volume=0.07, waveform="square"), ms(70)),
        ),
        "collect": _mix(
            (_oscillator(880, 0.18, volume=0.15), 0),
            (_oscillator(1174.66, 0.15, volume=0.13), ms(55)),
            (_oscillator(1567.98, 0.13, volume=0.11), ms(105)),
        ),
        "convert": _mix(
            (_sweep(170, 440, 0.52, volume=0.18), 0),
            (_oscillator(392, 0.35, volume=0.10), ms(120)),
            (_oscillator(587.33, 0.24, volume=0.09), ms(245)),
        ),
        "hit": _mix(
            (_noise(0.20, volume=0.20), 0),
            (_sweep(125, 58, 0.25, volume=0.25), 0),
        ),
        "bomb": _mix(
            (_sweep(740, 190, 0.34, volume=0.18), 0),
            (_noise(0.30, volume=0.12), ms(55)),
            (_oscillator(92, 0.38, volume=0.20, waveform="square"), ms(90)),
        ),
    }
    widths = {"hit": 0.08, "bomb": 0.28, "convert": 0.26, "logo": 0.30}
    for cue, samples in masters.items():
        _write_wav(source_root / "sfx" / cue / "master.wav", samples, width=widths.get(cue, 0.16))


def _run(command: list[str]) -> None:
    process = subprocess.run(command, check=False, capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or "ffmpeg audio render failed")


def _ogg_args(ffmpeg: str, source: Path, target: Path) -> list[str]:
    return [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map_metadata",
        "-1",
        "-fflags",
        "+bitexact",
        "-flags:a",
        "+bitexact",
    ]


def _render_sfx(ffmpeg: str, source: Path, target: Path, tier: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = _ogg_args(ffmpeg, source, target)
    command += ["-af", TIER_FILTERS[tier], "-codec:a", "libvorbis", "-q:a", TIER_QUALITY[tier], str(target)]
    _run(command)


def _render_music(
    ffmpeg: str,
    source: Path,
    target: Path,
    tier: str,
    *,
    start: float,
    end: float,
    crossfade: float,
    loop: bool,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    start = max(0.0, start)
    if loop:
        end = max(start + crossfade * 3, end)
        middle_start = start + crossfade
        middle_end = end - crossfade
        graph = (
            f"[0:a]atrim=start={middle_start:.6f}:end={middle_end:.6f},asetpts=PTS-STARTPTS[mid];"
            f"[0:a]atrim=start={middle_end:.6f}:end={end:.6f},asetpts=PTS-STARTPTS,"
            f"afade=t=out:st=0:d={crossfade:.6f}[tail];"
            f"[0:a]atrim=start={start:.6f}:end={middle_start:.6f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={crossfade:.6f}[head];"
            f"[tail][head]amix=inputs=2:duration=first:normalize=0,asetpts=PTS-STARTPTS[cross];"
            f"[mid][cross]concat=n=2:v=0:a=1,{TIER_FILTERS[tier]}[out]"
        )
    else:
        end = max(start + 0.001, end)
        graph = (
            f"[0:a]atrim=start={start:.6f}:end={end:.6f},"
            f"asetpts=PTS-STARTPTS,{TIER_FILTERS[tier]}[out]"
        )
    command = _ogg_args(ffmpeg, source, target)
    command += [
        "-filter_complex",
        graph,
        "-map",
        "[out]",
        "-codec:a",
        "libvorbis",
        "-q:a",
        TIER_QUALITY[tier],
        str(target),
    ]
    _run(command)


def _probe_duration(ffprobe: str, path: Path) -> float:
    process = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or f"could not probe {path}")
    return round(float(process.stdout.strip()), 6)


def _probe_levels(ffmpeg: str, path: Path) -> dict[str, float]:
    process = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-i",
            str(path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or f"could not measure {path}")
    mean = re.findall(r"mean_volume:\s*(-?[0-9.]+) dB", process.stderr)
    peak = re.findall(r"max_volume:\s*(-?[0-9.]+) dB", process.stderr)
    if not mean or not peak:
        raise RuntimeError(f"ffmpeg did not report audio levels for {path}")
    return {"meanDbfs": float(mean[-1]), "peakDbfs": float(peak[-1])}


def _build_digest(source_manifest: Path, source_files: list[Path]) -> str:
    digest = hashlib.sha256(BUILD_VERSION.encode("utf-8"))
    digest.update(source_manifest.read_bytes())
    for source in sorted(source_files):
        digest.update(source.relative_to(source_manifest.parent).as_posix().encode("utf-8"))
        digest.update(bytes.fromhex(_sha256(source)))
    return f"sha256:{digest.hexdigest()}"


def _validate_config(config: dict[str, Any], source_root: Path) -> None:
    if config.get("schema_version") != 1:
        raise RuntimeError("unsupported audio source-manifest schema")
    master = config.get("master")
    if not isinstance(master, dict) or not isinstance(master.get("file"), str):
        raise RuntimeError("audio source manifest is missing its master")
    relative_master = Path(master["file"])
    if relative_master.is_absolute() or ".." in relative_master.parts:
        raise RuntimeError("audio master path must stay within assets/source/audio")
    try:
        (source_root / relative_master).resolve().relative_to(source_root.resolve())
    except ValueError as exc:
        raise RuntimeError("audio master path escapes assets/source/audio") from exc
    music = config.get("music")
    sfx = config.get("sfx")
    scenes = config.get("scene_music")
    if not isinstance(music, list) or not isinstance(sfx, list) or not isinstance(scenes, dict):
        raise RuntimeError("audio source manifest is missing cue tables")
    known: set[str] = set()
    music_ids: set[str] = set()
    for kind, entries in (("music", music), ("sfx", sfx)):
        for cue in entries:
            if not isinstance(cue, dict):
                raise RuntimeError(f"{kind} cue must be a table")
            cue_id = str(cue.get("id") or "")
            if not _CUE_ID.fullmatch(cue_id) or cue_id in known:
                raise RuntimeError(f"invalid or duplicate audio cue id: {cue_id!r}")
            known.add(cue_id)
            if kind == "music":
                music_ids.add(cue_id)
                start = float(cue.get("start", -1))
                end = float(cue.get("end", -1))
                loop = bool(cue.get("loop", True))
                crossfade = float(cue.get("crossfade", 0))
                if start < 0 or end <= start:
                    raise RuntimeError(f"invalid range for audio cue {cue_id}")
                if loop and (crossfade <= 0 or end <= start + crossfade * 3):
                    raise RuntimeError(f"invalid loop range for audio cue {cue_id}")
            elif str(cue.get("bus") or "") not in {"sfx", "ui"}:
                raise RuntimeError(f"invalid bus for audio cue {cue_id}")
    unknown_scenes = sorted({str(value) for value in scenes.values()} - music_ids)
    if unknown_scenes:
        raise RuntimeError(f"scene music references unknown cues: {unknown_scenes}")


def build_audio_assets(asset_root: Path, *, force: bool = False) -> Path:
    """Render all runtime tiers directly from source masters."""

    asset_root = Path(asset_root)
    source_root = asset_root / "source" / "audio"
    source_manifest = source_root / "audio-manifest.toml"
    if not source_manifest.is_file():
        raise RuntimeError(f"audio source manifest is missing: {source_manifest}")
    config = tomllib.loads(source_manifest.read_text(encoding="utf-8"))
    _validate_config(config, source_root)
    _emit_sfx_masters(source_root)
    music_master = source_root / str(config["master"]["file"])
    if not music_master.is_file():
        raise RuntimeError(f"audio music master is missing: {music_master}")
    expected_master_digest = str(config["master"].get("decoded_master_sha256") or "")
    actual_master_digest = _sha256(music_master)
    if expected_master_digest and actual_master_digest != expected_master_digest:
        raise RuntimeError("decoded audio master does not match its provenance digest")
    source_files = [music_master]
    for cue in config["sfx"]:
        source_files.append(source_root / "sfx" / str(cue["id"]) / "master.wav")
    build_digest = _build_digest(source_manifest, source_files)
    runtime_root = asset_root / "audio"
    runtime_manifest = runtime_root / "audio-manifest.json"
    expected = [
        runtime_root / tier / kind / f"{cue['id']}.ogg"
        for tier in TIERS
        for kind, cues in (("music", config["music"]), ("sfx", config["sfx"]))
        for cue in cues
    ]
    expected_set = {path.resolve() for path in expected}
    for tier in TIERS:
        for kind in ("music", "sfx"):
            directory = runtime_root / tier / kind
            if not directory.is_dir():
                continue
            for stale in directory.glob("*.ogg"):
                if stale.resolve() not in expected_set:
                    stale.unlink()
    if not force and runtime_manifest.is_file() and all(path.is_file() for path in expected):
        try:
            prior = json.loads(runtime_manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prior = {}
        if prior.get("buildDigest") == build_digest:
            return runtime_manifest

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe are required to render audio assets")

    cues: dict[str, dict[str, Any]] = {}
    for source_cue in config["sfx"]:
        cue_id = str(source_cue["id"])
        source = source_root / "sfx" / cue_id / "master.wav"
        paths = {}
        levels = {}
        for tier in TIERS:
            target = runtime_root / tier / "sfx" / f"{cue_id}.ogg"
            _render_sfx(ffmpeg, source, target, tier)
            paths[tier] = target.relative_to(runtime_root).as_posix()
            levels[tier] = _probe_levels(ffmpeg, target)
        cues[cue_id] = {
            "kind": "sfx",
            "bus": str(source_cue["bus"]),
            "caption": str(source_cue["caption"]),
            "gain": float(source_cue["gain"]),
            "priority": int(source_cue["priority"]),
            "maxVoices": int(source_cue["max_voices"]),
            "files": paths,
            "levels": levels,
            "sourceDigest": f"sha256:{_sha256(source)}",
        }

    for source_cue in config["music"]:
        cue_id = str(source_cue["id"])
        paths = {}
        durations = {}
        levels = {}
        for tier in TIERS:
            target = runtime_root / tier / "music" / f"{cue_id}.ogg"
            _render_music(
                ffmpeg,
                music_master,
                target,
                tier,
                start=float(source_cue["start"]),
                end=float(source_cue["end"]),
                crossfade=float(source_cue.get("crossfade", 0.0)),
                loop=bool(source_cue.get("loop", True)),
            )
            paths[tier] = target.relative_to(runtime_root).as_posix()
            durations[tier] = _probe_duration(ffprobe, target)
            levels[tier] = _probe_levels(ffmpeg, target)
        cues[cue_id] = {
            "kind": "music",
            "bus": str(source_cue["bus"]),
            "caption": str(source_cue["caption"]),
            "gain": float(source_cue["gain"]),
            "loop": bool(source_cue.get("loop", True)),
            "files": paths,
            "durations": durations,
            "levels": levels,
            "sourceDigest": f"sha256:{_sha256(music_master)}",
        }

    output = {
        "schemaVersion": 1,
        "buildVersion": BUILD_VERSION,
        "buildDigest": build_digest,
        "tiers": list(TIERS),
        "defaultFidelity": "ultra",
        "cues": cues,
        "sceneMusic": dict(config["scene_music"]),
        "rights": {
            "provenance": str(config["master"]["provenance"]),
            "publicRedistribution": str(config["master"]["rights"]),
        },
    }
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_manifest.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return runtime_manifest


def main() -> int:
    root = Path(__file__).resolve().parents[2] / "assets"
    manifest = build_audio_assets(root, force=True)
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
