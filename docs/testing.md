# Issue-dependent testing

Omega Omarchy does not run every test by default. Each change records its
affected behavior and adjacent invariants, then runs the smallest convincing
selection. This keeps ordinary iteration fast without weakening the explicit
release gate.

## Choose the scope from the issue

Start with the exact regression and the closest existing module tests:

```bash
./scripts/omega test tests/test_omega_milestone.py -k cannon
./scripts/omega test tests/test_gameplay_upgrade.py::test_two_helpers_take_separate_delayed_rpg_stages
```

Use a maintained group when a change crosses several files in one area:

| Scope | Use for |
|---|---|
| `core` | physics, collision, save/identity, and privacy invariants |
| `gameplay` | traversal, encounters, milestones, and the Chapter 1 golden path |
| `combat` | side-view/RPG combat, bosses, helpers, and turn staging |
| `presentation` | renderer layout, animation, prologue, and visual state |
| `generation` | procedural maps, deterministic identity, and zone deltas |
| `content` | content-pack validation, storage, ordering, and deltas |
| `installer` | faux install state and the ordinary-input golden path |
| `assets` | source-to-fidelity asset derivation; intentionally expensive |
| `audio` | source/master provenance, tier resolution, settings, saves, and web audio |
| `web` | WebAssembly staging, launcher invariants, Ogg conversion, and browser persistence |
| `release` | artifact, release-audit, and privacy surfaces |

Example:

```bash
./scripts/omega test-scope combat
```

## Evidence rule

A pull request or handoff records:

1. the issue/risk area;
2. the exact commands and selectors run;
3. why those tests cover the changed behavior and neighboring invariant;
4. any manual visual, controller, performance, pack, or deterministic evidence;
5. whether the full release gate was run, and why.

Docs-only edits normally need `git diff --check` plus direct review of changed
links and claims. Asset edits require the asset scope and visual inspection of
every affected fidelity. Generator/pack identity changes require their scope,
updated version/digests, and a fixture identity receipt. Security, packaging,
shared physics, broad refactors, merge candidates, and release candidates may
warrant multiple scopes or the full gate.

## Full gate

The complete check is explicit and never runs from an omitted command or bare
`test` invocation:

```bash
./scripts/omega release-check
```

Hosted CI invokes this command explicitly on its protected integration path.
Passing a narrow scope is evidence for its issue, not a claim that unrelated
subsystems were requalified.
