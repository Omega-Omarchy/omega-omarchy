"""Tier-independent settings and the semantic runtime audio mixer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pygame

from .runtime_assets import asset_dir


AUDIO_FIDELITIES = ("sixteen-bit", "high", "ultra")
AUDIO_SETTING_ROWS = (
    "quality",
    "master",
    "music",
    "effects",
    "ui",
    "mute",
    "captions",
    "back",
)
DEFAULT_AUDIO = {
    "masterVolume": 0.80,
    "musicVolume": 0.65,
    "effectsVolume": 0.80,
    "uiVolume": 0.75,
    "muted": False,
    "captions": False,
}
AUDIO_CAPTIONS = {
    "ui": "Menu selection",
    "logo": "Omega signal",
    "jump": "Jump",
    "collect": "Item collected",
    "convert": "Opponent converted",
    "hit": "Impact",
    "bomb": "Logic Bomb thrown",
}


def cycle_audio_fidelity(current: str, delta: int) -> str:
    if current not in AUDIO_FIDELITIES:
        current = "ultra"
    return AUDIO_FIDELITIES[(AUDIO_FIDELITIES.index(current) + delta) % len(AUDIO_FIDELITIES)]


def normalize_audio_settings(
    settings: Mapping[str, Any] | None,
    *,
    legacy_fidelity: str | None = None,
) -> dict[str, Any]:
    """Return settings with bounded audio values and one-time legacy migration.

    Old saves inherit their visual fidelity once. Once ``audioFidelity`` exists,
    subsequent visual changes cannot alter the sound selection.
    """

    normalized = dict(settings or {})
    audio_fidelity = str(normalized.get("audioFidelity") or legacy_fidelity or "ultra")
    if audio_fidelity not in AUDIO_FIDELITIES:
        audio_fidelity = legacy_fidelity if legacy_fidelity in AUDIO_FIDELITIES else "ultra"
    normalized["audioFidelity"] = audio_fidelity
    provided = normalized.get("audio")
    audio = dict(provided) if isinstance(provided, Mapping) else {}
    for key, default in DEFAULT_AUDIO.items():
        value = audio.get(key, default)
        if key in {"muted", "captions"}:
            audio[key] = bool(value)
        else:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = float(default)
            audio[key] = round(max(0.0, min(1.0, numeric)), 2)
    normalized["audio"] = audio
    return normalized


class AudioManager:
    """Resolve semantic cues into the selected tier without touching gameplay.

    Music is streamed through pygame's music channel, keeping the four-minute
    Ultra track out of decoded RAM. Effects are small and loaded per tier.
    Every public method fails closed when a host has no audio device.
    """

    def __init__(
        self,
        root: Path | None = None,
        *,
        browser: bool = False,
        enabled: bool = True,
    ) -> None:
        self.root = Path(root) if root is not None else asset_dir() / "audio"
        self.browser = browser
        self.unlocked = not browser
        self.available = False
        self.manifest: dict[str, Any] = {}
        self.fidelity = "ultra"
        self.settings = normalize_audio_settings({})
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.active: dict[str, list[pygame.mixer.Channel]] = {}
        self.music_cue = ""
        self.music_path: Path | None = None
        self.music_start_offset = 0.0
        self.error = ""
        try:
            self.manifest = json.loads((self.root / "audio-manifest.json").read_text(encoding="utf-8"))
            if enabled:
                if pygame.mixer.get_init() is None:
                    pygame.mixer.init(frequency=44_100, size=-16, channels=2, buffer=768)
                self.available = pygame.mixer.get_init() is not None
        except (OSError, ValueError, pygame.error) as exc:
            self.error = str(exc)
            self.available = False

    def unlock(self) -> None:
        """Allow playback after a browser/user gesture."""

        self.unlocked = True

    def _cue(self, cue_id: str) -> dict[str, Any] | None:
        cues = self.manifest.get("cues")
        if not isinstance(cues, dict):
            return None
        cue = cues.get(cue_id)
        return cue if isinstance(cue, dict) else None

    def cue_path(self, cue_id: str, fidelity: str | None = None) -> Path | None:
        cue = self._cue(cue_id)
        if cue is None:
            return None
        files = cue.get("files")
        if not isinstance(files, dict):
            return None
        tier = fidelity if fidelity in AUDIO_FIDELITIES else self.fidelity
        candidates = (files.get(tier), files.get("ultra"), files.get("high"), files.get("sixteen-bit"))
        for relative in dict.fromkeys(candidates):
            if not isinstance(relative, str):
                continue
            path = self.root / relative
            if path.is_file():
                return path
        return None

    def apply_settings(self, settings: Mapping[str, Any]) -> None:
        normalized = normalize_audio_settings(settings)
        next_fidelity = str(normalized["audioFidelity"])
        changed = next_fidelity != self.fidelity
        self.settings = normalized
        self.fidelity = next_fidelity
        if changed:
            self.sounds.clear()
            if self.music_cue:
                self._play_music(self.music_cue, preserve_position=True)
        self._apply_music_volume()

    def _bus_volume(self, bus: str) -> float:
        audio = self.settings["audio"]
        if audio["muted"]:
            return 0.0
        bus_key = {"music": "musicVolume", "ui": "uiVolume"}.get(bus, "effectsVolume")
        return float(audio["masterVolume"]) * float(audio[bus_key])

    def _apply_music_volume(self) -> None:
        if not self.available:
            return
        cue = self._cue(self.music_cue) or {}
        try:
            pygame.mixer.music.set_volume(
                max(0.0, min(1.0, self._bus_volume("music") * float(cue.get("gain", 1.0))))
            )
        except pygame.error:
            self.available = False

    def _sound(self, cue_id: str) -> pygame.mixer.Sound | None:
        if cue_id in self.sounds:
            return self.sounds[cue_id]
        path = self.cue_path(cue_id)
        if path is None:
            return None
        try:
            sound = pygame.mixer.Sound(str(path))
        except pygame.error:
            return None
        self.sounds[cue_id] = sound
        return sound

    def play(self, cue_id: str) -> bool:
        if not self.available or not self.unlocked or bool(self.settings["audio"]["muted"]):
            return False
        cue = self._cue(cue_id)
        if cue is None or cue.get("kind") != "sfx":
            return False
        active = [channel for channel in self.active.get(cue_id, []) if channel.get_busy()]
        self.active[cue_id] = active
        if len(active) >= int(cue.get("maxVoices", 1)):
            return False
        sound = self._sound(cue_id)
        if sound is None:
            return False
        sound.set_volume(
            max(0.0, min(1.0, self._bus_volume(str(cue.get("bus") or "sfx")) * float(cue.get("gain", 1.0))))
        )
        channel = sound.play()
        if channel is None:
            return False
        active.append(channel)
        return True

    def _play_music(self, cue_id: str, *, preserve_position: bool = False) -> bool:
        if not self.available or not self.unlocked:
            return False
        path = self.cue_path(cue_id)
        cue = self._cue(cue_id)
        if path is None or cue is None or cue.get("kind") != "music":
            return False
        position = 0.0
        if preserve_position:
            try:
                position = max(
                    0.0,
                    self.music_start_offset + pygame.mixer.music.get_pos() / 1000.0,
                )
            except pygame.error:
                position = 0.0
        try:
            pygame.mixer.music.load(str(path))
            kwargs: dict[str, Any] = {
                "loops": -1 if bool(cue.get("loop", True)) else 0,
                "fade_ms": 260,
            }
            durations = cue.get("durations") or {}
            duration = float(durations.get(self.fidelity, 0.0)) if isinstance(durations, dict) else 0.0
            if preserve_position and position > 0.05 and duration > 0.2:
                kwargs["start"] = position % duration
            try:
                pygame.mixer.music.play(**kwargs)
            except (TypeError, pygame.error):
                kwargs.pop("start", None)
                pygame.mixer.music.play(**kwargs)
            self.music_start_offset = float(kwargs.get("start", 0.0))
            self.music_cue = cue_id
            self.music_path = path
            self._apply_music_volume()
            return True
        except pygame.error as exc:
            self.error = str(exc)
            return False

    def _desired_music(self, scene: str, *, in_combat: bool) -> str | None:
        if scene in {"pause", "audio-settings", "items", "remap", "customize", "boss-defeat"}:
            if self.music_cue == "credits-roll":
                return None
            return self.music_cue or None
        table = self.manifest.get("sceneMusic")
        if isinstance(table, dict):
            value = table.get(scene)
            if isinstance(value, str):
                return value
        return None

    def _stop_music(self) -> None:
        if self.available and self.unlocked:
            try:
                pygame.mixer.music.fadeout(260)
            except pygame.error:
                pass
        self.music_cue = ""
        self.music_path = None
        self.music_start_offset = 0.0

    def update(
        self,
        *,
        scene: str,
        in_combat: bool,
        settings: Mapping[str, Any],
        cues: list[str] | tuple[str, ...] = (),
    ) -> None:
        self.apply_settings(settings)
        desired = self._desired_music(scene, in_combat=in_combat)
        if desired is None and self.music_cue:
            self._stop_music()
        elif desired is not None and desired != self.music_cue and self.unlocked:
            if not self._play_music(desired):
                # Record the silent choice so a bad/missing stream does not
                # trigger an exception and filesystem probe every frame.
                self.music_cue = desired
        for cue_id in cues:
            self.play(str(cue_id))

    def shutdown(self) -> None:
        if not self.available:
            return
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
