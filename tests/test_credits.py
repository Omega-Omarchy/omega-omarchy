import copy
from datetime import date
import json
import math
import os
from pathlib import Path
import subprocess

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from omega_omarchy.audio import AudioManager
from omega_omarchy.app import _handle_credits_shortcut
from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.character_pack import available_characters
from omega_omarchy.credits import FPS, PATRON_FONT_SIZES, ROLL_TARGET_SPEED, cast_card, credit_manifest, roll_duration, title_duration
from omega_omarchy.credits_build import build_credits, compile_credits, history_attribution, resolve_contributor, song_credit
from omega_omarchy.physics import InputState, TILE, spawn_body
from omega_omarchy.installer import InstallerSession
from omega_omarchy.render import Renderer
from omega_omarchy.sim import FLIGHT_TICKS, GameSim


def test_names_use_opt_in_override_then_pinned_profile_then_github_login():
    config = {"contributors": {"author": {"name": "Screen Name", "aliases": ["person@example.test"]}}, "github_profiles": {"profile": {"name": "Public Name"}}}
    assert resolve_contributor("Git Name", "123+author@users.noreply.github.com", config) == ("author", "Screen Name")
    assert resolve_contributor("Git Name", "person@example.test", config) == ("author", "Screen Name")
    assert resolve_contributor("Git Name", "profile@users.noreply.github.com", config) == ("profile", "Public Name")
    assert resolve_contributor("Git Name", "offline@example.test", config, github_login="profile") == ("profile", "Public Name")
    assert resolve_contributor("Git Name", "999+newcomer@users.noreply.github.com", config) == ("newcomer", "newcomer")
    assert resolve_contributor("author", "author@users.example.test", config) == ("author", "Screen Name")
    identity, name = resolve_contributor("Offline Author", "private@example.test", config)
    assert identity.startswith("git:") and "private" not in identity and name == "Offline Author"


def test_git_attribution_preserves_authors_coauthors_renames_and_changed_paths(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()
    git("init", "-q")
    git("config", "user.name", "Author")
    git("config", "user.email", "123+author@users.noreply.github.com")
    (tmp_path / "render.py").write_text("pixels")
    git("add", ".")
    git("commit", "-qm", "Draw actors\n\nCo-authored-by: Partner <partner@users.noreply.github.com>")
    first = git("rev-parse", "HEAD")
    git("mv", "render.py", "animation.py")
    git("commit", "-qm", "Move animation")
    people, commits = history_attribution(tmp_path, {})
    by_id = {p["id"]: p for p in people}
    assert by_id["partner"]["commits"] == [first]
    assert by_id["partner"]["paths"] == ["render.py"]
    assert by_id["author"]["paths"] == ["animation.py", "render.py"]
    assert len(commits) == 2
    assert history_attribution(tmp_path, {}) == (people, commits)


def test_github_login_and_personal_email_collapse_to_one_screen_name(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Jeremy Dixon")
    git("config", "user.email", "123+author@users.noreply.github.com")
    (tmp_path / "sim.py").write_text("play")
    git("add", ".")
    git("commit", "-qm", "Play")
    git("config", "user.name", "author")
    git("config", "user.email", "author@users.example.test")
    (tmp_path / "docs.md").write_text("notes")
    git("add", ".")
    git("commit", "-qm", "Document")
    config = {"contributors": {"author": {"name": "Screen Name", "aliases": ["Jeremy Dixon"]}}}
    people, _ = history_attribution(tmp_path, config)
    assert [person["id"] for person in people] == ["author"]
    assert people[0]["name"] == "Screen Name"
    assert "sim.py" in people[0]["paths"] and "docs.md" in people[0]["paths"]


def test_manifest_is_reproducible_and_contains_every_pinned_name_and_accepted_cast():
    first = compile_credits()
    assert compile_credits() == first
    root = Path(__file__).resolve().parents[1]
    foundation = json.loads((root / "credits/omacom-foundation.json").read_text())
    expected = [name.upper() for group in foundation["groups"] for name in group["names"]]
    actual = [name for row in first["rows"] for name in row.get("names", [])]
    assert actual == expected and len(actual) >= 453
    boss_ids = {card["id"] for card in first["castCards"] if card["kind"] == "boss"}
    assert {spec.boss.id for spec in CAMPAIGN_ROSTER} <= boss_ids
    assert "goliath-cyborg-penguin" in boss_ids
    assert {card["kind"] for card in first["castCards"]} >= {"player", "royalty", "mobs", "orbs", "robots"}
    assert first["rows"][-1]["kind"] == "seals"
    assert first["musicCredits"][0]["artist"] == "Jeremy Dixon"
    assert first["musicCredits"][0]["creditSource"] == "embedded:artist"
    assert not any("Suno" in row.get("text", "") for row in first["rows"])
    text = [row.get("text") for row in first["rows"]]
    assert {"CODEX / ASTRA", "CODEX / SOL", "GROK BUILD", "GROK IMAGINE"} <= set(text)
    assert {person["name"] for person in first["contributors"]} == {"Jeremy Dixon"}
    start = next(i for i, row in enumerate(first["rows"]) if row.get("text") == "The following departments follow the Git history.")
    end = next(i for i, row in enumerate(first["rows"]) if row.get("text") == "AGENT COLLABORATORS")
    git_names = [row.get("text") for row in first["rows"][start:end] if row.get("kind") == "text"]
    assert "JEREMYDIXON22" not in git_names
    headings = [row.get("text") for row in first["rows"][start:end] if row.get("kind") == "heading"]
    assert git_names.count("JEREMY DIXON") == len(headings)
    extended = next(group["names"] for group in foundation["groups"] if group.get("compact"))
    assert [name for row in first["rows"] if row.get("compact") for name in row["names"]] == [name.upper() for name in extended]


def test_omacom_foundation_snapshot_is_not_stale():
    """Unlike Git-derived credits, the foundation/patrons roster is a hand-copied
    snapshot of external pages (see omacom-foundation.json's `sources`). Nothing
    re-fetches it, so this is the only tripwire that catches drift: it fails
    ./scripts/omega release-check (run on every push) once the snapshot is old
    enough that the source pages have plausibly changed, prompting a manual
    re-check and a bumped `retrieved` date rather than letting it rot silently.
    """
    root = Path(__file__).resolve().parents[1]
    foundation = json.loads((root / "credits/omacom-foundation.json").read_text())
    retrieved = date.fromisoformat(foundation["retrieved"])
    age_days = (date.today() - retrieved).days
    assert age_days <= 90, (
        f"credits/omacom-foundation.json was retrieved {age_days} days ago. "
        f"Re-check {foundation['sources']}, update the groups if they changed, "
        "and bump `retrieved` to today."
    )


@pytest.mark.parametrize("field", ["artist", "author", None])
def test_music_credit_reads_author_field_and_ignores_comment_metadata(tmp_path, field):
    source = tmp_path / "song.ogg"
    command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-t", "0.02", "-metadata", "comment=Made with an uncredited tool"]
    if field:
        command.extend(["-metadata", f"{field}=Embedded Author ft. Collaborator"])
    subprocess.run([*command, str(source)], check=True)
    song = {"title": "Song", "source": "song.ogg", "artist": "External Artist"}
    credit = song_credit(song, tmp_path)
    assert credit["artist"] == ("Embedded Author ft. Collaborator" if field else "External Artist")
    assert credit["creditSource"] == (f"embedded:{field}" if field else "external:credits/music.json")
    assert "uncredited tool" not in json.dumps(credit)
    if not field:
        with pytest.raises(ValueError, match="Missing author/artist"):
            song_credit({**song, "artist": ""}, tmp_path)


def test_credits_entry_transition_exit_and_slow_frames_follow_elapsed_time():
    sim = GameSim(installer=InstallerSession())
    sim.scene = "pause"
    sim.paused_from = "action"
    sim.pause_cursor = sim.pause_rows().index("credits")
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "credits" and sim.credits_ticks == 0
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "credits"  # entry debounce
    sim.step(InputState(), frame_seconds=2)
    assert sim.credits_ticks == 121
    sim.step(InputState(pause=True))
    assert sim.scene == "pause" and sim.paused_from == "action"
    sim.chapter_index = len(CAMPAIGN_ROSTER) - 1
    sim._advance_after_boss("goliath")
    assert sim.scene == "ending"
    sim.step(InputState(), frame_seconds=title_duration())
    assert sim.scene == "credits" and sim.credits_elapsed == 0
    sim.step(InputState(), frame_seconds=roll_duration() - 0.1)
    assert sim.scene == "credits"
    sim.step(InputState(), frame_seconds=0.2)
    assert sim.scene == "stage-map"
    sim.start_credits(return_scene="chapter-complete")
    assert sim.scene == "chapter-credits"
    sim.step(InputState(), frame_seconds=1)
    sim.step(InputState(interact=True))
    assert sim.scene == "chapter-complete"


def test_music_duration_matches_roll_and_does_not_continue_back_in_pause():
    manager = AudioManager(enabled=False)
    cue = manager.manifest["cues"]["credits-roll"]
    assert cue["loop"] is False
    assert all(abs(seconds - (roll_duration() - 5)) < 0.04 for seconds in cue["durations"].values())
    assert manager._desired_music("ending", in_combat=False) == "credits-theme"
    manager.music_cue = "credits-roll"
    assert manager._desired_music("pause", in_combat=False) is None


@pytest.mark.parametrize("origin", ["installer", "action", "pause", "edit", "turn", "chapter-complete"])
def test_credit_shortcuts_can_switch_sequences_and_restore_the_original_screen(origin):
    sim = GameSim(installer=InstallerSession(), scene=origin)
    sim.editing = origin == "edit"
    sim.edit_cursor = (10, 3)
    assert not _handle_credits_shortcut(sim, pygame.K_F10)
    assert sim.scene == origin
    assert _handle_credits_shortcut(sim, pygame.K_F11)
    assert sim.scene in {"credits", "chapter-credits"}
    sim.step(InputState(), frame_seconds=1)
    assert _handle_credits_shortcut(sim, pygame.K_F12)
    assert sim.scene == "ending" and sim.credits_elapsed == 0
    assert sim.credits_return_scene == origin
    sim.step(InputState(), frame_seconds=title_duration())
    assert sim.scene in {"credits", "chapter-credits"}
    sim.step(InputState(), frame_seconds=roll_duration())
    assert sim.scene == origin
    assert sim.editing == (origin == "edit") and sim.edit_cursor == (10, 3)
    assert sim.world is None  # previewing setup must not generate a world


def test_credits_preview_from_the_armed_complete_screen_requires_a_fresh_confirm():
    sim = GameSim.new("omega-fixture-1")
    guard = 0
    while sim.installer.step not in {"progress", "complete"} and guard < 24:
        sim.step(InputState(jump_pressed=True))
        guard += 1
    sim.step(InputState(jump_pressed=True))
    assert sim.installer.step == "complete"
    sim.step(InputState())
    assert sim.installer.play_now_armed is True
    assert _handle_credits_shortcut(sim, pygame.K_F12)
    assert sim.scene == "ending"
    assert sim.installer.awaiting_release is True
    assert sim.installer.play_now_armed is False
    # A held/repeating skip key drives both the cast-card skip and the
    # roll skip, landing back on "installer" while still "held".
    for _ in range(32):
        sim.step(InputState(jump_pressed=True))
    assert sim.scene == "credits"
    for _ in range(32):
        sim.step(InputState(jump_pressed=True))
    assert sim.scene == "installer"
    assert sim.installer.step == "complete"
    # The debounce must have swallowed the still-held key instead of
    # instantly (and synchronously) generating a world.
    assert sim.world is None
    assert sim.installer.play_now_armed is False
    # Releasing then pressing again still works normally afterward.
    sim.step(InputState())
    assert sim.installer.play_now_armed is True
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "prologue"
    assert sim.world is not None


def test_browser_credit_roll_uses_the_lighter_stream():
    manager = AudioManager(browser=True, enabled=False)
    assert manager._desired_music("ending", in_combat=False) == "credits-theme"
    assert manager._desired_music("credits", in_combat=False) == "credits-roll"
    path = manager.cue_path("credits-roll")
    assert path is not None and path.as_posix().endswith("sixteen-bit/music/credits-roll.ogg")


def test_cast_cards_preload_the_roll_so_skip_only_plays(monkeypatch):
    from omega_omarchy import audio as audio_mod

    order = []

    class FakeChannel:
        def stop(self):
            order.append("theme-stop")

        def fadeout(self, ms):
            order.append(("theme-fade", ms))

        def set_volume(self, volume):
            return None

        def get_busy(self):
            return True

    class FakeSound:
        def set_volume(self, volume):
            return None

        def play(self, *args, **kwargs):
            order.append("theme-play")
            return FakeChannel()

    class FakeMusic:
        def stop(self):
            order.append("stop")

        def fadeout(self, ms):
            order.append(("fadeout", ms))

        def load(self, path):
            order.append("load")

        def play(self, **kwargs):
            order.append("play")

        def set_volume(self, volume):
            return None

        def get_pos(self):
            return 0

    monkeypatch.setattr(audio_mod.pygame.mixer, "Sound", lambda path: FakeSound())
    monkeypatch.setattr(audio_mod.pygame.mixer, "music", FakeMusic())
    manager = AudioManager(enabled=False)
    manager.available = True
    manager.unlocked = True
    manager.update(scene="ending", in_combat=False, settings={})
    assert "theme-play" in order
    manager.update(scene="ending", in_combat=False, settings={})
    assert "load" in order
    assert "play" not in order
    manager.update(scene="credits", in_combat=False, settings={})
    assert "play" in order
    assert order.index("load") < order.index("play")


def test_credit_roll_music_loads_on_the_following_update(monkeypatch):
    from omega_omarchy import audio as audio_mod

    order = []

    class FakeMusic:
        def stop(self):
            order.append("stop")

        def fadeout(self, ms):
            order.append(("fadeout", ms))

        def load(self, path):
            order.append("load")

        def play(self, **kwargs):
            order.append("play")

        def set_volume(self, volume):
            return None

        def get_pos(self):
            return 0

    monkeypatch.setattr(audio_mod.pygame.mixer, "music", FakeMusic())
    manager = AudioManager(enabled=False)
    manager.available = True
    manager.unlocked = True
    manager.music_cue = "credits-theme"
    manager.update(scene="credits", in_combat=False, settings={})
    assert "load" not in order
    assert "stop" in order
    manager.update(scene="credits", in_combat=False, settings={})
    assert order.count("load") == 1
    assert order.index("stop") < order.index("load")
    assert manager.music_cue == "credits-roll"


def test_rapid_credit_shortcuts_do_not_restart_the_same_sequence():
    sim = GameSim(installer=InstallerSession(), scene="action")
    assert _handle_credits_shortcut(sim, pygame.K_F12)
    assert sim.scene == "ending"
    elapsed = sim.credits_elapsed
    assert _handle_credits_shortcut(sim, pygame.K_F12)
    assert sim.scene == "ending" and sim.credits_elapsed == elapsed
    assert _handle_credits_shortcut(sim, pygame.K_F11)
    assert sim.scene == "credits"


def test_skipping_cast_cards_starts_the_roll_without_holding_jump():
    sim = GameSim(installer=InstallerSession(), scene="action")
    sim.start_credits(cinematic=True, return_scene="action")
    for _ in range(32):
        sim.step(InputState())
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "credits"
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "credits"


def test_credit_music_stops_before_loading_the_next_stream(monkeypatch):
    from omega_omarchy import audio as audio_mod

    order = []

    class FakeMusic:
        def stop(self):
            order.append("stop")

        def fadeout(self, ms):
            order.append(("fadeout", ms))

        def load(self, path):
            order.append("load")

        def play(self, **kwargs):
            order.append("play")

        def set_volume(self, volume):
            return None

        def get_pos(self):
            return 0

    monkeypatch.setattr(audio_mod.pygame.mixer, "music", FakeMusic())
    manager = AudioManager(enabled=False)
    manager.available = True
    manager.unlocked = True
    manager.music_cue = "credits-theme"
    manager._music_fading = True
    assert manager._play_music("credits-roll")
    assert order[0] == "stop"
    assert "load" in order
    assert order.index("stop") < order.index("load")


def test_credit_shortcut_keys_cannot_be_captured_as_gameplay_bindings():
    sim = GameSim(installer=InstallerSession(), scene="remap")
    sim.remap_device, sim.remap_waiting = "keyboard", True
    before = sim.accessibility.to_record()
    for key in ("F11", "F12"):
        assert sim.capture_remap_key(key)
        assert sim.remap_waiting and "reserved" in sim.remap_feedback
        assert sim.accessibility.to_record() == before


def test_cast_theme_fades_out_before_the_roll(monkeypatch):
    from omega_omarchy import audio as audio_mod
    from omega_omarchy.credits import CAST_THEME_FADE_SECONDS, title_duration

    calls = []

    class FakeMusic:
        def fadeout(self, ms):
            calls.append(("music", ms))

        def set_volume(self, volume):
            return None

        def stop(self):
            return None

        def load(self, path):
            return None

        def play(self, **kwargs):
            return None

        def get_pos(self):
            return 0

    class FakeChannel:
        def fadeout(self, ms):
            calls.append(ms)

        def stop(self):
            return None

        def set_volume(self, volume):
            return None

    monkeypatch.setattr(audio_mod.pygame.mixer, "music", FakeMusic())
    manager = AudioManager(enabled=False)
    manager.available = True
    manager.unlocked = True
    manager.music_cue = "credits-theme"
    manager._theme_channel = FakeChannel()
    manager.update(scene="ending", in_combat=False, settings={}, music_fade_ms=round(CAST_THEME_FADE_SECONDS * 1000))
    assert calls == [round(CAST_THEME_FADE_SECONDS * 1000)]
    manager.update(scene="ending", in_combat=False, settings={}, music_fade_ms=round(CAST_THEME_FADE_SECONDS * 1000))
    assert calls == [round(CAST_THEME_FADE_SECONDS * 1000)]
    assert title_duration() > CAST_THEME_FADE_SECONDS


def test_repeating_credit_shortcut_restarts_the_backing_track():
    sim = GameSim(installer=InstallerSession())
    audio = AudioManager(enabled=False)
    audio.unlocked = True
    _handle_credits_shortcut(sim, pygame.K_F11, audio)
    audio.update(scene=sim.scene, in_combat=False, settings={})
    audio.update(scene=sim.scene, in_combat=False, settings={})
    assert audio.music_cue == "credits-roll"
    sim.step(InputState(), frame_seconds=90)
    _handle_credits_shortcut(sim, pygame.K_F11, audio)
    assert audio.music_cue == "" and sim.credits_elapsed == 0
    audio.update(scene=sim.scene, in_combat=False, settings={})
    audio.update(scene=sim.scene, in_combat=False, settings={})
    assert audio.music_cue == "credits-roll"


def test_editor_cursor_and_camera_cover_the_full_playfield_height():
    tiles = ["." * 40] * 38 + ["....S...................................", "#" * 40]
    sim = GameSim(installer=InstallerSession(), scene="edit", editing=True, tiles=tiles, body=spawn_body(tiles), cam_x=32, cam_y=460, edit_cursor=(5, 34))
    left, _, right, _ = sim._edit_bounds()
    for _ in range(60):
        sim.step(InputState(up=True, up_pressed=True))
        sim.cam_x, sim.cam_y = sim.camera_target()
    assert sim.edit_cursor[1] == 0 and sim.cam_y == 0
    for _ in range(60):
        sim.step(InputState(down=True, down_pressed=True))
        sim.cam_x, sim.cam_y = sim.camera_target()
    assert sim.edit_cursor[1] == 39 and sim.cam_y == 40 * TILE - 180
    assert sim._edit_bounds() == (left, 0, right, 39)
    body = (sim.body.x, sim.body.y)
    sim.flight_direction, sim.flight_ticks, sim.scene = "in", FLIGHT_TICKS, "flight"
    for _ in range(FLIGHT_TICKS): sim.step(InputState())
    assert sim.scene == "action" and (sim.body.x, sim.body.y) == body


@pytest.fixture(scope="module")
def studio():
    pygame.init()
    pygame.display.set_mode((960, 540))
    sim, renderer = GameSim.from_play_now(), Renderer(ensure_assets=False)
    yield sim, renderer
    pygame.quit()


@pytest.mark.parametrize("growth", ["patrons", "crew"])
def test_patron_compaction_absorbs_credit_growth_without_changing_other_type(studio, monkeypatch, growth):
    from omega_omarchy import credits_render
    _, renderer = studio
    manifest = copy.deepcopy(credit_manifest())
    # Start with enough slack to exercise the unchanged 8px default.
    manifest["music"]["duration"] += 12
    monkeypatch.setattr(credits_render, "credit_manifest", lambda: manifest)
    first, first_height = credits_render.CreditsRenderer(renderer).layout("David")
    assert {row["fontSize"] for _, _, row in first if row.get("compact")} == {8}
    if growth == "patrons":
        # A compact row now holds a whole group's names (chunked into
        # columns at render time), not a build-time-fixed pair, so growth
        # extends the existing group's roster instead of appending rows.
        for row in manifest["rows"]:
            if row.get("compact"):
                row["names"] = row["names"] + [f"Extra Patron {i}" for i in range(300)]
    else:
        manifest["rows"].append({"kind": "space", "height": 1000})
    original = copy.deepcopy(manifest)
    r = credits_render.CreditsRenderer(renderer)
    entries, height = r.layout("David")
    sizes = {row["fontSize"] for _, _, row in entries if row.get("compact")}
    assert len(sizes) == 1 and min(PATRON_FONT_SIZES) <= next(iter(sizes)) < 8
    assert (height + 105) / manifest["music"]["duration"] <= ROLL_TARGET_SPEED
    # Compaction steps through a fixed, discrete font-size list, so a single
    # large addition can legitimately land on a bucket several sizes down,
    # shrinking the (large) patron-name section by more than the content
    # that was added. The real guarantees are the ones already asserted
    # above: a single uniform compacted size was chosen, and scroll speed
    # stays within target -- not that total height is strictly monotonic.
    assert [(h, row) for _, h, row in entries[:len(first)] if not row.get("compact")] == [(h, row) for _, h, row in first if not row.get("compact")]
    assert [name for _, _, row in entries for name in row.get("names", [])] == [name for row in manifest["rows"] for name in row.get("names", [])]
    assert manifest == original  # runtime typography cannot mutate the roster
    assert r.layout("David") == (entries, height)


def test_omega_wordmark_bakes_underline_below_the_lettering(studio):
    from omega_omarchy.credits_render import CreditsRenderer

    _, renderer = studio
    credits = CreditsRenderer(renderer)
    surf = pygame.Surface((960, 540), pygame.SRCALPHA)
    credits.wordmark(surf, 80)
    plate, mark_top = credits.logos[(renderer._vs, 196)]
    scale = renderer._vs
    omega_h = credits.font(8, scale).size("OMEGA")[1]
    line_top = omega_h + max(2, scale)
    assert mark_top > line_top
    assert plate.get_height() > mark_top
    assert plate.get_at((max(0, 4 * scale), line_top))[:3] == (255, 255, 255)


def test_patron_compaction_has_a_legible_floor_and_wraps_long_names(studio, monkeypatch):
    from omega_omarchy import credits_render
    _, renderer = studio
    long_name = "A very long public patron name with 多吉康巴 and no lost characters"
    names = [long_name, "W" * 70] * 150
    manifest = {"music": {"duration": 100}, "rows": [{"kind": "names", "names": names, "height": 13, "compact": True}]}
    monkeypatch.setattr(credits_render, "credit_manifest", lambda: manifest)
    r = credits_render.CreditsRenderer(renderer)
    entries, height = r.layout("David")
    assert (height + 105) / 100 > ROLL_TARGET_SPEED  # floor wins over target
    for _, row_height, row in entries:
        assert row["fontSize"] == min(PATRON_FONT_SIZES)
        col_width = 284 / row["columnCount"]
        flat_wrapped = [lines for grid_row in row["grid"] for lines in grid_row]
        for original, lines in zip(row["names"], flat_wrapped):
            assert "".join("".join(lines).split()) == "".join(original.split())
            assert all(r.font(row["fontSize"], 4).size(line)[0] <= (col_width - 4) * 4 for line in lines)
        for grid_row, line_count in zip(row["grid"], row["gridLineCounts"]):
            assert line_count == max(len(lines) for lines in grid_row)
        assert row_height >= sum(row["gridLineCounts"]) * row["lineHeight"]
    for scale in (1, 2, 3):
        renderer._vs = scale
        frame = pygame.Surface((320 * scale, 180 * scale))
        frame.fill((0, 0, 0))
        for y, _, row in entries[:3]: r.draw_row(frame, row, y)
        assert pygame.surfarray.array3d(frame).max() > 0


def test_installer_credit_preview_uses_selected_character_and_detail_without_generating_world(studio):
    _, renderer = studio
    sim = GameSim(installer=InstallerSession())
    sim.installer.choices.character = available_characters()[0][2]
    sim.installer.choices.fidelity = "sixteen-bit"
    before = pygame.image.tobytes(renderer._character_sprite(sim, "portrait"), "RGBA")
    _handle_credits_shortcut(sim, pygame.K_F12)
    assert sim.world is None and sim.character_name == sim.installer.choices.character.name
    assert renderer._active_fid(sim) == "sixteen-bit"
    assert pygame.image.tobytes(renderer._character_sprite(sim, "portrait"), "RGBA") == before
    sim.credits_ticks = 10 * FPS
    assert pygame.surfarray.array3d(renderer.frame(sim)).max() > 0


def test_final_flight_and_first_edit_frame_share_the_actual_sprite(studio):
    base, renderer = studio
    sim = copy.deepcopy(base)
    for character in available_characters()[0][:3]:
        sim.world.character = character.to_record()
        for fidelity in ("sixteen-bit", "high", "ultra"):
            sim.set_presentation(fidelity=fidelity, display="clean")
            renderer._fid_cur, renderer._vs, renderer._iw, renderer._ih = renderer._layout(sim)
            sim.scene, sim.flight_ticks, sim.flight_direction = "flight", 1, "out"
            flight = pygame.Surface((renderer._iw, renderer._ih)); flight.fill((0, 0, 0))
            renderer._flight(flight, sim)
            sim.scene, sim.edit_cursor = "edit", (19, 0)
            edit = pygame.Surface(flight.get_size()); edit.fill((0, 0, 0))
            renderer._ots(edit, sim)
            ots, x, y = renderer._ots_layout(sim)
            # Exclude controls, compare all visible shoulders/face registration.
            rect = pygame.Rect(x, y, min(80 * renderer._vs - x, ots.get_width()), 142 * renderer._vs - y)
            assert rect.height > 0
            assert pygame.image.tobytes(flight.subsurface(rect), "RGB") == pygame.image.tobytes(edit.subsurface(rect), "RGB"), (character.name, fidelity)


def test_every_cast_card_and_credit_page_renders_with_pinned_glyphs(studio):
    base, renderer = studio
    sim = copy.deepcopy(base)
    for fidelity in ("sixteen-bit", "high", "ultra"):
        sim.set_presentation(fidelity=fidelity, display="crt")
        sim.start_credits(cinematic=True)
        time = 0
        for card in credit_manifest()["castCards"]:
            for local in (2, 4.3, card["seconds"] - 0.4):
                sim.credits_ticks = round((time + local) * FPS)
                frame = renderer.frame(sim)
                assert frame.get_at((0, 0))[:3] == (0, 0, 0)
                assert pygame.surfarray.array3d(frame).max() > 0
            time += card["seconds"]
        sim.start_credits()
        renderer.frame(sim)
        credit_renderer = renderer._credits_renderer
        entries, _ = credit_renderer.layout(sim.character_name)
        for _, _, row in entries:
            for columns in [*row.get("columns", []), row.get("lines", [])]:
                for line in columns:
                    assert all(metric is not None for metric in credit_renderer.font(8, 4).metrics(line)), line
        sim.credits_ticks = 80 * FPS
        frame = renderer.frame(sim)
        pixels = pygame.surfarray.array3d(frame)
        assert (pixels[:, :, 0] == pixels[:, :, 1]).all()
        assert (pixels[:, :, 1] == pixels[:, :, 2]).all()
        sim.settings["reducedMotion"] = True
        before = pygame.image.tobytes(renderer.frame(sim), "RGB")
        sim.credits_ticks += 1
        assert pygame.image.tobytes(renderer.frame(sim), "RGB") == before
        sim.settings["reducedMotion"] = False
        sim.credits_ticks = math.ceil((roll_duration() - 4) * FPS)
        assert pygame.surfarray.array3d(renderer.frame(sim)).max() == 0


def test_packaged_credits_refresh_without_mutating_source_snapshot(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src/omega_omarchy/data/credits.json"
    before = source.read_bytes()
    target = tmp_path / "package/omega_omarchy/data/credits.json"
    assert build_credits(target=target) == target
    assert json.loads(target.read_text()) == compile_credits()
    assert source.read_bytes() == before
    build_credits(target=target, check=True)
