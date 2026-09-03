from pathlib import Path

import pygame
import pytest

from omega_omarchy.accessibility import (
    DEFAULT_GAMEPAD,
    DEFAULT_KEYBOARD,
    DEFAULT_KEYBOARD_ALTERNATES,
    Accessibility,
)
from omega_omarchy.app import (
    _joystick_edges,
    _joystick_state,
    _map_keys,
    key_code_to_name,
    key_name_to_code,
)
from omega_omarchy.physics import InputState
from omega_omarchy.render import Renderer
from omega_omarchy.sim import GameSim


class _Held:
    def __init__(self, down: set[int] | None = None):
        self.down = set(down or ())

    def __getitem__(self, code: int) -> bool:
        return code in self.down


def test_remap_jump_to_w_not_z():
    pygame.init()
    a11y = Accessibility()
    a11y.remap("jump", "W")
    pressed_w = _map_keys(_Held(), {pygame.K_w}, {}, a11y)
    assert pressed_w.jump_pressed is True
    assert pressed_w.jump is False  # held set is empty; only the just-pressed W
    pressed_z = _map_keys(_Held({pygame.K_z}), {pygame.K_z}, {}, a11y)
    assert pressed_z.jump_pressed is False
    assert pressed_z.jump is False
    held_w = _map_keys(_Held({pygame.K_w}), set(), {}, a11y)
    assert held_w.jump is True


def test_return_is_edge_triggered_for_installer_debounce():
    held = _map_keys(_Held({pygame.K_RETURN}), set(), {})
    pressed = _map_keys(_Held({pygame.K_RETURN}), {pygame.K_RETURN}, {})
    assert not held.interact
    assert pressed.interact


def test_pygame_key_names_round_trip_for_capture():
    pygame.init()
    for code in (pygame.K_q, pygame.K_LEFT, pygame.K_SPACE, pygame.K_LSHIFT):
        assert key_name_to_code(key_code_to_name(code)) == code


def test_gamepad_direction_edges_pause_and_customize_reach_input_state():
    first = _joystick_edges(
        {"right": True, "start_pressed": True, "back_pressed": True},
        {"right": False},
    )
    mapped = _map_keys(_Held(), set(), first)
    assert mapped.right and mapped.right_pressed
    assert mapped.pause
    assert mapped.customize

    held = _joystick_edges({"right": True}, {"right": True})
    mapped_held = _map_keys(_Held(), set(), held)
    assert mapped_held.right
    assert not mapped_held.right_pressed


class _FakeJoystick:
    def __init__(self, instance_id: int, x: float, buttons: set[int] | None = None):
        self.instance_id = instance_id
        self.x = x
        self.buttons = set(buttons or ())

    def get_numaxes(self) -> int:
        return 2

    def get_axis(self, index: int) -> float:
        return self.x if index == 0 else 0.0

    def get_numhats(self) -> int:
        return 0

    def get_numbuttons(self) -> int:
        return max(8, max(self.buttons, default=-1) + 1)

    def get_button(self, index: int) -> int:
        return int(index in self.buttons)

    def get_instance_id(self) -> int:
        return self.instance_id


def test_multiple_gamepads_are_aggregated_and_button_edges_use_instance_ids():
    state = _joystick_state(
        {41: _FakeJoystick(41, -0.8), 42: _FakeJoystick(42, 0.0)},  # type: ignore[dict-item]
        {(42, 7)},
    )
    assert state["left"] is True
    assert state["pause_pressed"] is True


def test_keyboard_primary_and_alternate_bindings_are_live_and_conflict_safe():
    pygame.init()
    accessibility = Accessibility()
    assert accessibility.keyboard_alternates["jump"] == "Space"
    accessibility.remap("jump", "X")
    assert accessibility.keyboard["jump"] == "X"
    assert accessibility.keyboard["action"] == "Z"

    jump = _map_keys(_Held({pygame.K_x}), {pygame.K_x}, {}, accessibility)
    swapped_action = _map_keys(_Held({pygame.K_z}), {pygame.K_z}, {}, accessibility)
    alternate_jump = _map_keys(_Held({pygame.K_SPACE}), {pygame.K_SPACE}, {}, accessibility)
    assert jump.jump and jump.jump_pressed
    assert swapped_action.action and swapped_action.action_pressed
    assert alternate_jump.jump and alternate_jump.jump_pressed

    accessibility.remap("jump", "W", slot=1)
    assert accessibility.keyboard_alternates["jump"] == "W"
    assert accessibility.keyboard_alternates["up"] == "Space"

    accessibility.keyboard_alternates["action"] = ""
    with pytest.raises(ValueError, match="empty alternate"):
        accessibility.remap("action", "Z", slot=1)
    assert accessibility.keyboard["jump"] == "X"
    assert accessibility.keyboard["action"] == "Z"


def test_gamepad_action_buttons_are_remappable_by_physical_index():
    accessibility = Accessibility()
    accessibility.remap("jump", "RB", device="gamepad")
    assert accessibility.gamepad["jump"] == "RB"
    assert accessibility.gamepad["item"] == "A"

    state = _joystick_state(
        {7: _FakeJoystick(7, 0.0, {5})},  # type: ignore[dict-item]
        {(7, 5)},
        accessibility,
    )
    mapped = _map_keys(_Held(), set(), state, accessibility)
    assert mapped.jump and mapped.jump_pressed

    old_default = _joystick_state(
        {7: _FakeJoystick(7, 0.0, {0})},  # type: ignore[dict-item]
        {(7, 0)},
        accessibility,
    )
    old_mapped = _map_keys(_Held(), set(), old_default, accessibility)
    assert not old_mapped.jump
    assert old_mapped.item


def test_accessibility_record_round_trip_and_invalid_values_fail_to_defaults():
    accessibility = Accessibility()
    accessibility.remap("jump", "Q")
    accessibility.remap("pause", "Button 11", device="gamepad")
    restored = Accessibility.from_record(accessibility.to_record())
    assert restored.keyboard == accessibility.keyboard
    assert restored.keyboard_alternates == accessibility.keyboard_alternates
    assert restored.gamepad == accessibility.gamepad

    invalid = Accessibility.from_record(
        {
            "keyboard": {"jump": "\n"},
            "keyboardAlternates": {"jump": 3, "action": "Z"},
            "gamepad": {"jump": "Button 999"},
        }
    )
    assert invalid.keyboard["jump"] == DEFAULT_KEYBOARD["jump"]
    assert invalid.keyboard_alternates["jump"] == DEFAULT_KEYBOARD_ALTERNATES["jump"]
    assert invalid.keyboard_alternates["action"] == ""
    assert invalid.gamepad["jump"] == DEFAULT_GAMEPAD["jump"]


def test_pause_remap_ui_captures_resets_and_persists_keyboard_binding(tmp_path: Path):
    sim = GameSim.from_play_now("remap-save")
    sim.scene = "pause"
    sim.pause_cursor = sim.pause_rows().index("controls")
    sim.step(InputState(jump_pressed=True))
    assert sim.scene == "remap"

    sim.remap_cursor = sim.remap_actions.index("jump")
    identity_before = sim.identity_digest
    sim.step(InputState(jump_pressed=True))
    assert sim.remap_waiting
    assert sim.capture_remap_key("Q")
    assert not sim.remap_waiting
    assert sim.accessibility.keyboard["jump"] == "Q"
    assert sim.settings["accessibility"]["keyboard"]["jump"] == "Q"
    assert sim.identity_digest == identity_before

    sim.save_path = tmp_path / "remapped-save.json"
    sim.save_to_disk()
    restored = GameSim.from_play_now("other")
    restored.save_path = sim.save_path
    restored.load_from_disk()
    assert restored.accessibility.keyboard["jump"] == "Q"
    assert _map_keys(_Held(), {pygame.K_q}, {}, restored.accessibility).jump_pressed

    restored.scene = "remap"
    restored.remap_device = "keyboard"
    restored.remap_cursor = restored.remap_actions.index("jump")
    restored.step(InputState(action_pressed=True))
    assert restored.accessibility.keyboard["jump"] == DEFAULT_KEYBOARD["jump"]
    restored.step(InputState(item=True))
    assert restored.accessibility.keyboard_alternates == DEFAULT_KEYBOARD_ALTERNATES

    restored.remap_slot = 1
    restored.remap_cursor = restored.remap_actions.index("jump")
    restored.step(InputState(jump_pressed=True))
    assert restored.capture_remap_key("Backspace")
    assert restored.accessibility.keyboard_alternates["jump"] == ""


def test_remap_ui_supports_gamepad_capture_reserved_key_rejection_and_rendering():
    pygame.init()
    pygame.display.set_mode((1, 1))
    sim = GameSim.from_play_now("remap-render")
    sim.scene = "remap"
    sim.remap_feedback = "Choose an action, then bind it."
    sim.step(InputState(turn_pressed=True))
    assert sim.remap_device == "gamepad"
    sim.remap_cursor = sim.remap_actions.index("jump")
    sim.step(InputState(jump_pressed=True))
    assert sim.capture_remap_button(10)
    assert sim.accessibility.gamepad["jump"] == "Button 10"
    remapped = _map_keys(
        _Held(),
        set(),
        _joystick_state(
            {5: _FakeJoystick(5, 0.0, {10})},  # type: ignore[dict-item]
            {(5, 10)},
            sim.accessibility,
        ),
        sim.accessibility,
    )
    assert remapped.jump and remapped.jump_pressed
    assert Renderer._binding_pair(sim, "jump") == "Z/B10"
    assert sim.prompt_binding("jump", compact=True) == "B10"
    assert sim.prompt_binding("right", compact=True) == "PAD"

    sim.remap_device = "keyboard"
    sim.remap_cursor = sim.remap_actions.index("action")
    sim.step(InputState(jump_pressed=True))
    before = sim.accessibility.keyboard["action"]
    assert sim.capture_remap_key("F5")
    assert sim.remap_waiting
    assert sim.accessibility.keyboard["action"] == before
    assert "reserved" in sim.remap_feedback
    assert sim.capture_remap_key("Escape")
    assert not sim.remap_waiting

    renderer = Renderer()
    for fidelity in ("sixteen-bit", "high", "ultra"):
        sim.set_presentation(fidelity=fidelity, display="clean")
        for device in ("keyboard", "gamepad"):
            sim.last_input_device = device
            sim.scene = "remap"
            frame = renderer.frame(sim)
            assert frame.get_width() > 0 and frame.get_height() > 0
