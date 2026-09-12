# Rendering performance

Keep simulation timing, camera motion, animation, visual detail, and collision
rules fixed when optimizing the renderer. Native profiling is useful for finding
work to remove, but confirm the result in the shipped pygbag runtime: its SDL
and pygame versions differ from the native build.

## September 12, 2026 comparison

Compared with revision `6d312f8`, the renderer now skips fully transparent
parallax padding, skips offscreen wind/platform artwork, and reuses fitted wind,
ladder, portal, and platform images. Platform rotation and wind animation still
run at their existing cadence. The original parallax canvas dimensions and
camera registration remain intact; only the blit source rectangle changes.
Asset generation writes alpha bounds beside each background set so the first
frame does not need to scan large images. Missing, malformed, or size-mismatched
metadata falls back to a runtime scan. Tests check shipped metadata against
every source image; regenerate it when changing background artwork.

No tile compositing, resolution reduction, animation throttling, physics,
generation, or audio changes are included. Additional caches are bounded.

Measured in the Codex Desktop in-app Chromium browser on this development
machine, using pygame 2.5.7 / SDL 2.28.4 / Python 3.12.12 WebAssembly:

| Scenario | Detail | Before median | After median | Less render time |
| --- | --- | ---: | ---: | ---: |
| Chapter 1 start | 16-bit | 4.90 ms | 4.30 ms | 12% |
| Chapter 1 start | High | 18.00 ms | 11.85 ms | 34% |
| Chapter 1 start | Ultra | 47.70 ms | 24.55 ms | 49% |
| Boss area | Ultra | 49.70 ms | 29.95 ms | 40% |
| Platform area | Ultra | 43.40 ms | 20.70 ms | 52% |
| RPG battle | Ultra | 68.55 ms | 49.65 ms | 28% |
| Cow Level | Ultra | 95.80 ms | 67.60 ms | 29% |

All 18 browser scenarios improved their median and 95th-percentile render
times. Median improvements ranged from 7.7% to 52.3%. The native comparison
also improved all 18 medians, by 7.3% to 43.0%. These are single-machine,
render-only comparisons, not an end-to-end FPS measurement or a hardware-wide
guarantee. The Cow Level and Ultra RPG battle still exceed a 60 Hz frame budget
on this machine. First-use image decoding also remains noticeable. These are
useful targets for the next profiling pass.

Each scenario uses a fresh baseline and candidate renderer, alternates which
one runs first each frame, and supplies identical camera and animation inputs.
Timing excludes fixture generation, byte comparisons, event handling,
simulation, audio playback, and display presentation. There are 12 warm-up
frames followed by 60 measured frames per browser scenario (90 native).
Cold-frame measurements are recorded separately and are order-sensitive.

The browser run compared 162 sampled RGB frames byte-for-byte and checked the
camera on every pair. The native run compared 216 sampled frames. All matched.
Each scenario also verifies that rendering leaves gameplay state unchanged.
The fixture covers the start, boss, pit, and platform areas, an actual RPG
encounter, and the Cow Level at all three detail settings. This is rendering
regression coverage, not a substitute for playing through the campaign.

Full measurements: [browser](evidence/render-browser-2026-09-12.json),
[native](evidence/render-native-2026-09-12.json).

## Repeat locally

Save the reference renderer before changing it. Use a revision compatible with
the current simulation and assets; this harness compares renderer changes,
not arbitrary historical versions of the entire game.

```sh
mkdir -p .local
git show 6d312f8:src/omega_omarchy/render.py > .local/render-reference.py
.venv/bin/python tools/benchmark_render.py \
  --reference .local/render-reference.py \
  --output .local/render-native.json
```

For the browser comparison, build the ordinary game, then create a separate
benchmark copy. The output directory must not already exist. The helper embeds
a native-generated save fixture to avoid procedural generation during setup;
the browser loads it through normal save validation under a separate temporary
storage key.

```sh
./scripts/omega web --web-out .local/perf-game
.venv/bin/python tools/build_render_benchmark.py \
  --game-build .local/perf-game \
  --reference .local/render-reference.py \
  --output .local/perf-comparison
.venv/bin/python -m http.server 8841 --bind 127.0.0.1 \
  --directory .local/perf-comparison
```

Open `http://127.0.0.1:8841/` in a foreground browser tab and leave it visible
until `COMPLETE` appears. Copy the JSON report below it. Any pixel, camera,
fixture-loading, or gameplay-state failure stops the comparison and displays a
traceback. Keep other heavy work stopped during measurement. Serve the ordinary
`.local/perf-game` separately for interactive gameplay checks.

The benchmark build contains development fixtures and replaces the game entry
point. Never deploy it. Production packaging does not include these tools.
