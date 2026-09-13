# Cinematic credits

Open **Pause → Credits** to watch the roll. The Chapter 1 completion screen
opens the same roll and returns to its tally. After Goliath's final defeat and
grounded defeat pose, the game automatically plays the cast title sequence,
then the credits, then returns to the campaign map. Jump/confirm, Interact, or
Pause skips the cast sequence to the roll, or leaves the roll. A short entry
debounce prevents the button that opened it from immediately dismissing it.

For direct previews, **F11** starts the credit roll and **F12** starts the cast
cinematic followed by the roll. Both work during setup as well as gameplay,
use the selected character, and return to the previous screen. Pressing either
shortcut again restarts its sequence while retaining the original return
screen. In the browser, click the game canvas to focus it first.

The cast sequence uses accepted David/custom-character assets, both Omarch
packs, all shipped mobs, every campaign boss and Goliath's cyborg penguin, plus
the existing orb drawing and articulated custodian rigs. Its order, timing,
pose choices and movements depend only on the manifest, chosen character,
detail setting and elapsed time. It creates no new generative imagery.

The roll uses the title screen's wordmark silhouette in white on black, with
paired role/name columns, department headings and two-column name lists.
The four closing badges are original fictional guild parodies: I.A.T.S.E.T.,
SAG / APT-RA, DOLLY STEREO and M.P.A.A.A. They do not use actual union seals.
Reduced Motion substitutes complete static credit pages and still cast cards.

The badge designs take their visual cues from the spoke-shaped
[IATSE crest](https://iatse.net/), the reaching figure in
[SAG-AFTRA's identity](https://www.sagaftra.org/new-sag-aftra-logo),
[cinema sound-system lockups](https://news.dolby.com/en-WW/assets/categories/1219/),
and the orbital globe of the [Motion Picture Association](https://www.motionpictures.org/).
Our versions substitute a terminal medallion, an agent reaching for the Super
key, paired director's chairs, and a circuit iris. Letterspacing, inset strokes,
and smaller inscriptions provide the closing-film-credit treatment in white
on black. All shapes and lettering are drawn by the local generator; none of
the reference organizations' artwork is bundled.

Rebuild their three prepared detail sizes with:

```sh
.venv/bin/python tools/build_credit_badges.py
.venv/bin/python tools/build_credit_badges.py --check
```

The generator uses Pillow and the pinned credits font, supersamples offline,
and writes `assets/ui/credits/guild-badges-{1,2,3}x.png`. The game caches one
opaque image per detail tier and scrolls it with a single blit. The 132-pixel
row height is unchanged, including on Reduced Motion pages. The credits
manifest records the accepted badge image hashes alongside the cast assets.

## Names and attribution

Edit `credits/contributors.toml` to associate a GitHub login with a screen name:

```toml
[contributors.your-github-login]
name = "Your preferred credit"
aliases = ["Your Git author name", "your-commit-email@example.com"]
```

An explicit name wins. Otherwise a pinned GitHub public profile name wins,
then the GitHub username. GitHub noreply addresses, including numbered ones,
identify accounts automatically. Git authors whose account cannot be determined
retain their recorded Git name until an alias or GitHub snapshot connects them.
Normal builds perform no network lookups and expose no author email addresses
in the generated runtime data.

With `gh` installed, maintainers can refresh the optional public identity cache:

```sh
./scripts/omega credits --refresh-github
```

This reads the origin repository's GitHub commits and public profile names,
then writes `credits/github-identities.json`. Review and commit that input so
future builds use the same names. Renaming a GitHub profile never silently
changes a released game's credits.

`credits_build.py` reads the full Git history through HEAD, including authors
and `Co-authored-by` trailers. Changed paths assign contributors to engineering,
world building, art, sound, testing, release and documentation departments.
Every assignment has an audit trail of commit IDs and paths in the manifest.
These are path-based acknowledgments, not line-by-line ownership estimates.
The deliberately excessive film crew is a separate authored comedy section,
initially assigned to Jeremy Dixon through `production.lead`.
The Roman-numeral copyright notice names the Omega Omarchy contributors
collectively; it does not single out the production lead.

The Agent collaborators section also credits Codex / Astra, Codex / Sol,
Grok Build, and Grok Imagine for their assistance.

## Rebuilding

```sh
./scripts/omega credits
./scripts/omega credits --check
./scripts/omega test tests/test_credits.py
```

The runtime output is `src/omega_omarchy/data/credits.json`. Rebuilding twice
with the same Git history, accepted assets and credit inputs produces identical
JSON. It records its Git revision and input hashes. Rebuild it after committing
new contributions when running from source. Native and web release builders
write fresh credits directly into their staged packages, keeping the source
checkout clean. Builds reject shallow history rather than silently omit contributors.
The checked-in runtime snapshot also lets source archives play without Git.

`credits/omacom-foundation.json` is a dated snapshot of the public
[staff](https://omarchy.org/staff/), [artists in residence](https://omarchy.org/air/),
[patrons](https://omarchy.org/patrons/) and [teams](https://omarchy.org/teams/)
on 2026-09-11. It retains the published names and groupings, including companies.
Refresh that reviewed input when the acknowledgment roster changes. These are
special thanks for Omarchy, not game contributors or endorsements.

## Soundtrack and typography

The cast sequence uses the previously accepted renditions of **Make It Come
Alive — Coded Jason ft. The Gen X Ancients**, pinned as prepared Ogg inputs.
The credit roll starts **Super Key Love (Oh Omarchy — theme from Omega Omarchy)**
by **Jeremy Dixon**, supplied through CatchyTune's Inbox. Music credits read
only the embedded author/artist field from each configured source recording.
When that field is absent, `artist` in `credits/music.json` controls the name.
Comments, production tools, permission notes and other metadata are not turned
into on-screen credits. The generated `musicCredits` records the selected field
or fallback and source digest. The offline builder requires `ffprobe` (FFmpeg).
All three audio tiers retain the full supplied performance, encoded at
different Vorbis quality settings. There is no automatic chiptune rearrangement
of this recording.

The builder reads the actual non-looping runtime cue duration (currently
429.863991 seconds). Roll distance follows the measured layout height and that
duration, followed by five seconds of black and silence: approximately **7:15**
in total. The live app advances by elapsed wall time, so dropped frames do not
stretch the credits past the song. Muting music keeps the same visual timing.
To accommodate growth, the extended **All Patrons** list is marked `compact`
in the Foundation snapshot. Its font and line spacing decrease in quarter-point
steps from 8 to a minimum of 6.5 logical pixels only when the measured roll
would exceed 18 logical pixels per second (about ten seconds per screen).
The renderer chooses the largest size that meets that target. Headings,
contributor credits and the other Foundation groups keep their normal sizes.
Names retain their order and wrap at the chosen size; none are omitted.
If the roll still exceeds the target at the minimum, it retains that readable
floor and finishes with the song. Reduced Motion pages use the same layout.
The music section also acknowledges Rich Kilmer and Suvikyi's documented
development/inspiration tracks. These remain separate from active level cues.
Jeremy Dixon reconfirmed direct permission from Suvikyi to use her song on
2026-09-11; that confirmation is recorded in `credits/music.json`.

The roll vendors a subset of Noto Sans CJK with Latin, Greek, Cyrillic, general
punctuation and the current roster's CJK glyphs. Its OFL notice is included in
`assets/ui/credits/FONT-LICENSE.txt`. When adding names in additional scripts,
extend the font subset and run the glyph-coverage test. No host system font or
live website font is needed for the roll.

## Workshop movement

Over-the-shoulder flight resolves into the actual seated sprite during its last
28 percent, sharing the edit view's layout for every character and detail tier.
The cursor retains the event's horizontal area and can move through every map
row. The camera follows vertically with a central quiet band. Controls move to
the top when the cursor reaches the bottom rows, and the foreground character
becomes translucent when it would cover the selected tile. The physical player
and its protected ghost remain at their original playfield position.
