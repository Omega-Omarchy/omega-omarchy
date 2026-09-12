# Third-party notices

This inventory lists third-party and separately licensed components shipped or
referenced by Omega Omarchy. It is not a license grant and does not replace
the notices that travel with each file. See [ASSET-LICENSE.md](ASSET-LICENSE.md)
for how the MIT code license relates to assets and future content.

## Python runtime components

| Component | Pinned version | Reported license | Purpose |
|---|---:|---|---|
| Python | 3.12 | Python Software Foundation License | Bundled interpreter |
| pygame-ce | 2.5.8 | LGPL-2.1 | Native window, input, sound, and rendering |
| Pillow | 12.3.0 | HPND | Image processing and Omega Code output |
| NumPy | 2.4.6 | BSD-3-Clause with bundled-library notices | Pixel processing and packaged native libraries |
| qrcode | 8.2 | BSD | Standard QR encoding |
| PyInstaller | 6.22.2 | GPL-2.0-or-later with bootloader exception | Native bundle construction and bootloader |
| Pygbag | 0.9.3 | MIT | WebAssembly packaging and browser runtime launcher |

The web output also vendors BrowserFS 1.4.3 (MIT) as a compatibility layer for
the pinned Pygbag runtime. Its exact license is retained at
`vendor/browserfs-1.4.3/LICENSE` and copied beside the browser artifact as
`BROWSERFS-LICENSE.txt`. The minified file is retained unmodified from the
BrowserFS 1.4.3 npm package; provenance and digests are documented in the
vendor directory.

The native artifact copies the license/notice files supplied by each installed
distribution into `licenses/`, records their exact resolved versions in
`DEPENDENCIES.json`, and includes Python's license. NumPy, Pillow, pygame-ce,
and their wheels may contain additional native libraries; their upstream
license files are retained in full where shipped. Compare a built artifact's
shared-library inventory against these notices when preparing a distribution.

Build/test-only packages are pinned in `requirements/ci.txt`. They are not
intended to be imported as game features, although the PyInstaller bootloader
and its applicable exception are part of the player artifact.

## Music recordings and permissions

Jeremy Dixon supplied **Super Key Love (Oh Omarchy — theme from Omega Omarchy)**
for the credit roll on 2026-09-11. Its embedded artist field credits Jeremy
Dixon. The game preserves the supplied MP3 and full-length prepared Ogg
encodes. The song follows the project's asset-license scope, not the
source-code MIT license.

The maintainer confirmed **Coded Jason ft. GenX Ancients** as the artist
credit for **Make It Come Alive** on 2026-09-11.

The project includes the maintainer-supplied recording *Make It Come Alive*.
It preserves a decoded FLAC master and derives Ultra, High, and sixteen-bit
runtime interpretations from it. The maintainer reports direct creator
permission to use the work with or without attribution. This notice does not
broaden that grant.

The cinematic credits use a subset of **Noto Sans CJK**, under the SIL Open Font
License 1.1. Its complete distributed notice is retained at
`assets/ui/credits/FONT-LICENSE.txt`. The supplied credit-roll sample was used
as a layout reference; its image and watermark are not shipped.

The credit roll also bundles **Noto Sans Regular** (`credits-sans-fallback.ttf`),
under the SIL Open Font License 1.1 (`assets/ui/credits/NOTO-SANS-FALLBACK-LICENSE.txt`),
used only as a per-character fallback for the small set of accented Latin
letters the primary credits font has no glyph for.

The staged level cue is Rich Kilmer's *Beware the Omarchy Oligarchy*, sourced
from a maintainer-supplied video and independently matched to the copy in
`omacom/radio.omarchy.org`. The radio repository states that submissions must
be the submitter's own work, but specifies no license. The project therefore
does not infer reuse or redistribution rights from its public availability.

Suvikyi's *Boot Up Your New Digital World* is under local conversion review and
is not currently bundled. Jeremy Dixon explicitly reconfirmed direct permission
from Suvikyi to utilize her song in Omega Omarchy on 2026-09-11. That
confirmation is recorded in `credits/music.json`; Suvikyi remains its credited
artist.

## Branding references

- Omarchy logo geometry is sourced from the Basecamp Omarchy repository:
  <https://github.com/basecamp/omarchy>.
- Oligarchy logo geometry is sourced from the public page at
  <https://oligarchy.fyi/>.

Their provenance is recorded in `assets/source/branding/README.md`. These names
and marks are used for an unofficial parody/fan project. They are not relicensed
under MIT, and no affiliation or endorsement is implied.

## Display typeface

- Omarchy Font by Mark Cuda, pinned from commit
  `7268b68077239fcbf91f9e720b338aebcda42591`, is used for the stage-map title.
  The font is licensed under the MIT License; its upstream license is retained
  at `assets/source/fonts/OMARCHY-FONT-LICENSE.txt` and copied into runtime
  bundles as `assets/ui/OMARCHY-FONT-LICENSE.txt`. The typeface license does
  not alter the separate trademark treatment of the Omarchy name or logo
  described above.

## Optional integrations

Limitless Library is optional and is not bundled into the standard native
artifact. The Omarchy panel is source-only in this environment and is not
represented as native-shell-qualified.

Report missing or incorrect attribution through the private reporting route in
[SECURITY.md](SECURITY.md).
