"""Baseline accessibility: remapping, reduced motion, CRT independence, assists."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_KEYBOARD = {
    "left": "Left",
    "right": "Right",
    "up": "Up",
    "down": "Down",
    "jump": "Z",
    "action": "X",
    "item": "C",
    "interact": "E",
    "turn": "R",
    "customize": "Tab",
    "pause": "Escape",
}

DEFAULT_KEYBOARD_ALTERNATES = {
    "left": "A",
    "right": "D",
    "up": "W",
    "down": "S",
    "jump": "Space",
    "action": "",
    "item": "",
    "interact": "Return",
    "turn": "",
    "customize": "",
    "pause": "",
}

KEYBOARD_ACTIONS = tuple(DEFAULT_KEYBOARD)
GAMEPAD_ACTIONS = ("jump", "action", "interact", "turn", "item", "customize", "pause")
ACTION_LABELS = {
    "left": "MOVE LEFT",
    "right": "MOVE RIGHT",
    "up": "MOVE UP",
    "down": "MOVE DOWN",
    "jump": "JUMP / CONFIRM",
    "action": "KICK / ACTION",
    "item": "USE ITEM",
    "interact": "INTERACT",
    "turn": "REUSE / TURN",
    "customize": "CUSTOMIZE",
    "pause": "PAUSE",
}

DEFAULT_GAMEPAD = {
    "left": "LeftStick/DPad",
    "jump": "A",
    "action": "B",
    "interact": "X",
    "turn": "Y",
    "item": "RB",
    "customize": "Back/View",
    "pause": "Start",
}

GAMEPAD_BUTTON_NAMES = {
    0: "A",
    1: "B",
    2: "X",
    3: "Y",
    4: "LB",
    5: "RB",
    6: "Back/View",
    7: "Start",
    8: "LS",
    9: "RS",
}
_GAMEPAD_NAME_TO_BUTTON = {
    name.casefold(): index for index, name in GAMEPAD_BUTTON_NAMES.items()
}


def gamepad_button_name(index: int) -> str:
    if not 0 <= index <= 31:
        raise ValueError("gamepad button index must be 0..31")
    return GAMEPAD_BUTTON_NAMES.get(index, f"Button {index}")


def gamepad_button_index(binding: str) -> int:
    token = str(binding).strip()
    known = _GAMEPAD_NAME_TO_BUTTON.get(token.casefold())
    if known is not None:
        return known
    if token.casefold().startswith("button "):
        try:
            index = int(token.split()[-1])
        except ValueError as exc:
            raise ValueError(f"invalid gamepad binding {binding}") from exc
        if 0 <= index <= 31:
            return index
    raise ValueError(f"invalid gamepad binding {binding}")


def _safe_binding(value: Any, fallback: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if not value and allow_empty:
        return ""
    if not value or len(value) > 32 or not value.isprintable():
        return fallback
    return value


@dataclass
class Accessibility:
    reduced_motion: bool = False
    precision_assist: bool = False
    high_contrast: bool = False
    text_scale: float = 1.0
    subtitle: bool = True
    hold_to_repeat: bool = False
    keyboard: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_KEYBOARD))
    keyboard_alternates: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_KEYBOARD_ALTERNATES)
    )
    gamepad: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_GAMEPAD))
    crt_master: bool = False
    crt: dict[str, float] = field(default_factory=lambda: {
        "intensity": 0.0,
        "scanline": 0.0,
        "curvatureControl": 0.0,
        "phosphor": 0.0,
        "scanlines": 0.0,
        "scanlineSize": 0.0,
        "curvature": 0.0,
        "chromatic": 0.0,
        "bloom": 0.0,
        "noise": 0.0,
        "vignette": 0.0,
        "persistence": 0.0,
        "mask": 0.0,
        "enabled": 0.0,
    })

    def remap(self, action: str, key: str, *, device: str = "keyboard", slot: int = 0) -> None:
        if device not in {"keyboard", "gamepad"}:
            raise ValueError(f"unsupported input device {device}")
        if device == "keyboard":
            if action not in KEYBOARD_ACTIONS:
                raise KeyError(action)
            if slot not in {0, 1}:
                raise ValueError("keyboard binding slot must be 0 or 1")
            table = self.keyboard if slot == 0 else self.keyboard_alternates
            key = _safe_binding(key, "", allow_empty=slot == 1)
            if not key and slot == 0:
                raise ValueError("primary keyboard binding may not be empty")
            previous = table[action]
            if key:
                for candidate_slot, candidate_table in enumerate(
                    (self.keyboard, self.keyboard_alternates)
                ):
                    for other in KEYBOARD_ACTIONS:
                        if (
                            (other != action or candidate_slot != slot)
                            and candidate_table.get(other, "").casefold() == key.casefold()
                        ):
                            if candidate_slot == 0 and not previous:
                                raise ValueError(
                                    "an empty alternate cannot displace a primary binding"
                                )
                            candidate_table[other] = previous
                            break
            table[action] = key
            return
        if action not in GAMEPAD_ACTIONS:
            raise KeyError(action)
        if slot != 0:
            raise ValueError("gamepad bindings have one button slot")
        key = gamepad_button_name(gamepad_button_index(key))
        previous = self.gamepad[action]
        for other in GAMEPAD_ACTIONS:
            if other != action and self.gamepad.get(other) == key:
                self.gamepad[other] = previous
                break
        self.gamepad[action] = key

    def reset_binding(self, action: str, *, device: str = "keyboard", slot: int = 0) -> None:
        if device == "keyboard":
            defaults = DEFAULT_KEYBOARD if slot == 0 else DEFAULT_KEYBOARD_ALTERNATES
            if action not in defaults:
                raise KeyError(action)
            self.remap(action, defaults[action], device=device, slot=slot)
            return
        if action not in GAMEPAD_ACTIONS:
            raise KeyError(action)
        self.remap(action, DEFAULT_GAMEPAD[action], device=device)

    def reset_controls(self, device: str | None = None) -> None:
        if device in {None, "keyboard"}:
            self.keyboard = dict(DEFAULT_KEYBOARD)
            self.keyboard_alternates = dict(DEFAULT_KEYBOARD_ALTERNATES)
        if device in {None, "gamepad"}:
            self.gamepad = dict(DEFAULT_GAMEPAD)
        if device not in {None, "keyboard", "gamepad"}:
            raise ValueError(f"unsupported input device {device}")

    def binding(self, action: str, *, device: str = "keyboard", slot: int = 0) -> str:
        if device == "keyboard":
            table = self.keyboard if slot == 0 else self.keyboard_alternates
            return table[action]
        return self.gamepad[action]

    @classmethod
    def from_record(cls, record: Any) -> Accessibility:
        result = cls()
        if not isinstance(record, dict):
            return result
        for field_name, record_name in (
            ("reduced_motion", "reducedMotion"),
            ("precision_assist", "precisionAssist"),
            ("high_contrast", "highContrast"),
            ("subtitle", "subtitle"),
            ("hold_to_repeat", "holdToRepeat"),
            ("crt_master", "crtMaster"),
        ):
            if isinstance(record.get(record_name), bool):
                setattr(result, field_name, record[record_name])
        text_scale = record.get("textScale")
        if not isinstance(text_scale, bool) and isinstance(text_scale, (int, float)):
            result.text_scale = max(0.75, min(1.5, float(text_scale)))
        keyboard = record.get("keyboard")
        alternates = record.get("keyboardAlternates")
        gamepad = record.get("gamepad")
        if isinstance(keyboard, dict):
            for action, fallback in DEFAULT_KEYBOARD.items():
                result.remap(
                    action,
                    _safe_binding(keyboard.get(action), fallback),
                    device="keyboard",
                    slot=0,
                )
        if isinstance(alternates, dict):
            for action, fallback in DEFAULT_KEYBOARD_ALTERNATES.items():
                try:
                    result.remap(
                        action,
                        _safe_binding(alternates.get(action), fallback, allow_empty=True),
                        device="keyboard",
                        slot=1,
                    )
                except ValueError:
                    result.keyboard_alternates[action] = fallback
        if isinstance(gamepad, dict):
            for action in GAMEPAD_ACTIONS:
                value = _safe_binding(gamepad.get(action), DEFAULT_GAMEPAD[action])
                try:
                    result.remap(action, value, device="gamepad")
                except ValueError:
                    result.remap(action, DEFAULT_GAMEPAD[action], device="gamepad")
        crt = record.get("crt")
        if isinstance(crt, dict):
            result.crt.update(
                {
                    str(key): float(value)
                    for key, value in crt.items()
                    if isinstance(key, str)
                    and not isinstance(value, bool)
                    and isinstance(value, (int, float))
                }
            )
        return result

    def to_record(self) -> dict[str, Any]:
        return {
            "crt": self.crt,
            "crtMaster": self.crt_master,
            "gamepad": dict(self.gamepad),
            "highContrast": self.high_contrast,
            "holdToRepeat": self.hold_to_repeat,
            "keyboard": dict(self.keyboard),
            "keyboardAlternates": dict(self.keyboard_alternates),
            "precisionAssist": self.precision_assist,
            "reducedMotion": self.reduced_motion,
            "subtitle": self.subtitle,
            "textScale": self.text_scale,
        }
