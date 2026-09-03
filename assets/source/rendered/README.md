# Rendered production sources

These are versioned, generated source images for the deterministic asset build.
They contain no private reference photographs. `spritekit.py` removes chroma
backdrops or preserves source alpha, crops the subject, and emits the three
runtime fidelity treatments.

The built-in image-generation workflow used the following compact prompt set:

- David animation: preserve the long-haired, bearded character, black emblem
  shirt, cuffed dark jeans, and black boots; full-body side view facing right;
  create complementary opposite-stride walk, jump, and facing-away climb poses.
- David Ultra finish: modeled mid-1990s pre-rendered platform-game aesthetic,
  dimensional studio lighting, detailed materials, crisp silhouette.
- Boss roster: one transparent, compact game-readable subject for the Package
  Bureaucrat, Dependency Hydra, Distro Commander, Garden Gatekeeper,
  Singularity, Goliath, and Dogma Sprite; preserve each gameplay motif from
  `campaign.py`; use modeled pre-rendered volume and material detail for Ultra.
- Penguin: preserve the cheerful screen-right walking pose, black-and-white
  body, orange beak and raised orange foot; modeled pre-rendered Ultra finish.
- Shared constraints: one connected subject, clean alpha (or flat magenta
  chroma background), even padding, no floor, cast shadow, UI, scenery, border,
  added text, or watermark.
- Environment panoramas: six unique, non-tiling Ultra masters—enclosed
  installation chamber, package jungle, macro-scale computer hardware, glass
  garden, singularity cavern, and composite Goliath ruin—with no characters,
  text, logos, repeated landmarks, or seams. The hardware panorama has a
  separate sparse true-alpha foreground component plane.
- UI frame: one transparent, empty, thin pre-rendered obsidian/gunmetal frame
  with bronze mechanisms, cable detail, chartreuse crystals, and cyan edge
  light; no text, logo, scenery, or symbols.
- Corrected walk cycle: four separately rendered gait phases (two opposing
  contacts and two passing poses), with coherent anatomy, alternating arm and
  leg swing, idle-matched head/body proportions, only one behind-back arm
  phase, and both boot toes facing the direction of travel.
- Dedicated slide and throw poses: a low leaned-back push-off slide and a
  grounded, high-hand item-release follow-through, both derived from the Ultra
  idle model rather than transformed walk frames.
- Original minion roster: Cache Gremlin, Packet Wasp, Lint Launcher, Garden
  Glitch, Void Orbiter, Justice Signaler, and Consensus Crier. These have their
  own Ultra sources and no longer inherit boss silhouettes.
- Tool set: one modeled Ultra master for each of the seven tools. Penguin Flock
  is a bronze/cyan control beacon projecting three small penguin signals, not
  an ordinary low-resolution penguin pickup.
- Bouncer: a single modeled Ultra mechanical spring-pad master with bronze
  housing, chartreuse energy surface, cyan light, transparent background, and
  no lettering.
- Structural kit v3: five purpose-built Ultra objects replace the former
  procedural-mask/material blend: seamless solid ground, one modular deck bay,
  a continuous ladder segment, a visibly cracked breakable block, and a barred
  security gate. Ladder/platform crossings and moving or pivoting decks compose
  these same masters rather than introducing separate lookalikes.
- Chapter parallax v3: every one of the six chapter palettes has an independent
  far, middle, and near source plane. These are full-scene Ultra renders, not
  sixth-width crops from a shared strip. Studio/checker plates are recovered as
  deterministic alpha during the bake; opaque scene pixels are never generally
  faded. Ultra bakes once at the native 960×540 canvas height without color
  quantization, and lower tiers reduce those same full-resolution masters.
- Prologue and route plates: the first-person interdimensional transit tunnel
  and unified six-region world map are text-free Ultra masters. Login copy,
  OMEGA/OMARCHY branding, story choreography, boss icons, route state, and
  selection feedback remain deterministic renderer layers.
- Mind Machine table v2: the transfer-room master retains its original camera,
  lighting, architecture, rings, corruption display, and floor while replacing
  only the reclined chair with a tilted consciousness-transfer table.
- Hardware foreground planes v2: all four runtime segments now use separately
  authored transparent compositions with complete cooling, cabling, fan,
  socket, memory, and network structures. They are not crops of the environment
  panorama and contain no internal source seams.
- Cow parallax v4: the secret stage now has three independent transparent
  far/mid/near planes derived from the Ultra art direction. Celestial landmarks
  are excluded so no moon is duplicated while the planes move.
- Cow cannon v2: the Ultra cannon is split into an independent rotating barrel
  and a ground-locked base. The renderer layers the barrel behind the base and
  composites the official mark or live LAUNCH charge state onto its side panel.

Sixteen-bit derives from the Ultra composition at full target resolution with a
64-color SNES-class finish. High derives at twice the logical raster density
with a 256-color 32-bit-era finish. Ultra uses the unquantized modeled source at
three times the logical raster density.
