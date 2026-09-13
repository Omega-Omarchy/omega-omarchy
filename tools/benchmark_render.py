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
from omega_omarchy.physics import InputState
from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.sim import (GameSim, PROLOGUE_BEATS, PROLOGUE_LOGIN_TRANSITION_TICKS,
                              STAGE_MAP_TRANSITION_TICKS, LEVEL_INTRO_MAP_FADE_TICKS,
                              LEVEL_INTRO_WHITE_HOLD_TICKS, LEVEL_INTRO_BUILD_TICKS)


GAMEPLAY_SCENARIOS = ("start", "boss", "pit", "platforms", "turn", "cow", "cannon-charge", "cannon-aim")
STORY_SCENARIOS = tuple("prologue-" + beat[2] for beat in PROLOGUE_BEATS) + (
    "login-transition", "stage-map", "stage-map-advanced", "map-transition", "intro-build", "intro-hold")
EFFECT_SCENARIOS = ("penguin-pickup", "item-pickup", "hardware-block", "cracked-tile",
                    "flash-bomb", "flash-convert", "flash-combat", "flash-white")


def prepare_effect(sim, scenario):
    """Enter the actual post-event state, including scores, debris, and HUD."""
    x, y = sim.body.center
    if scenario.endswith("-pickup"):
        kind = scenario.removesuffix("-pickup")
        entity = copy.deepcopy(next(e for e in sim.entities if e.kind == kind))
        entity.x, entity.y, entity.alive = (x - 8) / 16, (y - 8) / 16, True
        sim.entities.append(entity)
        sim.step(InputState())
        assert not entity.alive
    elif scenario == "hardware-block":
        entity = copy.deepcopy(next(e for e in sim.entities if e.kind == "block"))
        entity.x, entity.y, entity.alive = int(x / 16), int(y / 16) - 2, True
        sim._trigger_block(entity)
    elif scenario == "cracked-tile":
        tx, ty = int(x / 16), int(y / 16) - 2
        row = list(sim.tiles[ty])
        row[tx] = "D"
        sim.tiles[ty] = "".join(row)
        assert sim._break_cracked_tile(tx, ty)
    else:
        sim.flash_kind = scenario.removeprefix("flash-")
        sim.flash_ticks = 12


def prepare_scenario(sim, scenario):
    if scenario in STORY_SCENARIOS:
        sim.scene = "prologue" if scenario.startswith("prologue-") or scenario == "login-transition" else (
            "level-intro" if scenario.startswith("intro-") else "stage-map")
        staging = scenario.removeprefix("prologue-") if scenario.startswith("prologue-") else "login"
        sim.story_beat = next(i for i, beat in enumerate(PROLOGUE_BEATS) if beat[2] == staging)
        sim.story_transition_ticks = sim.stage_map_transition_ticks = 0
        if scenario == "stage-map-advanced":
            sim.converted = [spec.boss.id for spec in CAMPAIGN_ROSTER[:3]]
        return
    if scenario == "cow" or scenario.startswith("cannon-"):
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
    if scenario.startswith("cannon-"):
        sim.cannon_loaded = True


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


async def compare(reference, *, frames=90, fixture=None, emit=print, suite="gameplay"):
    """Compare pairs; only browser effect frames allow one RGB rounding unit."""
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
    fixture_sim = sim
    results = []
    scenarios = {"story": STORY_SCENARIOS, "effects": EFFECT_SCENARIOS, "gameplay": GAMEPLAY_SCENARIOS}[suite]
    for scenario in scenarios:
        # Developer warps can retain an encounter or a transition flash. Each
        # case must begin independently, not inherit the preceding scenario.
        scenario_sim = copy.deepcopy(fixture_sim)
        if suite != "effects":
            prepare_scenario(scenario_sim, scenario)
        scenario_sim.flash_ticks = 0
        for fidelity in ("sixteen-bit", "high", "ultra"):
            sim = copy.deepcopy(scenario_sim)
            sim.fidelity = fidelity
            sim.settings["fidelity"] = fidelity
            if suite == "effects":
                prepare_effect(sim, scenario)
            renderers = [reference(ensure_assets=False), Renderer(ensure_assets=False)]
            timings = [[], []]
            cold = [0.0, 0.0]
            camera = sim.camera_target()
            def gameplay_state():
                return (sim.progress_record(), sim.body, sim.tiles, sim.entities,
                        sim.particles, sim.projectiles, sim.combat, sim.floaters,
                        sim.enemy_projectiles, sim.sfx, sim.flash_ticks, sim.flash_kind)

            before = copy.deepcopy(gameplay_state())
            all_pixels_equal = True
            max_difference = 0
            for frame in range(frames + 12):
                # Both renderers see identical moving camera/animation inputs.
                sim.tick = frame * 3
                original_flash = sim.flash_ticks
                if suite == "effects" and original_flash:
                    sim.flash_ticks = frame % 13  # All opacities, including no flash and the 90/255 cap.
                story_fields = ("story_ticks", "story_transition_ticks", "stage_map_transition_ticks", "stage_cursor", "level_intro_ticks")
                story_inputs = {name: getattr(sim, name) for name in story_fields}
                if suite == "story":
                    sim.story_ticks = frame * 5
                    sim.stage_cursor = (frame // 12) % len(CAMPAIGN_ROSTER)
                    if scenario == "login-transition":
                        sim.story_transition_ticks = 1 + frame % PROLOGUE_LOGIN_TRANSITION_TICKS
                    if scenario == "map-transition":
                        sim.stage_map_transition_ticks = STAGE_MAP_TRANSITION_TICKS - frame % STAGE_MAP_TRANSITION_TICKS
                    build_start = LEVEL_INTRO_MAP_FADE_TICKS + LEVEL_INTRO_WHITE_HOLD_TICKS
                    build_end = build_start + LEVEL_INTRO_BUILD_TICKS
                    sim.level_intro_ticks = (frame * 2) % build_end if scenario == "intro-build" else build_end + frame
                xy = (max(0, camera[0] + 28 * math.sin(frame / 15)),
                      max(0, camera[1] - 32 * math.sin(frame / 21)))
                cannon_inputs = None
                if scenario.startswith("cannon-"):
                    cannon = next(e for e in sim.entities if e.kind == "cow-cannon")
                    cannon_inputs = (dict(cannon.extra), sim.cannon_charge_ticks)
                    sim.cannon_charge_ticks = min(100, frame * 2)
                    if scenario == "cannon-aim":
                        cannon.extra["angle"] = 42 + 26 * math.sin(frame / 15)
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
                    if suite == "effects":
                        images[index] = surface.copy()
                    elif suite == "story" or frame % 10 == 0 or frame == frames + 11:
                        images[index] = pygame.image.tobytes(surface, "RGB")
                    cameras[index] = (sim.cam_x, sim.cam_y)
                pixels_match = images[0] == images[1]
                if suite == "effects":
                    pixels_match = pygame.image.tobytes(images[0], "RGB") == pygame.image.tobytes(images[1], "RGB")
                    if not pixels_match:
                        tolerance = 1 if sys.platform == "emscripten" and sim.flash_ticks else 0
                        close = pygame.transform.threshold(None, images[0], None, (tolerance, tolerance, tolerance, 255),
                                                           set_behavior=0, search_surf=images[1])
                        pixels_match = close == images[0].get_width() * images[0].get_height()
                        all_pixels_equal = False
                        max_difference = max(max_difference, tolerance)
                if not pixels_match or cameras[0] != cameras[1]:
                    raise AssertionError(f"Render difference: {scenario}/{fidelity}/frame {frame}")
                sim.flash_ticks = original_flash
                if cannon_inputs:
                    cannon.extra, sim.cannon_charge_ticks = cannon_inputs
                for name, value in story_inputs.items():
                    setattr(sim, name, value)
                await asyncio.sleep(0)
            # Rendering must not change gameplay state; tick/camera are harness inputs.
            assert gameplay_state() == before
            row = {"scenario": scenario, "fidelity": fidelity, "frames": frames,
                   "pixelsEqual": all_pixels_equal, "cameraEqual": True, "gameplayUnchanged": True}
            if suite == "effects":
                row.update(maxChannelDifference=max_difference, withinFlashTolerance=True)
            for label, values, first in zip(("before", "after"), timings, cold):
                row[label] = {"medianMs": round(median(values), 3),
                              "p95Ms": round(sorted(values)[math.ceil(len(values) * .95) - 1], 3),
                              "coldMs": round(first, 3)}
            row["improvementPercent"] = round(100 * (1 - median(timings[1]) / median(timings[0])), 1)
            results.append(row)
            emit(json.dumps(row))
    report = {"python": sys.version.split()[0], "platform": sys.platform, "suite": suite,
              "pygame": pygame.version.ver, "sdl": pygame.get_sdl_version(), "results": results}
    if sys.platform != "emscripten":
        pygame.quit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True, help="A saved baseline render.py")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--suite", choices=("gameplay", "story", "effects"), default="gameplay")
    args = parser.parse_args()
    if args.frames < 20:
        parser.error("Use at least 20 measured frames")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    report = asyncio.run(compare(reference_renderer(args.reference), frames=args.frames, suite=args.suite))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
