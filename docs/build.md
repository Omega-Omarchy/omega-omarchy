# Build, test, and run

Python 3.11+ on Linux. pygame-ce, Pillow, qrcode, numpy. Web packaging also
requires the pinned Pygbag package and `ffmpeg` on `PATH`.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --requirement requirements/bootstrap.txt
.venv/bin/python -m pip install --no-build-isolation --requirement requirements/ci.txt
# optional genuine Limitless queries:
# .venv/bin/pip install ./path/to/limitlesslibrary
./scripts/omega run
./scripts/omega doctor
```

Running `./scripts/omega` without a command prints help and does not launch an
expensive test or asset job. Development verification is issue-dependent; see
[testing.md](testing.md). The explicit `release-check` gate builds assets,
validates both maintained packs, runs the complete suite, dumps the fixture
identity/campaign, smoke-launches native play, and writes the Chapter 1 canvas
preview. That gate ignores player-enabled installed packs so its fixture
identity remains reproducible; normal native play applies them.

| Command | What it does |
|---|---|
| `./scripts/omega` | command help; no implicit test run |
| `./scripts/omega run` | native window (dummy SDL without DISPLAY) |
| `./scripts/omega test PATH...` | exact issue-relevant pytest paths/selectors |
| `./scripts/omega test-scope NAME` | maintained test group for an affected area |
| `./scripts/omega release-check` | full asset/pack/test/identity/smoke/web gate |
| `./scripts/omega doctor` | report contributor/runtime/web prerequisites without running tests |
| `./scripts/omega web` | playable Chapter 1 WebAssembly build using the authoritative game |
| `./scripts/omega web-serve` | serve `dist/web` on loopback for browser testing |
| `./scripts/omega audio` | deterministically rebuild every runtime sound tier from source masters |
| `./scripts/omega package` | portable native Linux archive + SHA-256 file |
| `./scripts/omega verify-package ARCHIVE CHECKSUM` | safely extract and smoke-test the portable artifact |
| `./scripts/omega audit-release` | redacted tree/history/artifact/SBOM audit |
| `./scripts/omega validate-pack PATH` | validate a data-only pack without activating it |
| `./scripts/omega seal-pack PATH` | atomically refresh a pack manifest's file declarations and digests |
| `./scripts/omega review-pack PATH` | safely inspect a pack directory or ZIP without installing it |
| `./scripts/omega install-pack PATH --accept` | install a reviewed pack, initially disabled |
| `./scripts/omega list-packs` | list installed versions and activation state |
| `./scripts/omega enable-pack ID` | activate an installed pack for native play |
| `./scripts/omega disable-pack ID` | stop activating an installed pack |
| `./scripts/omega remove-pack ID` | remove a disabled installed copy |

No directory is scanned implicitly. Packs explicitly enabled in game-owned
storage apply to native play by default; a contributor can still test a source
directory without installing it:

```bash
./scripts/omega run --content-pack examples/content-packs/vertical-garden
```

Use `--no-installed-content` for a one-off run without enabled installed packs.

See [content-packs.md](content-packs.md) for the schema, safety model, and full
create/validate/enable/disable/remove workflow.

Audio generation additionally requires `ffmpeg` and `ffprobe`. It preserves
lossless/PCM masters under `assets/source/audio/` and writes only runtime Ogg
files plus `assets/audio/audio-manifest.json`. See
[sound-support.md](sound-support.md) for recipes, rights, and listening gates.

The native target is pygame-ce. `dist/web` is a playable Chapter 1 browser
alpha backed by the same simulation and renderer, not a six-chapter web game.
See [web.md](web.md) for package boundaries and browser qualification.

The native package flow requires the pinned release tooling:

```bash
.venv/bin/python -m pip install --requirement requirements/bootstrap.txt
.venv/bin/python -m pip install --no-build-isolation --requirement requirements/ci.txt
./scripts/omega package --output dist/native-local
./scripts/omega verify-package \
  dist/native-local/omega-omarchy-0.1.2-linux-x86_64.tar.gz \
  dist/native-local/omega-omarchy-0.1.2-linux-x86_64.tar.gz.sha256
```

See [release-artifact.md](release-artifact.md) for contents, verification, and
the current reproducibility boundary.
