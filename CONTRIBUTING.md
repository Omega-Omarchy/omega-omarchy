# Contributing to Omega Omarchy

Omega Omarchy is a founder-led technical alpha. These rules define the intended
contribution surface. Repository visibility stays with the lead maintainer.

## Direction and scope

The lead maintainer owns product direction, canon, central voice, release
decisions, and final merge authority. Discussion and contributions inform those
decisions but do not turn them into a vote. The current product boundary is a
polished 10–15 minute Chapter 1. Later chapters are development scaffolding.

Targeted contributions are welcome in art, audio, accessibility, level content,
enemies, methods, tests, performance, tooling, and declarative content packs.
Read `GOVERNANCE.md`, `ROADMAP.md`, and the current NO-GO gates in
`docs/OPEN-SOURCE-CUTOVER.md` before starting broad work.

## Set up and verify

Linux with Python 3.11 or 3.12 is the current supported development target.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --requirement requirements/bootstrap.txt
.venv/bin/python -m pip install --no-build-isolation --requirement requirements/ci.txt
./scripts/omega test-scope core
./scripts/omega doctor
```

Testing is issue-dependent. Select the smallest scope that covers the behavior
and its adjacent invariants; do not run the whole suite merely by default.
`./scripts/omega release-check` is the explicit full asset, pack, test,
identity, native-smoke, and web-export gate for merges or release candidates
whose risk warrants it.

Useful focused commands:

```bash
./scripts/omega test-scope gameplay
./scripts/omega test-scope web
./scripts/omega test tests/test_generation.py
./scripts/omega validate-pack examples/content-packs/vertical-garden
./scripts/omega review-pack examples/content-packs/vertical-garden
./scripts/omega package --output dist/native-local
./scripts/omega verify-package dist/native-local/*.tar.gz dist/native-local/*.sha256
```

For browser work, build with `./scripts/omega web`, serve with
`./scripts/omega web-serve`, and follow [docs/web.md](docs/web.md). Do not open
the generated index through `file://` or replace the browser target with a
separate gameplay implementation.

## Change discipline

- Keep simulation/game rules input-independent and test them through `GameSim`.
- Preserve 16-pixel logical tiles and the documented collision footprint across
  fidelity tiers.
- Keep ordinary play offline and sharing explicitly opt-in.
- Version any deterministic generation, save, pack-schema, or canonicalization
  break; provide a migration or clear fail-closed rejection.
- Do not silently expand Chapter 1 claims to unfinished later content.
- Match existing plain Python style, type annotations, concise documentation,
  and deterministic serialization. There is no formatter waiver for unreadable
  code; avoid unrelated mechanical rewrites.

Generated runtime assets under `assets/` are tracked. Change them only through
`./scripts/omega assets`, include their production source/provenance where
required, and inspect all affected fidelity tiers. Never commit private visual
references, `.local/` captures, caches, or release artifacts. The expensive
asset build must never run during ordinary game launch.

Audio-only work uses `./scripts/omega audio` and `./scripts/omega test-scope
audio`. Every cue needs one semantic ID, all three direct-from-master outputs,
caption copy, bus/gain/voice metadata, source digests, and explicit rights.
Listen on headphones and ordinary speakers; attach a short recording or
measurement without uploading a source master to an issue.

Content-pack work follows `docs/content-packs.md`. A pull request must show
`PACK_OK`, exact seeds/identities, with/without-pack behavior, license and
attribution files, and safe disable/removal behavior.

## Evidence and review

Open a focused issue before substantial direction/canon/schema work. Pull
requests must use the template and include the smallest evidence that proves the
claim: tests for behavior, screenshots for visuals, recordings for motion/audio,
receipts for deterministic/integration changes, and measurements for
performance. Review may request a smaller patch or reject work that is polished
but outside accepted direction.

Do not include credentials, private correspondence, personal data, local paths,
unlicensed references, copied art/audio, or uncertain AI-generated material.
For every non-code asset, identify authorship, source, generation/editing tools,
model where relevant, reference inputs, modifications, license, and any
trademark/likeness implications. See `ASSET-LICENSE.md` and
`THIRD_PARTY_NOTICES.md`.

## Inbound contribution policy

Every commit must carry a Developer Certificate of Origin sign-off:

```bash
git commit -s -m "Describe the outcome"
```

The sign-off certifies the statements in `DCO.md`; it is not a blanket transfer
of trademark, likeness, or third-party rights. Original code and ordinary docs
accepted into the repository are contributed under the root MIT license.
Content packs and assets retain the explicit compatible license recorded with
them; assets without clear provenance and terms will not be accepted.

Report security problems privately through `SECURITY.md`, never through an
issue or public pull request. This project deliberately does not adopt a
standalone code-of-conduct regime; contribution acceptance and moderation
remain maintainer decisions under `GOVERNANCE.md`.
