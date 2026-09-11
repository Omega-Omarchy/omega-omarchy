"""Render the real character selector, scene substitutions, and pose coverage."""

from __future__ import annotations

import argparse
import copy
from dataclasses import replace
from html import escape
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
import pygame

from omega_omarchy.character_pack import POSES, available_characters, resolve_pack
from omega_omarchy.installer import PARODY_STEPS
from omega_omarchy.presentation import FIDELITIES
from omega_omarchy.render import Renderer, save_surface
from omega_omarchy.runtime_assets import asset_dir
from omega_omarchy.sim import GameSim, PROLOGUE_BEAT_TICKS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(".local/skyways-2026-09-09/characters"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    base = GameSim.from_play_now("omega-fixture-1")
    characters = available_characters()[0][:3]
    for character in characters:
        root = resolve_pack(character.to_record())
        for fid in FIDELITIES:
            pose_dir = args.out / character.kind / fid
            pose_dir.mkdir(parents=True, exist_ok=True)
            sheet = Image.new("RGB", (6 * 230, 5 * 225), "#141c2b")
            pen = ImageDraw.Draw(sheet)
            for index, pose in enumerate(POSES):
                source = root / fid / f"{pose}.png" if root else asset_dir() / "fidelity" / fid / "characters" / f"david_{pose}.png"
                shutil.copyfile(source, pose_dir / f"{pose}.png")
                with Image.open(source) as image:
                    image = image.convert("RGBA")
                    image.thumbnail((205, 185), Image.Resampling.NEAREST if fid == "sixteen-bit" else Image.Resampling.LANCZOS)
                    x, y = (index % 6) * 230, (index // 6) * 225
                    pen.rectangle((x + 3, y + 3, x + 226, y + 221), outline="#35465e")
                    sheet.paste(image, (x + (230 - image.width) // 2, y + 193 - image.height), image)
                    pen.text((x + 12, y + 201), pose, fill="#d6dfeb")
            sheet.save(args.out / f"{character.kind}-{fid}-poses.png")
            sim = copy.deepcopy(base)
            sim.world.character = character.to_record()
            sim.quality = sim.fidelity = fid
            sim.settings["fidelity"] = fid
            sim.installer.choices.character = character
            sim.installer.choices.quality = sim.installer.choices.fidelity = fid
            sim.installer.step_index = PARODY_STEPS.index("character")
            sim.scene = "installer"
            save_surface(renderer.frame(sim), args.out / f"{character.kind}-{fid}-selection.png")
            sim.scene = "action"
            save_surface(renderer.frame(sim), args.out / f"{character.kind}-{fid}-action.png")
            sim._begin_flight()
            sim.flight_ticks = 22
            save_surface(renderer.frame(sim), args.out / f"{character.kind}-{fid}-flight.png")
            sim._enter_edit()
            save_surface(renderer.frame(sim), args.out / f"{character.kind}-{fid}-workshop.png")
            sim.scene = "prologue"
            sim.story_ticks = PROLOGUE_BEAT_TICKS
            for beat, label in ((3, "captured"), (4, "transfer")):
                sim.story_beat = beat
                sim.story_ticks = 70 if label == "captured" else PROLOGUE_BEAT_TICKS
                save_surface(renderer.frame(sim), args.out / f"{character.kind}-{fid}-{label}.png")
            sim.editing = False
            sim.scene = "action"
            sim.dev_warp("boss")
            gate = next(e for e in sim.entities if e.kind == "boss-gate")
            sim.body = replace(sim.body, x=(gate.x + 1) * 16 + 1)
            sim._tick_boss_gates()
            sim._begin_combat(next(e for e in sim.entities if e.kind == "boss"), boss=True)
            assert sim.combat is not None
            save_surface(renderer.frame(sim), args.out / f"{character.kind}-{fid}-battle.png")
    shutil.copyfile(asset_dir() / "character-creation/agent-kit.zip", args.out / "character-agent-kit.zip")
    names = {char.kind: ("David" if char.kind == "david" else char.name) for char in characters}
    options = "".join(f'<option value="{key}">{escape(name)}</option>' for key, name in names.items())
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Omega · Choose your character</title>
<style>*{box-sizing:border-box}body{margin:0;background:#0e1520;color:#dbe5f2;font:16px/1.5 system-ui}main{max-width:1120px;padding:36px 24px;margin:auto}h1{font-size:clamp(30px,5vw,56px);line-height:1.05;margin:16px 0}h2{margin-top:36px}small{color:#9ece6a;letter-spacing:.12em}nav{display:flex;gap:24px;flex-wrap:wrap;margin:24px 0}a{color:#9ece6a}select,button{font:inherit;padding:10px;background:#1c2b3d;color:#deebfa;border:1px solid #566c89;border-radius:6px}label{display:inline-block;margin:12px 24px 12px 0}img{max-width:100%;height:auto;display:block;background:#111925;border:1px solid #30445e;border-radius:8px}figure{margin:20px 0}figcaption,p{color:#aebed1}code{background:#233046;padding:2px 5px}.motion{display:flex;align-items:end;gap:40px;min-height:180px;padding:20px;background:#1c293a;border-radius:10px}.motion img{height:144px;width:160px;object-fit:contain;border:0;image-rendering:pixelated}.chips{color:#7dcfff}</style>
<main><small>OMEGA OMARCHY / CHARACTER CREATION</small><h1>Choose who leads<br>the revolution.</h1><p>David, The Omarch King, The Omarch Queen—or a character made with your agent. Every view follows your choice; movement and abilities stay the same.</p>
<nav><a href="../play/">Play the updated build ↗</a><a href="character-agent-kit.zip" download>Download the agent kit</a><a href="../editor.html">Level editor ↗</a></nav>
<label>Character <select id="character">OPTIONS</select></label><label>Fidelity <select id="fidelity"><option value="ultra">Ultra</option><option value="high">High</option><option value="sixteen-bit">Sixteen-bit</option></select></label>
<h2>In the game</h2><label>Scene <select id="scene"><option value="selection">Character selection</option><option value="action">Side-scrolling</option><option value="flight">Flight to customization</option><option value="workshop">Over-the-shoulder workshop</option><option value="captured">Prologue: captured</option><option value="transfer">Prologue: transfer</option><option value="battle">Battle</option></select></label>
<figure><img id="scene-image" alt="Actual game render of the selected character and scene"><figcaption>Controlled captures from the game's actual renderer. These are scene previews, not recorded playthroughs.</figcaption></figure>
<h2>Movement study</h2><div class="motion"><img id="walk" alt="Four-frame walking cycle"><img id="climb" alt="Four-frame climbing cycle"><button id="motion">Pause animation</button></div>
<h2>Every appearance, covered</h2><p class="chips">26 poses · 3 fidelities · 78 validated PNGs per character</p><img id="poses" alt="All required character poses against a dark background">
<h2>Create a character with your agent</h2><ol><li>Download the kit and give its <code>AGENT-BRIEF.md</code> to your image-capable agent, along with your character idea.</li><li>Your agent supplies 26 Ultra poses. The compiler derives the other fidelities and validates the complete pack.</li><li>Install it natively or use <b>Import character ZIP</b> below the browser game. Choose it during character setup.</li></ol><p>The kit contains reference poses, dimensions, alignment rules, a machine-readable contract, and exact build/install commands. Imports remain local; keep your ZIP. Each saved world retains its chosen art version.</p></main>
<script>const char=document.getElementById('character'),fid=document.getElementById('fidelity'),scene=document.getElementById('scene');char.value='omarch-queen';let tick=0,running=true;function update(){const stem=char.value+'-'+fid.value;document.getElementById('scene-image').src=stem+'-'+scene.value+'.png';document.getElementById('poses').src=stem+'-poses.png';animate()}function animate(){for(const name of ['walk','climb'])document.getElementById(name).src=char.value+'/'+fid.value+'/side-'+name+'-'+(tick%4)+'.png'}for(const select of [char,fid,scene])select.addEventListener('change',update);document.getElementById('motion').addEventListener('click',event=>{running=!running;event.target.textContent=running?'Pause animation':'Play animation'});setInterval(()=>{if(running){tick++;animate()}},150);update();</script></html>'''.replace("OPTIONS", options)
    (args.out / "index.html").write_text(page, encoding="utf-8")
    print(args.out.resolve() / "index.html")


if __name__ == "__main__":
    main()
