# Native MFSK WAV encoder evidence harness

## Purpose and independence boundary

This harness supplies the offline text, picture, and MFSK composition oracle
established through Session 6. The Session 6R0 source-derived RSID vector in
`data/mfsk_encoder_rsid_oracle_v1.json` has been checked against the pinned
transmitter source and drives the independent native PCM checks. Pinned
receiver acceptance of a GramPy candidate remains open; local evidence cannot
accept the corrected whole-WAV fldigi requirement. The existing
`tests/mfsk_encoder_evidence.py` imports no
encoder code and derives its expected events from frozen protocol evidence and
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

## Session 6R0 pinned RSID transmitter evidence

The Pi already contained an unmodified tracked checkout of fldigi tag
`v4.2.12` at commit `b0032cabb70dc670064ed7561b9a626010a5e4ae`; no
source download was needed. Its `src/rsid/rsid.cxx`, `rsid_defs.cxx`, and
`src/include/rsid.h` have respective SHA-256 hashes
`7cb9de5ed14dff4a213027945dd06a8bdb7f767616ac129e27132a67c2573d6e`,
`e9b1405a1a51fc1074636218b404e2ca87111282365b769b85215b2f7298749e`,
and `5ff78314aa0da1fc7fa430983745b625d238fdefa7456f9cda9c3852dbecd4d0`.
The pinned transmitter and ID table establish:

- MFSK32 is primary code 147. MFSK64 is secondary code 620, sent as primary
  escape code 6, ten silent symbol periods, then secondary code 620.
- Each ID starts with five silent symbol periods. Each complete `send` ends
  with five more silent periods before modem data. These are receiver timing
  requirements, not caller-requested composition gaps.
- Each word has fifteen 16-tone symbols. The nominal period is
  `1024/11025` seconds and adjacent tones are `11025/1024` Hz apart. In
  normal sideband, the transmitter's tone formula is
  `tx_frequency + (tone_index - 7) * 11025/1024` Hz, with phase carried
  across symbols and reset before the secondary word.
- The native encoder's exact output rule is
  `floor(sample_rate_hz * 1024/11025)` frames per symbol, matching the pinned
  transmitter's integer truncation rule at its modem sample rate. At 48 kHz
  this is 4,458 frames per symbol, so the complete native RSID prefixes are
  111,450 frames for MFSK32 and 222,900 for MFSK64. The independent vector
  records every interval and all three 15-symbol words.
- The native PCM rule uses the already confirmed 16,384 peak and rounds each
  sine sample after advancing phase, with no extra envelope inside RSID.
  This is a native output contract, not a claim of bit-identical fldigi WAV
  output through its separate audio/resampler path.

An independent calculation using the pinned C++ `Squares` and `indices`
tables reproduced all three frozen words without importing the GramPy
decoder; a later `grampy.rsid.encode_rsid` cross-check is supporting evidence
only. The pinned source confirms the wire sequence, frequency and phase rule,
and required internal guards. It does not by itself prove that a new native
48-kHz output will be acquired during continuous playback; that is a Session
6R2/8 receiver acceptance check, not a reason to add speculative editorial
silence in 6R0. `tests/test_mfsk_rsid_oracle.py` validates the words and 48-kHz
intervals without importing the production encoder or decoder.

## Session 6R1 isolated waveform evidence

`tests/test_mfsk_encode_session6r1.py` compares complete little-endian PCM
against analytical integration of the frozen Session 6R0 frequencies and
words, without calling a GramPy decoder. Both modes match byte for byte at
48 kHz and carriers 700, 1500, and 2317.25 Hz, plus 8-kHz and 192-kHz endpoint
checks. Exact guards, unshaped 16,384 peak, advance-before-sample phase,
continuity across symbols, and secondary reset are covered by complete PCM
comparisons and boundary assertions.

All 24 supported rates have exact planned/emitted frame counts and
one-symbol sink writes. Three consecutive MFSK64 prefixes at 192 kHz to a
discard sink stay below 256 KiB of traced peak allocations. Deliberate tone,
spacing, carrier alignment, level, phase-sample, and guard/frame mutations
fail the independent PCM comparison. Invalid inputs write nothing; sink
exceptions and short writes propagate. Runtime synthesis reads no oracle
file and imports no RSID decoder.

The managed regression on 2026-10-01 passed 60 encoder/evidence tests in
6.132 seconds and 3 frozen RSID oracle tests in 0.016 seconds. This qualifies
the isolated native waveform; candidate reception is covered separately below.
It does not claim bit-identical fldigi audio/resampler output.

## Session 6R2 composition and local acquisition evidence

`tests/test_mfsk_encode_session6r2.py` compares public WAV data with the
independent frozen-oracle RSID PCM followed immediately by the existing MFSK
waveform, for both modes at 8, 48, and 192 kHz. This locks the source-derived
guards and unchanged payload oscillator/envelope without an editorial gap.
All 24 rates have exact prefix-inclusive preflight totals and nested empty
content timestamps. Repeated empty segments emit both complete prefixes.
The classic RIFF ceiling includes every prefix; overflow preserves an
existing output. Prefix exceptions, interruption, incorrect prefix frame
returns, and payload failures after RSID remove a replaced output.
Session 6's text-file/image coordinates now include the prefix, while its
audio, silence, alias, preflight, replacement, and cleanup checks remain.

The coupled acquisition matrix uses four ordered mode pairs (32→64, 64→32,
32→32, and 64→64), each in adjacent and caller-spaced layouts. The latter
begin with copied audio and insert 250 ms of explicit silence plus copied
audio between MFSK segments. Carriers change from 1400 to 1600 Hz in every
pair. A single Hilbert transform converts each complete 48-kHz WAV to
analytic SigMF; the public decoder runs once with `mode="auto"`, no carrier
hint, and no caller-selected windows. Both detected identifiers, both
carriers within 3 Hz, and both complete messages in order are required.
Every inserted audio byte and silence frame is also checked.

Receiver timing is deliberately approximate evidence: its bucket/refinement
algorithm can report a window before the on-air word and accepts code
distance up to two. Initial test runs incorrectly demanded zero distance and
near-exact tone-word starts; they failed those assertions despite acquiring
the expected modes. After applying the detector's existing contract, all
eight layouts recovered both ordered messages. Smoke checks require each
reported event window to overlap the corresponding on-air identifier word;
exact emitted words, guards, and public coordinates remain independently
checked. No encoder gap or decoder change was made to accommodate this.

This evidence is coupled and does not establish fldigi interoperability.
The unchanged v2 Pi matrix and manifest require pinned whole-WAV RxID
reception in Session 8. Session 7 retains package, long-duration resource,
and platform qualification work.

## Session 7 packaging and local-hardening evidence

The distribution remains library-only: `grampy.api` exports the complete
encoder surface and no `mfsk-wav-encode` console script is declared. Pillow is
a required base dependency, not an optional extra. The API guide documents the
input profile, automatic RSID rule, frame-derived timestamps, exact-path
cleanup behavior, and CLI scope; the README includes a text composition
example.

A managed isolated wheel build verified that the package contains
`grampy.api`, the public composer, the RSID writer, and the packaged Varicode
data, and that its core metadata declares Pillow. The local virtualenv did not
initially contain the PEP 517 backend, so the isolated build resolved the
already-declared `setuptools>=77.0.3` build requirement without changing the
repository or its virtualenv.

`tests/test_mfsk_encode_session7.py` proves that large copied-audio and
silence paths issue at most 64-KiB PCM writes and remain under a 512-KiB traced
working-allocation bound independent of the 2-MiB exercise input. Long text
files are read in the same fixed 64-KiB chunks, and a 1024-by-1024 image keeps
one source raster while component events stream without a second image-sized
plane. It also checks that a mixed output's returned coordinates are within,
ordered against, and duration-identical to the completed WAV. The existing
Session 6R1/R2 tests retain the independent RSID bounded-memory, frame-count,
interruption, short-write, accounting-mismatch, existing-output replacement,
and cleanup coverage.

The complete managed regression on 2026-10-01 passed **243 tests in 129.902
seconds with 6 expected skips**. The v2 matrix status is now
`candidate-ready-pending-pinned-receiver-execution`; its v2 schema is the
transfer-manifest contract for the Session 8 run. This is local evidence only;
pinned fldigi whole-WAV RxID reception is not claimed here.

The complete managed regression on 2026-10-01 passed 238 tests in
141.118 seconds with 6 expected skips; its authoritative result reports exit
0. Candidate hashes, initial receiver-assertion failures, and the Session 7
handoff are recorded in `mfsk_wav_encoder_change.md`.

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

## Pi/fldigi qualification contract under RSID correction

Use the [Pi fldigi decode runbook](../operations/fldigi-pi-decodes.md) to find
the qualified receiver and its normal WAV receive adapter. The historical
`run-corpus.sh` archives are examples, not the entry point for a new encoder
candidate.

The current deterministic case matrix is
`data/mfsk_encoder_pi_matrix_v1.json`. It fixes 48 kHz, normal sideband,
manually selected receiver modes, receiver identity
`fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`, six diagnostic compositions, and
their checks. Its existing coverage includes:

- independently framed MFSK32 and MFSK64 text;
- grayscale MFSK32 pictures at p8, p4, and p2;
- color MFSK64 pictures at p8, p4, and p2;
- text reacquisition after every picture;
- adjacent MFSK32/MFSK64 and a
  MFSK32/silence/copied-audio/silence/MFSK64 composition; and
- separate known receiver-mode windows at mixed-mode boundaries.

This matrix belongs to the no-RSID Session 6 slice. Its `rsid_enabled: false`
setting and manual mode windows cannot establish automatic mixed-mode fldigi
compatibility. Session 6R0 must amend and version the matrix so RxID is enabled
and continuous whole-WAV replay is a required pass condition. Manual windows
may remain diagnostic after a failed whole-WAV run. The amendment must cover
first acquisition, both mode-change directions, repeated modes, and MFSK
following audio or explicit silence; exact RSID codes, guard timing, and
configuration are settled through pinned-source evidence before that matrix
becomes final.

The confirmed but not yet executed replacement is
`data/mfsk_encoder_pi_matrix_v2.json`, with its
own `data/mfsk_encoder_pi_qualification_manifest_v2.schema.json`. It requires
RxID enabled and active (not notify-only), passband search, no auto-disable,
and one continuous full-output replay per composition from an unrelated
initial mode. Cases cover first MFSK32 and extended MFSK64 acquisition,
both mode-change directions, same-mode retune, audio/silence interruption,
and picture coverage. The manifest separates receiver-detected RSID events
from independent exact encoder frame accounting. Cross-field checks must
verify that every replay interval is exactly `[0, generated_wav.frame_count)`
and that the expected acquisitions and recovered content occur in order;
JSON Schema alone cannot prove those relationships. A manually selected
window can diagnose a failure, never change it to a pass. Pinned-source
verification and product confirmation are complete; candidate receiver
execution remains Session 6R2/8. Product management confirmed unconditional
RSID before every MFSK segment, including the first and repeated same-mode
segments, with no v1 caller opt-out or extra editorial gap.

### Qualified Pi receiver smoke (2026-10-01)

The existing Pi decoder adapter at
`/opt/radiogram/current/tools/fldigi-decode-wav` was run against the known
RSID mode-change WAV
`/var/lib/radiogram/rsid-debug/wrmi-425-475.wav` (SHA-256
`5ed7181628feaedc3b0e02f68eca3816df9850db4316e620441b86a9e8af75d9`).
The adapter used the qualified fldigi 4.2.13 build from the Session 10D
reference, started in MFSK32, and replayed the whole WAV with RxID on, AFC
off, a 1500 Hz initial carrier, and ALSA loopback. Its control process exited
successfully and the decoded text included “This is Shortwave Radiogram in
MFSK64”; the decode archive SHA-256 was
`56403cf1c040601605bd2c185f975e3387b16d9937e756e448cdb7fe41c6dcee`.
This verifies the established Pi receive path for an RSID mode change. It is
not encoder-candidate qualification: no GramPy-generated WAV was used, and
the current encoder does not yet emit RSID. The separate temporary fldigi
4.2.11 RPC service was stopped because the qualified adapter uses the same
RPC port.

Before Session 8, a checked-in reusable `tools/pi-*.sh` workflow must implement
the matrix and run through `tools/pi-remote.sh`. It must build or install the
candidate distribution, materialize the declared deterministic source inputs,
encode every case, perform the amended continuous RxID receive run, and retain
all artifacts named by the matrix. Session 1 did not implement or run that
external workflow.

The amended result must validate against
`data/mfsk_encoder_pi_qualification_manifest_v2.schema.json`. The manifest
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
