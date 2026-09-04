# Browser build

The browser target is a playable Chapter 1 alpha using the same `GameSim`,
renderer, input mapping, installer/prologue, and collision rules as native
play. It is no longer the old independent canvas mock-up. To keep first load
bounded, its package includes Chapter 1 and Cow Level art; later development
chapters and external content-pack installation remain native-only.

## Build and run locally

Prerequisites are Python 3.11+, the pinned development requirements, and
`ffmpeg` on `PATH`. From a clean checkout:

```bash
./scripts/omega doctor
./scripts/omega web
./scripts/omega web-serve
```

Then open <http://127.0.0.1:8000/>. Set `OMEGA_WEB_PORT` to choose another
loopback port. Opening `index.html` through `file://` does not work.

`./scripts/omega web` stages source into `build/web-stage/`, validates runtime
audio as browser-safe Ogg, and writes the deployable output to `dist/web/`.
Pass `--web-out PATH` for a disposable build. Source masters and unrelated
zone backgrounds are not copied into the browser archive.

## What is packaged

- the authoritative Python simulation and renderer;
- all three visual-fidelity tiers for Chapter 1 and Cow Level;
- installer, prologue, map, UI, character, enemy, boss, item, tile, and effect
  assets needed by those paths;
- all three independently selectable Ogg sound tiers and the runtime cue manifest;
- localStorage-backed saves and reroll archives;
- the selected Omega Omarchy application icon.

The three soundtrack tiers increase the current archive from the earlier 24
MiB build to approximately 38 MiB. It remains an intentionally stored ZIP:
PNG and Ogg files are already compressed, and applying DEFLATE again made
CPython/WebAssembly startup stall for little size benefit.

## Runtime and current boundaries

The launcher is built with pinned Pygbag 0.9.3 and downloads that version’s
CPython/Pygame WebAssembly runtime from `pygame-web.github.io` on first load.
Consequently the artifact is not offline-capable and deployment needs network
access plus a normal HTTP(S) origin. BrowserFS 1.4.3 is vendored and loaded
before the runtime because Pygbag 0.9.3’s generated BrowserFS CDN URL currently
returns 404. The launcher also installs Pygame explicitly and executes the
packaged entry point directly, bypassing an upstream dependency-scanner stall
with larger local import graphs. These workarounds are covered by tests and
should be removed when an upstream release is qualified.

Desktop Chromium has been smoke-tested through installer input. Firefox,
Safari, mobile layout/touch, controllers, long-session memory, audio autoplay,
resume/suspend, and production-host caching remain unqualified. The browser
stops at the Chapter 1 completion boundary rather than entering unfinished
later chapters. Do not describe this as six-chapter feature parity.

## Focused verification

```bash
./scripts/omega test-scope web
./scripts/omega web --web-out build/web-smoke
OMEGA_WEB_PORT=8010 ./scripts/omega web-serve
```

Manual smoke checklist:

1. first screen appears without a click-to-unlock loop or console exception;
2. Enter advances once to installer input selection;
3. keyboard navigation and typed character name work;
4. Play Now reaches the prologue and ordinary advance/skip behavior works;
5. Chapter 1 starts, moves, jumps, pauses, and resumes;
6. a save survives a same-origin reload;
7. Chapter 1 completion stays at the explicit web boundary.
8. the first accepted key gesture unlocks music, Pause → Sound changes tiers,
   and mute/captions continue working after a same-origin reload.

When reporting a web defect, include browser/version, OS, commit, whether the
runtime was cached, launch URL/origin, exact input sequence, console errors,
and a screenshot. Do not attach browser profiles or storage databases.

## Troubleshooting

- `No module named pygbag`: rerun the pinned CI requirement install or remove
  an incomplete `.venv` and let `./scripts/omega` bootstrap it.
- `web packaging requires ffmpeg`: install the distro’s `ffmpeg` package.
- Blank screen before the installer: hard-refresh once, confirm the CDN is
  reachable, and inspect the console for `[omega-web]` milestones.
- Stale code after rebuilding: close the old tab or use a cache-busting query
  parameter; Pygbag retains WebAssembly resources between loads.
- Saves missing: keep the same scheme/host/port. Browser persistence is scoped
  to the page origin and is separate from native save files.
