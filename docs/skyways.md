# Workshop skyways and invisible platforms

Generator **3.12.0** reserves an upper screen for optional routes on every
campaign map, hardware island and the Cow Level. Start a new world for this
geometry; old world identities are not rewritten. Core and example packs
are resealed for the new generator.

Connect a new landing in the workshop and seal the edit to create two linked
ring portals. Canceled, untouched or disconnected edits create no portal.
Enter by collision, exactly like ethernet/wifi traversal. Leaving the arrival
portal rearms transport; waiting there never bounces the player back. Endpoints,
headroom and support remain protected against edits and cannon damage. Portal
metadata and constructions persist, including the ephemeral Cow map.

Skyway transport moves the body and camera through the current world over 24
ticks (0.4 seconds), bypassing terrain during transit. It uses no transfer
screen. Ethernet/wifi keep their existing presentations.

The upper tier has terraces, gaps, split decks and raised reward branches,
with no continuous catch floor or recovery ladders. Miss a platform and fall
back into the level. Upper platforms stop before a descent corridor calculated
from map height, terminal fall speed and a running double jump, with a further
three-tile landing allowance. This reserves 41–44 tiles before the boss gate
in the standard fixture, rather than the old ten-tile gap. Small boss islands
therefore have shorter upper routes. Islands without a boss use their available
width. The special
skyway instructions, overview graphics, editor shortcut and cyan overlay have
been removed. Rising portal rings provide the visual cue; reduced motion freezes
them. Required progression, penguins and workshop pickups stay below the tier.

`K` is an invisible **one-way ceiling**, not solid terrain. It blocks upward
body crossings, including cannon and phase movement, but offers no support and
does not obstruct descending or horizontal motion. This retains workshop-only
entry while permitting falls out of the tier. The protected boundary is encoded
in the grid and is not a selectable tile.

## Traversal validation

Generator, workshop and browser editor share the same static checker. Standing
travel requires two cells of clearance. Low tunnels require a supported slide
corridor entered from grounded standing space. Ladder edges require body
clearance. Jumps sweep a 10×18 body through normal and single-air-jump trajectories
using the physics constants. Solid platforms block ascent; crossings and `K`
retain their one-way semantics. A straight line between landings is insufficient.

Upper connectivity is checked separately from spawn-to-boss access. Results
are cached by immutable geometry, so editing invalidates them. The checker does
not certify moving-platform timing, enemies or a complete input replay. Tests
also replay every adjacent upper-deck gap with normal movement/jumps over three
seeds and test contact portals, return trips, falls and cannon/phase exclusion.

## Invisible platforms

`I` uses Omarchy green (#9ece6a), retaining the source tile shading, and stays
solid while hidden. It reveals within one tile of the visible player
silhouette and hides again on departure. A faint shimmer occurs in
a 360-tick cycle, except with reduced motion. The twelve-frame pulse peaks at
56/255 alpha. Walled Garden contains hidden
middle sections of upper decks and a few optional spans below. Visible landing
pads flank upper hidden spans. The browser editor shows these tiles for editing.

The browser game packages Chapter 1 and Cow; later chapters are inspectable in
the editor/scene review and playable natively. See `refinement-review.md` for
review commands, asset registration and validation evidence.
