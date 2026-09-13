"""Package the local launch site, optionally including a fresh browser game."""
from __future__ import annotations
import argparse
from html import escape
from pathlib import Path
import shutil
import sys
from news_build import build_news, display_date, latest_announcement

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "website"
sys.path.insert(0, str(ROOT / "src"))


def build(out: Path, *, game_dir: Path | None = None, with_game: bool = True) -> Path:
    out = out.resolve()
    if out in {ROOT, SOURCE, Path.home(), Path('/')} or out in SOURCE.parents or SOURCE in out.parents:
        raise ValueError("Choose an output directory outside the website source.")
    out.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "style.css", "site.js", "theme.js", "motion.js", "motion-model.mjs", "news.js", "news-model.mjs", "robots.txt", "sitemap.xml", "404.html"):
        if (SOURCE / name).is_file():
            shutil.copyfile(SOURCE / name, out / name)
    shutil.copytree(SOURCE / "assets", out / "assets", dirs_exist_ok=True)
    announcement = latest_announcement(SOURCE)
    index_path = out / "index.html"
    page = index_path.read_text()
    page = page.replace("<!-- LAUNCH_URL -->", escape(announcement["url"], quote=True))
    page = page.replace("<!-- LAUNCH_TITLE -->", escape(announcement["title"]))
    page = page.replace("<!-- LAUNCH_DATETIME -->", escape(announcement["date"], quote=True))
    page = page.replace("<!-- LAUNCH_DATE -->", display_date(announcement["date"]))
    index_path.write_text(page)
    build_news(SOURCE, out, ROOT)
    if game_dir:
        game_dir = game_dir.resolve()
        if not (game_dir / "index.html").is_file():
            raise ValueError("The supplied game directory has no index.html.")
        if game_dir == out or game_dir in out.parents or out in game_dir.parents:
            raise ValueError("Keep the supplied game and website output in separate directories.")
        shutil.copytree(game_dir, out / "play", dirs_exist_ok=True)
    elif with_game:
        from omega_omarchy.web_build import build_web
        build_web(out / "play")
    for source, target in ((ROOT / "LICENSE", "CODE-LICENSE.txt"), (ROOT / "ASSET-LICENSE.md", "ASSET-LICENSE.md"),
                           (ROOT / "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md")):
        shutil.copyfile(source, out / target)
    print(f"WEBSITE={out}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist/website")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--game-dir", type=Path, help="Reuse an already built browser game.")
    mode.add_argument("--landing-only", action="store_true", help="Update the page without rebuilding the browser game.")
    args = parser.parse_args()
    build(args.out, game_dir=args.game_dir, with_game=not args.landing_only)
