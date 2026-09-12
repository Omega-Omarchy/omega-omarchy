"""Render announcements and a real git-history fallback for the News route."""
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import subprocess

REPOSITORY = "Omega-Omarchy/omega-omarchy"
REPO_URL = f"https://github.com/{REPOSITORY}"


def commits(root: Path) -> list[dict]:
    result = subprocess.run(
        ["git", "log", "-20", "--format=%H%x00%cI%x00%s%x1e"], cwd=root,
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return []  # Source archives still get announcements and live GitHub updates.
    entries = []
    for record in result.stdout.split("\x1e"):
        if not record.strip():
            continue
        sha, date, title = record.strip().split("\x00", 2)
        if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
            continue
        entries.append({"id": f"commit-{sha}", "type": "commit", "date": date,
                        "title": title, "paragraphs": [], "sha": sha[:7],
                        "url": f"{REPO_URL}/commit/{sha}"})
    return entries


def pin_to_top(entries: list[dict]) -> list[dict]:
    """Keep the freshest News announcement at the top of the All feed by
    default. A newer News entry automatically takes over that spot as it's
    added; an entry explicitly marked pinned overrides the default choice
    regardless of date."""
    pin = next((e for e in entries if e.get("pinned")), None)
    if pin is None:
        pin = next((e for e in entries if e["type"] == "news"), None)
    if pin is None:
        return entries
    return [pin, *(e for e in entries if e is not pin)]


def render_entry(entry: dict) -> str:
    e = lambda value: escape(str(value), quote=True)
    date = datetime.fromisoformat(entry["date"]).astimezone(timezone.utc)
    label = {"news": "News", "commit": "Commit", "release": "Release"}[entry["type"]]
    paragraphs = "".join(f"<p>{e(p)}</p>" for p in entry.get("paragraphs", []))
    sha = f'<span class="news-sha">{e(entry["sha"])}</span>' if entry.get("sha") else ""
    return (f'<article class="news-entry" id="{e(entry["id"])}" data-kind="{e(entry["type"])}">'
            f'<div class="news-meta"><time datetime="{e(entry["date"])}">{date.strftime("%b")} {date.day}, {date.year}</time>'
            f'<span class="news-kind">{label}</span>{sha}</div>'
            f'<div class="news-copy"><h2><a href="{e(entry["url"])}">{e(entry["title"])}</a></h2>{paragraphs}</div></article>')


def build_news(source: Path, out: Path, root: Path) -> dict:
    editorial = json.loads((source / "news/editorial.json").read_text())
    ids = set()
    pinned = 0
    for item in editorial:
        if item["type"] != "news" or not re.fullmatch(r"[a-z0-9-]+", item["id"]) or item["id"] in ids:
            raise ValueError("News announcements need unique lowercase slug IDs and type news.")
        if item["url"] != f'/news/#{item["id"]}':
            raise ValueError("Announcement URLs must point to their News permalink.")
        if datetime.fromisoformat(item["date"]).tzinfo is None:
            raise ValueError("News dates must include a timezone offset.")
        if "pinned" in item and item["pinned"] is not True:
            raise ValueError("An announcement's pinned field, when present, must be true.")
        pinned += item.get("pinned", False)
        ids.add(item["id"])
    if pinned > 1:
        raise ValueError("Only one announcement may set pinned: true.")
    snapshot = {"repository": REPOSITORY, "builtAt": datetime.now(timezone.utc).isoformat(),
                "editorial": editorial, "commits": commits(root), "releases": []}
    entries = sorted(editorial + snapshot["commits"], key=lambda item: datetime.fromisoformat(item["date"]), reverse=True)
    entries = pin_to_top(entries)
    home = (source / "index.html").read_text()
    header = re.search(r'<header class="site-header">.*?</header>', home, re.S).group(0)
    header = header.replace('href="/news/"', 'href="/news/" aria-current="page"')
    footer = re.search(r'<footer class="footer wrap">.*?</footer>', home, re.S).group(0)
    footer = footer.replace('href="#"', 'href="/"').replace('src="assets/', 'src="/assets/')
    page = (source / "news/template.html").read_text()
    page = page.replace("<!-- SITE_HEADER -->", header).replace("<!-- SITE_FOOTER -->", footer)
    page = page.replace("<!-- NEWS_ENTRIES -->", "\n".join(map(render_entry, entries)))
    # A commit subject or announcement must never terminate the inert JSON script.
    page = page.replace("<!-- NEWS_DATA -->", json.dumps(snapshot, ensure_ascii=True).replace("<", "\\u003c"))
    (out / "news").mkdir(exist_ok=True)
    (out / "news/index.html").write_text(page)
    return snapshot
