# Omega Omarchy deployment

Production: **https://omegaomarchy.org/**. First deployed September 11, 2026
from the reviewed working tree. The public GitHub repository is managed
separately; deployment does not commit or push it.

## Host and release layout

- SSH profile: `ocd-web-core` (OCD's shared Nginx host).
- Web root: `/srv/omegaomarchy/current`, a symlink into `releases/`.
- Initial release: `/srv/omegaomarchy/releases/20260911T121249Z/`.
- Centered credit opening: `/srv/omegaomarchy/releases/20260913T055314Z/`;
  ships `fb91a2f` (opening code `f9557af`). The wordmark holds by itself at
  vertical center for three seconds, then eases into all four introductory
  lines. Movement rejoins the prior linear scroll before STARRING enters.
  Its first visible pixel remains on frame 432 at 16-bit and 431 at High/Ultra;
  all 450 compared browser frames after the join match the previous roll.
  The 56 credits/scrubbing tests and site export checks passed. Scrubbing is
  deterministic, and Reduced Motion resumes its existing page schedule after
  the hold. Uploaded files were hash-verified and changed URLs purged.
  Public bundle SHA-256:
  `f8cbb5a4b073ac959908a4ea2207d7feec61226f7c4c249f8cc77ef4920ed2d9`.
  Previous release `20260913T053335Z` remains available for rollback.
- Credits smoothness and controls: `/srv/omegaomarchy/releases/20260913T053335Z/`;
  ships `78cb91f` (rendering/controls `627c327`, credit snapshot `6fab651`,
  readable movement hints `78cb91f`). Fallback glyphs now align by baseline.
  Prepared roll text and visible patron-row rendering cut measured Ultra
  patron render time by 84–85%, with 2,754 browser and 2,754 native pixel pairs
  matching after applying the font correction to both sides. Up/Down scrubs
  both sequences and backing tracks, with accelerating holds and audible seek
  previews. Editor taps move one tile and holds accelerate to a capped rate.
  The 164 focused tests passed; all 40 credits tests passed again after the hint
  correction. The browser audio integration check covered holds, reversals,
  release, silence, and the cast fade/roll transition. Site export checks passed.
  Uploaded files matched the local build before promotion, and changed URLs
  were purged from Cloudflare. Public bundle SHA-256:
  `f2125ca2371fffcb98fc9448a216fe2b778685d4883ac616144d0230ca78ac85`.
  Previous release `20260913T043402Z` remains available for rollback.
- Automatic landing announcement: `/srv/omegaomarchy/releases/20260913T043402Z/`;
  ships `e5ee4dd`. The landing link now mirrors the newest News headline,
  UTC date, and permalink at build time, with a wrapping headline and date
  below on narrow screens. All 15 News tests and the site export checks passed.
  Only the landing page, News snapshot, and stylesheet changed. Uploaded files
  were hash-verified and changed URLs purged from Cloudflare; the game bundle
  remains unchanged. Previous release `20260913T042709Z` is retained for rollback.
- Version 0.1.2 performance announcement: `/srv/omegaomarchy/releases/20260913T042709Z/`;
  publishes the News entry from `bcd7490`, automatically promoted to the top
  of the feed and linked from the landing page. All 14 News tests and the site
  export checks passed. Only `index.html` and `news/index.html` changed; the
  game and other assets matched the prior release. Uploaded hashes were
  verified before promotion, and changed URLs were purged from Cloudflare.
  Previous release `20260913T023737Z` remains available for rollback.
- Closing-credit artwork: `/srv/omegaomarchy/releases/20260913T023737Z/`;
  ships code `2fde504` and credits/build revision `af4c996`. The Roman-numeral
  copyright notice credits the Omega Omarchy contributors collectively. Four
  original guild parodies now use detailed, deterministically prepared artwork
  at each detail tier, drawn with one cached opaque blit during the roll.
  The 101 focused credits/render tests passed; after enlarging the small
  inscriptions, all 36 credits tests passed again. All three detail tiers were
  inspected in the browser. The production package contains the accepted PNGs
  and updated notice, with no diagnostic entry point. Every uploaded file was
  hash-verified before the atomic switch, and changed URLs were purged from
  Cloudflare. Public bundle SHA-256:
  `5b366e3ee54483af0ae69b85f20284a1d67bf16d0ea242be9618a24975e7e307`.
  Previous release `20260913T021321Z` remains available for rollback.
- Pickup and block-break performance: `/srv/omegaomarchy/releases/20260913T021321Z/`;
  ships code `6bbafb7` and credits/build revision `4a7e1eb`. Uniform-alpha
  browser flashes reduce Ultra post-event rendering from about 24.3 ms to
  16.2 ms; incremental menu SFX preloading removes first-use sound decoding
  from normal pickups and hits. The 154 focused tests passed. All 1,872
  browser comparison pairs preserved camera/gameplay state and stayed within
  the documented one-unit RGB rounding tolerance during flashes; unflashed
  output and all 1,872 native pairs matched exactly. Every uploaded file
  matched the local build before promotion; changed URLs were purged from
  Cloudflare. Public bundle SHA-256:
  `fa952a001e8a0e196e575db920c50fdc1a9f489ea90886b0ac02d9ff36a06894`.
  Previous release `20260913T001018Z` remains available for rollback.
- Prologue, route-map, and title-card optimization: `/srv/omegaomarchy/releases/20260913T001018Z/`;
  ships code `3ee10b7` and credits/build revision `b4986d5`. All 42 browser
  cases improved median and p95 render time; all 3,024 browser frame pairs
  matched the preceding renderer exactly. The 158 focused tests passed, as
  did native comparisons and an interactive installation/prologue/map-to-play
  check with The Omarch King. Every uploaded file matched the local website
  build before the atomic switch; changed URLs were purged from Cloudflare.
  Public bundle SHA-256: `b7d10447b783d521caa67c68b40537888e5a8ba96fc290b5d0bcbf141845ca91`.
  Previous release `20260912T223706Z` remains available for rollback.
- Opaque-background, panel, and cannon optimization: `/srv/omegaomarchy/releases/20260912T223706Z/`;
  ships code `3cf5cae` and credits/build revision `5eb5838`. All 24 isolated
  browser cases improved median render time by a further 21.7–44.9% relative
  to `14f7590`, with sampled pixels, camera output, and gameplay state matching.
  The 80 focused tests passed. Every uploaded file matched the local build
  before promotion, and changed URLs were purged from Cloudflare. Bundle
  SHA-256: `798da9beffc414af8dc581ef2847a2c52cd04a0ae473037231869a4e159a167b`.
  Previous release `20260912T221939Z` remains available for rollback.
- Transparent-padding and sprite-cache optimization: `/srv/omegaomarchy/releases/20260912T221939Z/`;
  ships code `e00340c` and credits/build revision `14f7590`. Browser comparisons
  improved all 18 measured medians while preserving sampled pixels and camera
  output. The ordinary game build passed interactive checks. Every uploaded
  file matched the local build before the atomic switch, changed URLs were
  purged from Cloudflare, and the public bundle SHA-256 matched
  `a7779617151fcf99b82291d3e2810938965ce198fb7184f883365691ad4e2cb5`.
  Previous release `20260912T205036Z` remains available for rollback.
- Landing-page refresh: `/srv/omegaomarchy/releases/20260911T124622Z/`;
  centered opening section, larger single-emblem pulses, and grounded gameplay
  previews in all three fidelity tiers. The previous release remains available.
- Game-fix release: `/srv/omegaomarchy/releases/20260911T195124Z/`; ships the
  fix for the credit roll quitting itself via a hijacked shutdown counter, the
  tightened chapter-complete panel, and the installer confirm-debounce fix.
  Previous releases remain available.
- Credits & responsiveness release: `/srv/omegaomarchy/releases/20260912T053230Z/`;
  ships the film-credit styling pass (caps convention, baked guild seals,
  multi-column patrons, Y-axis scroll-bobbling fix, per-character font
  fallback for accented names), the render caching fixes, the shortened
  installer post-generation hold, and the fix for the window taking multiple
  seconds to close mid-installation while a procedural-generation step was
  in flight. Previous releases remain available.
- Web glyph-fallback fix: `/srv/omegaomarchy/releases/20260912T055255Z/`; the
  prior release's per-character font-fallback check relied on
  `pygame.font.Font.metrics()` to detect missing glyphs, which matched the
  primary credits font's real coverage exactly on native SDL_ttf but
  disagreed under pygbag's WebAssembly build, rendering five accented
  contributor-name characters (Ć, İ, Ł, Ř, Ş) blank in the browser credit
  roll. Replaced with a fixed, fontTools-verified set of the primary font's
  actual gaps. Previous releases remain available.
- News pinning: `/srv/omegaomarchy/releases/20260912T060345Z/`; the freshest
  News-type announcement is now pinned to the top of the News page's
  unfiltered "All" feed by default (a newer announcement automatically
  supplants it; an entry explicitly marked `pinned: true` overrides the
  default), instead of announcements sorting purely by date alongside
  commits and releases. Applied identically to the static build and the
  client-side GitHub-merged feed. Previous releases remain available.
- Hero launch-note link and wandering-logo tweaks: `/srv/omegaomarchy/releases/20260912T062054Z/`;
  the "Chapter 01 / Open-source launch" hero note is now an undecorated link
  to whatever pin_to_top currently promotes on the News page (matching the
  omarchy.org convention of that badge always hooking the latest post), with
  its date wrapping onto its own line at narrow widths instead of the whole
  phrase. The wandering Omega logo drift doubled in speed and now also
  bursts on every edge bounce. Previous releases remain available.
- Restored the random-interval logo burst: `/srv/omegaomarchy/releases/20260912T062358Z/`;
  the prior release replaced the ~9-14s random flourish burst with the new
  bounce-triggered one instead of keeping both. Both fire now, as intended.
  Previous releases remain available.
- Loading-window centering and audio-settings caching: `/srv/omegaomarchy/releases/20260912T205036Z/`;
  the pygbag loading box appeared at its unstyled top-left flow position
  before its own JS measured and centered it; now centered via CSS from
  first paint, with the JS's own positioning patched to clear the CSS
  transform it would otherwise compound with. AudioManager.update() also
  re-normalized and re-validated every audio setting key every frame
  even when the exact same settings object was passed in; now skipped
  when unchanged (~8x faster for that path in isolation). Live in-browser
  profiling to chase further gameplay sluggishness was attempted but
  blocked by this environment's software-rendered headless Chromium
  never completing the WASM boot in reasonable time; native cProfile
  remains the verification method available here. Previous releases
  remain available.
- Render-loop optimization and version 0.1.2: `/srv/omegaomarchy/releases/20260912T200036Z/`;
  frame() already resolved fidelity once per frame via _layout(), but
  _fid() and several other call sites re-derived it independently every
  call (~100 redundant lookups/frame across every scene); fit_text(),
  blit_text(), and _panel() re-measured/re-rasterized on every call
  regardless of whether their input changed; the enemy/boss draw path
  re-ran its base fidelity scale every frame before its own wobble-cache
  even got a chance to help. All now cache by their actual inputs.
  Profiled locally: 10-34% less profiled frame cost depending on scene,
  with the turn-based battle UI improving the most. Previous releases
  remain available.
- Mobile/touch redirect: `/srv/omegaomarchy/releases/20260912T191213Z/`; reported
  after someone hit Play on an iPhone and reached the loading screen and
  character picker for a game with no touch input, having also started the
  ~60MB WebAssembly download. A touch-primary device now redirects away from
  `/play/` before browserfs.min.js or pygbag's loader can start, back to the
  homepage with an explanation and links to a desktop browser or the native
  Linux build; the homepage itself also retargets its own Play links up
  front. Verified via Chrome DevTools Protocol with an emulated iPhone.
  Previous releases remain available.
- Deferred off-screen robot-detail tiers: `/srv/omegaomarchy/releases/20260912T183008Z/`;
  reported after a several-second freeze partway into the hero robots'
  choreography on a cold-cache reload. `motion.js` previously fetched and
  decoded all 18 robot part images (3 fidelity tiers) before the first
  frame could draw, though only one tier is ever visible unless the
  showcase's fidelity toggle is touched. Now only the on-screen tier (6
  images) loads eagerly; the other two load on first request and are
  cached. Verified via Chrome DevTools Protocol that initial load only
  fetches the default tier, the toggle lazily fetches the others, and a
  repeat selection issues no further requests. Previous releases remain
  available.
- Virtual host: `/etc/nginx/sites-available/omegaomarchy.org`, enabled by a
  matching symlink in `sites-enabled/`; source: `omegaomarchy.nginx` here.
- ACME webroot: `/srv/omegaomarchy/acme`.
- Certificate: `/etc/letsencrypt/live/omegaomarchy.org/`, covering the apex
  and `www`. Certbot's existing timer renews it; the saved deployment hook
  reloads Nginx. The first certificate expires December 10, 2026.

The server hosts other projects. Deploy only into Omega's release directory
and virtual host. Never replace the shared Nginx configuration. The Cloudflare
API credential stays on the operator's machine and is never copied to the
server, generated site, or repository.

## Cloudflare configuration

The existing proxied apex A record points to this host; the existing proxied
`www` CNAME points to the apex. The launch kept DNS and mail records intact.

| Setting | Production value |
| --- | --- |
| SSL mode | Full (strict), with a public Let's Encrypt origin certificate |
| Always Use HTTPS | On |
| Minimum TLS version | 1.2 |
| Browser Cache TTL | Respect existing headers (`0` in the API) |
| Brotli / HTTP/3 | On |
| Rocket Loader | Off |

The zone has one added cache rule, **Cache Omega browser game bundles using
origin freshness headers**, with reference `omega_game_bundle_cache`. It
matches `.apk` and `.wasm` on the apex and `www`; cache eligibility is enabled,
edge TTL follows origin headers and bypasses if absent, and browser TTL
respects origin. Other cache rules must be preserved when updating it.

Nginx sends `no-cache` for HTML, five-minute browser caching for scripts and
the game bundle, one-hour browser caching for artwork, and a one-day shared
cache lifetime for the game bundle and artwork. Stable filenames require a
Cloudflare purge when their content changes. HTML is not cached as a page.
The ACME challenge is also served over HTTPS so certificate renewal works
after Cloudflare upgrades HTTP requests.

## Publish an update

Run from the repository root, after reviewing the changes:

```sh
./scripts/omega credits
./scripts/omega website
.venv/bin/python website/check.py

omega_release=$(date -u +%Y%m%dT%H%M%SZ)
ssh ocd-web-core "mkdir /srv/omegaomarchy/releases/$omega_release"
rsync -a --chmod=D755,F644 --delay-updates dist/website/ \
  "ocd-web-core:/srv/omegaomarchy/releases/$omega_release/"
(cd dist/website && sha256sum index.html play/omega-omarchy.apk) | \
  ssh ocd-web-core "cd /srv/omegaomarchy/releases/$omega_release && sha256sum -c -"
```

Only after the upload and both hash checks pass, promote that release:

```sh
ssh ocd-web-core "ln -s releases/$omega_release /srv/omegaomarchy/current.next && mv -Tf /srv/omegaomarchy/current.next /srv/omegaomarchy/current"
```

Compare local and remote SHA-256 hashes for `index.html` and
`play/omega-omarchy.apk` before promoting the symlink. Directory switching is
atomic; no Nginx reload is needed for ordinary content releases. Keep the
previous release for rollback.

After promotion, use Cloudflare's **Custom Purge** for every changed asset URL,
including `https://omegaomarchy.org/play/omega-omarchy.apk` when the game changes.
If using the API, send `POST /zones/{zone_id}/purge_cache` with a `files` array
of full HTTPS URLs. Keep request credentials out of shell tracing and logs.
Include any explicitly used query-string versions. Do not purge unrelated
hostnames. Existing browsers can retain changed assets for their short browser
TTL; a forced refresh obtains them immediately.

When changing the virtual host, upload the reviewed file, install it into the
Omega site, run `sudo nginx -t`, and reload only after that check passes.

## Verify and roll back

- Check the homepage, `/news/`, `/play/`, both sharing PNGs, and character-kit ZIP.
- Check HTTP and `www` redirect to `https://omegaomarchy.org/`, preserving paths.
- Verify `.mjs` serves as JavaScript and `.apk` as binary. A second bundle
  request should show `CF-Cache-Status: HIT`; byte ranges should return `206`.
- Open the public game: enter setup, use F11 for the roll, and test gameplay.
- Verify the Twitter crawler can read the sharing metadata and artwork.
- Check renewal with `sudo certbot renew --cert-name omegaomarchy.org --dry-run
  --no-random-sleep-on-renew` on the host. Target only Omega's certificate.

To roll back, atomically switch `current` to a previously verified release
using the same temporary-symlink procedure, then purge the changed URLs again.
Do not remove active or previous releases as part of deployment.

## Initial release evidence

- Site checks: both pages, 64 links, nine preview images, 18 robot parts,
  character kit, metadata, and included game passed.
- Credits: 23 tests passed, including embedded author/artist extraction and
  external fallback. Website JavaScript: 24 tests; News build: two tests.
- The public HTML, artwork, scripts, downloads, and game bundle matched the
  built files. The bundle served a cached `206` range response after warming.
- Browser checks reached the installer, displayed the F11 credits roll, and
  exercised movement and jumping in Chapter 1. News fetched the public GitHub
  feed. Twitter's crawler user agent received the metadata and card with `200`.
- A Certbot dry run succeeded after HTTPS redirects and Full (strict) were
  enabled, confirming the saved renewal configuration works through Cloudflare.
- Initial `index.html` SHA-256:
  `af32fbf51679517dc62b3a10cb4f65e7b2175e1c23b1db166a361d37f1241549`.
- Initial `play/omega-omarchy.apk` SHA-256:
  `82001fd91a7661e637a791be6c9acd00bbbbafe19c026dd9b294db707a775be5`.

The generated game includes the author-only Super Key Love credit (Jeremy
Dixon), and the notices record Jeremy's direct-permission confirmation from
Suvikyi. Social card 4 is linked by the homepage and News Open Graph/X metadata.
