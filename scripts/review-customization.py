"""Render a repeatable, local before/after review of the workshop interaction."""

from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame

from omega_omarchy.render import Renderer
from omega_omarchy.sim import GameSim
from omega_omarchy.physics import InputState, TILE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(".local/chapter-one-atlas"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now(seed="omega-fixture-1")
    sim._begin_flight()
    sim._enter_edit()
    gx, gy = sim.edit_start[0] + 6, sim.edit_start[1] - 4
    for stage in ("before", "connected"):
        if stage == "connected":
            sim.edit_ops = [{"op": "place", "x": gx, "y": y, "tile": "L"} for y in range(gy, sim.edit_start[1] + 1)]
            if not sim._refresh_edit_preview() or not sim.edit_goal_ready:
                raise RuntimeError("The demonstration scaffold no longer connects a landing.")
        for fidelity in ("sixteen-bit", "high", "ultra"):
            sim.set_presentation(fidelity=fidelity, display="clean")
            renderer = Renderer(ensure_assets=False)
            pygame.image.save(renderer.frame(sim), args.out / f"workshop-{fidelity}-{stage}.png")
    sim._seal_edit()
    for _ in range(36):
        sim.step(InputState())
    lower = next(entity for entity in sim.entities if entity.extra.get("skyway") and entity.y > 17)
    sim.network_armed = True
    sim._begin_network_transition(lower)
    for _ in range(54):
        sim.step(InputState())
    for fidelity in ("sixteen-bit", "high", "ultra"):
        sim.set_presentation(fidelity=fidelity, display="clean")
        pygame.image.save(Renderer(ensure_assets=False).frame(sim), args.out / f"workshop-{fidelity}-upper.png")
    sim.dev_warp("walled-garden:start")
    ix, iy = next((x, y) for y, row in enumerate(sim.tiles[:17]) for x, cell in enumerate(row) if cell == "I")
    fixed_camera = (max(0, (ix - 6) * TILE), max(0, (iy - 7) * TILE))
    for stage in ("hidden", "brush", "standing", "shimmer"):
        sim.body = replace(sim.body, x=(ix - 5) * TILE if stage in {"hidden", "shimmer"} else ix * TILE,
                           y=iy * TILE - 18 if stage != "brush" else (iy + 1) * TILE, vx=0, vy=0)
        sim.tick = 400 if stage != "shimmer" else (-(ix * 83 + iy * 137) + 2) % 1200
        sim.cam_x, sim.cam_y = fixed_camera
        for fidelity in ("sixteen-bit", "high", "ultra"):
            sim.set_presentation(fidelity=fidelity, display="clean")
            with patch.object(GameSim, "camera_target", return_value=fixed_camera):
                pygame.image.save(Renderer(ensure_assets=False).frame(sim), args.out / f"invisible-{fidelity}-{stage}.png")
    pygame.quit()
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Omega · Customization workshop study</title><style>
body{background:#0c141b;color:#e5eee9;font:15px Arial,sans-serif;margin:24px;line-height:1.55}main{max-width:1440px;margin:auto}a{color:#b4e77a;margin-right:20px}h1{font-size:29px;line-height:1.2;margin-bottom:12px}h2{font-size:18px}p{color:#a4b8b1;max-width:950px}.eyebrow{font-size:11px;letter-spacing:2px;color:#b4e77a}.images{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0;background:#14212c;border:1px solid #2c414e;border-radius:8px;overflow:hidden}img{display:block;width:100%;image-rendering:pixelated}figcaption{padding:14px}select{font:inherit;background:#1b2a34;color:#e5eee9;padding:7px 14px;border:1px solid #38515d;border-radius:5px}label{display:block;margin:20px 0}article{background:#14212c;border-left:3px solid #b4e77a;padding:2px 18px;margin:14px 0}footer{font-size:12px;color:#91a59f;margin-top:24px}@media(max-width:900px){.images{grid-template-columns:1fr}body{margin:16px}}
</style><main><p class="eyebrow">OMEGA OMARCHY / INTERACTION STUDY</p><h1>Build something you will use.</h1>
<nav><a href="editor.html">Level editor ↗</a><a href="index.html">Route atlas ↗</a><a href="play/">Play current build ↗</a></nav>
<p>A successful workshop now opens a whole upper traversal tier. Build a reachable landing, seal, then press UP at the new lift. Every chapter and hardware island has a connected skyway; the secret Cow map has one too. These are actual game renders from a controlled five-tile ladder demonstration.</p>
<label>Art fidelity <select aria-label="Art fidelity" id="fidelity"><option value="ultra">Ultra</option><option value="high">High</option><option value="sixteen-bit">Sixteen-bit</option></select></label>
<div class="images"><figure><img id="before" src="workshop-ultra-before.png" alt="Workshop showing the locked skyway objective"><figcaption><b>Before construction.</b> The skyway awaits a new connected landing. Entering the event has changed no terrain.</figcaption></figure>
<figure><img id="connected" src="workshop-ultra-connected.png" alt="A constructed ladder with green landing marks and Skyway lift ready"><figcaption><b>Ready to seal.</b> The new landing connects to the player. Sealing builds a two-way lift here. Undo and reset update the forecast.</figcaption></figure>
<figure><img id="upper" src="workshop-ultra-upper.png" alt="Player arriving on the upper skyway"><figcaption><b>Arrival above the map.</b> Short gaps, raised branches, rewards, and recovery ladders run across the upper tier. The return lift takes you back to your construction.</figcaption></figure></div>
<h2>Walled Garden: invisible platforms</h2><p>Platforms keep their collision while hidden. Nearby shoulders, heads and feet reveal them immediately. Far away, only a rare faint shimmer hints at the surface. Reduced motion disables the shimmer.</p>
<label>Visibility demonstration <select id="visibility"><option value="hidden">Player far away</option><option value="brush">Brushing from below</option><option value="standing">Standing on the platform</option><option value="shimmer">Rare shimmer</option></select></label>
<figure><img id="invisible" src="invisible-ultra-hidden.png" alt="Controlled Walled Garden invisible platform demonstration"><figcaption>Fixed camera and controlled player positions in the actual renderer. Invisible spans sit between visible landing pads. Both Walled Garden's skyway and optional middle routes use them.</figcaption></figure>
<p>The fixture route also passed a check using ordinary walking and climbing inputs in the actual simulation. The green overlay itself remains a static approximation; it does not simulate enemy pressure or moving-platform timing.</p>
<h2>Where later events can go</h2><p>The skyway replaces the earlier optional-cache placement experiment. These additional encounter types remain proposals.</p>
<article><h2>Broken crossing</h2><p>Choose a direct bridge or staggered landings over an optional corrupted detour. Return to play and cross the structure you built.</p></article>
<article><h2>Penguin extraction</h2><p>Bring a landing toward the rescue target or build an approach from below. The result is a visible rescue, with room for more than one solution.</p></article>
<article><h2>Crossfire workshop</h2><p>Choose cover, a high route, or an opening for a thrown item. Returning to play shows how the terrain changes the encounter.</p></article>
<footer>Controlled fixture: omega-fixture-1 · This page is a render review, not an interactive gameplay recording. Reproduce with PYTHONPATH=src .venv/bin/python scripts/review-customization.py.</footer>
<script>function refresh(){const fidelity=document.getElementById('fidelity').value;for(const stage of ['before','connected','upper'])document.getElementById(stage).src='workshop-'+fidelity+'-'+stage+'.png';document.getElementById('invisible').src='invisible-'+fidelity+'-'+document.getElementById('visibility').value+'.png'}document.getElementById('fidelity').addEventListener('change',refresh);document.getElementById('visibility').addEventListener('change',refresh);</script></main></html>'''
    (args.out / "workshop.html").write_text(html, encoding="utf-8")
    print(args.out.resolve() / "workshop.html")


if __name__ == "__main__":
    main()
