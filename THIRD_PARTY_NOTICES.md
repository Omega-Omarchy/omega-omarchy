# Third-party notices

This inventory covers direct runtime/build components and retained branding in
the current private technical alpha. It supports review; it is not a substitute
for the final G5 rights audit.

## Python runtime components

| Component | Pinned version | Reported license | Purpose |
|---|---:|---|---|
| Python | 3.12 | Python Software Foundation License | Bundled interpreter |
| pygame-ce | 2.5.8 | LGPL-2.1 | Native window, input, sound, and rendering |
| Pillow | 12.3.0 | HPND | Image processing and Omega Code output |
| NumPy | 2.1.3 | BSD-3-Clause with bundled-library notices | Pixel processing and packaged native libraries |
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
license files are retained in full where shipped. A final release must compare
the built artifact's actual shared-library inventory against these notices.

Build/test-only packages are pinned in `requirements/ci.txt`. They are not
intended to be imported as game features, although the PyInstaller bootloader
and its applicable exception are part of the player artifact.

## Branding references

- Omarchy logo geometry is sourced from the Basecamp Omarchy repository:
  <https://github.com/basecamp/omarchy>.
- Oligarchy logo geometry is sourced from the public page at
  <https://oligarchy.fyi/>.

Their provenance is recorded in `assets/source/branding/README.md`. These names
and marks are used for an unofficial parody/fan project. They are not relicensed
under MIT, and no affiliation or endorsement is implied. Retention for public
distribution remains subject to the separate trademark/branding review in
`docs/OPEN-SOURCE-CUTOVER.md`.

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

Report missing or incorrect attribution through the private security/contact
route described in `SECURITY.md` once that route is enabled for contributors.
