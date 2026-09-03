# Architecture

Omega Omarchy keeps **input-independent rules** in a pure Python package
(`omega_omarchy`). pygame-ce drives both the native presentation and a Pygbag
WebAssembly build. `dist/web/` packages the same first-chapter simulation and
renderer rather than maintaining a second canvas implementation.

## Engine

Godot remains a qualified future option, not the current migration target. A
pinned portable Linux build was measured against the real pygame-ce launch;
after removing the accidental runtime asset rebuild, pygame starts faster and
keeps the simulation and test surface unified. A later migration still needs a
clear win on shaders, pacing, controllers, size, and maintainability.
The Python core stays the reference for generation, combat, and tests either
way.

## Distribution boundary

The native player artifact freezes the Python/pygame runtime into a portable
one-directory Linux application, then wraps it in a normalized tar/gzip archive
with an external SHA-256 file. Runtime assets and the built-in content pack are
read directly from PyInstaller's frozen resource root; production-source
masters and private design/reference material are excluded. Optional Limitless
code is explicitly excluded from the standard offline artifact even when it is
installed in the build environment.

An independent verifier rejects traversal, escaping or unresolved links,
multiple roots, missing receipts/licenses/docs, source-only content, and
optional-integration leakage before extracting. Valid relative in-bundle
PyInstaller library links are preserved to avoid duplicated native payload. It
launches the extracted binary with an isolated HOME/XDG profile, checks the
sealed world identity/Play Now boundary, and proves runtime assets were not
rewritten. See [release-artifact.md](release-artifact.md).

The browser distribution stages only runtime code plus Chapter 1/Cow Level
assets, transcodes audio to Ogg, and stores the pre-compressed media in an
uncompressed ZIP for fast WebAssembly mounting. Pygbag/BrowserFS compatibility
workarounds live in `web_build.py` and are tested explicitly. Browser saves use
same-origin localStorage; no web storage path is treated as a native file.
See [web.md](web.md).

## Collision model

The hitbox is a 10×18 AABB. `Body.x, Body.y` is its top-left in world pixels.
TILE is always 16 world-pixels and does not change with art fidelity. Sprites
are drawn with their feet at the hitbox bottom-center, so extra visual width
hangs equally left and right. Solid tiles occupy their full cell. Ladder
triggers inflate the box by 4px and ease the body toward the rung center.
Quality presets never feed `step_body`.

## Presentation

Art **fidelity** (`sixteen-bit`, `high`, `ultra`) selects prepared assets,
animation density, parallax, and particles. Sixteen-bit is the baseline;
legacy `eight-bit` migrates up to it. **Display** (`clean`, `crt`) is a
post-process. Legacy `quality=crt` migrates to sixteen-bit + CRT. Reduced
motion forces clean display. The logical 320×180 camera rasterizes at 1× for
sixteen-bit, 2× for High, and 3× for Ultra. Tiles remain 16 world-pixels and
the player remains 36 world-pixels tall in every tier; only source detail and
raster density change. Generated production sources are versioned under
`assets/source/rendered/`, so the asset build has no machine-local inputs.
Sixteen-bit keeps full target resolution with a 64-color modeled SNES finish, High
uses a 256-color 32-bit-era finish, and Ultra keeps the unquantized generated
source. Lower-tier tiles, items, movement, and environment art derive from the
same Ultra compositions. Structural gameplay art is backed by explicit Ultra
ground, deck, ladder, breakable-block, gate, and bouncer masters; composites
such as ladder crossings and pivoting decks reuse those sources without changing
their collision cells. Each chapter also owns three independent full-scene
parallax masters (far, middle, near). They are baked once to each fidelity's
native canvas height, eliminating runtime resampling; High and sixteen-bit are
deterministic reductions rather than separately drawn or enlarged substitutes.

## Bound world identity

A world is identified by seed, generator version, schema version, ordered
content-pack ids, content digest, difficulty, and accessibility profile.
The built-in Chapter 1 generation profile is validated external data rather
than a cosmetic identity label. Explicit add-on directories pass through the
same fail-closed loader, extend only supported profile lists in deterministic
order, and change both generated output and the aggregate identity. Receipts
retain exact pack versions/digests. Saves require the identical ordered pack set
and aggregate digest on load. See [content-packs.md](content-packs.md).
Reviewed directory or ZIP packs can be installed disabled into game-owned user
data, then enabled separately. The digested registry records exact identities;
runtime launch revalidates enabled copies before passing them to the same loader.
Layout/loot/cosmetics/encounters/narrative/rare streams are separate.
Generator 3.3 uses 256–440-tile macro-route maps with 38–52-row vertical chambers,
multi-screen ladder/bumper routes, independently varied pits, encounters, loot,
secrets, edit-flight pickups, and chapter motifs. The computer-hardware chapter
adds sealed paired network nodes as ordinary bidirectional reachability edges;
its Ethernet/Wi-Fi operation labels come from the independent narrative stream.
Every map
is acceptance-tested for ordinary boss reachability before its receipt seals.

## Input ownership

Pygame translates raw keyboard and joystick state into semantic `InputState`
values before simulation. Player remaps live in the accessibility record:
keyboard actions carry primary and alternate keys, gamepad actions carry
physical button indices rendered as familiar labels, and stick/D-pad movement
remains conventional. Capture, conflict swapping, validation, reset, and save
persistence occur through the same `Accessibility` tables read by the mapper;
remaps never enter generated-world identity because they do not change world
topology or rules.

## Campaign (honest)

Chapter 1 (The Corrupted Install) is the ordinary-input qualification slice.
Chapters 2–6 now receive full-sized procedural maps and complete boss data, but
their complete end-to-end playthroughs are not yet golden-path qualified. The
default path stops on a Chapter 1 completion/credits surface; R/Y is an explicit
opt-in that labels and mounts the later development chapters. Saves made at the
boundary restore the boundary rather than respawning the boss or silently
advancing.

BS overload enters an explicit recovery state. Retrying respawns the player at
the chapter start while retaining the current generated map, sealed edits,
collected state, and converted entities. Confirmed rerolls are a separate,
fail-closed transaction: generate the deterministic successor first, write a
validated save archive of the prior sealed world, then swap live state. Archive
failure leaves the current world object and identity untouched.

## Limitless

Optional. Offline play starts fresh. When enabled, the in-game customize
panel calls `limitless_library.connector.query_local` against the shipped
catalog, verifies locally, and shows adoption / method / abstain evidence.

## Omarchy

`integrations/omarchy-plugin` follows schemaVersion 1. Theme colors load from
an Omarchy `colors.toml` when present. The QML panel is not loaded in this
environment.
