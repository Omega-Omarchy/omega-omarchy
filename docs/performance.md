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
| Cow Level with retained battle overlay¹ | Ultra | 95.80 ms | 67.60 ms | 29% |

All 18 browser scenarios improved their median and 95th-percentile render
times. Median improvements ranged from 7.7% to 52.3%. The native comparison
also improved all 18 medians, by 7.3% to 43.0%. These are single-machine,
render-only comparisons, not an end-to-end FPS measurement or a hardware-wide
guarantee. The combined Cow Level/battle case and Ultra RPG battle still exceed a 60 Hz frame budget
on this machine. First-use image decoding also remains noticeable. These are
useful targets for the next profiling pass.

¹ A subsequent audit found that the original harness's Cow Level warp retained
the preceding RPG encounter, and also retained a transition flash. Its numbers
describe that combined rendering workload, not ordinary Cow Level play. The
recorded measurements are preserved; the current harness now clones a clean
fixture for every scenario, clears transition flashes, and separately covers
cannon charging and continuous aiming. Compare both renderer revisions using
the same corrected harness for subsequent measurements.

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

## Second pass: opaque backgrounds, panels, and cannon artwork

Compared with the deployed `14f7590` build using the corrected, isolated
fixtures, all 24 browser cases improved their median and 95th-percentile
render times. Median improvements ranged from 21.7% to 44.9%.

| Scenario | Detail | Before median | After median | Less render time |
| --- | --- | ---: | ---: | ---: |
| Chapter 1 start | High | 11.20 ms | 7.20 ms | 36% |
| Chapter 1 start | Ultra | 23.60 ms | 14.65 ms | 38% |
| Boss area | Ultra | 28.85 ms | 20.10 ms | 30% |
| Platform area | Ultra | 20.15 ms | 11.10 ms | 45% |
| RPG battle | Ultra | 49.80 ms | 34.10 ms | 32% |
| Cow Level, no battle overlay | Ultra | 34.00 ms | 22.10 ms | 35% |
| Cannon charging | Ultra | 31.10 ms | 19.65 ms | 37% |
| Cannon continuously aiming | Ultra | 31.30 ms | 21.70 ms | 31% |

The largest browser gain comes from converting backgrounds certified fully
opaque by asset-generation metadata into display-format surfaces. PNGs had
retained an alpha channel even when every alpha value was 255. Transparent
layers keep their existing blend operation and source rectangle. The metadata
test verifies opacity against every source PNG.

UI panels now bake their opaque fill and translucent frame together once;
copying that opaque result preserves the original pixels while avoiding a
repeated alpha pass. Constant overlays reuse their filled surfaces, without
combining blend operations. HUD icons and player/battle sprite fits are reused.
The cannon caches its exact rendered angle, charge label, and flash color;
there is no angle rounding or reduction in animation cadence. Cache counts
are bounded (16 cannon images, 32 panels, 24 overlays, 64 character fits).

All 216 sampled browser frames and 288 native frames matched the baseline;
every frame pair matched camera output. All scenario gameplay-state checks
passed, as did 80 focused tests, including panel clipping/alpha equivalence
and character-source separation. The opacity metadata checks were rerun after
adding opaque background conversion.

These remain render-only measurements. Ultra RPG combat and some gameplay
areas still exceed a 16.7 ms frame budget on this browser. Native and browser
gains differ substantially: cannon rotation caching was much more valuable
in native SDL than WebAssembly, reinforcing the need to measure both.

Measurements: [browser](evidence/render-browser-second-pass-2026-09-12.json),
[native](evidence/render-native-second-pass-2026-09-12.json). Use `14f7590` as the
reference revision in the commands below to reproduce this comparison.

## Third pass: prologue, route map, and boss title cards

These scenes use their own drawing paths. They still resized full-screen art
every frame and alpha-blended backgrounds known to be opaque. The route map
also rebuilt its title, cropped emblem, and fitted/grayscaled boss portraits.
The title card reconstructed its settled backdrop throughout its hold.

Compared with `f198c8f` (the same renderer as deployed build `5eb5838`), all
42 browser cases improved both median and 95th-percentile render time:

| Scenario | Detail | Before median | After median | Less render time |
| --- | --- | ---: | ---: | ---: |
| Prologue title | Ultra | 7.65 ms | 6.00 ms | 22% |
| Orb capture | Ultra | 23.65 ms | 4.40 ms | 81% |
| Mind machine | Ultra | 24.20 ms | 5.15 ms | 79% |
| Transfer | Ultra | 26.00 ms | 6.10 ms | 77% |
| Installation corrupted | Ultra | 25.50 ms | 6.20 ms | 76% |
| Moving tunnel | Ultra | 36.80 ms | 27.75 ms | 25% |
| Route map | High | 10.50 ms | 1.50 ms | 86% |
| Route map | Ultra | 23.95 ms | 3.20 ms | 87% |
| Boss card construction | Ultra | 19.70 ms | 18.65 ms | 5% |
| Boss card hold | Ultra | 19.20 ms | 3.20 ms | 83% |

Backgrounds now reuse the original smoothscale result. Build-time opacity
metadata permits baking their existing shade into an opaque copy; unlisted,
transparent, or size-mismatched assets retain the original blending behavior.
Robot part fits, registered hero poses, map artwork, and the finished title-card
backdrop are reused. Cache keys distinguish detail, source character, pose,
rotation, boss target, and availability as appropriate; counts are bounded to
16 scene backgrounds and 96 scene art entries.

The moving wordmark highlight uses a generated ten-row tint atlas, copying the
original RGBA values for each of its ten falloff distances. This removes the
Python pixel loop without rounding colors or changing its motion. Tests compare
a full sweep, including low-alpha edges, and exercise the old-bundle fallback.
All continuously moving robot joints, tunnel zooms, rings, shakes, and scene
timings remain unchanged.

Both browser and native comparisons checked every frame: 3,024 identical RGB
pairs per runtime, plus matching camera output and unchanged gameplay state in
all cases. Coverage includes all eight prologue beats, login and map flashes,
locked/available/converted map nodes, and title-card construction and hold at
all three detail settings. The focused regression suite passed 158 tests.

The remaining Ultra tunnel and title-card construction costs still exceed a
16.7 ms render budget on this browser. Cold asset decoding also still costs up
to roughly 130 ms in these isolated cases; these changes principally improve
sustained rendering. Measurements exclude simulation, audio, and presentation,
and describe this machine rather than an end-to-end FPS guarantee.

Evidence: [browser](evidence/render-browser-story-2026-09-12.json),
[native](evidence/render-native-story-2026-09-12.json). Select `--suite story`
in **both** benchmark commands below and use reference `f198c8f` to repeat this
pass. The default suite continues to cover gameplay.

## Fourth pass: pickup and block-break stalls

Profiling actual pickup and break handlers separated event dispatch, simulation,
audio, and rendering. The scene caches remained valid. In the Ultra browser
test, a hardware-block break increased rendering from about 15.3 ms to
24.5–24.9 ms for seven frames; the full-screen flash alone consumed 9.2–9.3 ms
each frame. Simulation stayed around 0.4–0.6 ms. Particles and score labels
remained inexpensive after their first draw. A first-use sound decode added
about 2.6–2.9 ms independently (4.2 ms on the first diagnostic case).

The browser now uses SDL's uniform surface-alpha path for the single-color
flash, retaining one RGB surface and changing its opacity. An isolated Ultra
blend comparison dropped from 9.2 ms to 1.3 ms. Native SDL retains the previous
per-pixel path, which measured faster there. No flashes or particles are removed,
and their color choices, opacity curves, coverage, and simulation ticks remain
unchanged. SDL's two blend paths round differently: a flashed RGB channel may
differ by one value out of 255. This is an explicit exception to exact pixel
equivalence, limited to browser flash frames; all unflashed frames must still
match exactly. The tests cover all flash colors, the complete opacity ramp,
canvas resizing, and every possible input value per color channel.

Short sound effects preload one per frame during installation, the prologue,
map selection, level intros, pause, and audio settings. Preloading decodes but
does not play sounds, respects audio-tier changes, and excludes long music.
Failed preload attempts do not retry every menu frame. Gameplay retains lazy
loading as a fallback but does not preload unrelated sounds during action.

The `effects` benchmark suite creates post-event states through the real pickup
and break handlers, including changed tiles, inventory, score labels, and
particles. It checks every rendered pair, cycles the flash through zero and all
active opacities, and checks camera and gameplay state. Use `--suite effects`
in both benchmark commands with reference `bd29dfd`. Native output must match
exactly; the browser permits at most one RGB unit while a flash is active.
The 154 focused rendering, audio, gameplay, simulation-event, and web tests pass.

Interleaved browser rendering results (66 measured frames per case):

| Post-event state | Detail | Before median | After median | Less render time |
| --- | --- | ---: | ---: | ---: |
| Item pickup + flash | 16-bit | 3.90 ms | 3.00 ms | 23% |
| Item pickup + flash | High | 11.80 ms | 8.20 ms | 31% |
| Item pickup + flash | Ultra | 24.25 ms | 16.15 ms | 33% |
| Hardware block + flash | Ultra | 24.25 ms | 16.20 ms | 33% |
| Combat flash | Ultra | 24.20 ms | 15.90 ms | 34% |
| Penguin pickup, no flash | Ultra | 14.55 ms | 14.65 ms | effectively unchanged |
| Cracked tile, no flash | Ultra | 14.65 ms | 14.60 ms | effectively unchanged |

All 18 flash-bearing cases improved median and p95 rendering time. The six
unflashed controls remained effectively unchanged. All 1,872 browser frame
pairs passed their declared tolerance, with matching camera output and unchanged
gameplay state; all 1,872 native pairs matched exactly. Native timing is
effectively unchanged. A separate run through actual events after eight
pre-game audio updates measured first-use audio at 0–0.1 ms in all 12 cases.
This removes sound decoding from the event, rather than changing the sound.
Cold text/asset creation and ordinary gameplay rendering still take time;
some Ultra frames exceed a 16.7 ms total-frame budget. These remain
single-machine measurements, not an FPS guarantee.

Evidence: [browser rendering](evidence/render-browser-effects-2026-09-12.json),
[native rendering](evidence/render-native-effects-2026-09-12.json), and
[actual event timings](evidence/interaction-profile-2026-09-12.json).

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
until `COMPLETE` appears. Copy the JSON report below it. Any out-of-tolerance pixel, camera,
fixture-loading, or gameplay-state failure stops the comparison and displays a
traceback. Keep other heavy work stopped during measurement. Serve the ordinary
`.local/perf-game` separately for interactive gameplay checks.

The benchmark build contains development fixtures and replaces the game entry
point. Never deploy it. Production packaging does not include these tools.
