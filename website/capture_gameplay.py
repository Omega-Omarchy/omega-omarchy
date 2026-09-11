"""Render the website's grounded gameplay preview from a reproducible game scene."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

import pygame
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from omega_omarchy.physics import InputState, SOLID, TILE, step_body
from omega_omarchy.presentation import FIDELITIES
from omega_omarchy.render import Renderer
from omega_omarchy.sim import GameSim


def capture(out: Path) -> None:
    pygame.init()
    pygame.display.set_mode((320, 180))
    sim = GameSim.from_play_now("omega-fixture-1")
    sim._begin_flight()
    sim._enter_edit()
    x, y = sim.edit_start
    sim.edit_ops = [{"op": "place", "x": x + 6, "y": row, "tile": "L"}
                    for row in range(y - 4, y + 1)]
    assert sim._refresh_edit_preview() and sim.edit_goal_ready
    sim._seal_edit()
    portal = max((e for e in sim.entities if e.extra.get("skyway")), key=lambda e: e.y)

    # Stage beside the earned portal, on a visible floor with standing headroom.
    # The old transfer-review still positioned the body in air without settling it.
    candidates = [(abs(tx - (portal.x - 3)) + abs(ty - portal.y), tx, ty)
                  for ty in range(2, len(sim.tiles))
                  for tx in range(max(1, portal.x - 7), min(len(sim.tiles[0]) - 1, portal.x + 6))
                  if sim.tiles[ty][tx] in "#="
                  and all(sim.tiles[row][tx] not in SOLID for row in (ty - 2, ty - 1))]
    _, tx, ty = min(candidates)
    sim.body = replace(sim.body, x=tx * TILE + 3, y=ty * TILE - sim.body.height - 2,
                       vx=0, vy=0, on_ground=False, on_ladder=False, facing=1)
    for _ in range(30):
        sim.body = step_body(sim.body, InputState(), sim.tiles)
    assert sim.body.on_ground and sim.body.vy == 0
    assert abs(sim.body.y + sim.body.height - ty * TILE) < .001
    sim.scene = "action"
    sim.flash_ticks = 0
    sim.messages.clear()
    sim.floaters.clear()
    sim.tick = 90
    sim._snap_camera()
    renderer = Renderer(ensure_assets=False)
    out.mkdir(parents=True, exist_ok=True)
    for fidelity in FIDELITIES:
        sim.set_presentation(fidelity=fidelity, display="clean")
        sim.messages.clear()
        frame = renderer.frame(sim)
        image = Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB"))
        image.save(out / f"gameplay-{fidelity}.webp", lossless=True, method=6)
    print(f"Grounded at tile ({tx}, {ty}); three renderer captures saved to {out}")
    pygame.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "website/assets")
    capture(parser.parse_args().out)
