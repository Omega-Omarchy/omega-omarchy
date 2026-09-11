# Character, traversal and encounter refinement

## Character framing

King/Queen transfer poses match David's diagonal reclining perspective: feet
in the lower-left foreground, head in the upper-right background. Portraits align eye centers and face scale to David, at approximately
(31, 40) / (59, 40) on the 96px Ultra canvas. OTS views include torso, hands and upper thighs.
Slides use David's exact last alpha row: 28 / 57 / 86 in Sixteen-bit / High /
Ultra, accounting for the renderer's six-world-pixel slide offset.

The default selector label is David. Built-in fixes apply to existing royal
saves; custom character packs remain pinned to their saved digest. The agent
kit documents the corrected framing and registration.

David's per-pose source files are retained. A later sheet migration should first
export all existing frames without pixel or registration changes and compare
every rendered view. Authored climbing improvements can follow separately.
Four climb files already exist but include derived variants; file count alone
does not establish animation quality.

## Encounters and props

All six campaign bosses and Goliath's cyborg penguin have ready, active and
defeated sprites in every fidelity. They share scale/baseline and appear in the
field, RPG stage and introductions. Defeat plays in the arena before the
victory presentation; tally and ending screens contain no defeated sprite. Bosses no longer use
whole-sprite squash/rotation as their animation. The RPG counter tip says SHOW,
matching the menu; the internal combat action id stays stable.

Boss cards combine chapter scenery, illuminated framing and a separate animated
boss. Their hold grows from 120 to 180 ticks: one extra second at fixed 60 Hz.
Two white silo custodians flank the prologue table. Apple-core emblems and
separate arms/claws are pre-rendered; shoulder, elbow and wrist rotate around
registered pivots. Reduced motion gives a deterministic still pose. Ring portals
and the Cow EXIT sign also use pre-rendered components at every fidelity.

See `skyways.md` for geometry and clearance changes. Generator 3.11.0 requires
a new world for revised layouts.

## Reproduce the review

```sh
SDL_VIDEODRIVER=dummy PYTHONPATH=src .venv/bin/python scripts/review-characters.py --out .local/refinement-2026-09-09/characters
SDL_VIDEODRIVER=dummy PYTHONPATH=src .venv/bin/python scripts/review-refinement.py
./scripts/omega web --web-out .local/refinement-2026-09-09/play
```

The review uses actual renderer captures with controlled scene state/clocks;
it is not a complete playthrough. It covers every fidelity, all campaign bosses,
defeated battle poses, slide comparisons, robots/rings and Cow exit artwork.
`identity-receipt.json` binds its map review to the generated fixture.

## Validation

The asset scope passed 31 tests. Physics, collision, identity, zone edits,
chapter design and skyways passed 142 tests, followed by three ordinary-physics
deck-gap surveys (one per seed). Six editor state tests pass. Focused refinement
tests check registration, jump/headroom limits, slide corridors, portal rearming,
rig link lengths, boss poses and naming.

The broader character, presentation, gameplay, save, web and generation
selection passed 147 tests (two excluded: audio and the existing copy check
below). The browser editor also reported zero traversal issues for Chapter 1.
Live browser smoke testing covered King selection, fixture-world installation,
and the prologue's articulated table/transfer scenes, with no console errors.
Both content packs validate after resealing; `git diff --check` passes.

The broad presentation/gameplay selection initially stopped at an existing
prologue-copy assertion: `The Omarch Thesis` versus current `THE OMARCH THESIS`.
That copy was not changed by this art pass. The full release gate and native
binary packaging were not run; this is a development build.

## Choreography follow-up

- Robots enter from opposite sides over 180 ticks, starting as the orbs depart
  at story tick 144. Corruption adds bounded ±7px motion around their homes,
  overhead arm swings, fast claws and at most 1px horizontal / 1px vertical
  scene shake. Narration stays fixed. Reduced motion keeps the malfunction still.
- Royal table rotations add +8° (King) / +5° (Queen) to David's existing −8°.
  No source regeneration was needed. Portrait crops use measured facial
  registration instead of independently fitting alpha bounds.
- The Cow EXIT sign now renders at 18 × 6 logical pixels. Workshop route hints,
  new-landing marks and the route objective panel are removed; tool controls stay.
- RPG bosses change pose only during their turn. The active player uses the
  selected character's kick, air-action or throw pose, with a short lunge and
  return to rest. Actor movement respects reduced motion.
- Bosses settle to a supporting arena surface over 48 ticks, then hold their
  defeated pose for 180 ticks before tally / ending / next Goliath phase. The
  camera holds on the landing. Saving during this hold does not duplicate rewards.
- The review adds animated entrance/corruption, RPG timeline and arena-defeat
  choices, plus an actual in-world portal transfer.

Follow-up validation: 144 broader tests, 31 asset tests and 16 focused
choreography/audio checks passed. The same existing prologue-copy assertion
remains excluded from the broader selection. No full release gate was run.
Three portal integration checks also passed. Browser smoke testing verified
both royal portraits, the corruption/defeat review controls and clean console
error logs. Existing generated audio outputs were preserved after asset checks.

## Installer and presentation follow-up — September 10

Character packs now validate in small batches from the greeter. Validated
roots and portrait images are reused by the selection screen, including when
cycling characters. Imported packs still receive complete validation before
joining the roster. A very fast trip through setup may briefly show the
character-art preparation notice while additional choices arrive.

Confirmation changes to the installation screen before starting generation.
The same deterministic generator has blocking and staged entry points; the
staged path yields between terrain building, traversal checking, upper-route
checking, island checks and world sealing. Progress describes the real work,
and the timer includes its measured cost and display time. Completion still
has the existing short hold. Individual validation units remain synchronous;
this is not background generation on another thread.

Character headings use the same sentence case, typography and position as
other setup headings. Video and audio descriptions are separate. Confirmation
has no column headings, taller rows and the full Limitless Library label.
Robots enter over three seconds and render in front of the projected waves.
Corruption shake has a one-pixel maximum per axis and more stationary frames.
Invisible platforms use shaded Omarchy green, including the editor swatch.
The cannon label increases from six to seven logical pixels.

Generator 3.12.0 reserves a full double-jump/descent corridor before boss gates.
The new skyway geometry requires a new world; both bundled content manifests
are resealed. The regular and example content versions otherwise stay intact.

September 10 validation: 78 installer, character-pack, choreography, skyway,
generation, identity, invisible-platform, render and web tests passed; another
33 content-pack, save and editor tests passed. All 13 installer tests passed
again after separating the live wall clock from the headless simulation clock.
Browser smoke testing reached character selection without pack revalidation,
reviewed video/audio/confirmation pages, and completed the measured installation
with no console errors. Native captures checked all three fidelities, green
platforms, the cannon label and foreground robot layering. No full release gate
or asset regeneration was needed for these runtime changes.

The latest local build is http://127.0.0.1:8815/play/ and the review is at
http://127.0.0.1:8815/ (including setup, platform and motion captures). Earlier
8813/8814 builds are preserved for comparison.
