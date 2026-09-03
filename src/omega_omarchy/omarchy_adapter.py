"""Omarchy theme, plugin, and packaging boundary — real contracts, not fakes."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PLUGIN_SCHEMA_VERSION = 1
PLUGIN_ID = "omega.omarchy"
DEFAULT_THEME = {
    "mode": "dark",
    "accent": "#7aa2f7",
    "selection": "#292e42",
    "muted": "#414868",
    "background": "#1a1b26",
    "dark_background": "#13141c",
    "darker_background": "#0e0e14",
    "lighter_background": "#24283b",
    "foreground": "#a9b1d6",
    "dark_foreground": "#565f89",
    "light_foreground": "#b4bee6",
    "bright_foreground": "#c0caf5",
    "red": "#f7768e",
    "yellow": "#e0af68",
    "orange": "#eb927b",
    "green": "#9ece6a",
    "cyan": "#449dab",
    "blue": "#7aa2f7",
    "magenta": "#ad8ee6",
    "brown": "#75493d",
    "bright_red": "#ff7a93",
    "bright_yellow": "#ff9e64",
    "bright_green": "#b9f27c",
    "bright_cyan": "#0db9d7",
    "bright_blue": "#7da6ff",
    "bright_magenta": "#bb9af7",
}


def plugin_manifest() -> dict[str, Any]:
    """The shipped Omarchy plugin manifest. Shape matches Omarchy schemaVersion 1."""

    path = Path(__file__).resolve().parents[2] / "integrations" / "omarchy-plugin" / "manifest.json"
    if path.is_file():
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schemaVersion": PLUGIN_SCHEMA_VERSION,
        "id": PLUGIN_ID,
        "name": "Omega Omarchy",
        "version": "0.1.0",
        "author": "Omega Omarchy",
        "description": "Launch Omega Omarchy and sync the active Omarchy theme",
        "license": "MIT",
        "kinds": ["panel", "bar-widget"],
        "entryPoints": {"panel": "plugin/Panel.qml", "barWidget": "plugin/BarWidget.qml"},
        "barWidget": {
            "displayName": "Omega Omarchy",
            "description": "Play Omega Omarchy",
            "category": "Tools",
            "allowMultiple": False,
            "defaultSection": "right",
        },
        "keepLoaded": True,
    }


def validate_plugin_manifest(manifest: dict[str, Any]) -> list[str]:
    errors = []
    if manifest.get("schemaVersion") != 1:
        errors.append("schemaVersion")
    for key in ("id", "name", "version", "kinds", "entryPoints"):
        if key not in manifest:
            errors.append(key)
    if "omarchy." in str(manifest.get("id", "")) and not str(manifest.get("id")).startswith("omarchy."):
        pass
    plugin_id = str(manifest.get("id", ""))
    if plugin_id.startswith("omarchy."):
        errors.append("reserved-id-namespace")
    kinds = manifest.get("kinds") or []
    entries = manifest.get("entryPoints") or {}
    for kind in kinds:
        expected = {
            "panel": "panel",
            "bar-widget": "barWidget",
            "overlay": "overlay",
            "menu": "menu",
            "service": "service",
            "bar": "bar",
        }.get(kind)
        if expected and expected not in entries:
            errors.append(f"missing-entry:{kind}")
        rel = entries.get(expected, "")
        if rel.startswith("/") or ".." in Path(str(rel)).parts:
            errors.append("unsafe-entry-path")
    return errors


def parse_theme_colors(text: str) -> dict[str, str]:
    data = tomllib.loads(text)
    colors = {key: value for key, value in data.items() if isinstance(value, str) and value.startswith("#")}
    if "background" not in colors or "foreground" not in colors:
        raise ValueError("theme missing background/foreground")
    return colors


def load_omarchy_theme(path: Path | None = None) -> dict[str, str]:
    """Read an Omarchy colors.toml if present; otherwise the pinned Tokyo Night defaults."""

    candidates = []
    if path is not None:
        candidates.append(Path(path))
    home = Path.home()
    candidates.extend(
        [
            home / ".config/omarchy/current/theme/colors.toml",
            home / ".config/omarchy/themes/tokyo-night/colors.toml",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return parse_theme_colors(candidate.read_text(encoding="utf-8"))
    return dict(DEFAULT_THEME)


def theme_to_game_palette(theme: dict[str, str]) -> dict[str, tuple[int, int, int]]:
    def hx(key: str, fallback: str) -> tuple[int, int, int]:
        raw = theme.get(key, fallback).lstrip("#")
        return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)

    return {
        "bg": hx("background", "#1a1b26"),
        "fg": hx("foreground", "#a9b1d6"),
        "accent": hx("accent", "#7aa2f7"),
        "green": hx("green", "#9ece6a"),
        "cyan": hx("cyan", "#449dab"),
        "red": hx("red", "#f7768e"),
        "yellow": hx("yellow", "#e0af68"),
        "orange": hx("orange", "#eb927b"),
        "brown": hx("brown", "#75493d"),
        "bright_green": hx("bright_green", "#b9f27c"),
        "dark": hx("darker_background", "#0e0e14"),
        "muted": hx("muted", "#414868"),
        "fg": hx("foreground", "#a9b1d6"),
    }


def discover_agent_command() -> list[str] | None:
    """Best-effort discovery of a configured Omarchy agent. Never required."""

    import shutil

    for name in ("omarchy-agent", "grok", "claude", "codex"):
        path = shutil.which(name)
        if path:
            return [path]
    return None
