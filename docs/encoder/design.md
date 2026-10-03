# Encoder design

The encoder generates a complete WAV offline. It needs no GUI, modem
subprocess, audio device, network or fldigi installation. Its public boundary
is `grampy.api`; internal encoding helpers are implementation details.

`mfsk_compose.py` snapshots ordered inputs, inspects PNG/WAV/text inputs and
plans exact frames before opening the caller's output. It sequences MFSK,
copied audio and silence, records coordinates, checks emitted totals, and owns
output replacement and failure cleanup. Audio copying and silence use 64-KiB
blocks; ancillary source WAV chunks are not propagated.

`mfsk_segment_encode.py` plans and emits independently framed segments.
`text_encode.py` maintains Varicode, convolutional coding, interleaving and
Gray/tone state across caller text boundaries. Picture announcements,
flushes, prologues, raster transitions and resumed text have explicit
source-derived ordering. File-backed text is consumed in bounded chunks.

`picture_encode.py` inspects the supported PNG profile and retains one source
raster. It streams specified grayscale or RGB row-plane components into
frequency/duration events. `mfsk_encode.py` synthesizes these events and text
tones with continuous phase within a segment, bounded PCM buffers and the
specified envelope, into a canonical RIFF writer. It does not accumulate a
broadcast-sized waveform in memory.

`rsid_encode.py` emits the unconditional per-segment RSID prefix. Its isolated
codeword, tones, guards and timing are checked against a frozen pinned-source
oracle. At 48 kHz the complete prefixes occupy 111,450 frames for MFSK32 and
222,900 frames for MFSK64. These intervals are included in public timestamps
and final duration.

The [wire specification](../decoder/mfsk_wire_spec.md) and independent
[wire vectors](../decoder/data/mfsk_wire_vectors.json) describe shared protocol
behavior. Encoder tests use independent expectations rather than accepting
a paired decoder round trip as proof of transmitted correctness. Receiver
scorecards then assess whether practical broadcasts decode credibly; they do
not alter the waveform rules.

The separately accepted automatic MFSK32 picture correction is in the
decoder's dispatch layer. It connects acquired MFSK32 segments to their
existing picture path and preserves picture order and artifact identity;
it did not change encoder generation or decoder demodulation algorithms.
See the [decoder change record](../decoder/auto-mfsk32-pictures-change.md).
