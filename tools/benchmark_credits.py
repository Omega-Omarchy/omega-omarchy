#!/usr/bin/env python3
"""Compare credit rendering time and pixels against a saved credits_render.py.

Only drawing is timed, excluding asset preparation, mixer playback, display
presentation and pixel comparison. The async compare() also runs in WebAssembly.
The requested fallback-font correction is applied to both sides, so every pixel
must match while measuring the remaining rendering changes.
"""

import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pygame

from omega_omarchy.credits import credit_manifest, FPS
from omega_omarchy.credits_render import CreditsRenderer
from omega_omarchy.installer import InstallerSession
from omega_omarchy.render import Renderer
from omega_omarchy.sim import GameSim


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (ordered[middle] + ordered[~middle]) / 2


async def compare(reference_path, frames=90, emit=print):
    spec = importlib.util.spec_from_file_location("omega_omarchy._credits_reference", reference_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    reference = module.CreditsRenderer
    reference._render_text = CreditsRenderer._render_text
    pygame.init()
    pygame.display.set_mode((960, 540))
    results, compared = [], 0
    for fidelity, scale in (("sixteen-bit", 1), ("high", 2), ("ultra", 3)):
        sim = GameSim(installer=InstallerSession(), scene="credits")
        sim.set_presentation(fidelity=fidelity, display="clean")
        renderers = [Renderer(ensure_assets=False), Renderer(ensure_assets=False)]
        for renderer in renderers:
            renderer._fid_cur, renderer._vs, renderer._iw, renderer._ih = renderer._layout(sim)
        credits = [reference(renderers[0]), CreditsRenderer(renderers[1])]
        surfaces = [pygame.Surface((320 * scale, 180 * scale)) for _ in credits]
        layout, height = credits[1].layout(sim.character_name)
        duration = credit_manifest()["music"]["duration"]
        patrons = next((y, size) for y, size, row in layout if row.get("compact"))
        names = next(y for y, _, row in layout if row["kind"] == "names")
        seals = next(y for y, _, row in layout if row["kind"] == "seals")

        def at(offset):
            return (offset + 105) / (height + 105) * duration

        cases = [
            ("crew", 60, False), ("names", at(names), False),
            ("patrons", at(patrons[0] + patrons[1] / 2), False),
            ("patrons-end", at(patrons[0] + patrons[1] - 150), False),
            ("seals", at(seals - 24), False), ("reduced", 120, True),
        ]
        elapsed, seen = 0, set()
        for card in credit_manifest()["castCards"]:
            if card["kind"] in {"player", "boss", "robots"} and card["kind"] not in seen:
                cases.append(("cast-" + card["kind"], elapsed + 1, False))
                seen.add(card["kind"])
            elapsed += card["seconds"]
        for name, start, reduced in cases:
            sim.scene = "ending" if name.startswith("cast-") else "credits"
            sim.settings["reducedMotion"] = reduced
            timings = [[], []]
            for n in range(frames + 12):
                sim.credits_ticks = round((start + n / 60) * FPS)
                for k in ((0, 1) if n % 2 else (1, 0)):
                    began = time.perf_counter()
                    credits[k].draw(surfaces[k], sim)
                    elapsed = (time.perf_counter() - began) * 1000
                    if n >= 12:
                        timings[k].append(elapsed)
                if pygame.image.tobytes(surfaces[0], "RGB") != pygame.image.tobytes(surfaces[1], "RGB"):
                    pygame.image.save(surfaces[0], "/tmp/credits-before.png")
                    pygame.image.save(surfaces[1], "/tmp/credits-after.png")
                    raise AssertionError((fidelity, name, n, sim.credits_ticks))
                compared += 1
                await asyncio.sleep(0)
            before, after = [median(values) for values in timings]
            row = {
                "fidelity": fidelity, "case": name,
                "beforeMedianMs": round(before, 4), "afterMedianMs": round(after, 4),
                "improvementPercent": round((1 - after / before) * 100, 1),
            }
            results.append(row)
            emit(json.dumps(row))
    return {
        "platform": sys.platform, "framesCompared": compared, "allPixelsEqual": True,
        "fontAlignmentAppliedToBoth": True, "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=90)
    args = parser.parse_args()
    if args.frames < 20:
        parser.error("Use at least 20 measured frames")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    report = asyncio.run(compare(args.reference, args.frames))
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
