# Controls

Keyboard is sufficient for the first-chapter slice. Gamepads are mapped from
the start (hot-plug / keyboard fallback).

| Action | Keyboard | Gamepad |
|---|---|---|
| Move | Arrows / A D | Left stick / D-pad |
| Jump / confirm installer | Z or Space | A |
| Kick / equipped attack | X | B |
| Interact / recruit / Play Now | E or Return | X |
| Equipped item / open loadout (pause) | C | RB |
| Reuse (in battle/edit palette) | R | Y |
| Customize / Limitless panel | Tab | Back / View |
| Pause / settings | Escape | Start |
| Pause: choose row | Up / Down | D-pad Y |
| Pause: change fidelity/display/item | Left / Right | D-pad X |
| Installer: change option | Up / Down | D-pad |
| Installer: confirm Yes/No | Left / Right | D-pad X |

Pause → Credits opens the cinematic roll. Jump/confirm, Interact or Pause returns
to the previous screen; after Goliath, the first skip advances the cast sequence
to the roll. Reduced Motion presents static pages on the same soundtrack timer.
Up rewinds the credits and backing music; Down advances them. Tap for one second,
or hold to accelerate up to 32×. Release to resume playback. Scrubbing gives
short audible previews and respects mute. These controls also work in the cast
cinematic, with keyboard remaps and gamepad movement controls.
In the over-the-shoulder editor, Up/Down pans through the full playfield height.

Character setup: Up/Down or Left/Right chooses David, The Omarch King, The Omarch
Queen, or an installed character. Type to replace the name, Backspace to edit,
and Enter to select. **Create with your agent** opens the kit instructions;
Up/Down returns to selection. The browser's character import controls are
below the game. See [character creation](character-creation.md).

Enemy contact opens the turn encounter directly: Z reason, X patch, Left fork,
Right demonstrate, C use the equipped item, R reuse, E recruit. The opponent
then takes a visible turn and raises or lowers the BS Meter.

In side-scrolling play, X kicks and C throws or deploys the
item slot. Logic Bombs, Manifests, and Penguin Flocks are consumable; the other
tools remain equipped. Recovering any tool fills the HUD tool-strength meter;
item effects begin slightly below the former fixed baseline and grow beyond it
until the meter caps. Pause, highlight Items, then Z/X (or press C anywhere on
pause) for the two-row item and attack loadout screen.

Down crouches. Press Down with Left/Right—or press Left/Right while already
crouched—to push into a slide. Double-tap Left or Right to rush briefly. Press
Jump once more while airborne for a smaller height boost. A ladder holds David
in place without continued Up input; Down+Jump performs a fast slide while
holding the last climb pose. Outward input at a terminal ladder landing does
not remount the ladder. Kicks can trigger hardware blocks and destroy visibly
cracked optional cache tiles.

Hardware portals mount another generated map after their connection sequence.
The arrival portal remains inert until David completely exits its tile and
re-enters. Pivot platforms tilt under rider weight, moving lifts carry David,
and cyan updraft columns provide optional vertical routes. Jumping anywhere in
an active gust uses the same full-strength impulse as jumping from solid
ground. Red corrupted-code
pits slow falls and repeatedly deduct score while touched; talking-point
projectiles also deduct score, and score never drops below zero.
Closing and closed boss gates stop friendly and hostile projectiles. If BS
overload returns David to the checkpoint, the gate reopens and must be crossed
again before its boss becomes active.

OMARCHY edit: arrows or D-pad move the cursor within the editable playfield.
Taps move one tile; holding accelerates after a short delay, capped at 20 tiles
per second. Release or change direction to reset the acceleration. R/Y cycles
platform, ladder, and bumper, X/B places, C/RB removes, Space/Z or A seals,
E/X undoes the last operation (or cancels when no operations remain), and
Tab/Back resets the whole unsealed arrangement. Every edit is previewed before
the reversible zone delta is validated and sealed.

Chapter 1 ends at a dedicated completion screen. Z/A opens the credits, X/B
saves that completed boundary, and R/Y explicitly opts into the unqualified
development chapters. Ordinary completion never drops directly into Chapter 2.

Pause and select **New World** to enter the reroll confirmation. It defaults to
No; arrows/D-pad choose, Z/A confirms, and E/X or Pause cancels. A confirmed
reroll archives the old sealed world, retains character/settings/converted
capabilities, and resets chapter progress, score, items, and penguins. If the BS
Meter maxes out, Z/A or E/X retries from the chapter checkpoint with a 100-point
score deduction; nobody is deleted and the current generated world is retained.

## Remapping

Pause and select **Controls**. Up/Down chooses an action, Left/Right switches
between the primary and alternate keyboard slots, and Reuse switches between
keyboard and gamepad-button pages. Confirm begins capture. Action resets the
selected binding, Item resets every binding on the active device, and
Interact/Pause returns to pause. Escape cancels keyboard capture; D-pad Left
cancels gamepad capture. While capturing an alternate keyboard slot, Backspace
or Delete clears it.

When a captured key or button already belongs to another action, the two
non-empty bindings swap so a single press never silently triggers both. An
empty alternate slot cannot steal and erase a required primary binding; that
capture is rejected with feedback. F1–F12 are reserved for private-alpha
QA. Keyboard remaps and physical gamepad action buttons apply immediately and
persist in saves and world rerolls; compact gameplay prompts follow the most
recently active device. Controller stick/D-pad directions remain conventional
and are not yet remappable.

QA-only (never required for the golden path): F2 current boss minus 15 tiles,
F4 Goliath minus 15 tiles, F5 force edit, F6 boss-gate
approach, F7 edit pickup, F9 network portal, F10 Cow Level, F8 force turn-based, F1 skip
installer, F3 hitbox overlay, **F11 credit roll**, **F12 cast cinematic then credit roll**.
The credits shortcuts work from any screen, including setup, and return to the
screen you left. Focus the game canvas first in the browser. The CLI warp equivalents are documented in
`docs/playtest-warps.md`.

In the Cow Level, jump or fall into the cannon's forgiving rear-hatch capture
area. A short input lock follows entry; release the entry jump, then press and
hold Jump to spell LAUNCH and build power. Up/Down changes barrel angle and
releasing Jump fires. Upward and forward contacts are destroyed until landing,
while downward-only contact retains ordinary collision so the launch can end.

Programmatic integrations can use `Accessibility.remap`; they pass through the
same conflict-safe binding tables as the in-game screen.
