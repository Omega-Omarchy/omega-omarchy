# Character creation

The installer offers **David**, **The Omarch King**, and **The Omarch
Queen**, with a live portrait and an editable name. Up/down or left/right
changes the appearance; typing replaces the name; Enter selects it. Selection
does not change movement, collision, abilities, or map generation. Default
David records retain their previous serialized form and identity.

**Create with your agent** explains the workflow and, on native builds, copies
the portable kit to `character-agent-kit.zip` in the game's user data folder
(`~/.local/share/omega-omarchy/` by default). The browser has a kit download and
an **Import character ZIP** control below the game. The agent choice remains
on character setup until the player selects an actual character.

## The complete replacement contract

Every character provides **26 poses × 3 fidelities = 78 PNGs**. Coverage includes
four walk frames, four climb frames, jumping/falling/landing/crouching/sliding,
ground and air attacks, throwing and hurt, battle, rear view, flight, OTS,
portrait/turn, and the two special prologue poses. Every scene uses the same
resolver, including the ghost left behind during customization.

The source format contains `character.json` plus 26 Ultra PNGs. The offline
compiler derives High and Sixteen-bit while preserving the source canvas and
alpha. The exported `contract.json` lists every exact dimension and pose;
`AGENT-BRIEF.md` gives an agent the art instructions, registration rules,
reference images, validation commands, and visual review checklist. The kit
does not put David images in the output frames: missing replacements fail
validation. Idle/battle and portrait/turn may reuse the creator's own art.

```sh
./scripts/omega character-kit /path/to/new-character-kit
./scripts/omega validate-character-source /path/to/new-character-kit
./scripts/omega build-character /path/to/new-character-kit --out /path/to/new-pack
./scripts/omega validate-character /path/to/new-pack
./scripts/omega install-character /path/to/new-pack
./scripts/omega list-characters
```

`build-character` writes a sibling `new-pack.zip`. Install can also accept the
ZIP. Output directories must be empty so a build cannot erase an agent's work.
Compiled packs contain only a JSON manifest and PNGs; import never executes
agent code, fetches remote assets, or changes the game. Files are limited to
the 78 declared paths, with bounded dimensions and sizes, PNG decoding, and
SHA-256 checks. ZIP imports are capped at 4 MiB and 12 MiB expanded.
The runtime decodes the narrow noninterlaced RGBA PNG format directly, so a
browser-imported pose works without being present in pygbag's preload list.

Native imports go under `characters/<id>/<digest>/` in game-owned user data.
Different versions coexist. Move the character selector once to refresh after
an external install. A browser import refreshes the list automatically. It
uses the selected file locally and attempts to retain it in browser storage;
the status reports if storage is full. Keep the ZIP if storage is later cleared.

To distribute a browser build containing a specific custom character:

```sh
./scripts/omega web --web-out /path/to/web --character-pack /path/to/new-pack
```

Only explicitly supplied custom packs are bundled; local installations are
not swept into web artifacts. The standard build includes both Omarchs and
the downloadable agent kit. Native packaging includes those assets too.

## Saves and missing art

The character's display name, kind, pack id, and exact art digest are included
in its world record. Save/reload and reroll preserve those fields. Built-in
royal characters receive the current game’s framing/animation fixes; their
stored digest records the creation version. Custom characters remain pinned
to their exact digest. A shared
world does not itself distribute the custom images; share the ZIP separately.

If a saved custom version is unavailable or invalid, the entire character uses
David artwork with a visible message identifying the missing pack. No view
quietly uses a different partial fallback. Reinstall the saved pack and reopen
the game. Historical custom records without art metadata use David consistently;
their former partial green recolor was not a complete character pack.

## Built-in art and review

The King and Queen use the maintainer-supplied references now archived under
`assets/source/characters/`. Their pose atlases were created with the built-in
imagegen tool. The first atlas outputs contained painted checkerboards, so
the final source atlases use an explicit green chroma key, removed during the
offline build. The source README and prompt record document that step.

All lower fidelities derive from the same Ultra artwork. The build preserves
the ordinary 120 × 108 canvas and 36-world-pixel visual height, including
headroom in low poses; collision remains 10 × 18. No shader tint stands in for
a new character. Special rear busts, portraits, flight, and prologue poses have
their own artwork and dimensions.

```sh
PYTHONPATH=src SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python scripts/review-characters.py
./scripts/omega test tests/test_character_pack.py tests/test_installer.py \
  tests/test_save.py tests/test_identity.py tests/test_web.py -k 'not audio'
./scripts/omega test-scope assets
```

The review page contains captures of the actual selector and game scenes,
animated walk/climb studies, and complete pose sheets at each fidelity. These
are controlled render fixtures, not a claim of human playtesting. The tests
exercise selection, renaming, all-pose resolution, source/build/ZIP/install
round trips, missing-version fallback, malformed files, and save/reload.
The full release gate is separate and is not required for this development pass.

### Validation recorded on 2026-09-09

- Character, installer, save, identity, and web selection: **32 passed**, one
  audio test deselected; subsequent runtime-image changes were covered below.
- Character, installer, layout, flight, and web selection: **29 passed**, one
  audio test deselected.
- Asset scope: **31 passed**, including regeneration of both complete Omarchs.
- After the browser decoder change: character/installer/web selection
  **22 passed**, one audio test deselected.
- Final character/import/decoder, web packaging, and native artifact tests:
  **25 passed**, one audio test deselected. These runs overlap.
- All poses inspected on dark backgrounds at all three fidelities, with
  native scene renders for selection, action, flight, OTS, prologue, and battle.
- Live browser: actual ZIP chooser import succeeded, then ordinary Return and
  arrow inputs selected both the King and Queen with their correct portraits.
  A separate persistence test removed the installed files and restored a custom
  pack from a simulated browser storage record. No existing play save was replaced.

The full release gate and a new native executable build were not run. The
native packaging file list and artifact tests were updated, and the real
browser artifact was rebuilt and exercised.
