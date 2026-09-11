# Create an Omega Omarchy character with your agent

Give this entire folder to any agent with image creation and filesystem tools.
Tell it your character's appearance and name. A photograph is optional; the
game never sends one to an image service. Choose your own agent and provider.

## Message to the agent

Create a complete playable character for Omega Omarchy using my description.
Read contract.json and this brief. Use reference/ only to understand pose,
canvas registration, and game art style. Maintain my chosen identity, outfit,
hair, proportions, and accessories in every frame. Do not leave David artwork
in the deliverable. Generate the art with your image tool, inspect all poses,
and replace every path in character.json with the finished 26 PNGs.

This is a visual replacement. Do not alter collisions, speed, jump, abilities,
map generation, or game code. Keep descriptive metadata honest, including the
author and license; do not assume reference art transfers its license to new art.

## Delivery contract (version 1)

- Author **Ultra only** as the exact canvas sizes below; the compiler derives
  High and Sixteen-bit from the same artwork. All files are 8-bit RGBA PNGs
  (noninterlaced) with genuine transparency, an opaque subject, and no baked backdrop,
  checkerboard, ground shadow, labels, HUD, trails, projectiles, or machinery.
- Ordinary character canvases are 120 × 108. They render as 40 × 36 world
  pixels, centered horizontally on the player's feet and anchored at their
  bottom edge. Grounded feet should meet y=107, with body center around x=60.
  Keep consistent head scale and support-foot placement through the walk cycle.
  Do not independently enlarge a kick or crouch to fill its whole canvas.
- Collision stays **10 × 18 world pixels**, below the visible shoulders/head.
  TILE stays 16. Crowns, hair, capes, and weapons grant no extra reach.
- Right-facing side poses are flipped at runtime for left travel. Climbing,
  away, flight, and OTS are rear views. Portrait/turn face the viewer.
- A slide uses the normal 120 × 108 canvas and is lowered by six world pixels
  at runtime. Its lowest visible pixel is y=86, matching David (28 in
  Sixteen-bit, 57 in High). The compiler registers this baseline in each tier.
- Prologue poses are centered compositions fitted to their dedicated canvases.
  Captured sits upright facing right. Transfer matches the reference's diagonal
  three-quarter perspective: boots in the lower-left foreground, head in the
  upper-right background, face visible from above, lying supine. Do not use
  a horizontal side profile. Furniture and restraint effects come from the game.
- OTS is a dedicated rear view from head to upper thighs with both hands,
  composed against the bottom of its
  240 × 288 canvas. The edit grid is to its right. No face looking back.
- Portrait matches David's facial registration: on the 96 × 96 Ultra canvas,
  eye centers are roughly (31, 40) and (59, 40), with the mouth around y=68.
  Match face scale and placement before framing hair, crowns or shoulders.
  Distinctive headwear may extend beyond the crop.
- Keep a readable silhouette against dark scenery, and avoid tiny details
  that vanish at 36 pixels tall. Preserve alpha while downsampling.
- Reusing your own idle for battle and portrait for turn is allowed. All 26
  files must exist. No undeclared fallback or missing view is accepted.
- Maximum source PNG size: 1 MiB per frame. Compiled pack: 12 MiB expanded;
  distributable ZIP: 4 MiB for browser import. PNG files and JSON only.

| Frame/file stem | Ultra pixels | Required view or action |
| --- | --- | --- |
| `side-idle` | 120 × 108 | Standing, right-facing profile; neutral feet and hands. |
| `side-walk-0` | 120 × 108 | Right-facing walk: left leg forward, right leg behind (contact A). |
| `side-walk-1` | 120 × 108 | Right-facing walk: left support leg, right leg passing (passing A). |
| `side-walk-2` | 120 × 108 | Right-facing walk: right leg forward, left leg behind (contact B). |
| `side-walk-3` | 120 × 108 | Right-facing walk: right support leg, left leg passing (passing B). |
| `side-jump` | 120 × 108 | Rising jump, right-facing, knees lifted. |
| `side-fall` | 120 × 108 | Descending jump, right-facing, braced to land. |
| `side-land` | 120 × 108 | Brief compressed landing, right-facing, feet grounded. |
| `side-crouch` | 120 × 108 | Low crouch facing right, feet grounded. |
| `side-slide` | 120 × 108 | Low feet-first slide to the right, bracing hand behind; preserve canvas headroom. |
| `side-climb-0` | 120 × 108 | Rear-facing ladder climb: left hand high, right knee high. |
| `side-climb-1` | 120 × 108 | Rear-facing ladder climb: passing A. |
| `side-climb-2` | 120 × 108 | Rear-facing ladder climb: right hand high, left knee high. |
| `side-climb-3` | 120 × 108 | Rear-facing ladder climb: passing B. |
| `side-action` | 120 × 108 | Grounded forward kick to the right, supporting foot planted. |
| `side-air-action` | 120 × 108 | Airborne forward kick to the right. |
| `side-bomb` | 120 × 108 | Overhand throw to the right, empty hand; projectile is rendered separately. |
| `side-hurt` | 120 × 108 | Brief recoil, right-facing; no damage effects baked in. |
| `battle` | 120 × 108 | Right-facing full-body battle stance; may reuse idle. |
| `away` | 120 × 108 | Full-body back view, looking away from camera. |
| `flight` | 128 × 116 | Full-body back view flying away, visible hands and feet, no trail. |
| `ots` | 240 × 288 | Rear view from head to upper thighs, both arms/hands visible; no desk or monitor. |
| `portrait` | 96 × 96 | Face closeup from hairline to chin, eyes level, matching David's framing. |
| `turn` | 96 × 96 | Front portrait for facing the viewer; may reuse portrait. |
| `prologue-captured` | 144 × 162 | Slumped seated body facing right; no chair, orbs, cuffs or machinery. |
| `prologue-transfer` | 252 × 174 | Supine diagonal three-quarter view: boots lower left, head upper right; no bed or machine. |

## Compile, inspect, install

From the Omega Omarchy repository (Python and game dependencies installed):

```sh
./scripts/omega validate-character-source /path/to/this-folder
./scripts/omega build-character /path/to/this-folder --out /path/to/my-character-pack
./scripts/omega validate-character /path/to/my-character-pack
./scripts/omega install-character /path/to/my-character-pack
```

`build-character` also writes a sibling `.zip` for sharing/import. Installing
copies a complete validated version into game-owned local storage. It never
overwrites David or another saved version. Return to character setup (or move
its selection once) to refresh the list, select the installed character, and
start a new world. Existing saves retain their chosen appearance and name.
Built-in King/Queen characters receive the game's framing and animation fixes;
their stored digest records the version at creation. Custom packs remain pinned
to the exact installed digest and never silently select different artwork.

In the browser, use **Import character ZIP** below the game, then select it in
character setup. Import is local, with no upload to a server. Browser storage
attempts to retain the pack; keep your ZIP in case storage is cleared or full.
To bundle a custom character into a browser build, pass `--character-pack` to
the `web` command. World sharing does not distribute character art: share its
ZIP separately. A missing saved pack produces one consistent David fallback
and a visible message, never a mixture of characters between scenes.

Review every frame on dark and light backgrounds. Check right/left walking,
jumping, sliding, climbing, throwing, battle, portrait/turn, both prologue
poses, flight in/out, OTS, and the left-behind ghost at all three fidelities.
Check that crowns/hair are not clipped, feet do not drift, limbs alternate,
and no checkerboard or chroma-key color survives. Validation proves coverage,
dimensions and integrity; visual quality and animation still require review.
