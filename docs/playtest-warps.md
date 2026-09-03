# Developer playtest warps

Developer warps resolve against the current deterministic world instead of
hardcoding tile coordinates. They are intended for iteration and QA; none are
required to complete the game.

Run directly to a landmark:

```sh
scripts/omega run --skip-installer --warp boss
scripts/omega run --skip-installer --warp boss-15
scripts/omega run --skip-installer --warp goliath-amalgam:boss-15
scripts/omega run --skip-installer --warp corrupted-install:edit
scripts/omega run --skip-installer --warp distro-front:portal
scripts/omega run --skip-installer --warp singularity-core:pit
scripts/omega run --skip-installer --warp distro-front:map-4
scripts/omega run --skip-installer --warp prologue
scripts/omega run --skip-installer --warp stage-map
scripts/omega run --skip-installer --warp cow
```

The grammar is
`[chapter-id:]start|boss|boss-15|edit|portal|pit|cow|stage-map|prologue|map-N`. A chapter ID
alone opens its starting map. A numeric chapter selector is one-based. `boss`
stages David immediately before the still-open encounter gate so gate closure
can be tested rather than skipped. `boss-15` uses the boss entity's generated
arena position to place David exactly 15 tiles to its left while retaining the
gate. `prologue` opens the title-story sequence,
`stage-map` opens the active campaign route, and `cow` mounts the secret map
with O-M-E-G-A already resolved.

While side-scrolling, the keyboard shortcuts are:

- `F2`: 15 tiles left of the current chapter's boss
- `F4`: 15 tiles left of Goliath, switching to the final chapter as needed
- `F6`: current chapter's boss-gate approach
- `F7`: current chapter's first fly-out/edit pickup
- `F9`: current chapter's first network portal
- `F10`: enter the secret Cow Level directly
- `F5`: enter the existing edit QA flow directly
- `F3`: toggle collision hitboxes

Unavailable landmarks report in the HUD message stream and do not alter the
current map.
