from omega_omarchy import INSTALLER_COMPLETION_ACTION
from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.installer import (
    CONFIRM_PROMPT,
    GREETER_HINT,
    INSTALL_BREATH_TICKS,
    INSTALL_TICK_HZ,
    PARODY_STEPS,
    PROGRESS_BASE_TICKS,
    PROGRESS_TIPS,
    PROGRESS_TITLE,
    InstallerSession,
    default_fixture_world,
)
from omega_omarchy.physics import InputState
from omega_omarchy.render import Renderer
from omega_omarchy.sim import LEVEL_INTRO_TICKS, STAGE_MAP_INPUT_LOCK_TICKS, GameSim


def test_completion_action_is_play_now_not_reboot_now():
    session = InstallerSession()
    deck = session.copy_deck()
    assert deck["completionAction"] == "Play Now"
    assert deck["completionAction"] == INSTALLER_COMPLETION_ACTION
    assert deck["omarchyAffirmativeReplaced"] == "Reboot Now"
    assert deck["publicSharingPreselected"] is False
    assert deck["shareDefault"] == "local-only"
    assert deck["limitlessOptional"] is True
    assert deck["diskOverwriteOmitted"] is True
    assert deck["greeterHint"] == GREETER_HINT == "Press Return to Start Install"
    assert deck["confirmPrompt"] == CONFIRM_PROMPT == "Does this look right?"
    assert deck["progressTitle"] == PROGRESS_TITLE
    world = session.play_now()
    assert session.completion_action == "Play Now"
    assert world.identity.seed == "omega-fixture-1"


def test_quality_list_navigates_with_up_down_not_left_right():
    sim = GameSim.new("omega-fixture-1")
    while sim.installer.step != "quality":
        sim.step(InputState(jump_pressed=True))
        if sim.installer.step == "progress":
            break
    assert sim.installer.step == "quality"
    start = sim.installer.choices.fidelity
    sim.step(InputState(right_pressed=True))
    assert sim.installer.choices.fidelity == start
    sim.step(InputState(down_pressed=True))
    assert sim.installer.choices.fidelity != start


def test_confirm_no_change_it_returns_to_character():
    sim = GameSim.new("omega-fixture-1")
    while sim.installer.step != "confirm":
        sim.step(InputState(jump_pressed=True))
        if sim.installer.step == "progress":
            break
    assert sim.installer.step == "confirm"
    sim.step(InputState(right_pressed=True))
    assert sim.installer.confirm_accept is False
    sim.step(InputState(jump_pressed=True))
    assert sim.installer.step == "character"


def test_play_now_launches_campaign():
    sim = GameSim.from_play_now("omega-fixture-1")
    assert sim.scene == "action"
    assert sim.installer.completion_action == "Play Now"
    assert all("Play Now" not in message for message in sim.messages)
    assert sim.messages[0] == CAMPAIGN_ROSTER[0].blurb
    roster = sim.campaign_roster()
    assert "Oligarchy" in roster
    assert "Singularity" in roster
    assert "Goliath" in roster
    assert sim.world is not None
    assert default_fixture_world().identity.digest() == sim.world.identity.digest()


def _advance_to_progress(sim: GameSim) -> None:
    guard = 0
    while sim.installer.step not in {"progress", "complete"} and guard < 24:
        sim.step(InputState(jump_pressed=True))
        guard += 1


def test_complete_screen_stays_until_fresh_confirm():
    sim = GameSim.new("omega-fixture-1")
    _advance_to_progress(sim)
    assert sim.installer.step == "progress"
    sim.step(InputState(jump_pressed=True))
    assert sim.installer.step == "complete"
    assert sim.scene == "installer"
    assert sim.installer.play_now_armed is False
    # The skip input must not bleed: another confirm while still "held" does nothing.
    sim.step(InputState(jump_pressed=True, interact=True))
    assert sim.scene == "installer"
    assert sim.installer.step == "complete"
    assert sim.installer.complete_ticks >= 1
    # One idle frame renders the complete screen and arms Play Now.
    renderer = Renderer()
    frame = renderer.frame(sim)
    assert frame.get_size() == (960, 540)
    sim.step(InputState())
    assert sim.installer.play_now_armed is True
    assert sim.scene == "installer"
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "prologue"
    for _ in range(60):
        sim.step(InputState(turn=True))
    assert sim.scene == "stage-map"
    for _ in range(STAGE_MAP_INPUT_LOCK_TICKS):
        sim.step(InputState())
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "level-intro"
    for _ in range(LEVEL_INTRO_TICKS):
        sim.step(InputState())
    assert sim.scene == "action"
    assert sim.messages
    assert sim.messages[0] == "The installer finished. The world did not."
    assert all("Play Now" not in message for message in sim.messages)


def test_complete_copy_is_elapsed_install_not_world_sealed():
    session = InstallerSession()
    session.run_generation()
    session.enter_complete()
    line = session.installed_line
    assert line.startswith("Installed Omega Omarchy in ")
    assert line.endswith("s")
    assert "World sealed" not in line
    assert "(not Reboot Now)" not in line
    sim = GameSim.new("omega-fixture-1")
    _advance_to_progress(sim)
    sim.step(InputState(jump_pressed=True))
    renderer = Renderer()
    frame = renderer.frame(sim)
    # Sample the lime Play Now pill rather than the full canvas hash.
    lime = (158, 206, 106)
    found = False
    for x in range(300, 660):
        for y in range(300, 390):
            if tuple(frame.get_at((x, y))[:3]) == lime:
                found = True
                break
        if found:
            break
    assert found, "Play Now pill should be lime on the complete screen"


def test_complete_screen_keeps_rotating_tip_below_play_now(monkeypatch):
    sim = GameSim.new("omega-fixture-1")
    _advance_to_progress(sim)
    sim.step(InputState(jump_pressed=True))
    renderer = Renderer()
    centered: list[tuple[str, int]] = []
    original_center = renderer._center

    def record_center(surf, text, y, color, big=False):
        centered.append((text, y))
        return original_center(surf, text, y, color, big)

    monkeypatch.setattr(renderer, "_center", record_center)
    sim.tick = 0
    renderer.frame(sim)
    sim.tick = 90
    renderer.frame(sim)

    tips = [(text, y) for text, y in centered if text.startswith("Tip: ")]
    assert tips == [(f"Tip: {PROGRESS_TIPS[0]}", 138), (f"Tip: {PROGRESS_TIPS[1]}", 138)]


def test_progress_reserves_three_seconds_after_the_original_install_timing():
    session = InstallerSession(step_index=PARODY_STEPS.index("progress"))
    session.run_generation()
    for _ in range(PROGRESS_BASE_TICKS + INSTALL_BREATH_TICKS - 1):
        session.tick_progress()
    assert session.step == "progress"
    session.tick_progress()
    assert session.step == "complete"
    authored_seconds = (PROGRESS_BASE_TICKS + INSTALL_BREATH_TICKS) / INSTALL_TICK_HZ
    assert INSTALL_BREATH_TICKS / INSTALL_TICK_HZ == 3
    assert session.total_elapsed_s >= authored_seconds
    assert f"{session.total_elapsed_s:.2f}s" in session.installed_line


def test_character_setup_accepts_a_freeform_name_and_seals_it_into_the_world():
    session = InstallerSession(step_index=PARODY_STEPS.index("character"))
    assert session.choices.character.name == "David"
    assert session.edit_character_name("Ada")
    assert session.choices.character.name == "Ada"
    assert session.edit_character_name(backspace=True)
    assert session.choices.character.name == "Ad"
    session.next_step()
    world = session.run_generation()
    assert world.character["name"] == "Ad"


def test_quality_page_explains_where_fidelity_can_be_changed():
    session = InstallerSession(step_index=PARODY_STEPS.index("quality"))
    page = session.gum_page()
    assert page is not None
    assert page["footnote"] == "Ultra adds detail. Change fidelity later in Pause."


def test_sound_fidelity_is_a_separate_installer_choice():
    session = InstallerSession(step_index=PARODY_STEPS.index("sound"))
    page = session.gum_page()
    assert page is not None
    assert page["prompt"] == "Select audio quality"
    assert page["footnote"] == "Music and sound effects. Change audio later in Pause."
    session.cycle(-1)
    assert session.choices.fidelity == "ultra"
    assert session.choices.audio_fidelity == "high"
    world = session.run_generation()
    assert world.settings["fidelity"] == "ultra"
    assert world.settings["audioFidelity"] == "high"


def test_confirmation_draws_progress_before_any_generation_and_keeps_real_time(monkeypatch):
    import omega_omarchy.installer as installer
    clock = [100.0]
    monkeypatch.setattr(installer.time, "perf_counter", lambda: clock[0])
    started = []
    prepared = object()

    def work(self):
        started.append(True)
        yield .1, "Building terrain"
        clock[0] += 12.0
        yield .9, "Checking traversal"
        return prepared

    monkeypatch.setattr(InstallerSession, "_prepare_world", work)
    session = InstallerSession(step_index=PARODY_STEPS.index("confirm"), realtime=True)
    session.next_step()
    assert session.step == "progress" and session.world is None and not started
    session.tick_progress()
    assert session.progress_label == "Building terrain" and session.world is None
    session.tick_progress()
    assert session.progress_fraction == .9 and session.total_elapsed_s >= 12
    session.tick_progress()
    assert session.world is prepared and session.step == "progress"
    assert session._generation_work is None
    for _ in range(PROGRESS_BASE_TICKS + INSTALL_BREATH_TICKS):
        session.tick_progress()
    elapsed = session.total_elapsed_s
    clock[0] += 50
    assert session.complete and session.total_elapsed_s == elapsed


def test_character_preload_begins_at_greeter_and_selection_reuses_validation(monkeypatch):
    sim = GameSim.new()
    sim.step(InputState())
    assert sim.installer.step == "greeter"
    assert sim.installer._character_work is not None
    for _ in range(60):
        sim.step(InputState())
    assert sim.installer.characters_ready
    assert len(sim.installer.character_options) >= 3
    monkeypatch.setattr(sim.installer, "refresh_characters", lambda: (_ for _ in ()).throw(AssertionError("selection revalidated packs")))
    sim.installer.step_index = PARODY_STEPS.index("character")
    sim.step(InputState(down_pressed=True))
    assert sim.installer.choices.character.kind == "omarch-king"
