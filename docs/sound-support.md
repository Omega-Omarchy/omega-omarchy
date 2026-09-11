# Sound support and fidelity design

Status: first vertical-slice runtime and production pipeline implemented on
2026-09-03; tempo-aligned symbolic-arrangement replacement under local
listening review as of 2026-09-04. Multi-browser and public-rights gates remain
open.

## Outcome and invariants

Omega Omarchy should treat sound the way it treats visual art: preserve
high-quality masters, derive deliberately authored lower-fidelity versions,
and let the player choose the presentation. The approach is technically
feasible, including a SNES-era interpretation, provided the lower tier is an
arrangement/rendering target rather than a generic bitcrusher preset.

The following are non-negotiable:

- `audioFidelity` is independent of visual `fidelity` and display/CRT effects.
  Ultra video with sixteen-bit sound is a supported first-class combination.
- Music and important effects have one semantic cue ID across every tier.
  Game rules request a cue, never a filename or fidelity.
- Masters and reproducible arrangement inputs are retained; runtime files are
  generated and never used as the source for another lossy derivation.
- Tier changes never affect timing, hit detection, simulation state, or score.
- No tier uses copyrighted console samples, soundfonts, or recordings without
  explicit redistribution rights.
- Mute, captions, volume buses, and reduced-audio-surprise behavior work at
  every tier and on native and web targets.

## Current implementation

The maintainer-supplied *Make It Come Alive* MP4 carried a 44.1 kHz stereo AAC
stream. The pipeline decodes that once into a FLAC preservation/Ultra master,
records both container and decoded digests, and renders the complete,
non-looping `credits-theme` cue. The song is reserved for the credits and is
not reused for installation, level, or boss scenes. Those scenes remain silent
until they receive appropriate masters. The FLAC avoids another lossy source
generation; it cannot restore information absent from the original AAC stream.

The maintainer-supplied *Omarchy Oligarchy* MP4 has likewise been decoded once
into a FLAC preservation master. Its intended home is Chapter 4, `walled-garden`
(**The Walled Garden — Revenue Retreat**), whose boss victory triggers the
OMARCHY-to-OLIGARCHY event. It remains deliberately absent from the runtime cue
manifest until its High and sixteen-bit arrangements pass listening review.

The maintainer reports direct creator permission to use *Make It Come Alive*
and Suvikyi's local conversion candidate *Boot Up Your New Digital World*, in
both cases with or without attribution. Before public cutover, the project must
archive those exchanges and confirm their scope for binary and public
source-master distribution. The staged level master was matched to Rich
Kilmer's *Beware the Omarchy Oligarchy* in `omacom/radio.omarchy.org`; because
that repository specifies no track license, its public presence is not treated
as reuse permission and the cue remains private pending clearance.

Seven short semantic effects—`jump`, `collect`, `convert`, `hit`, `bomb`,
`logo`, and `ui`—have deterministic 48 kHz stereo PCM masters. Every music and
effect runtime file is rendered directly from its master into Ultra, High, and
sixteen-bit Ogg/Vorbis. `AudioManager` streams music, loads short effects by
tier, bounds simultaneous voices, applies master/music/effects/UI levels,
switches music by manifest-defined scene, and degrades silently when playback
is unavailable.

The committed sixteen-bit credits output is a reproducible experimental first
pass, not a qualified remake. Direct mixed-audio resynthesis and stem-remix
experiments did not produce a musically usable result. The replacement path
uses separation only as input to an inspectable symbolic arrangement, then
renders that identical score through neutral, SNES-oriented, and
Genesis-oriented instrument paths. A 20-second A/B produced the same key and
chord progression from Demucs `htdemucs` and BS-RoFormer, with only small note
and drum-count differences. Demucs is therefore the fast draft separator;
RoFormer is an optional problem-stem pass rather than a routine prerequisite.
No new lower-tier music is promoted into the game until the neutral reference
is recognizably the source composition.

## Fidelity targets

| Tier | Creative target | Runtime interpretation |
|---|---|---|
| Ultra | Modern full-quality master | Full stereo arrangement, natural tails, layered ambience, broad dynamics within the loudness target |
| High | 32-bit/CD-ROM era | Reduced layers and sample density, tighter ambience, era-appropriate synth/sample choices, restrained stereo field |
| Sixteen-bit | SNES/DKC-inspired production values | Sample-based sequenced arrangement, small curated sample palette, short looped instruments, limited simultaneous voices, deliberate pitch/velocity steps |

“Sixteen-bit” describes an artistic console-era constraint, not merely 16-bit
PCM encoding. A full-quality song passed through a sample-rate reducer will
usually sound broken, not like a strong SNES arrangement. Each music cue needs
a shared composition plus tier-specific orchestration. Effects can be more
automated, but each generated result still requires listening approval.

## Source and runtime layout

Implemented source layout:

```text
assets/source/audio/
  music/make-it-come-alive/master-ultra.flac
  music/omarchy-oligarchy/master-ultra.flac
  sfx/<cue>/master.wav
  audio-manifest.toml
  README.md
```

Generated runtime layout:

```text
assets/audio/<tier>/music/<cue>.ogg
assets/audio/<tier>/sfx/<cue>.ogg
assets/audio/<tier>/sfx/<cue>-02.ogg
assets/audio/audio-manifest.json
```

The generated manifest records cue ID, bus, tier files, gain trim, duration,
priority, maximum simultaneous voices, caption key, variant policy, provenance,
and source digest. Generation must be deterministic for identical tools and
inputs. Lossless masters remain outside the player artifact.

Rebuild and test only this subsystem with:

```bash
./scripts/omega audio
./scripts/omega test-scope audio
```

`ffmpeg` and `ffprobe` are required. The browser and native package stages copy
runtime Oggs and the JSON manifest but exclude `assets/source/` and the offline
builder.

## Production pipeline

Music begins with a shared tempo map, melody/harmony, structural markers, and
loop points. Ultra receives the full arrangement. High receives a purposeful
re-orchestration with fewer layers and period-appropriate processing.
Sixteen-bit is resampled and sequenced against a small, rights-cleared sample
bank with explicit voice limits and loop points. Offline renders then receive
tier-specific sample rate, stereo, dynamics, and encoding settings.

For finished-mix imports, the experimental authoring sequence is deliberately
staged: specialist source separation; audio-to-MIDI transcription for
vocals/bass; drum-event classification; chord/key analysis against the full
mix; instrument discovery across otherwise-abandoned guitar, keys, and residual
stems; quantization and voice leading into JSON/MIDI; a neutral SoundFont
render; and only then console-oriented rendering. A failed neutral render is a
transcription/arrangement failure and must not be hidden behind console effects.
Flagship cues may require human correction of the emitted MIDI before tier
rendering.

The offline `omega_omarchy.music_diagnostic` tool detects tempo and the beat
phase relative to an arbitrary source clip, records source hashes plus the
separator label, and writes a versioned `arrangement.json`. That file is the
handoff boundary between machine analysis and musical editing. It can be
corrected in JSON (with the emitted MIDI available for inspection) and rendered
again with `--arrangement` without rerunning separation or Basic Pitch.
Identical arrangements produce byte-identical four-operator renders. SoundFont
renders are for local listening only until the project adopts and audits a
redistributable sample bank.

Long cues also retain a locally spaced sixteenth-note timing grid derived from
the detected beat sequence. This lets gradual tempo movement survive symbolic
cleanup instead of forcing an entire song onto the average tempo inferred from
a short excerpt. Sparse intros and outros are covered by conservative
extrapolation from their nearest reliable beat intervals.

The optional repeatable `--instrument-stem LABEL=PATH` input prevents useful
parts from disappearing merely because they landed outside the lead, bass, or
drum stems. One-second overlapping windows are grouped by recurring timbre and
written to `instrument-inventory.json`; source-faithful region clips are written
under `instrument-extracts/`. Coherent tonal candidates receive independent
symbolic lanes and patch archetypes. Low-confidence, diffuse, and percussive
residue remains inventoried but unpromoted. These labels and thresholds are an
auditable first pass for a musician, not a substitute for one.

Fingerprint pitch bounds must match the voice. An early bass pass began above
the song's 39–62 Hz fundamentals, locked onto an upper harmonic, and made a
filtered saw bass appear nearly pure. Bass analysis now uses a lower range while
the wide synth is fitted separately. Source-informed bass and sustained-synth
profiles are attached with repeatable `--voice-fingerprint ROLE=PATH` inputs so
one generic oscillator estimate cannot flatten both defining voices.

Its optional musical-cleanup stage consolidates selected melody fragments,
corrects weak chromatic guesses against the inferred key, constrains uncertain
bass events by the active chord, and regularizes transient detections into a
deliberate groove. The enhanced-retro renderer then combines wavetable, FM,
PCM-drum, stereo, and short-echo techniques. This is a creative era
interpretation: recognizable early-console texture and phrasing matter more
than exact historical sample rates, voice counts, chips, or DSP restrictions.
The evolving native renderer and its invariants are specified in
[`omega-chip.md`](omega-chip.md).

For cues that already contain useful synthesis, the tool can derive a
parameter-only Omega Chip fingerprint from an isolated candidate: harmonic
distribution, harmonic/noise balance, envelope, modulation, and stereo
character. A private diagnostic may additionally blend an averaged single-cycle
wavetable. The parameter model is the preferred distributable result; the raw
derived wavetable remains out of tree until separately cleared.

For draft work, extract six stems with `htdemucs_6s`, then run the diagnostic
with `--separator-label htdemucs_6s` and pass `other`, `guitar`, and `piano` as
separate `--instrument-stem` inputs. A four-stem Demucs pass remains acceptable
for fast lead/bass/drum iteration. Use a slower specialist separator only when
the inventory or neutral reference exposes a specific contaminated stem. Keep
15–30 second representative sections during iteration; process a full cue only
after the arrangement and recovered-instrument palette pass listening review.

Effects begin with a clean, high-resolution master. A recipe may shorten the
tail, reduce layers, quantize pitch envelopes, narrow the stereo image, or
resample to the chosen tier. Transient-critical cues—jump, damage, conversion,
menu confirm, item throw, boss warning—must remain immediately recognizable in
all mixes. Variation comes from a small approved set of rendered alternates,
not nondeterministic runtime processing.

Recommended build stages:

1. validate source provenance and cue metadata;
2. render each authored arrangement at a lossless working resolution;
3. apply deterministic per-tier processing and loudness trim;
4. verify true peak, integrated/short-term loudness, duration, and loop seam;
5. emit browser-safe Ogg and the native format selected by measurement;
6. write source/output digests into the manifest and release audit.

## Runtime model and settings

`AudioManager` sits between simulation cue IDs and Pygame’s mixer. It
owns `music`, `sfx`, and `ui` buses, per-cue voice limits, fades, scene music
state, and seamless loop metadata. Ambient material currently shares the music
bus. The
simulation continues to append semantic IDs such as `collect`; it does not
know which tier or file played.

Pause/settings exposes:

- Sound Quality: `Sixteen-bit`, `High`, or `Ultra`;
- Master, Music, Effects, and UI volume;
- Mute and audio-caption options.

New installs default both art and sound to Ultra. Existing saves migrate once
by initializing `audioFidelity` from their current visual tier, after which the
two settings are independent. Switching sound quality performs a short faded
handoff at the same approximate musical position when the host's Ogg seek
supports it; otherwise it restarts at the loop boundary. Loading a second
four-minute track as a decoded `Sound` just to overlap streams is deliberately
rejected on the target hardware. Effects already playing finish in their
original tier.

## Browser and performance contract

Web builds ship only the vertical-slice cue set as committed Ogg. Audio does
not play before a browser gesture; the first keyboard/gamepad press unlocks the
mixer. Decode work is bounded by streaming music and loading only the selected
tier's short effects. Missing or blocked audio fails silently while captions
remain available and gameplay continues.

Runtime DSP is intentionally modest. Expensive convolution, emulated console
mixers, and bitcrushing belong in offline generation. Tier selection should
lower memory/voice count where useful, but it is an artistic selection rather
than a performance promise.

## Content-pack interface

This remains the next extension point; the core runtime manifest is
externalized, but the content-pack loader does not accept audio files yet.
Content packs may declare new cue IDs and tier files through the externalized
manifest schema. They may override core cues only through an explicit namespaced
replacement declaration accepted during pack review. A pack must provide all
three tiers or name a documented fallback; it must include license/provenance,
loudness metadata, and captions. Invalid or missing audio disables that cue,
not the entire pack or save.

## Qualification gates

The first implementation milestone supplies the credits theme plus gameplay/UI
effects across all three tiers. Purpose-built Chapter 1, boss, installer, and
ambient masters remain open production work. The automated system gates are
implemented; human listening and browser qualification are still required
before release:

- [x] every referenced cue resolves at every tier and missing-file fallback is safe;
- [x] all nine visual/audio tier combinations can be selected, saved, and restored;
- [x] tier switching cannot alter deterministic simulation behavior;
- loop seams, cue latency, voice stealing, fades, and rapid repeated actions
  pass automated checks plus headphone and speaker listening review;
- true peaks/loudness remain inside the project target and speech/caption cues
  remain legible in the densest encounter;
- [x] native no-device/mute behavior and browser gesture gating fail safely;
- [ ] the release audit inventories generated audio and confirms recording rights;
- [ ] at least one external collaborator can rebuild the emitted files from the
  documented source inputs without private tools.

Later milestones add adaptive stems, per-zone themes, helper/boss motifs,
effect variants, and content-pack audio exchange. Console-hardware-exact
emulation is explicitly outside the first vertical slice; convincing, coherent
era interpretation is the goal.
