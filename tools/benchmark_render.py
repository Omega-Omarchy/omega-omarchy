#!/usr/bin/env python3
"""Compare renderer frame time and pixels against a saved render.py revision.

Only rendering is timed: generation, event handling, mixer playback, display
presentation, and byte comparisons are outside the measurements. The async
runner can also be included in a local pygbag build to measure WebAssembly.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import replace
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

import pygame

from omega_omarchy.combat import make_foe, make_player, start_encounter
from omega_omarchy.render import Renderer
from omega_omarchy.sim import GameSim


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return (ordered[middle] + ordered[~middle]) / 2


def reference_renderer(path: Path):
    spec = importlib.util.spec_from_file_location("omega_omarchy._render_reference", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.Renderer


async def compare(reference, *, frames=90, fixture=None, emit=print):
    """Run interleaved pairs; stop immediately on any pixel/camera difference."""
    pygame.init()
    pygame.display.set_mode((960, 540))
    if fixture:
        sim = GameSim.new()
        sim.save_path = Path(fixture)
        if sys.platform == "emscripten":
            # Browser saves use localStorage, while the packaged fixture is
            # a file. Use its separate benchmark key and remove it afterward.
            from platform import window
            from omega_omarchy.save import WEB_STORAGE_PREFIX, write_save
            write_save(sim.save_path, json.loads(sim.save_path.read_text()))
            try:
                sim.load_from_disk()
            finally:
                window.localStorage.removeItem(WEB_STORAGE_PREFIX + sim.save_path.name)
        else:
            sim.load_from_disk()
        if sim.world is None:
            raise RuntimeError(f"Benchmark fixture did not load: {sim.messages}")
    else:
        sim = GameSim.from_play_now()
    results = []
    for scenario in ("start", "boss", "pit", "platforms", "turn", "cow"):
        if scenario == "cow":
            sim.dev_warp("cow")
        else:
            sim.dev_warp("start" if scenario == "platforms" else "boss" if scenario == "turn" else scenario)
        if scenario == "platforms":
            entity = next(e for e in sim.entities if e.kind == "tilt-platform")
            sim.body = replace(sim.body, x=entity.x * 16, y=entity.y * 16 - 40)
        if scenario == "turn":
            boss_id = str(next(e for e in sim.entities if e.kind == "boss").extra["boss"])
            sim.combat = start_encounter(make_player(), make_foe(boss_id, as_boss=True), boss_id=boss_id, mode="turn")
            sim.scene = "turn"
        for fidelity in ("sixteen-bit", "high", "ultra"):
            sim.fidelity = fidelity
            sim.settings["fidelity"] = fidelity
            renderers = [reference(ensure_assets=False), Renderer(ensure_assets=False)]
            timings = [[], []]
            cold = [0.0, 0.0]
            camera = sim.camera_target()
            def gameplay_state():
                return (sim.progress_record(), sim.body, sim.tiles, sim.entities,
                        sim.particles, sim.projectiles, sim.combat)

            before = copy.deepcopy(gameplay_state())
            for frame in range(frames + 12):
                # Both renderers see identical moving camera/animation inputs.
                sim.tick = frame * 3
                xy = (max(0, camera[0] + 28 * math.sin(frame / 15)),
                      max(0, camera[1] - 32 * math.sin(frame / 21)))
                images, cameras = [None, None], [None, None]
                for index in ((0, 1) if frame % 2 == 0 else (1, 0)):
                    sim.cam_x, sim.cam_y = xy
                    started = time.perf_counter()
                    surface = renderers[index].frame(sim)
                    elapsed = (time.perf_counter() - started) * 1000
                    if frame == 0:
                        cold[index] = elapsed
                    if frame >= 12:
                        timings[index].append(elapsed)
                    if frame % 10 == 0 or frame == frames + 11:
                        images[index] = pygame.image.tobytes(surface, "RGB")
                    cameras[index] = (sim.cam_x, sim.cam_y)
                if images[0] != images[1] or cameras[0] != cameras[1]:
                    raise AssertionError(f"Render difference: {scenario}/{fidelity}/frame {frame}")
                await asyncio.sleep(0)
            # Rendering must not change gameplay state; tick/camera are harness inputs.
            assert gameplay_state() == before
            row = {"scenario": scenario, "fidelity": fidelity, "frames": frames,
                   "pixelsEqual": True, "cameraEqual": True, "gameplayUnchanged": True}
            for label, values, first in zip(("before", "after"), timings, cold):
                row[label] = {"medianMs": round(median(values), 3),
                              "p95Ms": round(sorted(values)[math.ceil(len(values) * .95) - 1], 3),
                              "coldMs": round(first, 3)}
            row["improvementPercent"] = round(100 * (1 - median(timings[1]) / median(timings[0])), 1)
            results.append(row)
            emit(json.dumps(row))
    report = {"python": sys.version.split()[0], "platform": sys.platform,
              "pygame": pygame.version.ver, "sdl": pygame.get_sdl_version(), "results": results}
    if sys.platform != "emscripten":
        pygame.quit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True, help="A saved baseline render.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=90)
    args = parser.parse_args()
    if args.frames < 20:
        parser.error("Use at least 20 measured frames")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    report = asyncio.run(compare(reference_renderer(args.reference), frames=args.frames))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
