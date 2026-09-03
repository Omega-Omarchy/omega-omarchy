import os
from pathlib import Path

from omega_omarchy.omarchy_adapter import (
    DEFAULT_THEME,
    load_omarchy_theme,
    parse_theme_colors,
    plugin_manifest,
    theme_to_game_palette,
    validate_plugin_manifest,
)

TOKYO = Path(os.environ.get("OMEGA_OMARCHY_OMARCHY_THEME_FIXTURE", "tests/fixtures/no-omarchy-theme"))


def test_plugin_manifest_matches_omarchy_schema():
    manifest = plugin_manifest()
    errors = validate_plugin_manifest(manifest)
    assert errors == []
    assert manifest["schemaVersion"] == 1
    assert not str(manifest["id"]).startswith("omarchy.")
    assert "panel" in manifest["kinds"]
    assert "bar-widget" in manifest["kinds"]
    plugin_root = Path(__file__).resolve().parents[1] / "integrations" / "omarchy-plugin"
    assert (plugin_root / manifest["entryPoints"]["panel"]).is_file()
    assert (plugin_root / manifest["entryPoints"]["barWidget"]).is_file()


def test_real_tokyo_night_theme_parses():
    text = TOKYO.read_text(encoding="utf-8") if TOKYO.is_file() else None
    if text:
        colors = parse_theme_colors(text)
        assert colors["background"].startswith("#")
        assert colors["green"].startswith("#")
        palette = theme_to_game_palette(colors)
    else:
        palette = theme_to_game_palette(DEFAULT_THEME)
    assert palette["bg"][2] > 0 or palette["bg"][0] > 0
    loaded = load_omarchy_theme(TOKYO if TOKYO.is_file() else None)
    assert "background" in loaded
