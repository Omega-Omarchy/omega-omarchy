# Omega virtual sound chip

Status: experimental authoring renderer under private listening review.

## Intent

The Omega Chip is Omega Omarchy's native retro-audio identity. It should evoke
the immediacy, strong melodic writing, synthetic timbres, sampled percussion,
and spatial tricks associated with earlier console music without copying one
particular machine or enforcing its hardware specification. Historical limits
are useful compositional prompts, not product requirements.

The engine consumes the same versioned symbolic arrangement used by the
neutral diagnostic renderer. It does not analyze or remix finished audio at
render time. This keeps transcription errors, arrangement decisions, patch
design, and final mixing separately inspectable.

## Voice architecture

The experimental renderer has six independently mixed voice families:

- **Lead:** triangle body, pulse-width movement, an upper harmonic, vibrato,
  and a fast but non-clicking envelope.
- **Bass:** a low-pass saw body, sub-octave reinforcement, and asymmetric
  overdrive. It remains centered and comparatively dry.
- **Harmony:** detuned, stereo-positioned sustained voices with slower
  envelopes.
- **Arpeggio:** a quiet chord-derived eighth-note voice that supplies motion
  without replacing the composed melody.
- **Recovered instruments:** separately identified lanes from coherent regions
  in residual, guitar, keys, or other separator stems. Patch archetypes include
  bright plucked string, sustained synth, guitar-like, keys-like, and melodic
  residual voices. Generated arpeggios yield while these source-authored parts
  are active so the recovery does not become added clutter.
- **Percussion:** deterministic synthesized kick, snare, and metallic hat
  voices. It remains centered and dry.

Lead, harmony, and arpeggio buses receive separate short cross-channel echoes.
Recovered instruments receive a quieter independent echo and mix bus. They are
mixed with the dry bass and percussion buses before gentle saturation, amplitude
quantization, peak control, and PCM output. The current 32 kHz working rate is a
color choice and may change; it is not a claim of hardware fidelity.

## Instrument discovery

Separation stems are not disposable catch-alls. The offline discovery stage
measures overlapping windows for level, harmonic energy, spectral flatness,
onset density, centroid, and stereo width; deterministically groups recurring
timbres; and writes every result to `instrument-inventory.json`. Each candidate
retains its source stem, audition regions, proposed patch archetype, confidence,
promotion decision, and source digest. `instrument-extracts/` contains lossless
audition clips so a musician can rename, split, merge, reject, or reassign a
candidate without trusting an opaque label.

Only coherent tonal candidates cross into symbolic performance lanes
automatically. Percussive and diffuse residuals remain visible in the inventory
but do not contaminate the score. Separation labels are evidence, not truth:
content in a model's `other`, `guitar`, or `piano` output may be leakage, and the
archetype is explicitly a patch proposal rather than a claimed instrument name.
The opening plucked-string part in *Make It Come Alive* is the first acceptance
case for this general mechanism, not a cue-specific exception.

### Coupled saw voices

*Make It Come Alive* depends on a wide saw-based synth and a darker overdriven
saw bass. They are treated as flagship voices, not generic pulse substitutes.
The synth uses a band-limited full harmonic series, source-informed spectral
weighting, detuned oscillators, and a moving filter envelope. The bass uses a
more tightly filtered saw, sub reinforcement, near-mono placement, and
asymmetric saturation.

Fingerprint extraction must search the actual range of the voice. The first
bass pass started at C2 while this performance reaches roughly 39–62 Hz; it
therefore locked onto an upper harmonic and incorrectly described the bass as
nearly pure. The corrected low-range pass retains the fundamental plus the
filtered saw harmonic slope. Voice fingerprints are supplied by role with
repeatable `--voice-fingerprint ROLE=PATH` arguments; this keeps bass and synth
timbre fitting independent from the general lead-fingerprint experiment.

## Profiles

`balanced` is the reference profile. It favors separation, moderate width, a
quiet arpeggio layer, and restrained pulse and echo content.

`vivid` uses the exact same score and synthesis architecture with wider
harmonies, stronger arpeggios, brighter lead pulse content, and more echo. It
exists to identify where a cue belongs on the clarity-to-energy spectrum, not
as a separate sound-quality tier.

Per-cue profiles may eventually interpolate between these settings. Profile
selection must remain an authoring decision and must not change gameplay.

## Source-informed patches

An optional offline analysis pass can fit an Omega Chip patch to an isolated
synth candidate. It searches for stable harmonic windows and records harmonic
amplitudes, harmonic/noise balance, envelope shape, pitch modulation, stereo
width, and channel correlation in `synth-fingerprint.json`. The production
candidate is reconstructed from those parameters; it does not need the source
recording at render time.

A separate listening experiment may extract a 256-value wavetable by averaging
aligned single cycles from the strongest stable window. That artifact is still
derived from the recording and remains private until the recording and sample
rights are explicitly cleared. A successful parameter-only patch is preferred
for public runtime assets. Separation residue must not silently become part of
the permanent patch identity, so every source-informed patch is compared with
the isolated candidate and the existing Omega Chip baseline.

## Performance-guided phrasing

The local authoring renderer can apply source phrasing to selected, explicitly
bounded problem regions with `--lead-guidance-region START:END`. The symbolic
note remains authoritative. The analysis discards the source's absolute pitch,
recenters each contour on the symbolic note, clamps the surviving motion to 1.5
semitones, and then applies profile-controlled pitch-bend and amplitude
articulation depth. This prevents octave errors and separator leakage from
silently rewriting the melody while retaining useful attack, release, and bend
evidence from the performance.

CatchyTune identifies candidate regions and measures whether a focused pass
improves the intended factor without materially regressing melody, timbre, or
dynamics. Its scores guide iteration; paired listening remains the acceptance
gate. Source contours are authoring evidence only and are not runtime assets.

## Vocal sample channel

Vocals remain performed audio rather than being reduced to oscillator notes.
The local reintegration pass can high-pass an isolated vocal, suppress separator
leakage with an activity envelope plus authored arrangement regions, and duck
the instrumental bed only while the vocal is present. A clean profile preserves
the performance; Omega sample-channel profiles use deliberately bounded sample
rate, bit depth, and saturation as an aesthetic interpretation.

Vocal extraction is separator-dependent. For *Make It Come Alive*, the Demucs
four-stem vocal retains the performance more reliably, while the RoFormer vocal
contains enough misclassified instrumentation to regress melody and rhythm.
Separator selection is therefore measured per role rather than made once for an
entire cue.

## Vocal-to-chip melody

For a fully synthetic tier, the authoring renderer can remove the earlier
symbolic lead and replace it with a monophonic oscillator driven by the isolated
vocal's fundamental frequency and activity contour. Pitch is pulled toward
semitone centers while phrase starts, stops, and level changes retain source
timing. The resulting asset contains no intelligible speech recording: the
performance has become a chip melody.

The default candidate uses the Demucs vocal contour to drive the Omega saw
voice with restrained residual bends. Hard-quantized saw, pulse/triangle, and
octave-accented profiles remain listening alternatives. Exact-time continuous
contours currently retain rhythm better than re-segmenting the performance into
discrete Basic Pitch events, which tends to over-articulate syllables.

Activity and delivery strength are separate controls. The activity contour
preserves phrase boundaries, while a profile-specific active-note floor and
compression curve prevent quiet recorded syllables from becoming weak chip
notes. This raises delivery authority without filling rests or moving onsets.

## Invariants

- A saved arrangement and profile render deterministically.
- The engine never depends on copyrighted console samples or firmware.
- Performance guidance cannot replace a symbolic note's absolute pitch and is
  confined to explicitly selected authoring regions.
- Vocal activity regions are authored and reviewable; an amplitude gate alone
  cannot promote separator leakage into a finished mix.
- Source fingerprints record their input digest; raw-derived wavetables stay
  outside the repository unless separately cleared.
- Rejected discovery candidates remain auditable, and automatic promotion never
  treats diffuse or percussion-like separator residue as a melodic lane.
- Instrument character may exceed historical channel, memory, stereo, sample
  rate, or DSP constraints.
- Retro character comes from composition, envelopes, modulation, timbre, and
  mix behavior—not generic bitcrushing.
- Bass and rhythm clarity take priority over a large reverberant image.
- Every promoted cue passes neutral-arrangement review before patch and mix
  review.
- Experimental renders remain outside runtime assets until listening approval
  and rights review are complete.

## Development path

The next useful extensions are external patch definitions, human-editable
candidate labels and promotion overrides, cue-level automation lanes, compatible
percussion kits, phrase-region suggestions, and MIDI re-import for correction.
Full-song renders remain review artifacts until the recovered lanes pass
sparse-intro, verse, chorus, and transition listening tests.
