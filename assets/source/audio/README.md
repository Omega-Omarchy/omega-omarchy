# Audio source masters

`music/make-it-come-alive/master-ultra.flac` is the lossless decoded
preservation master extracted from the maintainer-supplied MP4. The original
container carried AAC audio, so decoding to FLAC prevents another lossy source
generation but does not recreate information absent from that AAC stream.
The recording is reserved for the closing cast sequence. Jeremy Dixon confirmed
the artist credit as **Coded Jason ft. The Gen X Ancients** on 2026-09-11.
`music/make-it-come-alive/accepted/` pins the previously accepted runtime
renditions so rebuilding credits does not reinterpret this song.

`music/super-key-love/source.mp3` is Jeremy Dixon's **Super Key Love (Oh Omarchy —
theme from Omega Omarchy)**, copied from the supplied CatchyTune Inbox recording
on 2026-09-11. Its artist tag names Jeremy Dixon. Only author/artist metadata is
used for the song's on-screen attribution. The three adjacent prepared Oggs preserve the full
performance at Vorbis quality 3, 5 and 8; they do not run through chiptune
resynthesis. The runtime cue is `credits-roll`, lasting 429.863991 seconds.
The roll adds five silent seconds after the recording. Source hashes, credits
and cue metadata are recorded in `credits/music.json` and the audio manifest.

The local, Git-ignored `music/omarchy-oligarchy/master-ultra.flac` is the decoded preservation master
from the maintainer-supplied *Omarchy Oligarchy* MP4. Its intended semantic cue
is the Chapter 4 level theme for `walled-garden` — **The Walled Garden — Revenue
Retreat** — whose Garden Gatekeeper victory triggers the OMARCHY-to-OLIGARCHY
event. It is intentionally not wired into the runtime manifest until its High
and sixteen-bit arrangements pass listening review and redistribution permission
is documented. Public checkouts do not need this reference; the credits use
the external artist entry in `credits/music.json`.

`sfx/*/master.wav` files are deterministic 48 kHz stereo source masters emitted
by `python -m omega_omarchy.audio_build`. Every runtime tier is rendered from
these masters; no lower tier is derived from another lower tier.

The preservation master was extracted with the equivalent of:

```bash
ffmpeg -i "Make It Come Alive.mp4" -map 0:a:0 -vn -map_metadata -1 \
  -c:a flac -sample_fmt s16 master-ultra.flac
```

The supplied container's audio stream was AAC at 44.1 kHz stereo, approximately
128 kb/s, and 233.36 seconds. Re-extraction is accepted only when its decoded
PCM matches the recorded master digest; container-level FLAC bytes can vary by
encoder version.

The *Omarchy Oligarchy* container likewise carried 44.1 kHz stereo AAC. Its
duration is 254.77 seconds. The source-container SHA-256 is
`5cbef47ba81f4939c4167a41737b95e20426417b5e23167f258cfd194c1d8ecc` and
the decoded FLAC SHA-256 is
`84525d56dd660d5629f4275738d035feb8f8e85dcc22c07bdb2abf5e44bbad0c`.

The TOML manifest records the active credits source; this document records the
staged level source until cue promotion. The maintainer reports direct permission
from the creator of *Make It Come Alive* to use the work with or without
attribution. A copy and date of that exchange must still be retained in the
release evidence, and public source-master redistribution must be confirmed as
within its scope rather than inferred.

The staged level source matches Rich Kilmer's *Beware the Omarchy Oligarchy* in
`omacom/radio.omarchy.org` (melody 0.998, rhythm 0.992, timbre 0.970 in the
local source comparison). That repository accepts creator-owned tracks for
streaming but carried no explicit repository or track license when inspected at
commit `8a28e3af4e05ef821e71bb3d39002981c6d092a3`. Availability through Omarchy
Radio is not treated as permission to redistribute the recording or its
derivatives. This cue remains a private review asset until its creator grants
permission or an applicable license is documented.

Suvikyi's *Boot Up Your New Digital World* is presently a local conversion
candidate rather than a tracked master. Its supplied MP3 is byte-identical to
the Omarchy Radio file at that same inspected revision. Jeremy Dixon explicitly
reconfirmed direct permission from Suvikyi to utilize her song on 2026-09-11.
The permission record lives in `credits/music.json`; source-master distribution
rights remain separate from the source-code license.
