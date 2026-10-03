# Encoder contracts

The supported interface is `grampy.api`; version one is library-only.
`encode_mfsk_wav` takes keyword-only `parts`, `output_path` and optional
`config`, and returns immutable result records. The default `EncodeConfig`
uses **48,000 Hz**, the required and receive-qualified broadcast rate.

## Caller content and timeline

`MfskSegment` contains ordered `TextPart`, `TextFilePart` and `ImagePart`
items, with a mode (`MFSK32` or `MFSK64`) and carrier (default 1500 Hz).
`TextPart` transmits exact bytes; `from_text` uses strict encoding. Text files
are binary inputs with no newline, Unicode or framing normalization. Each
segment is independently framed and includes RSID, including the first and
repeated same-mode segments. There is no opt-out or implicit editorial pause.

`AudioPart` copies compatible PCM frames unchanged. `SilencePart` adds only
zero frames and requires a finite positive duration mapping to an integer
frame count. Parts retain caller order, including adjacent mode changes and
text resumed after pictures. The encoder does not resample, remix, resize,
apply color profiles or insert editorial content.

`EncodeResult.output_path` is the exact caller path. Its duration and all
`SegmentStart`/`ContentStart` values derive from integer frame coordinates
divided by the rate. Indices are zero-based. Each top-level input has one
segment record; each supplied MFSK content item has one content record.
Top-level MFSK time begins at the RSID lead guard. An image's content time
begins at its generated picture announcement, not at the later raster.
Audio and silence begin at their first copied or zero frame. Framing, RSID,
picture transitions and termination are included in output duration.

## Input and resource bounds

- PNG: 8-bit `L` or `RGB`, without alpha or `tRNS`, at most 64 MiB on disk;
  each dimension 1–4095. Color/grayscale and speeds 8, 4 and 2 are explicit
  options. RGB-to-gray uses `(31*R + 61*G + 8*B)//100`; gray-to-RGB expands
  components equally. PNG sample values are not transformed by metadata.
- Audio: classic RIFF/WAVE format tag 1, mono PCM16, nonempty complete frames,
  at the configured rate. Ancillary chunks are omitted from the canonical
  output. RF64, extensible/compressed/float WAV, partial data, other widths,
  stereo and rate mismatch are rejected.
- Configuration: finite carrier with the complete mode span strictly inside
  zero and Nyquist. The validator retains integer multiples of 8000 from
  8000–192000 Hz for compatibility; only 48 kHz has a receive-quality
  commitment. Booleans do not count as numeric configuration values.
- Output: canonical 44-byte-header mono PCM16 RIFF/WAVE, at most
  2,147,483,629 frames. Preflight rejects predicted RIFF overflow. Working
  allocation consists of fixed streaming buffers, one decoded image and
  per-input timestamp records; it does not grow with WAV duration.

The receiver-quality promise is the practical scope in the
[production baseline](production-baseline.md), not bit-perfect decoded
pixels at every accepted input dimension/rate. Independent protocol and
waveform checks remain exact; copied audio, silence and coordinates remain
exact.

## Files and failures

The parent directory must exist. The caller controls all paths and keeps
inputs stable for the call. Preflight validates the whole composition before
opening or replacing the output, including aliases to any input (same path,
symlink or hard link). Predictable validation failures preserve an existing
output. Invalid content/configuration raises `ValueError`; filesystem errors
remain `OSError` subclasses. Strict text conversion keeps normal codec errors.

After writing starts, a reported failure closes handles and removes the
requested output, including a replaced file; the old file is not restored.
There is no temporary output path. If removal fails, its `OSError` reports
the residual path and chains the original error. Forced process or machine
termination is outside the cleanup guarantee.
