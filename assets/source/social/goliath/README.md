# Goliath social artwork

For the fictional Omega Omarchy final boss's public persona, **@goliathfyi**.

- `profile-original.png`: maintainer-supplied upscaled Goliath image, received 2026-09-11 as `goliath-upscaled.png`; original pixels retained.
- `../../../ui/social/goliath-profile.png`: 160 × 160 runtime derivative for the final boss's mock X panel, rendered with a circular mask. Boss animation assets remain separate.
- `header-master.png`: generated with Codex's built-in image-generation tool using that supplied image as a subject reference, 2026-09-11, 2172 × 724.
- `goliath-x-header.png`: final 1500 × 500 PNG export, proportionally downscaled without cropping. Also delivered to `~/Transfer/Outbox/omega-omarchy/goliath-x-header.png`.

X's recommended header dimensions are 1500 × 500: [official help](https://help.x.com/en/managing-your-account/common-issues-when-uploading-profile-photo). The main copy and eye stay inside the central vertical band, and the lower-left is reserved for the overlapping profile photo. These are local artwork files; nothing was uploaded to the account.

Export commands (ImageMagick):

```sh
convert header-master.png -resize 1500x500 goliath-x-header.png
convert profile-original.png -resize 160x160 ../../../ui/social/goliath-profile.png
```

## Generation prompt

Use case: ads-marketing.
Asset type: final X/Twitter profile header for the fictional final boss Goliath in the pixel-art game Omega Omarchy.
Generate a polished panoramic banner, exactly 3:1 aspect ratio, 1500 x 500 pixels if possible (otherwise 1536 x 512 for export at 1500 x 500). This is the finished artwork, not a screenshot or a mockup.
Input image 1 is a subject and palette reference only: Goliath's accepted upscaled game artwork. Preserve his distinctive horned industrial mech silhouette, green/red/blue/ivory armor with brass edging, violet eye and circular violet chest core. Use a dramatic close crop of his head and shoulder/chest at the far RIGHT, partially emerging from darkness, rather than duplicating the entire square profile portrait.
Scene/backdrop: a blackened technical command console with precise thin schematic circuit traces, branching pathways that converge into a single violet-lit route, restrained instrument markings and a faint engineering grid. Pixel-art-informed high quality game key art, sharp readable silhouette, deliberate texture, no generic blue corporate background. Near-black, desaturated armor green, brass, and violet glow drawn from the supplied character.
Main text verbatim: "ONLY ONE CHOICE" on the first line, "IS PERMITTED." on the second. Large off-white industrial condensed uppercase typography, impeccable spelling, centered in the left-middle of the banner around x=640,y=215, occupying roughly x=320..1030, y=135..290 at 1500x500. Small technical label above it: "GOLIATH // CONTROL AUTHORITY". Text must remain very readable when the banner is reduced to 600 pixels wide.
Composition: visual menace through scale and rigid technical precision. Keep all vital text, face and eye inside the central vertical band y=70..410. Keep the lower-left x=0..300,y=300..500 free of any text or essential detail because the profile avatar overlaps there. Let atmospheric circuitry extend naturally to all edges. No border, no X logo, no additional slogans, no watermark.
