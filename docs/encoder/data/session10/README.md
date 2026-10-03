# Final encoder package and Pi measurements

**Closed, 2026-10-03:** practical 48-kHz acceptance is final. The local
`radiogrampy` 0.1.3 wheel includes the accepted automatic MFSK32 picture
dispatch and the separately verified L-to-color row-plane correction.
No publication, appliance replacement or commit was performed.

Wheel SHA-256: `e549e3d7cc635f678e04a43b2cd79407f2c7622d56293e98fc50eca67b543ab7` (166,368 bytes).
The local artifact is retained at `.local/session10/final/distribution/radiogrampy-0.1.3-py3-none-any.whl`;
[package identity](package.json) contains every module hash and metadata.
The isolated installed-wheel suite ran **248 tests with six expected skips**,
zero failures/errors, in 145.172 seconds.

## Encoder-only Pi performance

Device: **Raspberry Pi 3 Model B Plus Rev 1.4**, aarch64, Python
3.13.5, at 48 kHz. Two fresh-process samples per workload;
the table gives medians for time/ratio and maximum peak RSS.

Generated text/picture/mixed workloads used **0.133–0.172 CPU
seconds per broadcast second**, or 8.0–10.3 CPU
seconds per broadcast minute. Wall ratios were 0.133–0.172,
about 5.8–7.5 times faster than playback.
This estimates offline generation for similar workloads on this device;
two repetitions are not a performance SLA or a live-streaming CPU percentage.

| Workload | Broadcast s | CPU s | Wall s | CPU/broadcast | Peak RSS MiB | WAV bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Accepted MFSK32 grayscale p8 240x180 | 63.678 | 9.494 | 9.507 | 0.14910 | 101.01 | 6,113,120 |
| Accepted MFSK64 color p8 240x180 | 145.360 | 21.950 | 21.957 | 0.15101 | 101.02 | 13,954,580 |
| Accepted MFSK64 color p2 160x120 | 30.288 | 5.208 | 5.210 | 0.17197 | 100.75 | 2,907,668 |
| Accepted MFSK64 color p4 240x180 with MFSK32 text, audio and silence | 99.706 | 15.723 | 15.729 | 0.15769 | 101.02 | 9,571,784 |
| 2048-byte MFSK32 text file | 250.898 | 33.334 | 33.351 | 0.13286 | 100.14 | 24,086,240 |
| 30-second exact AudioPart copy | 30.000 | 0.010 | 0.010 | 0.00034 | 100.14 | 2,880,044 |
| 300-second exact AudioPart copy | 300.000 | 0.091 | 0.091 | 0.00030 | 100.14 | 28,800,044 |

Timings bracket `encode_mfsk_wav` only: imports, preparation, validation,
receiver and decoder execution are excluded. Process CPU includes user/kernel
time and all threads. File writing and close are included; there is no
`fsync` or cold-storage claim. Peak process RSS (maximum 101.02 MiB)
includes interpreter/imports and inspected input, not just incremental encoder
allocation. The 30-second and five-minute AudioParts copy exact PCM with
similar RSS, corroborating duration-independent copying. WAV size at 48 kHz
is exactly 44 header bytes plus 96,000 bytes per second of output.

## Retained evidence

- [Frozen benchmark workloads](benchmark-matrix.json),
  [all samples and summaries](pi-encoder-benchmark.json),
  [device/runtime/source/input identity](pi-encoder-identity.json), and
  [authoritative-run and integrity verification](benchmark-verification.json).
- [Final build result](build-result.md),
  [packaged data/type files](package-data-checks.json),
  [installed-wheel regression](installed-wheel-regression.json),
  [regression wrapper result](regression-result.md), and
  [regression log](regression.log).
- [All ten accepted WAVs preserved byte for byte](accepted-waveform-preservation.json),
  [four package smoke checks](wheel-waveform-checks.json),
  [full-size L/RGB equivalence](large-l-color-checks.json), and
  [corrected independent assertion rejects the prior wheel](defect-regression-sensitivity.json).
- [Final closeout integrity](closeout-integrity.json) binds the package to
  the source and unchanged frozen acceptance records.

Earlier package and Pi results remain under `pre-correction/` and
`.local/session10/`. The initial installed-wheel suite attempt could not
import three repository test helpers because its runner omitted the test
directory from the module search path. The corrected runner uses the normal
discovery behavior; the full final suite above passes. Its failed attempt/log
remain in `.local/session10/superseded/`, without treating a runner setup error
as a production failure. Final full Pi logs/staging and inputs are preserved;
only new benchmark/check WAVs and consumed managed run directories are removed.

## Subsequent artifact cleanup (2026-10-03)

The [cleanup and restoration record](cleanup.md) supersedes earlier statements
that all loose working files and transferred Pi staging remain in their
original locations. Unique evidence is preserved; obsolete snapshots/logs
are archived, derivable IQ caches are removed after exact regeneration, and
inactive Pi staging is retired. Accepted measurements and source are unchanged.
