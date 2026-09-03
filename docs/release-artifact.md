# Native Linux artifact

The player artifact is a portable PyInstaller one-directory runtime wrapped in
a deterministic tar/gzip container. It contains the Python interpreter and
native runtime libraries, generated play assets, the built-in content pack,
player documentation, build/dependency receipts, license texts, and notices.
Production-source masters and private design/reference material are excluded.

## Build and verify

```bash
.venv/bin/python -m pip install --requirement requirements/bootstrap.txt
.venv/bin/python -m pip install --no-build-isolation --requirement requirements/ci.txt
./scripts/omega package --output dist/native-local
./scripts/omega verify-package \
  dist/native-local/omega-omarchy-0.1.0-linux-x86_64.tar.gz \
  dist/native-local/omega-omarchy-0.1.0-linux-x86_64.tar.gz.sha256
```

CI adds `--require-clean`, performs the verification from a fresh extracted
directory and isolated HOME/XDG profile, smoke-launches the sealed Chapter 1
world, runs the maintained pack through review, install-disabled, enable,
identity-change, disable, and remove using the frozen launcher, and confirms
packaged assets were not rewritten. It attempts to retain the archive and
checksum for three days; account storage quota can prevent that last delivery
step without invalidating the recorded build/verification result.

Players extract the archive and run `./omega-omarchy`. Git, a compiler, network
access, a source checkout, and system Python are not required. Saves remain
under `$XDG_DATA_HOME/omega-omarchy` (or the freedesktop
`~/.local/share/omega-omarchy` fallback) when the bundle is removed.

## Reproducibility boundary

The freezer receives the source commit time (or explicit `SOURCE_DATE_EPOCH`)
and `PYTHONHASHSEED=0`; tar member order, ownership, modes, and timestamps are
also normalized. Two consecutive builds from the same dirty source tree and
toolchain produced the same SHA-256 during the 2026-08-29 engineering probe.
`BUILD-INFO.json` records the commit, dirty state, Python, PyInstaller,
architecture, and runtime-asset
digest. `DEPENDENCIES.json` records resolved direct runtime versions and copied
license files.

The v2 archive format preserves PyInstaller's relative internal shared-library
links instead of duplicating their targets. The writer resolves every link
inside the staging root; the verifier independently rejects escaping,
unresolved, absolute, hard, or non-file-target links before extraction. This
reduced the measured local archive from about 98 MB to 83 MB.

PyInstaller output remains platform/toolchain dependent and is not yet claimed
to be bit-for-bit reproducible across independent builders. The exact inputs
currently include Ubuntu 24.04, x86_64, Python 3.12, pinned
`requirements/bootstrap.txt` and `requirements/ci.txt`, tracked runtime assets,
and the source commit. A public candidate still requires a clean
environment that did not build the artifact to independently extract, play,
inspect shared libraries/licenses, and record the result.
