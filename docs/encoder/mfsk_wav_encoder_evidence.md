# Native MFSK WAV encoder evidence harness

## Purpose and independence boundary

This harness supplies the offline acceptance oracle for Sessions 2 through 7
of the native MFSK WAV encoder plan. It is intentionally independent of future
encoder production modules: `tests/mfsk_encoder_evidence.py` imports no encoder
code and derives its expected events from the frozen protocol evidence and the
wire equations.

The frozen inputs are:

| Input | SHA-256 | Role |
| --- | --- | --- |
| `docs/decoder/data/mfsk_wire_vectors.json` | `e98ecc1982c97d4362846c6cf56e163cab035f73c9c9bc35b2406bccb613e4bc` | FEC, interleaver, text-to-tone, timing, framing, and picture-frequency vectors |
| `docs/decoder/data/mfsk_varicode.json` | `8e40e8927059dc592f97f15e1a96d2ad430c284f1d074c8df61e0847ffaf27a3` | Complete independently compared 256-octet Varicode table |
| `docs/decoder/data/mfsk_fixture_evidence.json` | `062fbfe512c32c645c4f16b83d8076aea7e481fdb0bd3c4c97735423d6055cb2` | Controlled fldigi WAV hashes and frozen waveform measurements |
| `tests/fixtures/mfsk/primary-color-8x4.ppm` | `21d5e19be8566a266d8c01f214e4049b59b9fdbba96ab1069178e88a548dc104` | Known RGB raster that exposes row and component-order defects |

Changing any frozen input is an evidence change. It requires an explicit
investigation and baseline update; an encoder candidate must never regenerate
its own expected values and silently repin them.

## Executable contract

`tests/test_mfsk_encoder_evidence.py` makes these checks executable:

- all 256 Varicode entries, including exact control and extended-octet
  checkpoints;
- every frozen convolutional-code vector using a small independent equation
  implementation;
- the fldigi transmitter interleaver orientation, packed labels, and all 16
  binary-label-to-physical-tone mappings;
- MFSK32 and MFSK64 symbol rate, tone spacing, tone span, transmitted start
  zeros, framing characters, and empty/half-full flush counts;
- all six grayscale/color `p8`, `p4`, and `p2` picture control tokens;
- the 352-modem-sample prologue, exact output-frame scaling, grayscale
  arithmetic, row-major grayscale order, per-row red/green/blue plane order,
  raster frame counts, and endpoint pixel frequencies in both modes;
- the checked-in MFSK64 reference-WAV prologue and raster measurements; and
- coverage and schema checks for the final Pi qualification contract.

The oracle is mutation-sensitive. The suite changes one tone index, shortens
the prologue and one pixel interval, and substitutes pixel-interleaved RGB for
row-plane RGB. Each deliberate defect must raise `EvidenceMismatch`. This is
the minimum proof required before a new candidate-facing assertion is trusted.

Future session tests should compare candidate intermediate events directly
with these helpers. A candidate must not import the test oracle or share its
implementation. If a production optimization removes an intermediate event,
the test adapter may reconstruct that event only from the candidate's emitted
bytes, indices, frequencies, frame coordinates, or PCM—not by calling the
oracle from production code.

## Controlled fixture inventory

Session 1 ran the existing inventory against `.local/fldigi-fixtures`. All four
expected fixtures were absent, and none had a hash mismatch:

```text
verified: 0
missing: 4
hash-mismatch: 0
```

The large WAV and SigMF files are optional local evidence. Their absence does
not weaken or alter their checked-in hashes and frozen measurements, and does
not block Sessions 2 through 7. If artifacts later appear locally, run
`tools/mfsk-fixture-inventory --require-all`; any mismatch is an investigation,
not permission to regenerate expected hashes.

## Coupled GramPy round-trip convention

A local encoder-to-GramPy-decoder test is useful only as a smoke test. Name
such tests and evidence `coupled_round_trip`, and record both the encoder and
decoder source revision and configuration. The test may check that expected
text and images survive an end-to-end local path, but it must not:

- accept wire behavior that disagrees with the independent vectors;
- replace exact tone, timing, framing, raster, or PCM assertions;
- be described as independent interoperability evidence; or
- accept the production candidate without pinned fldigi reception.

Failure is actionable because it can expose integration defects. Success is
supporting evidence only because the encoder and decoder may share the same
misinterpretation.

## Final Pi/fldigi qualification contract

The deterministic case matrix is
`data/mfsk_encoder_pi_matrix_v1.json`. It fixes 48 kHz, normal sideband, explicit
receiver modes, receiver identity
`fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`, five case compositions, and the
required checks. Its coverage includes:

- independently framed MFSK32 and MFSK64 text;
- grayscale MFSK32 pictures at p8, p4, and p2;
- color MFSK64 pictures at p8, p4, and p2;
- text reacquisition after every picture;
- a mixed MFSK32/silence/copied-audio/silence/MFSK64 composition; and
- separate known receiver-mode windows at mixed-mode boundaries, because v1
  emits no RSID.

Before Session 8, a checked-in reusable `tools/pi-*.sh` workflow must implement
the matrix and run through `tools/pi-remote.sh`. It must build or install the
candidate distribution, materialize the declared deterministic source inputs,
encode every case, replay the specified window in the selected receiver mode,
and retain all artifacts named by the matrix. Session 1 does not implement or
run that external workflow.

The result must validate against
`data/mfsk_encoder_pi_qualification_manifest_v1.schema.json`. The manifest
binds the source revision, matrix, distribution, inputs, Pi platform, receiver
binary/configuration, generated WAVs, encoder results and integer frame
coordinates, logs, recovered text, recovered images and pixel hashes, checks,
and discrepancy classifications. Every referenced artifact records its path,
byte count, and SHA-256.

Exact text, dimensions, and pixels are preferred. When the receiver artifact
does not permit exact pixel comparison, or when exact scores could conceal a
localized raster defect, use the change-management candidate-set N-up review
and retain its artifacts. A pass cannot contain an unresolved discrepancy.

Session 8 classifies every discrepancy as an encoder defect, reference
limitation, automation failure, environment failure, or unresolved. It does
not repin the matrix or relax a required check during the run.
