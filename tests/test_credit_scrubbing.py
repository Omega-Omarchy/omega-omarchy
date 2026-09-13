import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from omega_omarchy.audio import AudioManager
from omega_omarchy.credits import roll_duration, title_duration
from omega_omarchy.installer import InstallerSession
from omega_omarchy.physics import InputState, spawn_body
from omega_omarchy.sim import GameSim


def credits_sim(cinematic=False):
    sim = GameSim(installer=InstallerSession())
    sim.start_credits(cinematic=cinematic)
    sim.credits_elapsed = 50
    return sim


def test_credit_taps_direction_changes_release_and_acceleration():
    sim = credits_sim()
    sim.step(InputState(up_pressed=True))
    assert sim.credits_elapsed == 49
    sim.step(InputState())
    assert sim.credits_elapsed == pytest.approx(49 + 1 / 60)
    sim.step(InputState(down=True, down_pressed=True))
    assert sim.credits_elapsed == pytest.approx(50 + 1 / 60)
    for _ in range(240):
        sim.step(InputState(down=True))
    before = sim.credits_elapsed
    for _ in range(60):
        sim.step(InputState(down=True))
    assert sim.credits_elapsed - before == pytest.approx(32)
    before = sim.credits_elapsed
    sim.step(InputState(up=True))
    assert sim.credits_elapsed == before - 1
    sim.step(InputState(up=True, down=True))
    assert sim.credits_scrub_direction == 0 and sim.credits_scrub_held == 0


def test_credit_hold_travel_is_independent_of_frame_rate():
    positions = []
    for fps in (15, 30, 60, 120):
        sim = credits_sim()
        for _ in range(fps * 2):
            sim.step(InputState(down=True), frame_seconds=1 / fps)
        positions.append(sim.credits_elapsed)
    assert positions == pytest.approx([positions[0]] * 4)


@pytest.mark.parametrize("cinematic", [False, True])
def test_scrub_endpoints_hold_then_release_and_rewind_does_not_trap_exit(cinematic):
    sim = credits_sim(cinematic)
    duration = title_duration() if cinematic else roll_duration()
    sim.step(InputState(down=True), frame_seconds=60)
    assert sim.credits_elapsed == duration
    assert sim.scene == ("ending" if cinematic else "credits")
    sim.step(InputState())
    assert sim.scene == ("credits" if cinematic else "pause")
    sim = credits_sim(cinematic)
    sim.step(InputState(up=True), frame_seconds=60)
    assert sim.credits_elapsed == 0
    sim.step(InputState(up=True, pause=True))
    assert sim.scene == ("credits" if cinematic else "pause")


def edit_sim():
    tiles = ["." * 100] * 98 + ["....S" + "." * 95, "#" * 100]
    return GameSim(installer=InstallerSession(), scene="edit", editing=True,
                   tiles=tiles, body=spawn_body(tiles), edit_cursor=(5, 50))


def test_edit_taps_are_single_tiles_and_hold_repeats_accelerate_to_a_cap():
    sim = edit_sim()
    sim.step(InputState(up_pressed=True))
    assert sim.edit_cursor == (5, 49)
    for _ in range(17):
        sim.step(InputState(up=True))
    assert sim.edit_cursor == (5, 49)
    # Genuine taps, with release frames, remain precise at any previous speed.
    sim.step(InputState())
    for _ in range(5):
        before = sim.edit_cursor[1]
        sim.step(InputState(down=True, down_pressed=True))
        assert sim.edit_cursor[1] == before + 1
        sim.step(InputState())
    steps = []
    for frame in range(180):
        before = sim.edit_cursor
        sim.step(InputState(up=True))
        if sim.edit_cursor != before:
            steps.append(frame)
    gaps = [b - a for a, b in zip(steps, steps[1:])]
    assert gaps[0] == 18 and gaps[-1] == 3 and min(gaps) == 3
    before = sim.edit_cursor[1]
    sim.step(InputState(down=True))
    assert sim.edit_cursor[1] == before + 1 and sim.edit_hold_ticks == 0
    sim.step(InputState(up=True, down=True))
    assert sim.edit_move_direction == (0, 0)
    sim.step(InputState(pause=True))
    sim.step(InputState(pause=True))
    before = sim.edit_cursor[1]
    sim.step(InputState(down=True))
    assert sim.edit_cursor[1] == before + 1 and sim.edit_hold_ticks == 0


class Music:
    def __init__(self):
        self.seeks, self.loads, self.plays = [], [], []
        self.busy = True
        self.volume = 1
        self.unsupported = False

    def get_busy(self): return self.busy
    def get_pos(self): return 5000 if self.busy else -1
    def set_volume(self, value): self.volume = value
    def load(self, path): self.loads.append(path)
    def stop(self): self.busy = False
    def fadeout(self, ms): self.busy = False
    def play(self, **kwargs):
        self.plays.append(kwargs)
        self.busy = True
    def set_pos(self, seconds):
        self.seeks.append(seconds)
        if self.unsupported:
            raise pygame.error("Seeking unsupported")


@pytest.fixture
def mixer(monkeypatch):
    music = Music()
    monkeypatch.setattr(pygame.mixer, "music", music)
    audio = AudioManager(enabled=False)
    audio.available = audio.unlocked = True
    audio.music_cue = "credits-roll"
    audio.music_path = audio.cue_path("credits-roll")
    return audio, music


def update(audio, position, direction=0, scene="credits", **kwargs):
    audio.update(scene=scene, in_combat=False, settings=kwargs.pop("settings", {}),
                 credit_position=position, credit_scrub_direction=direction, **kwargs)


def test_audible_previews_are_throttled_and_release_seeks_exactly(mixer):
    audio, music = mixer
    for _ in range(60): update(audio, 10)
    assert music.seeks == []  # normal playback incurs no seeking
    update(audio, 20, 1)
    for _ in range(6): update(audio, 21, 1)
    assert music.seeks == [20]
    update(audio, 25, -1)
    assert music.seeks == [20, 25]  # reversal is immediate
    update(audio, 24.123)
    assert music.seeks[-1] == 24.123
    assert audio.music_start_offset == pytest.approx(19.123)
    update(audio, 30, 1, settings={"audio": {"muted": True}})
    assert music.volume == 0 and music.seeks[-1] == 30
    assert music.loads == []


def test_scrub_silent_tail_and_restart_before_it(mixer):
    audio, music = mixer
    update(audio, roll_duration(), 1)
    assert not music.busy
    update(audio, 300, -1)
    assert music.plays[-1]["start"] == 300 and music.loads == []


def test_scrub_released_during_deferred_music_start_keeps_its_position(mixer):
    audio, music = mixer
    audio.music_cue = ""
    update(audio, 40, 1)
    assert audio._credit_seek_pending and music.loads == []
    update(audio, 40.25)
    assert music.seeks[-1] == 40.25 and len(music.loads) == 1


def test_cast_scrub_exchanges_sound_for_one_stream_and_retains_fade(mixer):
    audio, music = mixer
    class Channel:
        stopped = False
        def stop(self): self.stopped = True
        def set_volume(self, value): pass
    channel = Channel()
    audio.music_cue = "credits-theme"
    audio.music_path = audio.cue_path("credits-theme")
    audio._theme_channel = channel
    audio._roll_preloaded = True
    update(audio, 20, 1, scene="ending")
    assert channel.stopped and audio._credit_cast_stream
    assert not audio._roll_preloaded and not audio._need_roll_preload
    assert len(music.loads) == 1 and music.plays[-1]["start"] == 20
    update(audio, title_duration() - 1, scene="ending")
    volume = audio._bus_volume("music") * audio._cue("credits-theme")["gain"]
    assert music.volume == pytest.approx(volume / 2.5)
    update(audio, 30, -1, scene="ending")
    assert music.volume == pytest.approx(volume) and len(music.loads) == 1


def test_unsupported_seek_does_not_crash_or_retry_each_frame(mixer):
    audio, music = mixer
    music.unsupported = True
    for n in range(60): update(audio, n, 1)
    assert len(music.seeks) == 1 and "unsupported" in audio.error
