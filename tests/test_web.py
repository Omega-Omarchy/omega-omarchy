import shutil
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from omega_omarchy.web_build import (
    CHARACTER_CONTROLS,
    WEB_BACKGROUNDS,
    _encode_web_audio,
    _repair_pygbag_launcher,
    _store_web_archive,
    _replace_directory,
    stage_web,
)


def test_web_character_tools_can_be_dismissed():
    assert 'id="character-tools-close"' in CHARACTER_CONTROLS
    assert "omega-character-tools-hidden" in CHARACTER_CONTROLS
    assert "Hide custom character tools" in CHARACTER_CONTROLS


def test_web_output_replacement_refuses_repository_root():
    from omega_omarchy.web_build import ROOT

    with pytest.raises(ValueError, match="unsafe web output"):
        _replace_directory(ROOT)


def test_web_stage_contains_authoritative_runtime_and_bounded_art(tmp_path):
    stage = stage_web(tmp_path / "omega-omarchy", seed="browser-seed")
    source = (stage / "main.py").read_text(encoding="utf-8")

    assert "await run_game_async(seed='browser-seed')" in source
    assert "import pygame" in source
    assert (stage / "omega_omarchy" / "sim.py").is_file()
    assert (stage / "omega_omarchy" / "render.py").is_file()
    assert (stage / "assets/ui/social/goliath-profile.png").is_file()
    assert not (stage / "omega_omarchy" / "assets.py").exists()
    assert not (stage / "omega_omarchy" / "character_build.py").exists()
    assert (stage / "omega_omarchy" / "character_pack.py").is_file()
    assert (stage / "assets/character-creation/agent-kit.zip").is_file()
    for character in ("omarch-king", "omarch-queen"):
        assert (stage / "assets/character-packs" / character / "manifest.json").is_file()
        assert (stage / "assets/character-packs" / character / "ultra/prologue-transfer.png").is_file()
    assert not (stage / "omega_omarchy" / "audio_build.py").exists()
    assert not (stage / "omega_omarchy" / "credits_build.py").exists()
    assert (stage / "omega_omarchy/data/credits.json").is_file()
    assert (stage / "assets/ui/credits/credits-sans.otf").is_file()
    assert (stage / "assets/audio/ultra/music/credits-roll.ogg").is_file()
    assert not (stage / "omega_omarchy" / "music_diagnostic.py").exists()
    assert not (stage / "assets" / "source").exists()
    assert (stage / "assets" / "audio" / "audio-manifest.json").is_file()
    for fidelity in ("sixteen-bit", "high", "ultra"):
        backgrounds = stage / "assets" / "fidelity" / fidelity / "bg"
        assert {path.name for path in backgrounds.iterdir()} == set(WEB_BACKGROUNDS)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is a web-build prerequisite")
def test_web_audio_is_transcoded_to_browser_safe_ogg(tmp_path):
    stage = stage_web(tmp_path / "omega-omarchy")
    _encode_web_audio(stage)
    audio = stage / "assets" / "audio"

    assert not list(audio.rglob("*.wav"))
    assert not list(audio.rglob("*.flac"))
    encoded = sorted(audio.rglob("*.ogg"))
    assert encoded
    assert all(path.read_bytes().startswith(b"OggS") for path in encoded)
    for fidelity in ("sixteen-bit", "high", "ultra"):
        assert (audio / fidelity / "music" / "credits-theme.ogg").is_file()


def test_launcher_workarounds_are_explicit_and_archive_is_stored(tmp_path):
    built = tmp_path / "web"
    built.mkdir()
    (built / "index.html").write_text(
        '<html><script src="https://pygame-web.github.io/cdn/0.9.3//browserfs.min.js"></script>\n'
        "appdir.mkdir()\n"
        "    # unpack filesystem from compressed archive into work dir\n"
        "    if platform.window.location.host.find('.itch.zone')>0:\n"
        "    # preloader will change to work dir and prepend it to sys.path\n"
        "    # wait preloading complete : that includes images and wasm compilation of bundled modules\n"
        "    await shell.source(main, callback=ui_callback)\n"
        "        platform.window.infobox.innerText = msg\n"
        "#7f7f7f background-color:powderblue;\n"
        "background: green;\n            color: blue;\n"
        '<div id="infobox">Loading, please wait ...</div>\n'
        "</html>",
        encoding="utf-8",
    )
    apk = built / "omega-omarchy.apk"
    with ZipFile(apk, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("assets/main.py", "print('ok')")
    (built / "omega-omarchy.tar.gz").write_bytes(b"redundant")

    _store_web_archive(apk)
    _repair_pygbag_launcher(built)

    with ZipFile(apk) as archive:
        entries = archive.infolist()
        assert {entry.compress_type for entry in entries} == {ZIP_STORED}
        assert {entry.date_time for entry in entries} == {(2024, 1, 1, 0, 0, 0)}
        assert {entry.create_system for entry in entries} == {3}
    html = (built / "index.html").read_text(encoding="utf-8")
    assert html.startswith('<script src="browserfs.min.js"></script>')
    assert "github.io/cdn/0.9.3//browserfs.min.js" not in html
    assert 'await aio.pep0723.pip_install("pygame")' in html
    assert "exec(compile(main.read_text()" in html
    assert "if True:  # the build replaces this with a stored ZIP" in html
    assert 'id="infobox-build"' in html
    assert "Omega Omarchy" in html
    assert "Loading, please wait ..." in html
    assert '(document.getElementById("infobox-msg") or platform.window.infobox).innerText' in html
    assert not (built / "omega-omarchy.tar.gz").exists()
    assert (built / "browserfs.min.js").stat().st_size > 200_000
    assert (built / "BROWSERFS-LICENSE.txt").is_file()
