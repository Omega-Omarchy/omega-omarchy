"""Generate a local, zoomable atlas of actual campaign collision maps."""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path

from omega_omarchy.content import load_content
from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.generation import generate_world
from omega_omarchy.identity import GENERATOR_VERSION
from omega_omarchy.level_editor import build_editor, editor_server


COLORS = {
    "#": "#46586d", "=": "#91a5bb", "+": "#8eda81", "L": "#8eda81",
    "M": "#eb5e65", "D": "#b18b61", "B": "#54b6de", "O": "#edc662",
    "E": "#eb5e65", "X": "#ff8bb1", "S": "#ffffff", "C": "#a7a3ff",
    "P": "#fafafa", "H": "#fafafa", "^": "#73d8ce",
    "I": "#6ce4df", "K": "#223e51",
}


def map_svg(chapter: dict) -> str:
    tiles = chapter["tiles"]
    width, height = chapter["width"], chapter["height"]
    top = 0
    pieces = [f'<svg role="img" aria-label="Generated tile map" viewBox="0 0 {width} {height - top + 7}" xmlns="http://www.w3.org/2000/svg">']
    for i, section in enumerate(chapter["placements"]):
        x, span = section["x"], section["width"]
        label = escape(str(section.get("route") or section["recipe"]))
        beat = escape(str(section.get("beat") or "legacy sector"))
        pieces.append(f'<rect x="{x}" y="6" width="{span}" height="{height - top}" fill="{("#172432", "#202f3e")[i % 2]}"/>')
        pieces.append(f'<text x="{x + 1}" y="2" fill="#e6edf3" font-size="1.7">{i + 1}. {label}</text>')
        pieces.append(f'<text x="{x + 1}" y="4.4" fill="#9daec0" font-size="1.6">{beat} · {span} tiles</text>')
    for y in range(top, height):
        for x, glyph in enumerate(tiles[y]):
            if glyph not in COLORS:
                continue
            yy = y - top + 6
            color = COLORS[glyph]
            if glyph in {"L", "+"}:
                pieces.append(f'<path d="M{x + .3} {yy}v1 M{x + .7} {yy}v1 M{x + .3} {yy + .5}h.4" stroke="{color}" stroke-width=".12"/>')
            else:
                tile_height = .22 if glyph in {"=", "I"} else 1
                pieces.append(f'<rect x="{x}" y="{yy}" width="1" height="{tile_height}" fill="{color}"><title>{escape(glyph)} ({x}, {y})</title></rect>')
            if glyph in {"O", "E", "X", "S", "C", "P", "H"}:
                pieces.append(f'<text x="{x + .5}" y="{yy + .8}" text-anchor="middle" fill="#0b1018" font-size=".9">{glyph}</text>')
    for key, color in (("movingPlatforms", "#dd93ff"), ("tiltingPlatforms", "#ffa974"), ("windColumns", "#63cddd")):
        for feature in chapter.get(key, []):
            x, y = feature["x"], feature["y"] - top + 6
            h = feature.get("height", .4)
            pieces.append(f'<rect class="toy" x="{x}" y="{y}" width="{feature["width"]}" height="{h}" fill="{color}" opacity=".55"><title>{key}</title></rect>')
    pieces.append('</svg>')
    return "".join(pieces)


def metrics(chapter: dict) -> dict:
    sections = chapter["placements"]
    recipes = [section["recipe"] for section in sections]
    return {
        "width": chapter["width"],
        "sections": len(sections),
        "distinctRoutes": len({section.get("route", section["recipe"]) for section in sections}),
        "distinctWidths": len({section["width"] for section in sections}),
        "adjacentRecipeRepeats": sum(a == b for a, b in zip(recipes, recipes[1:])),
        "ladderTiles": sum(row.count("L") + row.count("+") for row in chapter["tiles"]),
        "pits": chapter["pitCount"],
        "editPickups": chapter["editPickupCount"],
        "attempt": chapter["attempt"],
    }


def write_atlas(records: list[dict], destination: Path) -> None:
    editor_name = "editor.html" if destination.stem == "index" else f"editor-{destination.stem}.html"
    build_editor(records, destination.with_name(editor_name))
    cards = []
    for record_index, record in enumerate(records):
        name = escape(record["seed"])
        chapter = record["chapter"]
        stats = metrics(chapter)
        cards.append(f'<section><h2>{name} <a href="{editor_name}?map={record_index}">Edit this map ↗</a></h2><p>{stats["distinctRoutes"]} route shapes · {stats["distinctWidths"]} section widths · {stats["adjacentRecipeRepeats"]} adjacent recipe repeats · {stats["ladderTiles"]} ladder tiles</p><div class="map">{map_svg(chapter)}</div></section>')
    destination.write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Omega · Route atlas</title>
<style>body{background:#0d151f;color:#e6edf3;font:16px Arial,sans-serif;margin:32px}h1{margin-bottom:8px}p{color:#a9bacb}section{margin-top:32px;border-top:1px solid #344354;padding-top:8px}h2{font-size:19px}h2 a{font-size:13px;margin-left:18px}a{color:#b4e77a}.map{overflow:auto;background:#111c28;border-radius:6px}svg{display:block;width:var(--map-width,100%)}label{margin-right:24px}input{vertical-align:middle}select{color:#e6edf3;background:#1b2a34;border:1px solid #38515d;padding:7px;border-radius:5px}.hide-toys .toy{display:none}</style>
<h1>Omega Omarchy · Route atlas</h1><p>Actual generated tiles. Read left to right; scroll horizontally when zoomed. This is a design inspection, not a human playtest.</p>
<label>Zoom <select aria-label="Map zoom" onchange="document.body.style.setProperty('--map-width',this.value)"><option value="100%">Fit map</option><option value="1500px">1500 px</option><option value="2200px">2200 px</option><option value="3200px">3200 px</option><option value="4800px">4800 px</option><option value="6400px">6400 px</option></select></label><label><input type="checkbox" checked onchange="document.body.classList.toggle('hide-toys',!this.checked)">Show moving platforms and wind</label>
<p>Gray: terrain / decks · Cyan: invisible platforms (shown for inspection) · Dark K: skyway separator · Green: ladders · Red: corruption / enemies · Gold O: edit pickup · Purple C: item · White P/H: penguin / secret · Blue B: reward block</p>
''' + "".join(cards) + '</html>', encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", action="append")
    parser.add_argument("--difficulty", choices=("casual", "standard", "precise"), default="standard")
    parser.add_argument("--chapter", action="append", choices=[spec.id for spec in CAMPAIGN_ROSTER])
    parser.add_argument("--out", type=Path, default=Path(".local/chapter-one-atlas"))
    parser.add_argument("--serve", action="store_true", help="Serve the atlas, editor, and live traversal checks locally")
    parser.add_argument("--port", type=int, default=8814)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    index = load_content()
    seeds = args.seed or ("omega-fixture-1", "chapter-design-a", "chapter-design-b")
    worlds = {seed: generate_world(seed, difficulty=args.difficulty, force_logo=True, content=index) for seed in seeds}
    records = [{"seed": seed if chapter_id == "corrupted-install" else f"{seed} / {chapter_id}", "chapter": next(chapter for chapter in worlds[seed].chapters if chapter["chapterId"] == chapter_id)}
               for chapter_id in args.chapter or ("corrupted-install",)
               for seed in seeds]
    (args.out / "chapters.json").write_text(json.dumps({"generatorVersion": GENERATOR_VERSION, "difficulty": args.difficulty, "records": records}, indent=2) + "\n")
    write_atlas(records, args.out / "index.html")
    print(args.out.resolve() / "index.html")
    if args.serve:
        with editor_server(args.out, args.port) as server:
            print(f"Level editor: http://127.0.0.1:{server.server_port}/editor.html", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
