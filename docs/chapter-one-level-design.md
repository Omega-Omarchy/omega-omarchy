# Chapter 1 procedural level design

The Chapter 1 generator plans a sequence of player decisions before placing
terrain. Generator `3.9.0` replaces the old independent, equally sized sector
rolls with a paced route grammar. The aim is to make the main path interesting
and give side routes a purpose, while keeping editing optional.

## The route grammar

- A calm terraced opening introduces a small height change and a visible,
  optional edit pickup.
- An early discovery offers an upper reward route.
- Traversal and encounter sections vary in order, with a quiet cache garden
  near the middle of the chapter.
- A final remix combines familiar traversal with a reward branch and an
  opponent beyond the landing, followed by the existing boss approach.

Six ground-route shapes supply different situations: terraces, stepped ridges,
two-gap stepping stones, overpasses with upper/lower routes, encounter
courtyards with enemies at different elevations, and cache gardens.
Section widths, route choices, eligible mirrored approaches, ridge heights,
and reward-route recipes are deterministic seed variations. Section width in
a content profile remains a target; the partition absorbs the remainder and
keeps sections at least 24 tiles wide.

The selector prefers less-used choices and avoids the previous two choices
where possible. Consecutive reward routes also avoid the same structural
family: tower, switchback, or platform chain. A content pack with fewer choices
falls back to the available recipes. Its recipe and motif lists still
participate in generation and identity.

Vertical structures are concentrated in discovery sections and the final
remix. This replaces a tall ladder structure in nearly every sector. The
early route stays lower, and the later tower/switchback can reach 16 tiles
above the floor. Continuous ground, small steps, and bounded gaps preserve an
ordinary route to the boss without climbing every optional structure.

## Placement guarantees

- Spawn and boss approaches remain outside the section partition. Section
  joins are protected from the later ground-relief pass.
- Casual gaps span two tiles; standard and precise gaps span three. Encounters
  have dedicated ground/perches instead of being scattered into pit takeoffs.
- The opening and middle breather contain no enemies, corrupt pits, bumpers,
  moving platforms, or wind columns.
- Physical toys are assigned to active traversal/discovery sections. Moving
  platforms need clear space along their full travel and above the platform;
  horizontal travel cannot extend into a quiet section.
- Every Chapter 1 edit pickup must pass reachability validation before a
  generated chapter is accepted. The existing ladder moat remains in force.
- The middle secret crate has a solid base beneath its penguin. Breaking the
  shell exposes a usable landing instead of forcing the repair pass to move
  the reward out of the crate.
- Cosmetic RNG draws cannot alter Chapter 1 collision geometry.

The section plan, including route, beat, dimensions, recipe, and mirroring,
is recorded in the existing placement receipts. Generator compatibility is
now `3.9.0`; both bundled packs were resealed for that version. New worlds have
new deterministic identities. This change does not migrate older saves or
third-party packs.

## Inspect and iterate

From the repository root:

```sh
PYTHONPATH=src .venv/bin/python scripts/review-chapter-one.py \
  --seed omega-fixture-1 --seed chapter-design-a --seed chapter-design-b \
  --out .local/chapter-one-atlas
```

Open the resulting `index.html` in a browser. It shows the actual generated
tiles, section boundaries, recipe/route labels, rewards, and physical toys.
The zoom and toy-visibility controls help inspect joins and alternate routes.
`chapters.json` contains the same generated data for further analysis. The
tool generates only Chapter 1 and does not access installed packs or saves.

Play the matching seed with:

```sh
./scripts/omega run --seed chapter-design-a --skip-installer
```

Use the existing [developer warps](playtest-warps.md) for focused edit or boss
checks. Full pacing checks should begin at the ordinary chapter start.

## Evidence from the implementation pass

The six baseline seeds were `omega-fixture-1` and `chapter-design-a` through
`chapter-design-e`. Their old layouts used one sector width and had zero to
four adjacent recipe repeats. The new layouts use six to eight distinct
section widths and have no adjacent recipe repeats. All six use the six ground
route shapes. Recipe counts between the two versions are not equivalent:
the old choices mostly varied optional climbing structures, while the new
ground-route choices affect the ordinary path.

The final seed sweep covers `chapter-sweep-0` through `chapter-sweep-29` at
casual, standard, and precise difficulty: 90 layouts. All pass on the first
generation attempt, retain six ground-route shapes, contain no adjacent
ground-route repeat, retain at least eight floating blocks, and have usable
edit rewards and clear moving-platform travel bounds.

Targeted verification:

```sh
./scripts/omega test tests/test_chapter_design.py tests/test_generation.py \
  tests/test_golden_path.py tests/test_identity.py tests/test_zone_delta.py
./scripts/omega test tests/test_golden_path.py tests/test_identity.py \
  tests/test_content_packs.py tests/test_zone_delta.py tests/test_save.py \
  tests/test_web.py -k 'not prepared and not audio'
```

The final generation/gameplay selection passed 102 tests; the adjacent
pack/save/web selection passed 36 tests. The ordinary-input completion test
covers `omega-fixture-1`,
`chapter-design-a`, and `chapter-design-b`, from installer through Chapter 1
completion. Pack, save, zone-delta, identity, and web-staging checks cover the
adjacent compatibility surfaces. The full release gate was not run for this
level-design change.

Local artifacts for this pass are under
`.local/chapter-one-design-2026-09-08/`: before/after maps, a browser comparison,
native Ultra stills, the seed-sweep record, and the fixture identity receipt.
These are development evidence, not shipped game assets.

The fixture world identity is
`sha256:9d72b88dd689a849c19e9a3d85a2b1a552853f110c3c92307b1bbccb1a66529b`.
A fresh browser build was produced with `./scripts/omega web --web-out
.local/chapter-one-design-2026-09-08/atlas/play --no-installed-content`.
Its archive contains the current grammar and generator version; the in-app
browser reached the greeter and accepted Return to enter input selection.

This establishes variation and completion, not human enjoyment or the target
10–15 minute pacing. The next playtest should judge whether the upper/lower
route choices are apparent, rewards justify detours, and the quiet section
feels like a deliberate pause. Tune those observations before adding more
route shapes. Native controller feel and browser gameplay need their own
player sessions; browser gameplay qualification in this pass stops at the
installer input screen. Route inspection used the atlas and native stills.
