# Website asset provenance

Raster art uses accepted Omega Omarchy assets and the selected social card. No official
Omarchy page screenshots, third-party testimonial portraits, or marketing
paragraphs are reproduced.

- `wordmark.png`: `assets/ui/omarchy-wordmark.png`, the game's existing
  Omarchy wordmark raster. Branding provenance is recorded in
  `assets/source/branding/README.md` at the repository root.
- `social-one-choice-og.png` and `social-one-choice-x.png`: selected social
  card 4, **One choice? Think again.**, approved by Jeremy Dixon on 2026-09-11.
  Generated using the accepted Goliath, Omega emblem and wordmark references.
  Masters and prompts are in `assets/source/social/site-card-samples/`.
  Open Graph uses 1200 × 630; the X large-image card uses 1200 × 600.
- `icon.png`: `assets/ui/omega-omarchy-icon-128.png`, derived from the game's
  selected Powered Artifact Omega emblem.
- `robots/{sixteen-bit,high,ultra}/custodian-*.png`: unchanged copies of the six
  robot parts from each matching `assets/fidelity/{tier}/ui/` directory.
  The website animates these original body, upper arm, forearm, joint, and
  claw sprites using the game's link lengths and image pivots. Preview detail
  switches the entire crew's sprite set; 16-bit rendering disables smoothing.
  No new raster artwork was generated for the sign crew.
- `david.webp`, `king.webp`, `queen.webp`: lossless WebP encodings of the
  existing Ultra portrait PNGs in the main asset tree and royal packs.
- `gameplay-*.webp`: refreshed September 11 with `website/capture_gameplay.py`.
  A fixed-seed Chapter 1 workshop earns the portal; the character is placed
  beside it, then settled using real collision physics before rendering all
  three fidelity tiers. The capture asserts grounded feet and clear headroom.
- `prologue-*.webp`, `battle-*.webp`: WebP encodings of
  `robots-*.png` and `battle-0-*.png` from the September 10
  renderer review in `.local/refinement-2026-09-09/`. The review is generated
  by `scripts/review-refinement.py`. These are controlled game-scene captures,
  not a claim of a continuous recorded playthrough.
- `character-agent-kit.zip`: copied from `assets/character-creation/agent-kit.zip`.
- `omarchy-font.ttf` and its notice: existing game font and license, retained
  for future display lettering; the current large wordmark uses the raster.
- `geist-latin.woff2`: Geist Variable Latin from the official Omarchy site's
  stylesheet (`/_astro/geist-latin-wght-normal.BgDaEnEv.woff2`), downloaded
  September 11, 2026. SIL Open Font License copied from
  https://github.com/vercel/geist-font/blob/main/LICENSE.txt.
- `jetbrains-mono-latin.woff2`: JetBrains Mono Variable Latin from the official
  site's stylesheet (`/_astro/jetbrains-mono-latin-wght-normal.B9CIFXIH.woff2`),
  downloaded September 11, 2026. SIL Open Font License copied from
  https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt.

Font files are served locally. The game's existing `ASSET-LICENSE.md` and
`THIRD_PARTY_NOTICES.md` describe the scope of the game media and branding.
