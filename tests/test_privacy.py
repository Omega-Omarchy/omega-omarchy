from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gitignore_excludes_private_design_and_refs():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for line in (
        "/docs/OMEGA-OMARCHY-GAME-DESIGN.md",
        "/docs/ONE-SHOT-DEVELOPMENT-GOAL.md",
        "/docs/references/",
        ".env",
        "/docs/records/",
        ".cache/",
    ):
        assert line in text


def test_no_reference_jpegs_in_packaged_trees():
    forbidden = []
    for path in (ROOT / "assets").rglob("*"):
        if path.suffix.lower() in {".jpg", ".jpeg"} and "reference" in path.name.lower():
            forbidden.append(path)
    for path in (ROOT / "dist").rglob("*") if (ROOT / "dist").exists() else []:
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            forbidden.append(path)
    assert forbidden == []
    # shipped installer copy must be Play Now
    installer = (ROOT / "src/omega_omarchy/installer.py").read_text(encoding="utf-8")
    assert "Play Now" in installer
    assert "Reboot Now" in installer  # mentioned as the replaced Omarchy label
