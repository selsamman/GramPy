# Encoder validation and maintenance

Maintain the exact protocol/file contracts and the accepted practical
receive-quality scope separately. Passing a visual score does not excuse
wrong framing, frequencies, frame counts, audio bytes or timestamps.

## Local regression and package checks

Use the repository virtualenv and managed Mac wrapper on a network-capable
surface, as required by [AGENTS.md](../../AGENTS.md). The batch normally runs:

```sh
PYTHONPATH="$PWD/src" PATH="$PWD/.venv/bin:$PATH" \
  .venv/bin/python -m unittest discover -s tests
```

The encoder evidence/oracle tests freeze independent wire and RSID vectors.
The session-named regression files retain useful coverage after development:
`test_mfsk_encode_session2.py` covers byte-to-tone state/chunking;
`session3` covers waveform, framing, canonical WAV and cleanup; `session4`
covers PNG/raster profiles; `session5` covers picture transitions and resumed
text; `session6` covers the public API, composition, AudioParts, aliases and
failures; `session6r1`/`session6r2` cover RSID and automatic acquisitions;
`session7` covers bounded reads/writes, large inputs and package metadata.
`test_auto_picture_roundtrip.py` protects mixed MFSK32/MFSK64 picture order,
unique files and recovered text at 48 kHz.

For a package candidate, build with the repository Python's
`pip wheel --no-deps`, inspect wheel metadata/data/source hashes, and install
with `--no-deps --no-index --target` into a fresh isolated directory. Select
that directory explicitly in `PYTHONPATH` for installed-wheel validation;
confirm the imported API comes from it. This intentional replacement of the
source-tree import checks the actual artifact without changing the virtualenv
dependencies. Existing dependencies must be available; do not silently use a
different implementation when one is missing.

## Practical receiver qualification

The frozen [v3 matrix](data/mfsk_encoder_pi_matrix_v3.json) contains ten whole
48-kHz broadcasts with 240x180 or 160x120 pictures, both modes, retained
picture speeds and a text/audio/silence/picture composition. Its engineering
screen requires raw MAE ≤25/255, aligned MAE ≤20/255, absolute channel bias
≤15/255, offset ≤12 components and ≤12 offset changes. Correct geometry,
picture count, ordered text/announcements and automatic mode/carrier
acquisition are also required. These margins are scoped engineering criteria,
not a calibrated universal quality standard. PM reviews all images after
numerical screening and can reject visible defects despite passing averages.

The pinned Pi receiver is fldigi 4.2.13 with whole-WAV playback, initial
BPSK31, RxID on and AFC off. Use the managed Pi wrapper and the checked-in
`tools/pi-qualify-mfsk-broadcast.sh` workflow with explicit local staging.
Retain exact source/WAV/config/binary identities, ordered text, settled viewer
buffers and autosaves; an exit status alone never qualifies a case. Manual
mode/window decoding is diagnostic only.

The original v3 execution used the then-current MFSK64-only automatic picture
dispatch. Its record remains frozen. The separately evaluated
[MFSK32 correction](../decoder/data/auto-mfsk32-pictures/qualification.json)
recovers all ten unchanged WAVs in the public automatic decoder, with seven
previous MFSK64 rasters pixel-identical. The
[PM acceptance overlay](data/session9/practical-acceptance.json) records the
subsequent acceptance without rewriting execution-time pending status.

Original tiny-image failures and non-exact pixel scores remain historical
evidence. No universally safe minimum picture size or 8-kHz picture-quality
promise has been established. Mac manual decoding is useful independent
harness evidence; it does not replace the complete Pi acquisition checks.

## Encoder performance procedure

`tools/benchmark-mfsk-encoder.py` takes a staged bundle and fresh results
directory. Freeze `matrix.json` and inputs before execution. Use a fresh
worker process for each case/repeat, with imports, input preparation and
validation outside the timers. Measure `time.process_time()` and elapsed
wall time around `encode_mfsk_wav` only. Process CPU includes all worker
threads and user/kernel time; receiver and decoder execution are absent.

Report CPU seconds / emitted broadcast seconds and wall seconds / broadcast
seconds separately. A ratio of 0.1 means ten seconds of encoding per hundred
seconds of broadcast. Retain each sample, ranges, medians, architecture,
runtime/dependency versions, wheel/source/input hashes, peak RSS, frame count
and WAV bytes. Peak RSS includes interpreter, imports and inspected input;
it is not incremental encoder allocation. Timed I/O includes normal writes
and close, without `fsync` or a cold-storage guarantee. Two repeats estimate
feasibility; they are not a statistical performance SLA.

`tools/pi-benchmark-mfsk-encoder.sh` installs the supplied wheel into an
isolated target with an explicitly supplied runtime. Invoke it through
`tools/pi-remote.sh`; keep machine addresses, runtime/staging paths and
transport commands in `.local/`. Do not install into the active appliance.
Only freshly generated benchmark WAVs are removed after exact WAV,
AudioPart/silence and coordinate checks; hashes/metrics remain. The final
measured records are linked from the [production baseline](production-baseline.md).

## Evidence preservation

Keep frozen failed and passing records, PM decisions, original signals,
scorecard settings, source identities and review pages. Investigation scripts
remain historical reproductions, not runtime dependencies. Preserve valuable
`.local/` state and the external corpus. Consume each managed `result.md` and
remove only its completed run directory, never an active one. Future changes
use [Change Management v1](../operations/change-management-v1.md) and repeat
the evidence appropriate to the changed behavior.
