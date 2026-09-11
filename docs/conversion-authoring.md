# Expressive conversion and reviewed runtime cues

CatchyTune is the authoring workbench for the new automatic conversion proposals.
Omega's symbolic extraction now retains raw attacks, chromatic pitches, confidence,
and Basic Pitch bend offsets. It no longer folds notes into a fixed register or
makes confidence stand in for velocity before the author can inspect them. Default
score cleanup preserves the performance; `--musical-cleanup --cleanup-style
standard-backbeat` explicitly requests the older conventional regularization.

Install optional analysis dependencies with `pip install -e '.[audio-authoring]'`.
Basic Pitch/ONNX and stem separation remain separate tools in the existing offline
ML environment. The game has no new inference dependency. Import the arrangement
into CatchyTune, generate proposals, audition, and keep the accepted `.chy`.
CatchyTune renders the expressive curves; legacy Omega voices remain diagnostic
comparison renderers.

## Build an accepted authoring render

From CatchyTune, run:

```bash
catchytune export-runtime accepted.chy --output runtime --cue-id chapter-one
```

The package contains separate intro, settled loop, and outro Ogg cues plus a JSON
receipt with the arrangement digest, sample counts, file SHA-256 values, and seam
evidence. It does not assert listening approval. A project without loop markers
exports one non-looping full cue.

Copy a selected Ogg beneath `assets/source/audio/` and add a prepared entry inside
the corresponding `[[music]]` table in `audio-manifest.toml`:

```toml
[music.prepared.sixteen-bit]
file = "prepared/chapter-one-loop.ogg"
sha256 = "<the 64-character lowercase file hash from the receipt>"
loop = true
```

The entry's loop behavior must match that semantic cue. The builder rejects missing
files, escaping paths, altered hashes, and mismatched loop behavior. It copies the
selected tier byte-for-byte, recording per-tier source digests and render methods.
Other tiers use their source-master settings. The prepared input participates in
the build digest.

Omega loops whole files. Use the exported loop for a looping cue; intro and outro
are separate non-looping cues if an engine integration chooses to schedule them.
Internal markers in an enhanced authoring Ogg do not themselves implement that
scheduling in the current runtime.

The experiment stays local. The active music manifest has not been changed to
select candidate files. Local evaluations and paired listening artifacts live in
CatchyTune's ignored `.local/conversion-evaluation/` directory, with a review copy
prepared in the Transfer Outbox.
