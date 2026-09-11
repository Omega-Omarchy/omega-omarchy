# Omega Omarchy deployment

Production: **https://omegaomarchy.org/**. First deployed September 11, 2026
from the reviewed working tree. The public GitHub repository is managed
separately; deployment does not commit or push it.

## Host and release layout

- SSH profile: `ocd-web-core` (OCD's shared Nginx host).
- Web root: `/srv/omegaomarchy/current`, a symlink into `releases/`.
- Initial release: `/srv/omegaomarchy/releases/20260911T121249Z/`.
- Landing-page refresh: `/srv/omegaomarchy/releases/20260911T124622Z/`;
  centered opening section, larger single-emblem pulses, and grounded gameplay
  previews in all three fidelity tiers. The previous release remains available.
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
