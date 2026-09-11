# Omega Omarchy launch website

The launch site for **[omegaomarchy.org](https://omegaomarchy.org/)**, deployed September 11, 2026.
This is an independent parody of [omarchy.org](https://omarchy.org/), using
Omarchy's Tokyo Night colors, the block wordmark, a pixel field, monospaced
copy, large sans-serif headings, and a theme shortcut. The game copy is
original. Attribution to the operating system stays visible in the footer.

The site presents the actual launch scope: playable Chapter 1, a browser game,
a Linux source build, three built-in characters, and an agent character kit.
It does not advertise the five development chapters as a finished campaign.

## Local build and preview

From the repository root:

```sh
./scripts/omega website
./scripts/omega website-serve
```

Open **http://127.0.0.1:8820/**. The build emits `dist/website/` with a fresh
browser game at `play/`. It uses the existing Python/game toolchain; the
website itself is plain HTML, CSS, and JavaScript, with no npm dependencies.

For copy/style edits, retain the already-built game:

```sh
./scripts/omega website --landing-only
```

Refresh the same preview after rebuilding. To copy a different already-built
browser runtime into the site, use `--game-dir PATH`. `--out PATH` changes the
export directory; use the server's `--directory PATH` to preview that export.

## What's wired up

- Main Play / Install links launch the real Chapter 1 game at `play/`.
- Explore / Corrupt / Convert select actual game-renderer captures. The Explore
  capture uses a collision-settled character standing beside the earned portal. 16-bit,
  High, and Ultra change the capture's real fidelity, not a CSS blur filter.
  The same Preview detail selection swaps the robot crew to the game's actual
  matching sprite tier, without restarting their assembly or idle motion.
- News opens its own `/news/` page. Authored announcements share a chronological
  feed with repository commits and published GitHub releases, with filters for
  each category. The header shows the emblem, News, Game, Characters, and Manual.
- The theme button or `T` cycles Tokyo Night, Everforest, and Gruvbox. Theme
  and motion preferences are stored locally. Text entry and standard browser
  keyboard shortcuts are left alone.
- The real apple-core robot sprites assemble the hero once when the page
  loads: etch and lift the Omarchy wordmark, hang it, add OMEGA with the left
  claw, then retract and idle indefinitely. Claws remain open until contact,
  close before carrying, and open at the installed sign before withdrawing.
  Neither sign is taken down. Compact screens use a separately staged
  composition with the same arm proportions. OMEGA uses the installer's
  proportional inset from the wordmark's left edge. The shorter hero stage
  and smaller tagline bring the introductory content higher on the page.
  The left robot has its own slower elbow dip and wrist flourish.
- The opening section fills the viewport beneath the navigation, with the
  complete sign crew, copy, and buttons centered as one group. Short screens
  and enlarged text can grow the section naturally without clipping controls.
- A pixel trail follows mouse movement. On wide screens a larger Omega artifact
  bounces around the viewport and periodically emits one expanding, fading
  emblem. Empty-space clicks emit that same single emblem. These decorations
  let clicks and selections pass through.
- The persistent Pause motion button stops all decorative motion and shows
  the completed sign. Device reduced-motion settings do the same. Hidden
  tabs suspend the animation, and the robot clock pauses outside the viewport.
  Pausing or requesting reduced motion finishes the assembly; resuming does
  not replay it. Theme changes, resizing, and tab visibility preserve progress.
  Pointer effects use a bounded particle pool and a capped canvas resolution.
- The character kit is a real downloadable ZIP. Character import remains in
  the game. The cast on the website is a showcase, not a saved player choice.
- The manual's native disclosure controls work without JavaScript. The Linux
  command block copies to the clipboard, with text selection as a fallback.
- Layouts adapt to narrow screens, controls have visible keyboard focus, and
  reduced-motion preferences disable decorative transitions.
- No accounts, analytics, trackers, external font requests, or autoplay media.
- Canonical and social metadata, sitemap, robots file, favicon, and a custom
  404 page are included. Both pages use the selected **One choice? Think again.**
  Goliath card, with separate Open Graph and X large-image exports and alt text.

## Validation

```sh
node --check website/site.js
node --check website/theme.js
node --check website/motion.js
node --check website/news.js
node --test website/motion.test.mjs website/news.test.mjs
.venv/bin/python -m unittest discover -s website -p 'test_news_build.py'
.venv/bin/python website/check.py
bash -n scripts/omega
```

The export check verifies both pages' links and anchors, media variants, fonts and
licenses, robot parts and animation modules, the agent kit, metadata, and the
game payload. It also rejects local URLs in the production page. The motion
tests sample both compositions at 60 Hz to verify fixed link lengths and
reachable grips, prop attachment, contact and release timing, indefinitely
installed signs with moving idle arms, continuity at every transition,
reflected motion bounds, and pause conditions.
News tests cover real git history, HTML/script escaping, live feed normalization,
draft exclusion, sorting, deduplication, and partial or unavailable API responses.
This is code/build/content validation, not a claim of browser interaction or
visual QA.

Animation timing and inverse kinematics are in `motion-model.mjs`; canvas
rendering, input, and motion preferences are in `motion.js`. The lettering and
robot artwork already exist in the game. The web animation is an original
implementation inspired by the reference site's pointer, pixel-etch, and
bouncing effects; it does not embed that site's code or effect runtime.

## Updating News

Add intentional announcements to `news/editorial.json`, using a unique slug,
a timestamp with a timezone, a title, and plain-text paragraphs. The permalink
must be `/news/#YOUR-SLUG`. Rebuild the site to include the announcement.

Every build reads the latest 20 commits from the local checkout and renders
them directly into `news/index.html`, so the feed is readable without JavaScript.
It records committed history, not the uncommitted working tree. Source archives
without `.git` still produce the authored announcements.

On visiting News, the page requests the latest 20 commits and releases from
the public `Omega-Omarchy/omega-omarchy` GitHub API. These read-only requests
use no credentials or embedded tokens. Unavailable endpoints retain their
build snapshot independently; status text explains when fallback data is shown.
Draft releases are omitted, prereleases are labeled, and titles and excerpts
are rendered as text. No releases are invented from development notes or tags.
The local fallback currently contains commits; published releases arrive from
GitHub when available. These requests only run on the News page.

## Production hosting

The public site runs on the OCD web host behind Cloudflare. HTTPS redirects to
the canonical domain, the origin certificate renews with Certbot, and the game
bundle is cached at Cloudflare. See [the deployment runbook](deploy/README.md)
for release promotion, cache purges, verification, and rollback. The matching
Nginx virtual host is kept in `deploy/omegaomarchy.nginx`.

Serve **the contents of `dist/website/`** as the HTTPS web root. There is no
server-side application or database.
Keep normal directory-index behavior so `/play/` serves `play/index.html`;
do not rewrite all requests to the landing page. The `.apk` file is the
browser game's downloadable resource bundle and must be served as a binary
file, with its filename preserved. The game currently fetches its Python /
WebAssembly runtime from the existing pygbag CDN, as the standalone build does.

The prepared canonical origin is `https://omegaomarchy.org`. The source and
contribution links target `https://github.com/Omega-Omarchy/omega-omarchy`,
which becomes publicly usable when the repository is made public. The Linux
instructions use a source checkout; no nonexistent binary release is linked.
The launch date in `index.html` and `sitemap.xml` is September 11, 2026.

The build and preview scripts remain local; they do not deploy or publish the
repository. Local preview responses use `Cache-Control: no-cache`. Production
HTML revalidates, browser caches remain short, and large static assets receive
a one-day Cloudflare cache lifetime, with explicit purges after releases.

The export contains the code license and the existing asset/third-party
notices. Font and image provenance is in `assets/README.md`. Keep those notices
with the site. Source-code licensing and game-asset licensing are distinct.
