"""Capture character registration, boss states, portals and articulated prologue."""

from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import json
from pathlib import Path

from PIL import Image, ImageDraw
import pygame

from omega_omarchy.campaign import CAMPAIGN_ROSTER
from omega_omarchy.character_pack import available_characters
from omega_omarchy.level_editor import build_editor
from omega_omarchy.physics import TILE
from omega_omarchy.presentation import FIDELITIES
from omega_omarchy.render import Renderer, save_surface
from omega_omarchy.runtime_assets import asset_dir
from omega_omarchy.sim import GameSim, LEVEL_INTRO_BUILD_TICKS, LEVEL_INTRO_MAP_FADE_TICKS, LEVEL_INTRO_WHITE_HOLD_TICKS, BOSS_SETTLE_TICKS, BOSS_DEFEAT_HOLD_TICKS, SKYWAY_TRANSFER_TICKS
from omega_omarchy.physics import InputState


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(".local/refinement-2026-09-09"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pygame.init()
    pygame.display.set_mode((320, 180))
    renderer = Renderer(ensure_assets=False)
    base = GameSim.from_play_now("omega-fixture-1")
    records = [{"seed": "omega-fixture-1", "label": f"{index + 1}. {CAMPAIGN_ROSTER[index].name}", "chapter": chapter}
               for index, chapter in enumerate(base.world.chapters)]
    build_editor(records, args.out / "editor.html")
    (args.out / "identity-receipt.json").write_text(json.dumps({"identity": base.world.identity.to_record(), "worldDigest": base.world.seal_digest(), "receipt": base.world.receipt}, indent=2) + "\n")

    def capture(sim, name):
        image = renderer.frame(sim)
        save_surface(image, args.out / f"{name}-{sim.fidelity}.png")
        return Image.frombytes("RGB", image.get_size(), pygame.image.tobytes(image, "RGB"))

    for fid in FIDELITIES:
        sim = copy.deepcopy(base)
        sim.set_presentation(fidelity=fid, display="clean")
        sim.world.character = available_characters()[0][1].to_record()
        sim.scene = "prologue"
        sim.story_beat = 4
        frames = []
        for tick in range(0, 160, 5):
            sim.story_ticks = sim.tick = tick
            frame = renderer.frame(sim)
            frames.append(Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB")))
        frames[0].save(args.out / f"robots-{fid}.webp", save_all=True, append_images=frames[1:], duration=83, loop=0, quality=85)
        sim.story_ticks = 120
        capture(sim, "robots")
        for beat, label, ticks in ((3, "robots-arrive", range(100, 370, 3)),
                                   (5, "robots-corrupt", range(0, 240, 3))):
            sim.story_beat = beat
            frames = []
            for tick in ticks:
                sim.story_ticks = sim.tick = tick
                frame = renderer.frame(sim)
                frames.append(Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB")))
            frames[0].save(args.out / f"{label}-{fid}.webp", save_all=True, append_images=frames[1:], duration=50, loop=0, quality=85)
        for index, chapter in enumerate(CAMPAIGN_ROSTER):
            sim.dev_warp(f"{chapter.id}:boss")
            sim._begin_level_intro(index)
            sim.level_intro_ticks = LEVEL_INTRO_MAP_FADE_TICKS + LEVEL_INTRO_WHITE_HOLD_TICKS + LEVEL_INTRO_BUILD_TICKS
            sim.tick = 0
            capture(sim, f"intro-{index}")
            sim.tick = 24
            capture(sim, f"intro-active-{index}")
            sim.scene = "action"
            gate = next(e for e in sim.entities if e.kind == "boss-gate")
            sim.body = replace(sim.body, x=(gate.x + 1) * TILE + 1)
            sim._tick_boss_gates()
            boss = next(e for e in sim.entities if e.kind == "boss")
            sim._begin_combat(boss, boss=True)
            sim.tick = 0
            capture(sim, f"battle-{index}")
            turn_sim = copy.deepcopy(sim)
            turn_sim._queue_battle_round(action="patch", use_item=False, has_evidence=True, has_reuse=False)
            frames = []
            for tick in range(100):
                if tick % 2 == 0:
                    frame = renderer.frame(turn_sim)
                    frames.append(Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB")))
                turn_sim.step(InputState())
            frames[0].save(args.out / f"battle-motion-{index}-{fid}.webp", save_all=True, append_images=frames[1:], duration=33, loop=0, quality=85)
            defeat_sim = copy.deepcopy(sim)
            defeat_sim.combat = None
            fallen = next(e for e in defeat_sim.entities if e.kind == "boss")
            if index == 5:
                fallen.extra["goliath_stage"] = defeat_sim.goliath_stage = "duel"
            defeat_sim._begin_boss_defeat(fallen, chapter.boss.id)
            frames = []
            for tick in range(BOSS_SETTLE_TICKS + BOSS_DEFEAT_HOLD_TICKS):
                if tick % 4 == 0:
                    frame = renderer.frame(defeat_sim)
                    frames.append(Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB")))
                if tick == BOSS_SETTLE_TICKS:
                    capture(defeat_sim, f"defeat-{index}")
                defeat_sim.step(InputState())
            frames[0].save(args.out / f"defeat-{index}-{fid}.webp", save_all=True, append_images=frames[1:], duration=67, loop=0, quality=85)
            sim.combat = None
            boss.extra["in_combat"] = False
            sim._advance_after_boss(chapter.boss.id)
            capture(sim, f"victory-{index}")
        # Ground-aligned slides on the exact same simple terrain and camera.
        sheet = Image.new("RGB", (3 * 250, 220), "#121b28")
        pen = ImageDraw.Draw(sheet)
        for index, character in enumerate(available_characters()[0][:3]):
            source = asset_dir() / "fidelity" / fid / "characters/david_side-slide.png" if character.kind == "david" else asset_dir() / "character-packs" / character.kind / fid / "side-slide.png"
            image = Image.open(source).convert("RGBA").resize((200, 180), Image.Resampling.NEAREST)
            # 5× logical-pixel enlargement, with the renderer's +6px offset.
            sheet.paste(image, (index * 250 + 25, 170 - 180 + 30), image)
            pen.line((index * 250, 170, index * 250 + 249, 170), fill="#9ece6a", width=2)
            pen.text((index * 250 + 10, 195), character.name, fill="#c0caf5")
        sheet.save(args.out / f"slides-{fid}.png")
        sim = copy.deepcopy(base)
        sim.set_presentation(fidelity=fid, display="clean")
        sim._begin_flight(); sim._enter_edit()
        x, y = sim.edit_start
        sim.edit_ops = [{"op": "place", "x": x + 6, "y": yy, "tile": "L"} for yy in range(y - 4, y + 1)]
        assert sim._refresh_edit_preview() and sim.edit_goal_ready
        sim._seal_edit()
        lower = max((e for e in sim.entities if e.extra.get("skyway")), key=lambda e: e.y)
        sim.scene = "action"
        sim.body = replace(sim.body, x=(lower.x - 2) * TILE, y=(lower.y + 1) * TILE - 18)
        sim._snap_camera()
        capture(sim, "portal")
        sim._begin_network_transition(lower)
        frames = []
        for tick in range(SKYWAY_TRANSFER_TICKS + 1):
            frame = renderer.frame(sim)
            frames.append(Image.frombytes("RGB", frame.get_size(), pygame.image.tobytes(frame, "RGB")))
            if sim.scene == "network":
                sim.step(InputState())
        durations = [500] + [17] * (len(frames) - 2) + [500]
        frames[0].save(args.out / f"portal-{fid}.webp", save_all=True, append_images=frames[1:], duration=durations, loop=0, quality=85)
        sim.dev_warp("cow")
        door = next(e for e in sim.entities if e.kind == "omega-door" and e.extra.get("exit"))
        sim.flash_ticks = 0
        sim.messages.clear()
        sim.body = replace(sim.body, x=(door.x + (4 if door.x < 6 else -4)) * TILE, y=(door.y + 1) * TILE - 18)
        sim._snap_camera()
        capture(sim, "cow-exit")
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Omega Omarchy · Refinement review</title>
<style>*{box-sizing:border-box}body{background:#0d1420;color:#dfe8f2;font:16px/1.5 system-ui;margin:0}main{max-width:1100px;margin:auto;padding:32px 24px}h1{font-size:44px;line-height:1.1}h2{margin-top:36px}nav{display:flex;gap:25px;flex-wrap:wrap}a{color:#9ece6a}p,figcaption{color:#a7b9cc}select{padding:9px;font:inherit;background:#1b2a3d;color:#dfe8f2;border:1px solid #5d718c;border-radius:5px}label{display:inline-block;margin:18px 24px 10px 0}img{display:block;width:100%;height:auto;background:#0a1018;border:1px solid #34465f;border-radius:7px}figure{margin:16px 0}.row{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:750px){.row{grid-template-columns:1fr}}</style>
<main><p>OMEGA OMARCHY / DEVELOPMENT REVIEW</p><h1>Framing, motion,<br>and room to fall.</h1><nav><a href="play/">Play Chapter 1 ↗</a><a href="editor.html">Open level editor ↗</a><a href="characters/">Character scenes & agent kit ↗</a></nav>
<p>Captures from the actual game renderer. Scene positions and clocks are controlled for review; these are not complete recorded playthroughs.</p>
<label>Fidelity <select id="fid"><option value="ultra">Ultra</option><option value="high">High</option><option value="sixteen-bit">Sixteen-bit</option></select></label>
<h2>Boss introduction and defeat</h2><label>Chapter <select id="boss">BOSS_OPTIONS</select></label><label>State <select id="state"><option value="intro">Introduction · ready</option><option value="intro-active">Introduction · active</option><option value="battle">RPG · ready</option><option value="battle-motion">RPG · action timeline</option><option value="defeat">Arena · settle and defeat</option><option value="victory">Victory screen</option></select></label><img id="boss-image" alt="Selected boss state in the game">
<h2>Three articulated joints per custodian</h2><label>Scene <select id="robot-scene"><option value="robots-arrive">Orbs depart · robots enter</option><option value="robots">Transfer</option><option value="robots-corrupt">Installation corrupted</option></select></label><img id="robots" alt="Animated prologue table scene with two articulated robots"><p>Robots arrive from opposite sides, then malfunction within a bounded area during corruption. Three articulated joints and a slight scene shake; narration stays steady. Reduced motion keeps the malfunction still.</p>
<h2>Contact portals and the Cow Level exit</h2><div class="row"><figure><img id="portal" alt="Animated ring transport"><figcaption>Contact begins a rapid transfer through the world to the other portal. The clip pauses at each endpoint for comparison; travel takes 0.4 seconds.</figcaption></figure><figure><img id="exit" alt="Pre-rendered EXIT sign at the Cow Level door"><figcaption>The EXIT sign is a pre-rendered sprite at all three fidelities.</figcaption></figure></div>
<h2>Slide registration</h2><img id="slides" alt="David, King and Queen slide sprites on an identical ground baseline"><p>The lowest nontransparent pixel matches David exactly in every fidelity.</p></main>
<script>const fid=document.getElementById('fid'),boss=document.getElementById('boss'),state=document.getElementById('state'),robotScene=document.getElementById('robot-scene');function update(){document.getElementById('boss-image').src=state.value+'-'+boss.value+'-'+fid.value+(['battle-motion','defeat'].includes(state.value)?'.webp':'.png');document.getElementById('robots').src=robotScene.value+'-'+fid.value+'.webp';document.getElementById('portal').src='portal-'+fid.value+'.webp';document.getElementById('exit').src='cow-exit-'+fid.value+'.png';document.getElementById('slides').src='slides-'+fid.value+'.png'}for(const s of [fid,boss,state,robotScene])s.addEventListener('change',update);update();</script></html>'''
    page = page.replace("BOSS_OPTIONS", "".join(f'<option value="{index}">{chapter.boss.name}</option>' for index, chapter in enumerate(CAMPAIGN_ROSTER)))
    (args.out / "index.html").write_text(page)
    print(args.out.resolve() / "index.html")


if __name__ == "__main__":
    main()
