# Audio source masters

`music/make-it-come-alive/master-ultra.flac` is the lossless decoded
preservation master extracted from the maintainer-supplied MP4. The original
container carried AAC audio, so decoding to FLAC prevents another lossy source
generation but does not recreate information absent from that AAC stream.

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

The TOML manifest records the source container and decoded-master digests. The
recording is cleared for the current private development build only until the
maintainer completes the public-distribution rights check required by
`docs/OPEN-SOURCE-CUTOVER.md`.
