# Engine qualification (2026-08-29)

Pinned Godot: **4.4.1.stable.official.49a5bc7b6** portable Linux x86_64
(`Godot_v4.4.1-stable_linux.x86_64`, 123 MiB). Downloaded for this pass; not
shipped in git.

Probe: empty 320×180 headless scene that prints and quits, versus pygame-ce
2.5.8 opening a 320×180 dummy window and quitting.

| Measure | Godot 4.4.1 headless | pygame-ce 2.5.8 dummy |
|---|---:|---:|
| Startup | 1.19 s | 0.45 s |
| Peak RSS (time -f %M) | 93 MB | 26 MB |
| Binary / wheel footprint | 123 MiB editor binary | pygame-ce 2.5.8 in the venv |
| Controller API | InputMap + joypads | pygame.joystick hot-plug (wired) |
| Linux + web export | native + export templates | native play + authoritative Chapter 1 WebAssembly build |
| Tests vs presentation | GDScript would duplicate the Python core | tests call the same `GameSim.step` the window uses |

Decision for this alpha: **keep pygame-ce** for the playable first chapter.
Godot is viable later if we want richer shaders or a different distribution model; the
Python core (identity, generation, combat, golden path) stays the reference
either way. Absence of a preinstalled binary is **not** the reason.

## Full-game startup follow-up

The slow launch reported after the Ultra art expansion was not pygame image
loading: `run_game` rebuilt every generated fidelity asset before opening the
window. On this machine that offline build takes **46.14 s / 115,248 KiB peak
RSS**. It is now confined to the explicit `assets`/`check` workflows. The
committed-asset launch path measures **0.77 s / 53,532 KiB** for the installer
and **0.81 s / 53,804 KiB** when it also generates and mounts a world.

That result removes startup performance as a reason to migrate now. A Godot
rewrite would still duplicate or bridge the Python simulation and would not
beat the corrected path on the existing qualification probe.

## CRT curvature follow-up

The original curved-screen pass performed a full-resolution NumPy coordinate
remap, retained full-resolution index buffers, and allocated source and
destination arrays every frame. At Ultra's 960×540 raster, the CRT
post-process alone measured **29.09 ms** with the default curve (about 34 FPS
before game drawing), versus 5.41 ms with the curve disabled.

The replacement approximates the same bowed silhouette with coalesced
horizontal bands transformed in pygame/SDL's compiled path. Band geometry and
the static scanline/phosphor/vignette overlay are cached. The scanline
size/depth, curvature, and phosphor controls are now independent.

| Hyper-V/dummy Ultra probe | Frame time | Implied ceiling |
|---|---:|---:|
| New CRT post-process, curve off | 2.14 ms | 468 FPS |
| New CRT post-process, default 12% curve | 5.61 ms | 178 FPS |
| New CRT post-process, maximum curve | 5.70 ms | 175 FPS |
| Complete game frame, curve off | 13.28 ms | 75 FPS |
| Complete game frame, default 12% curve | 14.08 ms | 71 FPS |
| Complete game frame, maximum curve | 14.32 ms | 70 FPS |

These are comparative observations on the development VM, not a minimum-spec
hardware qualification. They show an approximately 81% reduction in the
curved CRT post-process and, more importantly, no cliff as curvature increases.
This bottleneck therefore does not justify a Godot migration. Godot remains a
future option for shader-heavy presentation, subject to a
representative whole-game benchmark rather than an assumption that an engine
rewrite is inherently faster.

As of 2026-09-03, `dist/web` runs the authoritative pygame simulation and
renderer through Pygbag/WebAssembly and has reached the installer under desktop
Chromium with working keyboard progression. It deliberately packages only
Chapter 1/Cow Level art, so this removes “a real web target” as a migration
reason without claiming full-campaign or cross-browser qualification.
