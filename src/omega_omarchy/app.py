"""Native Linux pygame entry: keyboard, gamepad hot-plug, dummy-headless safe."""

from __future__ import annotations

import asyncio
from functools import lru_cache
import os
from pathlib import Path
import sys

import pygame

from . import FIXTURE_SEED, INSTALLER_COMPLETION_ACTION
from .accessibility import (
    DEFAULT_GAMEPAD,
    DEFAULT_KEYBOARD,
    DEFAULT_KEYBOARD_ALTERNATES,
    GAMEPAD_ACTIONS,
    Accessibility,
    gamepad_button_index,
)
from .audio import AudioManager
from .physics import InputState
from .render import INTERNAL, Renderer, save_surface
from .runtime_assets import asset_dir
from .sim import CHAPTER_COMPLETE_TALLY_TICKS, GameSim
from .character_pack import poll_browser_import, restore_browser_characters

SCALE = 4

_NAMED_KEYS = {
    "left": pygame.K_LEFT,
    "right": pygame.K_RIGHT,
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
    "space": pygame.K_SPACE,
    "escape": pygame.K_ESCAPE,
    "tab": pygame.K_TAB,
    "return": pygame.K_RETURN,
    "enter": pygame.K_RETURN,
}


@lru_cache(maxsize=128)
def key_name_to_code(name: str) -> int:
    token = str(name).strip()
    if not token:
        raise ValueError("empty key name")
    lower = token.lower()
    if lower in _NAMED_KEYS:
        return _NAMED_KEYS[lower]
    try:
        return int(pygame.key.key_code(lower))
    except (ValueError, pygame.error):
        pass
    attr = f"K_{lower}" if len(lower) == 1 else f"K_{token}"
    if hasattr(pygame, f"K_{lower}"):
        return int(getattr(pygame, f"K_{lower}"))
    if hasattr(pygame, attr):
        return int(getattr(pygame, attr))
    raise ValueError(f"unknown key {name}")


def key_code_to_name(code: int) -> str:
    name = pygame.key.name(code).strip()
    if not name:
        raise ValueError(f"unknown key code {code}")
    if len(name) == 1:
        return name.upper()
    return " ".join(part.title() for part in name.split())


def _handle_credits_shortcut(sim: GameSim, key: int, audio: AudioManager | None = None) -> bool:
    """Preview either sequence without abandoning the current game/session."""
    if key not in {pygame.K_F11, pygame.K_F12}:
        return False
    return_scene = (
        sim.credits_return_scene
        if sim.scene in {"credits", "chapter-credits", "ending"}
        else sim.scene
    )
    cinematic = key == pygame.K_F12
    target = "ending" if cinematic else ("chapter-credits" if return_scene == "chapter-complete" else "credits")
    if sim.scene == target and sim.credits_shortcut_lock > 0:
        return True
    sim.start_credits(cinematic=cinematic, return_scene=return_scene)
    sim.credits_shortcut_lock = 20
    if return_scene == "installer":
        # Re-arm the confirm debounce so a held/repeating skip key cannot
        # instantly fire play_now() on the frame the installer reappears.
        sim.installer.awaiting_release = True
        sim.installer.play_now_armed = False
    if audio is not None:
        # Halt immediately. A fadeout here races mixer.load() on the next cue.
        audio._stop_music(fade_ms=0)
    return True


def _held(keys: object, code: int) -> bool:
    try:
        return bool(keys[code])
    except (KeyError, IndexError, TypeError):
        return False


def _map_keys(
    keys: object,
    just: set[int],
    joy: dict[str, bool],
    accessibility: Accessibility | None = None,
) -> InputState:
    primary = dict(DEFAULT_KEYBOARD)
    alternates = dict(DEFAULT_KEYBOARD_ALTERNATES)
    if accessibility is not None:
        primary.update(accessibility.keyboard)
        alternates.update(accessibility.keyboard_alternates)

    def bound(action: str) -> set[int]:
        result: set[int] = set()
        for name in (primary[action], alternates.get(action, "")):
            if not name:
                continue
            try:
                result.add(key_name_to_code(name))
            except ValueError:
                fallback = DEFAULT_KEYBOARD[action]
                result.add(key_name_to_code(fallback))
        return result

    codes = {action: bound(action) for action in DEFAULT_KEYBOARD}

    def held(action: str) -> bool:
        return any(_held(keys, code) for code in codes[action])

    def pressed(action: str) -> bool:
        return bool(just & codes[action])

    return InputState(
        left=bool(held("left") or joy.get("left")),
        right=bool(held("right") or joy.get("right")),
        left_pressed=bool(pressed("left") or joy.get("left_pressed")),
        right_pressed=bool(pressed("right") or joy.get("right_pressed")),
        up=bool(held("up") or joy.get("up")),
        down=bool(held("down") or joy.get("down")),
        up_pressed=bool(pressed("up") or joy.get("up_pressed")),
        down_pressed=bool(pressed("down") or joy.get("down_pressed")),
        jump=bool(held("jump") or joy.get("jump") or joy.get("a")),
        jump_pressed=bool(pressed("jump") or joy.get("jump_pressed") or joy.get("a_pressed")),
        action=bool(held("action") or joy.get("action") or joy.get("b")),
        action_pressed=bool(
            pressed("action") or joy.get("action_pressed") or joy.get("b_pressed")
        ),
        # Interact remains edge-triggered so one held key cannot submit several
        # faux-install screens.
        interact=bool(pressed("interact") or joy.get("interact_pressed") or joy.get("x_pressed")),
        turn=bool(held("turn") or joy.get("turn") or joy.get("y")),
        turn_pressed=bool(
            pressed("turn") or joy.get("turn_pressed") or joy.get("y_pressed")
        ),
        item=bool(pressed("item") or joy.get("item_pressed") or joy.get("rb_pressed")),
        customize=bool(
            pressed("customize") or joy.get("customize_pressed") or joy.get("back_pressed")
        ),
        pause=bool(pressed("pause") or joy.get("pause_pressed") or joy.get("start_pressed")),
    )


def _joystick_state(
    joysticks: dict[int, pygame.joystick.Joystick],
    just_buttons: set[tuple[int, int]],
    accessibility: Accessibility | None = None,
) -> dict[str, bool]:
    state: dict[str, bool] = {}
    bindings = dict(DEFAULT_GAMEPAD)
    if accessibility is not None:
        bindings.update(accessibility.gamepad)
    for joy in joysticks.values():
        try:
            ax_x = joy.get_axis(0) if joy.get_numaxes() else 0.0
            ax_y = joy.get_axis(1) if joy.get_numaxes() > 1 else 0.0
            hat = joy.get_hat(0) if joy.get_numhats() else (0, 0)
            instance_id = joy.get_instance_id()
        except pygame.error:
            continue
        dead = 0.35
        directions = {
            "left": ax_x < -dead or hat[0] < 0,
            "right": ax_x > dead or hat[0] > 0,
            "up": ax_y < -dead or hat[1] > 0,
            "down": ax_y > dead or hat[1] < 0,
        }
        for name, active in directions.items():
            state[name] = bool(state.get(name) or active)

        def pressed(index: int) -> bool:
            return joy.get_numbuttons() > index and bool(joy.get_button(index))

        for action in GAMEPAD_ACTIONS:
            try:
                index = gamepad_button_index(bindings[action])
            except ValueError:
                index = gamepad_button_index(DEFAULT_GAMEPAD[action])
            state[action] = bool(state.get(action) or pressed(index))
            edge_name = f"{action}_pressed"
            state[edge_name] = bool(state.get(edge_name) or (instance_id, index) in just_buttons)
    return state


def _joystick_edges(current: dict[str, bool], previous: dict[str, bool]) -> dict[str, bool]:
    """Add one-frame stick/D-pad edges used by menus and movement combos."""

    state = dict(current)
    for name in ("left", "right", "up", "down"):
        state[f"{name}_pressed"] = bool(current.get(name) and not previous.get(name))
    return state


def _set_window_icon() -> bool:
    """Install the selected Omega mark without making headless launch fragile."""

    path = asset_dir() / "ui" / "omega-omarchy-icon-128.png"
    if not path.is_file():
        return False
    try:
        pygame.display.set_icon(pygame.image.load(str(path)))
    except pygame.error:
        return False
    return True


async def run_game_async(
    *,
    seed: str = FIXTURE_SEED,
    headless: bool = False,
    dump_identity: bool = False,
    dump_campaign: bool = False,
    inspect_dir: Path | None = None,
    skip_installer: bool = False,
    ticks: int = 0,
    content_packs: tuple[Path, ...] = (),
    dev_warp: str | None = None,
) -> GameSim:
    if headless and not os.environ.get("SDL_VIDEODRIVER"):
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.joystick.init()
    restore_browser_characters()
    sim = GameSim.new(seed, content_packs)
    sim.installer.realtime = not headless
    sim.web_chapter_one = sys.platform == "emscripten"
    sim.installer.web_chapter_one = sim.web_chapter_one
    audio = AudioManager(browser=sim.web_chapter_one, enabled=not headless)
    if skip_installer or headless or dev_warp:
        sim.confirm_play_now(skip_prologue=True)
    if dev_warp:
        resolved = sim.dev_warp(dev_warp)
        print(f"DEV_WARP={resolved}")
    renderer = Renderer()
    if headless:
        window_size = INTERNAL
    elif sys.platform == "emscripten":
        window_size = renderer.frame(sim).get_size()
    else:
        window_size = (INTERNAL[0] * SCALE, INTERNAL[1] * SCALE)
    window = pygame.display.set_mode(window_size)
    _set_window_icon()
    pygame.display.set_caption("Omega Omarchy")
    clock = pygame.time.Clock()
    joysticks: dict[int, pygame.joystick.Joystick] = {}
    previous_joy: dict[str, bool] = {}
    for index in range(pygame.joystick.get_count()):
        stick = pygame.joystick.Joystick(index)
        stick.init()
        joysticks[stick.get_instance_id()] = stick
    running = True
    remaining = ticks
    while running:
        import_message = poll_browser_import()
        if import_message:
            sim.installer.refresh_characters()
            sim.installer.character_notice = import_message
            sim.messages.append(import_message)
            from platform import window as browser_window
            browser_window.omegaCharacterImportStatus = import_message
        just: set[int] = set()
        just_buttons: set[tuple[int, int]] = set()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                audio.unlock()
                sim.last_input_device = "keyboard"
                if sim.capture_remap_key(key_code_to_name(event.key)):
                    continue
                if _handle_credits_shortcut(sim, event.key, audio):
                    continue
                if sim.scene == "installer" and sim.installer.step == "character":
                    if event.key == pygame.K_BACKSPACE:
                        sim.installer.edit_character_name(backspace=True)
                        continue
                    if event.unicode and event.unicode.isprintable() and event.unicode not in "\r\n\t":
                        sim.installer.edit_character_name(event.unicode)
                        continue
                just.add(event.key)
                if event.key == pygame.K_F1 and sim.scene == "installer":
                    sim.installer.skip_progress()
                    sim.confirm_play_now(skip_prologue=True)
                if event.key == pygame.K_F5 and sim.editing is False and sim.scene == "action":
                    # accessibility / test: force OMARCHY edit
                    sim._enter_edit()
                if event.key in {
                    pygame.K_F2,
                    pygame.K_F4,
                    pygame.K_F6,
                    pygame.K_F7,
                    pygame.K_F9,
                    pygame.K_F10,
                } and sim.scene == "action":
                    landmark = {
                        pygame.K_F2: "boss-15",
                        pygame.K_F4: "goliath-amalgam:boss-15",
                        pygame.K_F6: "boss",
                        pygame.K_F7: "edit",
                        pygame.K_F9: "portal",
                        pygame.K_F10: "cow",
                    }[event.key]
                    try:
                        sim.dev_warp(landmark)
                    except (RuntimeError, ValueError) as exc:
                        sim.messages.append(f"DEV WARP unavailable: {exc}")
                if event.key == pygame.K_F3:
                    sim.debug_hitboxes = not sim.debug_hitboxes
                if event.key == pygame.K_F8 and sim.combat:
                    sim.scene = "turn"
                    from .combat import enter_turn_based

                    sim.combat = enter_turn_based(sim.combat)
            elif event.type == pygame.JOYDEVICEADDED:
                stick = pygame.joystick.Joystick(event.device_index)
                stick.init()
                joysticks[stick.get_instance_id()] = stick
            elif event.type == pygame.JOYDEVICEREMOVED:
                joysticks.pop(event.instance_id, None)
            elif event.type == pygame.JOYBUTTONDOWN:
                audio.unlock()
                sim.last_input_device = "gamepad"
                if sim.capture_remap_button(event.button):
                    continue
                just_buttons.add((event.instance_id, event.button))
            elif event.type == pygame.JOYHATMOTION and event.value != (0, 0):
                sim.last_input_device = "gamepad"
            elif event.type == pygame.JOYAXISMOTION and abs(float(event.value)) > 0.5:
                sim.last_input_device = "gamepad"
        keys = pygame.key.get_pressed()
        raw_joy = _joystick_state(joysticks, just_buttons, sim.accessibility)
        joy = _joystick_edges(raw_joy, previous_joy)
        previous_joy = {name: bool(raw_joy.get(name)) for name in ("left", "right", "up", "down")}
        inp = _map_keys(keys, just, joy, sim.accessibility)
        if sim.scene == "oligarchy" and (inp.interact or inp.jump_pressed):
            sim.dismiss_oligarchy()
        sim.step(inp, frame_seconds=clock.get_time() / 1000)
        active_audio_settings = (
            sim.installer.choices.to_record() if sim.scene == "installer" else sim.settings
        )
        if sim.credits_cut_music:
            audio._stop_music(fade_ms=0)
            sim.credits_cut_music = False
        music_fade_ms = None
        if sim.scene == "ending":
            from .credits import CAST_THEME_FADE_SECONDS, title_duration

            cast_remaining = title_duration() - sim.credits_elapsed
            if 0 < cast_remaining <= CAST_THEME_FADE_SECONDS:
                music_fade_ms = round(CAST_THEME_FADE_SECONDS * 1000)
        audio.update(
            scene=sim.scene,
            in_combat=sim.combat is not None,
            settings=active_audio_settings,
            cues=tuple(sim.sfx),
            music_fade_ms=music_fade_ms,
        )
        sim.sfx.clear()
        if sim.scene == "installer":
            renderer.preload_character_portraits(sim.installer)
        frame = renderer.frame(sim)
        if sys.platform == "emscripten":
            if window.get_size() != frame.get_size():
                window = pygame.display.set_mode(frame.get_size())
            window.blit(frame, (0, 0))
        elif window.get_size() != frame.get_size():
            pygame.transform.scale(frame, window.get_size(), window)
        else:
            window.blit(frame, (0, 0))
        pygame.display.flip()
        clock.tick(60)
        if remaining:
            remaining -= 1
            if remaining <= 0:
                running = False
        if headless and ticks == 0:
            running = False
        # Browser builds must yield to the host once per frame; doing the same
        # in native builds keeps one authoritative loop and is effectively
        # free next to the 60 Hz clock.
        await asyncio.sleep(0)
    if dump_identity:
        if sim.world is None:
            sim.confirm_play_now()
        print(f"WORLD_IDENTITY={sim.world.identity.digest()}")
    if dump_campaign:
        print("CAMPAIGN:" + ",".join(sim.campaign_roster()))
        print("COMPLETION:" + INSTALLER_COMPLETION_ACTION)
    if inspect_dir:
        _inspect(sim, renderer, Path(inspect_dir))
    audio.shutdown()
    if sys.platform != "emscripten":
        pygame.quit()
    return sim


def run_game(
    *,
    seed: str = FIXTURE_SEED,
    headless: bool = False,
    dump_identity: bool = False,
    dump_campaign: bool = False,
    inspect_dir: Path | None = None,
    skip_installer: bool = False,
    ticks: int = 0,
    content_packs: tuple[Path, ...] = (),
    dev_warp: str | None = None,
) -> GameSim:
    """Run the authoritative loop on native Python."""

    return asyncio.run(
        run_game_async(
            seed=seed,
            headless=headless,
            dump_identity=dump_identity,
            dump_campaign=dump_campaign,
            inspect_dir=inspect_dir,
            skip_installer=skip_installer,
            ticks=ticks,
            content_packs=content_packs,
            dev_warp=dev_warp,
        )
    )


def _inspect(sim: GameSim, renderer: Renderer, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    presets = ("sixteen-bit", "high", "ultra")
    # installer greeter + play now
    inst = GameSim.new(sim.installer.choices.seed, sim.installer.content_paths)
    for preset in presets:
        inst.installer.choices.fidelity = preset
        inst.installer.choices.quality = preset
        inst.set_presentation(fidelity=preset, display="clean")
        save_surface(renderer.frame(inst), dest / f"install-greeter-{preset}.png")
        inst.installer.skip_progress()
        save_surface(renderer.frame(inst), dest / f"install-play-now-{preset}.png")
        inst.confirm_play_now()
        inst.set_presentation(fidelity=preset, display="clean")
        for beat, label, ticks in (
            (0, "title", 64),
            (1, "orb-capture", 96),
            (2, "door", 130),
            (3, "machine", 150),
            (4, "transfer", 64),
            (5, "corrupt", 64),
            (6, "rift-entry", 24),
            (6, "rift-transit", 92),
            (6, "rift-exit", 176),
            (7, "login", 64),
        ):
            inst.scene = "prologue"
            inst.story_beat = beat
            inst.story_ticks = ticks
            save_surface(renderer.frame(inst), dest / f"prologue-{label}-{preset}.png")
        inst.scene = "action"
        frame = renderer.frame(inst)
        for _ in range(23):
            frame = renderer.frame(inst)
        save_surface(frame, dest / f"action-{preset}.png")
        inst.last_input_device = "gamepad"
        save_surface(renderer.frame(inst), dest / f"action-gamepad-{preset}.png")
        inst.last_input_device = "keyboard"
        if inst.body is not None:
            from dataclasses import replace

            resting = inst.body
            inst.body = replace(resting, vx=2.0, on_ground=True)
            inst.tick = 0
            save_surface(renderer.frame(inst), dest / f"walk-a-{preset}.png")
            inst.tick = 12
            save_surface(renderer.frame(inst), dest / f"walk-b-{preset}.png")
            inst.body = replace(resting, vy=-3.0, on_ground=False)
            save_surface(renderer.frame(inst), dest / f"jump-{preset}.png")
            inst.body = replace(resting, vy=-1.7, on_ground=True, on_ladder=True)
            save_surface(renderer.frame(inst), dest / f"climb-{preset}.png")
            inst.body = resting
        inst.paused_from = "action"
        inst.scene = "pause"
        save_surface(renderer.frame(inst), dest / f"pause-{preset}.png")
        inst.set_presentation(display="crt")
        inst.pause_cursor = inst.pause_rows().index("controls")
        save_surface(renderer.frame(inst), dest / f"pause-crt-{preset}.png")
        inst.set_presentation(display="clean")
        inst.scene = "remap"
        inst.remap_device = "keyboard"
        inst.remap_slot = 0
        inst.remap_cursor = inst.remap_actions.index("jump")
        inst.remap_feedback = "Choose an action, then bind it."
        save_surface(renderer.frame(inst), dest / f"remap-{preset}.png")
        inst.remap_device = "gamepad"
        inst.remap_slot = 0
        inst.remap_cursor = inst.remap_actions.index("jump")
        inst.remap_waiting = True
        inst.remap_feedback = "Press a gamepad button for JUMP / CONFIRM."
        save_surface(renderer.frame(inst), dest / f"remap-gamepad-{preset}.png")
        inst.scene = "action"
        inst.scene = "turn"
        from .combat import make_foe, make_player, start_encounter, enter_turn_based

        inst.combat = enter_turn_based(
            start_encounter(
                make_player(inst.character_name),
                make_foe("package-bureaucrat", as_boss=True),
                boss_id="package-bureaucrat",
            )
        )
        save_surface(renderer.frame(inst), dest / f"turn-{preset}.png")
        inst._begin_flight()
        save_surface(renderer.frame(inst), dest / f"flight-{preset}.png")
        inst._enter_edit()
        save_surface(renderer.frame(inst), dest / f"edit-{preset}.png")
        inst.editing = False
        inst.scene = "oligarchy"
        inst.oligarchy = True
        inst.hud_wordmark = "OLIGARCHY"
        save_surface(renderer.frame(inst), dest / f"oligarchy-{preset}.png")
        inst.scene = "ending"
        save_surface(renderer.frame(inst), dest / f"ending-{preset}.png")
        inst.scene = "chapter-complete"
        inst.post_boss = True
        inst.post_boss_ticks = CHAPTER_COMPLETE_TALLY_TICKS
        inst.pending_chapter = 1
        save_surface(renderer.frame(inst), dest / f"chapter-complete-{preset}.png")
        inst.scene = "chapter-credits"
        save_surface(renderer.frame(inst), dest / f"chapter-credits-{preset}.png")
        inst._open_stage_map(min(1, len(inst.campaign_roster()) - 1), transition=False)
        save_surface(renderer.frame(inst), dest / f"stage-map-{preset}.png")
        inst.combat = None
        inst.battle_queue = []
        inst.battle_delay_ticks = 0
        inst.scene = "action"
        inst.dev_warp("cow")
        save_surface(renderer.frame(inst), dest / f"cow-level-{preset}.png")
        inst.scene = "reroll-confirm"
        inst.reroll_confirm_yes = False
        save_surface(renderer.frame(inst), dest / f"reroll-confirm-{preset}.png")
        inst.scene = "recovery"
        inst.recovery_reason = "argument-overload"
        save_surface(renderer.frame(inst), dest / f"recovery-{preset}.png")
        # reset a fresh sim for next preset
        inst = GameSim.new(sim.installer.choices.seed, sim.installer.content_paths)
