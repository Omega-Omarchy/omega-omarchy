# Level workshop and customization experiments

**2026-09-09 update:** generated maps now use the
[workshop skyway objective](skyways.md), with an upper traversal tier and
invisible platforms in Walled Garden. The cache experiment below records the
previous iteration and remains the fallback for maps without skyway metadata.

The local Chapter 1 atlas now includes a browser editor. Start it from the
repository root:

```sh
./scripts/omega editor
# Add repeatable maps or choose another port/output directory:
./scripts/omega editor --seed omega-fixture-1 --seed chapter-design-a --port 8814
```

Open `http://127.0.0.1:8814/editor.html`. The server binds to localhost and serves
the generated atlas and editor. It runs until stopped. No external service or
JavaScript dependency is needed.

## Editing maps

- **Zoom:** fit the full map or choose 25%, 50%, 75%, 100%, 150%, 200%, 300%, or
  400%. The original atlas also has stepped zoom in place of its checkbox.
- **Lock:** maps start locked. Inspect and pan while locked; unlock to change
  tiles, import, repair, or change history. Switching maps locks the new map.
- **Tiles:** select a palette tile and click or drag. A continuous drag becomes
  one undo level. Spawn, boss, and progression anchors are protected.
- **History:** undo/redo or jump to an earlier history entry. Each map keeps up
  to 100 undo levels in the current session. Resetting to the original is also
  undoable. Starting a new edit after undo discards that branch's redo history.
- **Navigation:** Space+drag or the Pan tool moves the view. Go to spawn brings
  the starting area back into view. Arrow keys select a cell; Enter paints and
  Delete erases when the canvas is focused and unlocked.
- **Drafts:** changed tiles are saved in browser storage. Reload restores the
  draft as one history entry. Export/import portable JSON to keep a copy or
  share it with another developer. The seed and original tile digest must match
  the selected map, so a draft cannot quietly attach to a different generation.

Exports contain a draft tile layer with its source identity. They do not replace
active saves or automatically become a sealed content pack. Dynamic platforms
and wind remain visible as dashed outlines for context; their positions, timing,
and other chapter metadata are not editable in this first version. Browser
storage is convenience storage, so export important drafts.

## Traversal checks

The browser posts its current tile array to the local Python service. The
service calls the same `validate_level` and `reachable_from` functions as the
generator; there is no second JavaScript implementation to drift out of sync.

The result checks boss access without rare events, every edit pickup, ladder
endpoints, and penguin routes. Green cells show reachability. Coordinate-based
errors link to the affected tile. **Repair ladder ends** runs the existing
normalizer and adds one undo level; it may add landing tiles or remove an
obstructing tile, so inspect the highlighted changes. Painting, importing,
undoing, or resetting clears the previous result. Late responses from an older
draft cannot mark a newer map as passed.

This is a **static route forecast**, with approximate jumps. It does not model
the player's full collision footprint, damage from corruption, enemies, or
moving-platform timing. A passed map still needs an actual gameplay test. A
standalone `editor.html` can edit and export without a server; live checks need
the server above.

## Over-the-shoulder events: implemented first pass

The previous event always staged a high cache on five newly added platforms.
Entering the event changed both the working map and its original baseline, so
cancel left those platforms behind. Sealing an empty edit also awarded 500
points. The player had little feedback connecting their construction to a
useful result.

The revised event has a short, visible objective: **build to the gold cache,
seal, then collect it**.

- The camera frames the build space above the player's left-behind pose.
- Cache placement uses the local geometry. It seeks an initially disconnected
  target with a scaffold that fits the 16-placement budget under the static
  checker. It avoids existing entities, protected cells, and the ordinary
  pickup envelope around reachable terrain. That scaffold is a feasibility
  check only; it is never added to the map for the player.
- If there is no suitable location, the event offers free building rather than
  staging an arbitrary target. The objective recognizes a newly connected
  landing and invites the player to try that approach. This is a fallback,
  not another puzzle type.
- New reachable landings get small green marks. The objective changes to
  **Cache route connected** when the forecast connects the target. Undo/reset
  update this immediately. The forecast includes the ladder normalization used
  when sealing.
- Actual cache collection pays an additional **300 points**, once. A creative
  route can still earn this when the static checker did not recognize it.
  Sealing a changed map retains the existing 500-point edit reward; an empty
  seal awards nothing. Uncollected sealed caches survive saving and reloading;
  collected caches do not respawn.
- Cancel removes the pending cache and restores the event's exact entry
  terrain, including changes made during action play. Entry itself grants no
  platforms. Reset keeps the objective available for another attempt.

This improves feedback and consequence, but it still has one main objective
family. More visual variation around a cache would not fix that limitation.
An initial survey of 12 actual pickup locations across three Chapter 1 seeds
found five suitable cache targets; seven used the free-build fallback. The
scaffold check supports bridging from elevated ledges as well as a vertical
ladder, but this coverage still needs improvement through purpose-designed
encounters. The survey is evidence about placement, not evidence of fun.

## Next encounter designs to prototype

Each event should change the player's next action and make the consequence
visible on returning to play. These are design proposals, not implemented modes.

| Encounter | Player decision | Visible consequence | Placement rule |
| --- | --- | --- | --- |
| Broken crossing | Spend material on a direct bridge, or use staggered landings to keep more material available | Cross the route they just built | An optional detour around corruption; preserve the original safe path |
| Penguin extraction | Bring a landing toward the penguin or build an approach from below | Reach the penguin using the new approach | Use a clearly visible optional rescue with enough headroom; avoid replacing every cache with a differently colored pickup |
| Crossfire workshop | Build cover, take the high route, or leave an opening for a thrown item | Enemy shots interact with the chosen terrain | Introduce only after the relevant enemy attack has been demonstrated |
| Two-way shortcut | Build an ascent that also provides a fast return, or trade return speed for a nearby reward | Traversal changes in both directions | Use a real loop or branch, not another isolated high platform |
| Companion relay | Arrange a route around a recruited helper's demonstrated capability | The helper contributes to opening or defending the route | Offer only when the player already has the required helper |

**Start with the broken crossing and penguin extraction.** They create different
spatial problems using current movement, tiles, and pickups. Crossfire is a
useful next step once enemy pressure can be rehearsed reliably. Companion relay
needs more rules and presentation work, so it should follow those experiments.

Keep Chapter 1's first workshop simple: one visible objective and room for two
solutions. A later event should change the purpose of building. Across seeds,
choose event families with recent-history exclusion and attach them to suitable
terrain; do not simply rotate labels on the same layout. Give difficult events
a calm approach and keep cancellation available.

The most useful next tool is **rehearsal with the actual game simulation**: run
a disposable copy of the edited state, try movement or replay an input trace,
then return to the workshop without consuming the pickup or saving the trial.
The same mechanism could become the browser editor's Play draft command.
Python/WebAssembly already runs the game, so this should reuse `GameSim` and
`step_body` instead of growing another approximation in JavaScript. Keep the
static check as the fast first check, and record actual rehearsal success
separately.

Evaluate encounters by whether players understand the objective, attempt more
than one solution, use their construction after returning, and encounter a
different decision at the next workshop. A large count of random layouts alone
does not establish that they are interesting.

## Focused checks

```sh
./scripts/omega test tests/test_level_editor.py tests/test_edit_challenge.py
node --test tests/level_editor_state.test.cjs
./scripts/omega test tests/test_gameplay_upgrade.py tests/test_sim_events.py tests/test_flight_render.py -k 'edit or flight'
# Generate the controlled before/after art review in the atlas directory:
PYTHONPATH=src .venv/bin/python scripts/review-customization.py
```

The checks cover API agreement with the generator, malformed inputs, ladder
repair, draft isolation, grouped undo, anchor protection, event cancellation,
empty-seal rewards, route forecast updates, and collection payout. One generated
fixture is also sealed and traversed using ordinary walking/climbing inputs in
the actual simulation, without teleporting the player. This is a concrete
physics check of that route, not a substitute for testing all generated events.

For this pass, the broader affected suite passed 105 Python tests. A final
targeted run added the free-build fallback check and three Chapter 1 golden
paths, for 109 distinct Python tests in total; five JavaScript checks also
passed. Browser interaction checks exercised stepped zoom, grouped painting,
ladder error reporting and repair, undo, direct history selection, locking,
and draft separation across maps. The isolated browser game build was refreshed.

Implementation lives in `tools/level-editor/`, `level_editor.py`,
`scripts/review-chapter-one.py`, `edit_challenge.py`, and the edit-related parts
of `sim.py` and `render.py`.
