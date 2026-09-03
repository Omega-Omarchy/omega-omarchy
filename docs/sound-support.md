# Sound support and fidelity design

Status: approved direction; runtime tier selection and authored music are not
yet implemented. This document defines the contribution and release contract.

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

## Current baseline

The game has short generated cues for `jump`, `collect`, `convert`, `hit`,
`logo`, and `ui`, plus a two-second `loop` file that is not yet used as a
proper music system. Native builds load WAV; web packaging produces Ogg/Vorbis
copies because browser Pygame rejects common desktop WAV arrangements. There
is no authored soundtrack, cue manifest, mixer bus model, variation system,
loop metadata, audio-fidelity setting, or complete action coverage yet.

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

Proposed source layout:

```text
assets/source/audio/
  music/<cue>/composition.mid
  music/<cue>/arrangement-ultra.*
  music/<cue>/arrangement-high.*
  music/<cue>/arrangement-sixteen-bit.*
  sfx/<cue>/master.wav
  samples/<licensed-pack>/LICENSE
  audio-manifest.toml
```

Generated runtime layout:

```text
assets/audio/<tier>/music/<cue>.ogg
assets/audio/<tier>/sfx/<cue>-01.ogg
assets/audio/<tier>/sfx/<cue>-02.ogg
assets/audio/audio-manifest.json
```

The manifest records cue ID, bus, tier files, gain trim, loop start/end,
priority, maximum simultaneous voices, caption key, variant policy, provenance,
and source digest. Generation must be deterministic for identical tools and
inputs. Lossless masters remain outside the player artifact.

## Production pipeline

Music begins with a shared tempo map, melody/harmony, structural markers, and
loop points. Ultra receives the full arrangement. High receives a purposeful
re-orchestration with fewer layers and period-appropriate processing.
Sixteen-bit is resampled and sequenced against a small, rights-cleared sample
bank with explicit voice limits and loop points. Offline renders then receive
tier-specific sample rate, stereo, dynamics, and encoding settings.

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

Introduce an `AudioManager` between simulation cue IDs and Pygame’s mixer. It
owns `music`, `sfx`, `ui`, and `ambience` buses, cue priority/voice limits,
variant rotation, fades, scene music state, and seamless loop metadata. The
simulation continues to append semantic IDs such as `collect`; it does not
know which tier or file played.

Pause/settings should expose:

- Sound Quality: `Sixteen-bit`, `High`, or `Ultra`;
- Master, Music, Effects, and UI volume;
- Mute and audio-caption options.

New installs default both art and sound to Ultra. Existing saves migrate once
by initializing `audioFidelity` from their current visual tier, after which the
two settings are independent. Switching sound quality crossfades music at the
same musical position when compatible stems/loop markers exist; otherwise it
changes at the next safe phrase boundary. Effects already playing finish in
their original tier.

## Browser and performance contract

Web builds ship only the selected vertical-slice cue set and encode it as Ogg.
Audio must not play before a browser gesture; the installer’s first accepted
input may unlock the mixer. Decode work should be bounded: preload UI and
critical gameplay cues, stream music where Pygame/WebAssembly proves reliable,
and lazy-load uncommon boss/item cues before their encounter gate. Missing or
blocked audio must fail silently into captions, never stop gameplay.

Runtime DSP is intentionally modest. Expensive convolution, emulated console
mixers, and bitcrushing belong in offline generation. Tier selection should
lower memory/voice count where useful, but it is an artistic selection rather
than a performance promise.

## Content-pack interface

Content packs may declare new cue IDs and tier files through the externalized
manifest schema. They may override core cues only through an explicit namespaced
replacement declaration accepted during pack review. A pack must provide all
three tiers or name a documented fallback; it must include license/provenance,
loudness metadata, and captions. Invalid or missing audio disables that cue,
not the entire pack or save.

## Qualification gates

The first implementation milestone is one Chapter 1 music theme, boss music,
ambient bed, and complete gameplay/UI effects across all three tiers. It passes
only when:

- every referenced cue resolves at every tier and missing-file fallback works;
- all nine visual/audio tier combinations can be selected, saved, and restored;
- tier switching cannot alter deterministic simulation receipts;
- loop seams, cue latency, voice stealing, fades, and rapid repeated actions
  pass automated checks plus headphone and speaker listening review;
- true peaks/loudness remain inside the project target and speech/caption cues
  remain legible in the densest encounter;
- native and browser builds survive muted/no-device/autoplay-blocked operation;
- the release audit inventories generated audio and every source/sample license;
- at least one external collaborator can rebuild the emitted files from the
  documented source inputs without private tools.

Later milestones add adaptive stems, per-zone themes, helper/boss motifs, and
content-pack exchange. Console-hardware-exact emulation is explicitly outside
the first vertical slice; convincing, coherent era interpretation is the goal.
