"""Compile reviewed credit inputs and Git attribution into a runtime manifest.

No network lookups or working-tree authorship guesses. Paths and commit IDs
remain in the manifest so every engineering credit can be audited.
"""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib

from .campaign import CAMPAIGN_ROSTER
from .combat import ENEMY_ARCHETYPES

ROOT = Path(__file__).resolve().parents[2]


def song_credit(song: dict, root: Path = ROOT) -> dict:
    """Credit only the source author/artist tag, or an explicit fallback."""
    credit = {"title": song["title"]}
    source = song.get("source")
    if source:
        path = (root / source).resolve(strict=True)
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Music credit sources must be inside the project")
        metadata = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format_tags=author,artist:stream_tags=author,artist", "-of", "json", str(path),
        ], text=True))
        credit.update(source=source, sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest())
        containers = [metadata.get("format", {}), *metadata.get("streams", [])]
        for container in containers:
            tags = {key.casefold(): str(value).strip() for key, value in container.get("tags", {}).items()}
            for field in ("author", "artist"):
                if tags.get(field):
                    return {**credit, "artist": tags[field], "creditSource": f"embedded:{field}"}
    artist = str(song.get("artist") or "").strip()
    if not artist:
        raise ValueError(f"Missing author/artist credit for {song['title']}")
    return {**credit, "artist": artist, "creditSource": "external:credits/music.json"}

DEPARTMENTS = {
    "Gameplay engineering": ("src/omega_omarchy/sim.py", "src/omega_omarchy/physics.py", "src/omega_omarchy/combat.py", "src/omega_omarchy/skyway.py", "src/omega_omarchy/invisible_platform.py"),
    "World building & traversal": ("*generation*", "*chapter_design*", "*reachability*", "*edit_challenge*", "*level_editor*", "*zone_delta*", "*chapters/*", "tools/level-editor/*"),
    "Visual effects & animation": ("*render.py", "*articulation*", "assets/*", "*assets.py", "*refinement_art*"),
    "Character department": ("*character*",),
    "Story & installation": ("*installer*", "*campaign*", "*prologue*", "*content*", "*identity*"),
    "Music & sound engineering": ("*audio*", "*music*", "*chiptune*", "*vocal*", "*chip*"),
    "Accessibility & player experience": ("*accessibility*", "*presentation*", "*controls*", "*app.py"),
    "Quality assurance": ("tests/*", "*verify*", "*review*"),
    "Release engineering": (".github/*", "scripts/*", "tools/*", "*build*", "*requirements*", "pyproject.toml"),
    "Publicity & documentation": ("website/*", "docs/*", "*.md"),
    "Project contributors": ("*",),
}

# These deliberately excessive film jobs are authored comedy, not inferred
# claims about individual commits. Real path-based departments follow them.
FILM_CREW = {
    "a JEREMY DIXON production": ["Written and directed by", "Produced by", "Executive producer", "Associate producer", "Co-producer", "Producer's producer"],
    "Production office": ["Production manager", "Production coordinator", "First assistant director", "Second assistant director", "Second second assistant director", "Director of approved detours", "Office production assistant", "Keeper of the remaining budget"],
    "Camera department": ["Director of photography", "Camera operator", "First assistant camera", "Second assistant camera", "Steadicam operator", "Over-the-shoulder camera", "Over-the-other-shoulder camera", "Skyway aerial unit", "Lens cap continuity"],
    "Art department": ["Production designer", "Art director", "Set decorator", "Lead scenic artist", "Construction coordinator", "Invisible platform painter", "Walled Garden horticulturist", "Gate distressing", "Emergency ladder carpenter"],
    "Costume & creature shop": ["Costume designer", "Royal wardrobe supervisor", "Crown wrangler", "Hair and makeup", "Beard continuity", "Creature fabrication", "Hydra head count", "Penguin fitting room", "Claw articulation supervisor"],
    "Stunts & special effects": ["Stunt coordinator", "Double-jump double", "Slide safety supervisor", "Cannon launch double", "Fall-through floor specialist", "Portal ring technician", "Practical corruption effects", "Robot panic coordinator", "Apple-core demolition"],
    "Grip & electric": ["Gaffer", "Best boy electric", "Key grip", "Best boy grip", "Dolly grip", "Rigging gaffer", "Cable wrangler", "Ethernet cable wrangler", "Wi-Fi cable wrangler", "Super key grip"],
    "Visual effects": ["VFX supervisor", "VFX producer", "Pipeline technical director", "Compositing supervisor", "Lead compositor", "Rotoscope artist", "Matte painter", "Matchmove artist", "Lighting artist", "Creature effects artist", "Simulation technical director", "Orb tether solver", "Shimmer density technician", "Final pixel inspector"],
    "Editorial": ["Editor", "Assistant editor", "Assembly editor", "Online editor", "Offline editor", "Colorist", "Digital intermediate producer", "Title designer", "Credit roll length negotiator"],
    "Sound department": ["Supervising sound editor", "Sound designer", "Re-recording mixer", "Foley artist", "Foley recordist", "Dialogue editor", "Music supervisor", "Music editor", "Saw-wave restraint officer", "Seven-minute love-song liaison"],
    "Locations & transport": ["Location manager", "Corrupted Install location scout", "Dependency Mines unit manager", "Walled Garden gate liaison", "Cow Level livestock transport", "Robot parking marshal", "Portal traffic control", "Travel coordinator"],
    "Unit services": ["Craft services", "Second breakfast", "Coffee continuity", "Production accountant", "Payroll accountant", "One-person crowd coordinator", "Additional Jeremy Dixon", "Stand-in for Jeremy Dixon", "Person who stayed for the credits"],
}


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8")


def resolve_contributor(name: str, email: str, config: dict, *, github_login: str = "") -> tuple[str, str]:
    entries = config.get("contributors", {})
    match = re.fullmatch(r"(?:\d+\+)?([^@]+)@users\.noreply\.github\.com", email, re.I)
    login = match.group(1).lower() if match else github_login.lower()
    folded_name = name.casefold()
    folded_email = email.casefold()
    for key, item in entries.items():
        aliases = {str(alias).casefold() for alias in item.get("aliases", [])}
        aliases.add(key.casefold())
        display = str(item.get("name") or "").strip()
        if display:
            aliases.add(display.casefold())
        if login == key.lower() or folded_email in aliases or folded_name in aliases:
            login = key
            break
    if login:
        override = entries.get(login, {}).get("name")
        profile = config.get("github_profiles", {}).get(login, {}).get("name")
        return login, str(override or profile or login).strip()
    # A Git commit does not always identify a GitHub account. Do not invent one
    # from an arbitrary email local-part or query a changing profile at runtime.
    return "git:" + hashlib.sha256(email.lower().encode()).hexdigest()[:16], name


def history_attribution(root: Path, config: dict) -> tuple[list[dict], list[dict]]:
    people: dict[str, dict] = {}
    history = []
    for revision in sorted(_git(root, "rev-list", "HEAD").splitlines()):
        name, email, body = _git(root, "show", "-s", "--format=%an%x00%ae%x00%B", revision).split("\0", 2)
        paths = sorted(set(p for p in _git(root, "diff-tree", "--root", "-m", "--no-commit-id", "--name-only", "-r", "-z", revision).split("\0") if p))
        authors = [(name.strip(), email.strip()), *re.findall(r"^Co-authored-by:\s*(.*?)\s*<([^>]+)>\s*$", body, re.I | re.M)]
        ids = set()
        for index, (author, address) in enumerate(authors):
            hint = config.get("commit_logins", {}).get(revision, "") if index == 0 else ""
            login, display = resolve_contributor(author, address, config, github_login=hint)
            ids.add(login)
            person = people.setdefault(login, {"id": login, "name": display, "commits": set(), "paths": set()})
            person["commits"].add(revision)
            person["paths"].update(paths)
        history.append({"commit": revision, "contributors": sorted(ids), "paths": paths})
    result = [{**p, "commits": sorted(p["commits"]), "paths": sorted(p["paths"])} for p in people.values()]
    return sorted(result, key=lambda p: (p["name"].casefold(), p["id"])), history


def compile_credits(root: Path = ROOT) -> dict:
    config = tomllib.loads((root / "credits/contributors.toml").read_text(encoding="utf-8"))
    snapshot = root / "credits/github-identities.json"
    if snapshot.is_file():
        identities = json.loads(snapshot.read_text(encoding="utf-8"))
        config["commit_logins"] = identities.get("commits", {})
        config["github_profiles"] = {**identities.get("profiles", {}), **config.get("github_profiles", {})}
    foundation = json.loads((root / "credits/omacom-foundation.json").read_text(encoding="utf-8"))
    contributors, history = history_attribution(root, config)
    lead = config["production"]["lead"]
    lead_name = config["contributors"][lead]["name"]
    rows = [{"kind": "logo", "height": 90}]
    # Film-credit convention: section headers and credited names read in caps;
    # role descriptions stay in sentence case. `upper=False` opts a specific
    # heading out, for the one that stylizes only the embedded name.
    def heading(title, *, upper=True, subtitle=None): rows.append({"kind": "heading", "text": title.upper() if upper else title, "height": 34, "subtitle": subtitle})
    def pair(role, name): rows.append({"kind": "pair", "role": role, "name": name, "height": 12})
    def line(text): rows.append({"kind": "text", "text": text, "height": 14})
    line("A slightly corrupted installation.")
    line("A video game.")
    line("A motion picture.")
    line("Somehow, all three.")
    heading("Starring")
    pair("The player", "{CHARACTER}")
    pair("Decisions, mostly reversible", "YOU")
    for title, roles in FILM_CREW.items():
        heading(title, upper=(title != "a JEREMY DIXON production"))
        for role in roles: pair(role, lead_name.upper())
    heading("Built in the open")
    line("The following departments follow the Git history.")
    for department, patterns in DEPARTMENTS.items():
        names = []
        seen = set()
        for person in contributors:
            if not any(fnmatchcase(path, pattern) for path in person["paths"] for pattern in patterns):
                continue
            label = person["name"]
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(label)
        if names:
            heading(department)
            for name in names: line(name.upper())
    heading("Agent collaborators")
    line("CODEX / ASTRA")
    line("CODEX / SOL")
    line("GROK BUILD")
    line("GROK IMAGINE")
    line("CLAUDE / SONNET")
    line("CLAUDE / HAIKU")
    line("Code, artwork workflows, and patient pixel arguments")
    heading("Screen cast")
    for spec in CAMPAIGN_ROSTER: pair(spec.boss.name.upper(), "As themselves, eventually cooperative")
    enemies = sorted((root / "assets/fidelity/ultra/enemies").glob("*.png"))
    mobs = [{"id": p.stem, "name": ENEMY_ARCHETYPES.get(p.stem, (p.stem.replace("-", " ").title(),))[0]} for p in enemies if not p.stem.endswith("-converted")]
    mob_captions = {
        "cow": "Rather tipsy, but harmless",
        "llama": "Frequently mistaken for a large language model",
    }
    for mob in mobs:
        pair(mob["name"].upper(), mob_captions.get(mob["id"], "Additional institutional resistance"))
    pair("THE THREE ORBS", "Unscheduled mind maintenance")
    pair("THE APPLE-CORE CUSTODIANS", "Left unit / Right unit")
    pair("THE OMARCH KING & QUEEN", "Royal alternatives")
    heading("Music")
    music = json.loads((root / "credits/music.json").read_text(encoding="utf-8"))
    audio = json.loads((root / "assets/audio/audio-manifest.json").read_text(encoding="utf-8"))
    cue = audio["cues"][music["roll"]["cue"]]
    music["roll"]["duration"] = float(cue["durations"]["ultra"])
    if cue["loop"] or any(abs(value - music["roll"]["duration"]) > .04 for value in cue["durations"].values()):
        raise RuntimeError("The credit roll needs non-looping audio with matching tier durations.")
    music_credits = [song_credit(song, root) for song in music["songs"]]
    for song, credit in zip(music["songs"], music_credits):
        heading(credit["title"], subtitle=song.get("subtitle"))
        line(credit["artist"].upper())
        if song.get("cue") == music["roll"]["cue"]:
            music["roll"]["artist"] = credit["artist"]
    heading("Special Thanks")
    line("The Omacom Foundation and the Omarchy community")
    line("For the operating system. We supplied the corruption.")
    for group in foundation["groups"]:
        heading(group["title"])
        capped_names = [str(person_name).upper() for person_name in group["names"]]
        # One row per group; credits_render chunks these into 2-4 columns
        # (more columns as the compacted font shrinks, real estate
        # permitting) rather than a build-time-fixed pair-per-row grid.
        rows.append({"kind": "names", "names": capped_names, "height": 13, "compact": bool(group.get("compact", False))})
    heading("And to")
    for name in ["The Linux, Arch, and open-source communities", "pygame-ce, SDL, and the pygbag contributors", "Python, NumPy, Pillow, and FFmpeg contributors", "The Noto font project", "CatchyTune and the people who listen twice", "Everyone who reported a bug instead of laughing at it", "You, for taking the long way home"]: line(name)
    heading("Production notes")
    for text in [
        "No penguins, cows, llamas, or feelings were harmed in the making of this game.",
        "Several institutions were inconvenienced.",
        "All invisible sets were returned in invisible condition.",
        "Any resemblance to a working installer is intentional.",
        "Special thanks does not imply endorsement.",
        "Fictional guilds. Actual gratitude.",
        "Made with open source, stubbornness, and the Super key.",
        "© MMXXVI Jeremy Dixon and the Omega Omarchy contributors. All rights reserved, to the extent the MIT License reserves any.",
        "Unauthorized duplication, distribution, or exhibition is actually fine. Please see LICENSE.",
    ]:
        line(text)
    rows.append({"kind": "space", "height": 20})
    line("OMEGA OMARCHY")
    line("The revolution will be customized.")
    rows.append({"kind": "space", "height": 20})
    rows.append({"kind": "space", "height": 24})
    rows.append({"kind": "seals", "height": 132})
    cards = [{"kind": "title", "seconds": 6}, {"kind": "player", "seconds": 8}, {"kind": "royalty", "seconds": 6}]
    for i in range(0, len(mobs), 4): cards.append({"kind": "mobs", "seconds": 6, "cast": mobs[i:i+4]})
    for spec in CAMPAIGN_ROSTER:
        cards.append({"kind": "boss", "seconds": 6, "id": spec.boss.id, "name": spec.boss.name, "subtitle": spec.boss.title})
    cards.insert(-1, {"kind": "boss", "seconds": 6, "id": "goliath-cyborg-penguin", "name": "Goliath’s Cyborg Penguin", "subtitle": "Firewall Shell"})
    cards.extend([{"kind": "orbs", "seconds": 6}, {"kind": "robots", "seconds": 8}, {"kind": "curtain", "seconds": 6}])
    sources = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / "credits").glob("*")) if p.suffix in {".json", ".toml"}}
    assets = {str(p.relative_to(root / "assets")): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root / "assets/fidelity/ultra").rglob("*.png")) if p.parent.name in {"bosses", "enemies", "characters", "ui"}}
    for p in sorted((root / "assets/character-packs").glob("*/manifest.json")):
        assets[str(p.relative_to(root / "assets"))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"schemaVersion": 1, "revision": _git(root, "rev-parse", "HEAD").strip(), "contributors": contributors, "history": history, "sources": sources, "acceptedAssets": assets, "foundationSources": foundation["sources"], "foundationRetrieved": foundation["retrieved"], "music": music["roll"], "musicCredits": music_credits, "rows": rows, "castCards": cards}


def build_credits(root: Path = ROOT, *, check: bool = False, target: Path | None = None) -> Path:
    if _git(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise RuntimeError("Credit attribution requires full history; fetch with --unshallow before building.")
    target = target or root / "src/omega_omarchy/data/credits.json"
    output = json.dumps(compile_credits(root), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if check:
        if not target.is_file() or target.read_text(encoding="utf-8") != output:
            raise RuntimeError("Credits need rebuilding: ./scripts/omega credits")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    return target


def refresh_github(root: Path = ROOT) -> Path:
    """Explicitly pin GitHub identities; normal builds remain offline."""
    remote = _git(root, "remote", "get-url", "origin").strip()
    match = re.fullmatch(r"(?:git@github\.com:|https://github\.com/)([^/]+/[^/]+?)(?:\.git)?", remote)
    if not match:
        raise RuntimeError("The identity refresh requires a github.com origin.")
    repo = match.group(1)
    def api(path, *args):
        return json.loads(subprocess.check_output(["gh", "api", path, *args], text=True))
    # gh handles public access or the developer's existing authentication.
    # Only commit hashes, GitHub logins and public display names are retained.
    pages = api(f"repos/{repo}/commits?per_page=100", "--paginate", "--slurp")
    commits = {entry["sha"]: entry["author"]["login"] for page in pages for entry in page if entry.get("author")}
    profiles = {}
    for login in sorted(set(commits.values())):
        profile = api(f"users/{login}")
        profiles[login] = {"name": str(profile.get("name") or ""), "url": profile["html_url"]}
    target = root / "credits/github-identities.json"
    target.write_text(json.dumps({"repository": repo, "commits": commits, "profiles": profiles}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if runtime credits need rebuilding")
    parser.add_argument("--refresh-github", action="store_true", help="Use gh to pin public GitHub usernames and profile names before building")
    args = parser.parse_args()
    if args.refresh_github:
        print(refresh_github())
    print(build_credits(check=args.check))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
