#!/usr/bin/env python3
"""Make a separate local WebAssembly renderer comparison from a game build."""

import argparse
import json
import os
from pathlib import Path
import shutil
import zipfile


WEB_MAIN = '''import asyncio, json, traceback
from pathlib import Path
from platform import window
import pygame

async def main():
    output = window.document.getElementById('omega-render-report')
    lines = ['Running baseline/current renderer comparison in WebAssembly...']
    def emit(line):
        lines.append(line)
        output.textContent = '\\n'.join(lines)
    try:
        from benchmark_render import compare
        from omega_omarchy._render_reference import Renderer as ReferenceRenderer
        report = await compare(ReferenceRenderer, frames=__FRAMES__,
            fixture=Path(__file__).parent / 'benchmark-fixture.json', emit=emit)
        output.textContent = 'COMPLETE\\n' + json.dumps(report)
    except Exception:
        output.textContent = 'FAILED\\n' + traceback.format_exc()
    while True:
        await asyncio.sleep(1)

asyncio.run(main())
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-build", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="A new local directory; never deploy it")
    parser.add_argument("--frames", type=int, default=60)
    args = parser.parse_args()
    if args.frames < 20:
        parser.error("Use at least 20 measured frames")
    if args.output.exists():
        parser.error("Output already exists; choose a new benchmark directory")
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from omega_omarchy.sim import GameSim

    fixture = GameSim.from_play_now().save_record()
    reference = args.reference.read_bytes()
    runner = Path(__file__).with_name("benchmark_render.py").read_bytes()
    source_apk = args.game_build / "omega-omarchy.apk"
    with zipfile.ZipFile(source_apk) as source:
        entry = "assets/main.py"
        if entry not in source.namelist():
            parser.error("Expected the Omega pygbag archive layout")
        shutil.copytree(args.game_build, args.output, ignore=shutil.ignore_patterns("*.apk"))
        with zipfile.ZipFile(args.output / source_apk.name, "w", compression=zipfile.ZIP_STORED) as output:
            for info in source.infolist():
                if info.filename != entry:
                    output.writestr(info, source.read(info.filename))
            output.writestr(entry, WEB_MAIN.replace("__FRAMES__", str(args.frames)))
            output.writestr("assets/benchmark_render.py", runner)
            output.writestr("assets/omega_omarchy/_render_reference.py", reference)
            output.writestr("assets/benchmark-fixture.json", json.dumps(fixture))
    with (args.output / "index.html").open("a") as page:
        page.write('<pre id="omega-render-report" style="position:fixed;inset:0;z-index:99999;'
                   'overflow:auto;background:#111;color:#b5df90;padding:20px;font:12px monospace;'
                   'white-space:pre-wrap">Loading renderer benchmark...</pre>')
    print(f"Serve {args.output} locally. Results appear as JSON after COMPLETE; do not publish this build.")


if __name__ == "__main__":
    main()
