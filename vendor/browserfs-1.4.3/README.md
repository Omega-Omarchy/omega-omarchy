# BrowserFS 1.4.3

Unmodified browser distribution and MIT license from the published
`browserfs@1.4.3` npm package, retrieved through jsDelivr on 2026-09-03.

- Upstream: <https://github.com/jvilk/BrowserFS>
- Package: <https://www.npmjs.com/package/browserfs/v/1.4.3>
- Distribution URL: <https://cdn.jsdelivr.net/npm/browserfs@1.4.3/dist/browserfs.min.js>
- `browserfs.min.js` SHA-256: `a2a2b38cd567dc20cd024e681df55f34f42174c692f553f8350dae171c2b875b`
- `LICENSE` SHA-256: `3a7e16fe59c38735309c9df4657cda635cfd7a1bf672f5404b7c7ab5cf949d94`

It is loaded before Pygbag 0.9.3 because that release's generated BrowserFS
CDN URL returns 404. Remove the vendored copy only after the replacement web
runtime passes the checks in `docs/web.md`.
