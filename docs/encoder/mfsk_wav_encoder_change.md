# Native MFSK WAV encoder active change record

**Change ID:** `mfsk-wav-encoder-v1`  
**Status:** active — Session 6 local slice retained; RSID product correction
requires Sessions 6R0–6R2 before feature completion
**Session 0 completed:** 2026-10-01  
**Session 1 completed:** 2026-10-01
**Session 2 completed:** 2026-10-01
**Session 3 completed:** 2026-10-01
**Session 4 completed:** 2026-10-01
**Session 5 completed:** 2026-10-01
**Session 6 local slice completed:** 2026-10-01; whole-WAV mixed-mode acceptance
withdrawn pending RSID remediation
**Accepted production behavior changed:** no

## Request and boundary

Build the native, streaming MFSK WAV encoder defined in
`mfsk_wav_encoder_plan.md`. The product outcome is one caller-directed mono
16-bit PCM WAV composed from independently framed MFSK32/MFSK64 content,
compatible audio, and explicit silence, with exact caller-content start times.
The encoder must interoperate with pinned fldigi and must not depend on fldigi
at runtime. Product management clarified after Session 6 that interoperability
includes automatic mode acquisition during continuous playback of one
mixed-mode WAV with fldigi RxID enabled. Manually selecting a mode for each
window does not satisfy that outcome.

This record covers the full encoder change through acceptance and closeout.
Session 0 only defines the contract and acceptance cases. It deliberately
changes no production source, package metadata, tests, fixtures, or generated
artifacts.

Change Management v1 calls for a definition restore-point commit. Commit
`f1901e225ffd158bdecba32435aa1c356d02db9d` (`Encoding session 0 complete`)
satisfies that entry condition. Session 1 adds evidence infrastructure and no
production encoder behavior.

In scope and exclusions are the current product requirements and explicit
exclusions in the plan. The former RSID exclusion is superseded by the
whole-WAV fldigi acquisition requirement. V1 still excludes reverse-sideband
transmission, live sound output, channel simulation, image editing, audio
conversion, and additional MFSK modes. A CLI is not part of the confirmed v1
contract and requires a later explicit scope decision.

## Definition baseline

The immutable product baseline at the start of this change is:

| Baseline dimension | Identity |
| --- | --- |
| Source revision | `d471eff6afcc96c15af88947ec02bca1d4f1c708` (`Prepare for encoding immplementaiton`) |
| Existing public API | `src/grampy/api.py` at the source revision; decoder API only |
| Existing accepted decoder | `docs/decoder/production-baseline.md`; `supported_hybrid`, `response_matched`, `bounded_correlation`, `full_hann`, `unified_grid`, persistent-tone `measure` |
| Python/package baseline | Python 3.11+; distribution `radiogrampy` 0.1.3; NumPy, SciPy, and jsonschema core dependencies |
| Target platforms | macOS and Linux; Raspberry Pi is the target qualification host |

No encoder candidate exists yet. The eventual candidate delta must be limited
to new encoder behavior and the smallest necessary packaging, public-export,
documentation, and test changes. Existing decoder behavior and accepted
decoder defaults are behavior-lock constraints, not refactoring opportunities.

## Evidence baseline

The following checked-in evidence is available before implementation:

| Evidence | Identity and role |
| --- | --- |
| Independent wire vectors | `docs/decoder/data/mfsk_wire_vectors.json`, SHA-256 `e98ecc1982c97d4362846c6cf56e163cab035f73c9c9bc35b2406bccb613e4bc`; exact Gray, FEC, interleaver, framing, timing, picture, and short text-to-tone expectations |
| Complete Varicode table | `docs/decoder/data/mfsk_varicode.json`, SHA-256 `8e40e8927059dc592f97f15e1a96d2ad430c284f1d074c8df61e0847ffaf27a3`; independently compared 256-octet table |
| Frozen fixture evidence | `docs/decoder/data/mfsk_fixture_evidence.json`, SHA-256 `062fbfe512c32c645c4f16b83d8076aea7e481fdb0bd3c4c97735423d6055cb2`; controlled text and picture artifact hashes and measurements |
| Controlled transmitter | fldigi tag `v4.2.12`, commit `b0032cabb70dc670064ed7561b9a626010a5e4ae`, binary SHA-256 `de63a235e959e01e31ab05045fd703d59d3ee74017b64d9b254e8f48cb0d6e9c` |
| Controlled compatibility receiver | fldigi `4.2.06`, used for the frozen fixture receive results |
| Final independent receiver | qualified Pi reference `fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`, already named by the accepted decoder baseline |
| Wire contract | `docs/decoder/mfsk_wire_spec.md`; review-draft status is an explicit evidence risk, not permission to silently diverge |
| Pi execution entry point | `tools/pi-remote.sh`, SHA-256 `d1a4486667b846081854b60e4391bb05c2e66e804035001d2b57bef63c5ab07b`; it runs a checked-in reusable workflow or a one-off `.local/pi-command.sh` through managed execution |

Large controlled WAV/SigMF artifacts are optional local evidence and are not
part of Git. Session 1 inventoried the default `.local/fldigi-fixtures` root:
all four fixture sets were missing and none had a hash mismatch. Missing
artifacts remain an evidence gap to fill, not a reason to regenerate and
silently repin expected hashes.

The current Pi scripts generate transmitter fixtures or exercise historical
decoder paths. They do not constitute the encoder's final receive-
qualification matrix. Session 1 specifies the matrix and artifact manifest in
`docs/encoder/data/`; before Session 8, a reusable checked-in `tools/pi-*.sh`
workflow must run it through `tools/pi-remote.sh` and record the pinned receiver
identity, configuration, input/output hashes, logs, recovered text, and images.

Session 1 adds these immutable evidence entry points for later encoder work:

| Evidence | SHA-256 | Role |
| --- | --- | --- |
| `tests/mfsk_encoder_evidence.py` | `37608e70aea3f22686b2c2bc91169cc58eda764894fb6fb807bb288d03d3404d` | Encoder-independent oracle helpers |
| `tests/test_mfsk_encoder_evidence.py` | `5b9a5015dc5a446ba937f2fb761505782164d1e8815ec1ad608df31b7f068d00` | Exact-vector, mutation, matrix, and schema tests |
| `docs/encoder/data/mfsk_encoder_pi_matrix_v1.json` | `456e810bf93bbade1f0af055689366ff8aa1d2f8b31463af2a6786e396d3dfbb` | Final pinned-receiver case matrix |
| `docs/encoder/data/mfsk_encoder_pi_qualification_manifest_v1.schema.json` | `0972037aa31c9e5caaa5137f4bffb634a820e1966bc45b3bc6225b80246dc66c` | Final run artifact and outcome contract |

## Session 0 decision review

The exact API was reviewed against filesystem safety, RIFF field limits,
streaming bounds, image dependency behavior, content-boundary timing, and the
existing evidence. No public type, field, field order, default, or callable
signature changed. The plan now contains the normative detail behind these
outcomes:

| Decision | Session 0 outcome | Rationale |
| --- | --- | --- |
| D-001 | Confirmed with preflight, alias, failure, sequence-snapshot, error, and timestamp clarifications | Without these rules, exact-path replacement can destroy an input and content timestamps are ambiguous across stateful text boundaries. |
| D-002 | Confirmed | Ordered heterogeneous composition is the core product outcome and does not conflict with the wire contract. |
| D-003 | Confirmed | Independent framing makes mode state explicit and preserves the exclusion of RSID and seamless switching. |
| D-004 | Confirmed with empty-item and codec-error clarifications | Octets remain authoritative. Empty byte items are well-defined logical boundaries; strict `str.encode` behavior should not be wrapped into a novel exception contract. |
| D-005 | Confirmed with a narrowed exact PNG profile | The phrase “supported PNG color forms” was open-ended. V1 now accepts only 8-bit `L` and `RGB`, rejects transparency and implicit editorial conversion, and applies exact grayscale arithmetic. |
| D-006 | Confirmed with an exact classic-PCM profile | “16-bit PCM WAV” did not decide RF64, extensible WAV, truncation, empty audio, or ancillary chunks. The clarified profile is directly copyable and testable. |
| D-007 | Confirmed with output/input alias rejection | Caller ownership of paths must not permit the output open to truncate a source through path, symlink, or hard-link aliasing. |
| D-008 | Confirmed | The vectors and frozen evidence are suitable inputs, but Session 1 must demonstrate that the harness rejects deliberate defects before it is trusted. Self-decoding remains smoke evidence only. |
| D-009 | Confirmed with exact reference identities | Controlled transmit evidence stays pinned to 4.2.12; final receive acceptance uses the already-qualified 4.2.13 Pi reference. An early Pi exception still requires a concrete contradiction. |
| D-012 | Core dependency | PNG encoding is mandatory in v1, so making Pillow an extra would make the base API fail a required use case. Package metadata changes wait for implementation. |

New D-014 through D-016 record the resource, replacement/alias, and timestamp
decisions introduced by this review. D-010, D-011, and D-013 remain assigned to
their later sessions; none blocks Session 1 after the definition restore point
is committed.

Rejected Session 0 alternatives:

- An optional Pillow extra was rejected because image input is mandatory, not
  an optional adapter.
- Broad automatic PNG-mode conversion was rejected because palette,
  transparency, precision loss, and color-management behavior would become
  implicit product policy.
- RF64 was rejected for v1 because the API promises canonical WAV and does not
  otherwise define an extended container. The classic RIFF ceiling is now an
  explicit preflight limit.
- Allowing an output to alias an input was rejected even when ordering might
  make a particular composition appear safe; it makes behavior order-
  dependent and can irreversibly destroy caller data.
- Restoring a replaced output after an encoding failure was not added. It
  would require a temporary or backup file and contradict the explicit
  no-temporary-file contract.

## Acceptance cases

These are requirements-level cases. Sessions 1–7, including 6R0–6R2, must turn the applicable
cases into executable tests and evidence without weakening their oracles.
Session 8 supplies the independent fldigi outcomes. Exact wire assertions use
the frozen evidence above, not values generated by the candidate.

| ID | Case and input | Required evidence |
| --- | --- | --- |
| AC-001 | Import every specified encoder alias, dataclass, and function from `grampy.api`; inspect field order, frozen behavior, defaults, annotations, and keyword-only function signature. | Exact API-surface test; existing decoder exports remain available. |
| AC-002 | Encode all 256 possible octets, representative empty/nonempty `TextPart`s, strict UTF-8 text, a failing strict codec conversion, and an unknown codec. | Exact Varicode/FEC/interleaver/tone vectors where applicable; normal `str.encode` exceptions; no byte normalization or inserted text. |
| AC-003 | Read text files containing CRLF, lone CR, NUL, `0xff`, no final newline, and an empty file. | Transmitted octets exactly equal file bytes; file paths are caller-controlled; content boundaries follow the integer-frame rule. |
| AC-004 | Compose adjacent independently framed MFSK32 and MFSK64 text segments at different valid carriers. | Each has its own confirmed MFSK framing and mode timing; the amended stream includes the required RSID and acquisition spacing. Pinned fldigi with RxID enabled recovers both during one continuous playback without manual mode selection. |
| AC-005 | In both modes, encode an 8-bit `L` PNG as grayscale and color and an 8-bit `RGB` PNG as color and grayscale, including values 0, 128, and 255. | Exact dimensions, component bytes, grayscale floor arithmetic, row order, RGB row-plane order, frequencies, and duration. |
| AC-006 | Exercise grayscale and color pictures at `samples_per_pixel` 8, 4, and 2, retaining dimensions. | Exact announcement suffix, raster frame count, and pixel frequency/duration vectors; final Pi matrix recovers each retained speed. |
| AC-007 | Encode image-first, text-image-text, multiple-image, and text-after-final-image MFSK segments. | Announcement, flush, prologue, raster, post-picture flush, resumed text, and content timestamps occur in exact order; GramPy decode is labeled smoke evidence. |
| AC-008 | Insert a compatible audio WAV between generated MFSK and silence parts. Include ancillary source chunks. | Source PCM frame bytes appear unchanged at the exact returned start frame; output contains only canonical header/data; subsequent coordinates remain exact. |
| AC-009 | Insert positive silence values that map to integral frame counts, including one frame, and reject zero, negative, NaN, infinity, and non-integral-frame durations. | Exact zero frames and duration/timestamps for valid cases; `ValueError` and no output mutation for invalid cases. |
| AC-010 | Supply a mixed composition of MFSK32 text-file content, silence, compatible audio, and MFSK64 text–RGB-image–text. | One canonical mono PCM WAV in caller order; all top-level and nested indices are zero-based and complete; integer frame coordinates include confirmed RSID/acquisition intervals and agree with every returned second value and final duration. |
| AC-011 | Encode successfully to a new exact path and over an existing regular file whose parent already exists. | No alternate or temporary path is created; existing content is replaced only after preflight; `EncodeResult.output_path` equals the caller-supplied path. |
| AC-012 | Cause preflight failures with a missing input, malformed PNG/WAV, incompatible audio, invalid carrier/rate/mode/color/speed, oversized PNG, invalid dimensions, and predicted RIFF overflow while an existing output is present. | `ValueError` for invalid content/configuration or the original `OSError` subclass for filesystem failure; existing output bytes remain unchanged. Boundary arithmetic for the RIFF ceiling is tested without writing a multi-gigabyte fixture. |
| AC-013 | Inject a reported read, synthesis, or output-write failure after output writing has begun, both for a new path and a replaced path; separately inject output-removal failure. | With normal cleanup, handles close, the requested output is absent, the prior file is not restored, and the primary failure propagates. If removal itself fails, its `OSError` is raised from the primary failure and the residual path is reported. No temporary file exists. |
| AC-014 | Make output equal to or alias each input kind by identical spelling, relative/absolute spelling, symlink, and hard link. | Preflight rejects every existing-object alias and preserves all input bytes and any existing output. |
| AC-015 | Validate `L`, `RGB`, alpha, `tRNS`, palette, bilevel, 16-bit, non-PNG, zero dimension/malformed, 4095-by-4095, 4096-wide/high, 64-MiB, and over-64-MiB image boundaries. | Only the exact v1 profile passes; rejection never resizes, composites, applies color metadata, or opens the output. Large valid-image evidence records peak memory. |
| AC-016 | Validate classic PCM mono/16-bit/rate-matched nonempty WAV plus stereo, 8/24/32-bit, rate mismatch, float/compressed, extensible, RF64, empty, truncated, and partial-frame inputs. | Only the exact v1 audio profile passes; valid PCM bytes are unchanged; all incompatible content fails in preflight. |
| AC-017 | Exercise minimum/maximum supported sample rate, nonmultiples of 8000, numeric booleans, carrier lower/upper strict boundaries, and one-step-inside valid carriers for both modes. | Exact `ValueError` boundary behavior and frequency calculations; 48 kHz remains the operational qualification rate. |
| AC-018 | Encode long text-file, long audio, and long silence cases with chunk boundaries deliberately crossing Varicode, convolutional, PCM-copy, and sink-buffer boundaries. | Output is invariant to chunking; peak working memory follows fixed buffers plus one decoded image and result records, not duration or file length; measured time, memory, I/O, and predicted/output byte counts are recorded. |
| AC-019 | Install the built distribution in a clean Python 3.11+ environment and use the public API on macOS and Linux without GUI, audio device, modem subprocess, or network. | Pillow arrives as a core dependency; PNG and text/audio composition work; imports and decoder regressions pass. |
| AC-020 | Run the amended final 48-kHz candidate matrix through managed Pi execution and qualified receiver `fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`. | With RxID enabled, continuously play each whole mixed-mode WAV and recover the first and subsequent MFSK modes and their text/images without manual mode selection or window replay. Also retain exact pixels where artifacts permit, otherwise scoped candidate-set visual review; full hashes, identity, config, logs, and discrepancy classification. Manual-window replay is diagnostic only. |
| AC-021 | Run the complete existing decoder regression suite against the unchanged accepted decoder configuration. | No unexplained decoder/API regression; any changed score or artifact requires its own explicit evaluation rather than being absorbed into this feature. |
| AC-022 | Emit fldigi-compatible RSID for required MFSK32/MFSK64 acquisitions, including the first MFSK segment and mode changes in one WAV. | Independent, pinned-source RSID code and waveform vectors, exact guard/frame counts, and mutation rejection; the precise per-segment policy and API are confirmed in Session 6R0. |
| AC-023 | Exercise continuous whole-WAV RxID reception through adjacent modes, reversed mode order, repeated modes, and audio/silence before later MFSK. | Pinned fldigi automatically selects the expected mode and carrier at every required acquisition point; exact output duration and public timestamps include all generated intervals. |

## Acceptance and evaluation policy

The change remains investigative until all locally applicable cases pass and
the Session 8 independent qualification is complete. A successful GramPy
round trip cannot accept wire behavior. Product management makes the final
accept/reject/defer decision after reviewing exact vectors, mutation tests,
waveform measurements, local regressions, resource measurements, and fldigi
results. Only an accepted candidate may update the production baseline.

Target-Pi work is mandatory because final interoperability depends on the
pinned receiver and because packaging/runtime feasibility is a product
requirement. Mac-only evidence is not sufficient for this change.

## Session 0 closeout

1. **Learned or changed:** the published API shape is coherent, but its safe
   implementation required explicit preflight/alias rules, exact timestamp
   boundaries, exact image/audio forms, a classic-RIFF ceiling, and a runtime
   dependency decision. Those are now normative in the plan.
2. **Evidence produced:** this active record, the baseline identities above,
   and AC-001 through AC-021. No runtime evidence was generated.
3. **Decisions:** D-001 through D-009 are confirmed with the stated
   clarifications; D-012 selects Pillow as core; D-014 through D-016 were
   added. D-010, D-011, and D-013 remain open in their assigned sessions.
4. **Unresolved risks:** the wire spec still says review draft; local presence
   of the large frozen fixtures has not been established; the final encoder Pi
   matrix/workflow and artifact manifest do not yet exist; exact framing level
   and envelope, cross-part phase, and announcement whitespace remain open by
   design. The required definition restore-point commit awaits explicit
   authorization under repository instructions.
5. **Candidate state:** still investigative. No production candidate or
   production implementation exists.
6. **Session 1 entry condition:** first create the authorized definition
   restore-point commit, then use this record and the amended plan; inventory
   the frozen evidence; build an independent, mutation-sensitive offline
   harness; specify the final Pi matrix and manifest without running fldigi
   unless a concrete contradiction invokes D-009's exception.
7. **Fold recommendation:** keep Session 1 separate. Evidence availability is
   not yet established and the mutation-sensitive oracle requires independent
   reasoning; it is not plainly mechanical.

## Session 1 decision review

Session 1 required no change to the public API or wire profile. Its important
decisions concern only evidence independence and final qualification:

| Decision | Session 1 outcome | Rationale |
| --- | --- | --- |
| D-008 / D-017 | Confirmed as an encoder-independent, hash-bound test oracle with mandatory mutation rejection | A locally successful encoder or encoder-to-GramPy round trip could share a tone, timing, or raster-order error. The oracle therefore imports no encoder code and proves that representative defects fail. |
| D-009 / D-018 | Confirmed as a versioned 48-kHz matrix and manifest schema for the pinned Pi receiver | A fixed case list, explicit mode windows, artifact hashes, receiver configuration, and discrepancy classes make Session 8 reproducible without running fldigi during Session 1. |

The exact evidence convention and external procedure are documented in
`mfsk_wav_encoder_evidence.md`. The matrix is
`data/mfsk_encoder_pi_matrix_v1.json`, and its result contract is
`data/mfsk_encoder_pi_qualification_manifest_v1.schema.json`.

## Session 1 closeout

1. **Learned or changed:** the frozen local evidence is sufficient to make
   Varicode, FEC, interleaving, tone mapping, framing counts, picture tokens,
   prologue timing, raster order, and pixel frequencies executable without an
   encoder or live Pi. The correct transmitter Gray operation is the inverse
   direction of the published tone-to-label table; the all-16 oracle now locks
   that orientation. All four optional large controlled fixture sets are
   absent locally, with no hash mismatch.
2. **Evidence produced:** `tests/mfsk_encoder_evidence.py` and
   `tests/test_mfsk_encoder_evidence.py`; the evidence guide above; the Pi
   matrix and manifest schema under `docs/encoder/data/`; and a managed focused
   run of 10 tests, all passing. The suite proves rejection of deliberate tone,
   prologue/pixel timing, and pixel-interleaved RGB defects. Frozen reference-
   WAV measurements remain checked against the existing evidence document.
3. **Decisions:** D-017 and D-018 were added and confirmed. D-008 and D-009
   retain their Session 0 meaning. No production or API decision changed.
4. **Unresolved risks and discarded approaches:** the wire specification
   remains a review draft; optional large WAV/SigMF artifacts are unavailable
   on this Mac; and the reusable Pi qualification workflow must still be
   implemented before Session 8. The Session 1 closure commit awaits explicit
   authorization under the repository contract. Treating GramPy self-decode
   as an acceptance oracle and allowing an encoder candidate to generate
   expected values were rejected as coupled evidence. Pixel-interleaved RGB
   was retained only as a negative mutation.
5. **Candidate state:** still investigative. Session 1 changes evidence and
   documentation only; there is no production encoder candidate to accept.
6. **Session 2 entry condition:** first create the authorized Session 1
   evidence/closure checkpoint commit. Then use the hash-bound Session 1 oracle
   without importing it from production code; implement stateful byte-to-tone
   behavior for MFSK32 and MFSK64; pass every applicable frozen vector,
   all-16 Gray-map, chunk-equivalence, partial-group, and state-checkpoint test;
   and leave WAV synthesis, public API construction, and Pi execution out of
   scope.
7. **Fold recommendation:** no separate evidence investigation blocks Session
   2, so it may be folded into a subsequent authorized implementation session
   after the closure checkpoint. This Session 1 request stops at the offline
   harness boundary.

## Session 2 decision review

Commit `45b41dbd0720a18cdc78c7aec8af546795e4ddfd` (`Encoding session 1
complete`) satisfies the Session 2 entry condition. No evidence contradiction
requires a new investigation or early Pi work.

| Decision | Session 2 outcome | Rationale |
| --- | --- | --- |
| D-019 | Confirmed | The wire contract is a continuous Varicode/FEC/interleaver stream. Preserving state across chunks and caller text items, retaining a half-filled coded group, and avoiding implicit flush are required for chunk invariance and later text-picture transitions. D-003 already requires a fresh state for each independently framed segment. |
| D-020 | Confirmed | A complete immutable checkpoint makes chunk and restore equivalence testable without exposing a public persistence format. Thirty raw groups are the fixed history needed by the 0/10/20/30-group fldigi transmit delays. |

Session 2 remains below WAV synthesis and the public API. It fixes the logical
tone stream and mode parameters only; start/end framing, signal level,
envelope, phase, and sample boundaries remain assigned to Session 3.

Session 2 adds these candidate and evidence identities:

| Artifact | SHA-256 | Role |
| --- | --- | --- |
| `src/grampy/text_encode.py` | `a815c65ea303b789a3a058caa957da6d2b2f7ae84545dfe1640777704af6bed2` | Stateful byte/bit-to-physical-tone candidate and mode parameters |
| `tests/test_mfsk_encode_session2.py` | `bb765e64f56d353c1ab4c3328fe20f8a37b5f89903abb7b85755848a3b00df9c` | Exact vectors, chunking, partial-group, checkpoint, validation, and bounded-history evidence |

## Session 2 closeout

1. **Learned or changed:** a small NumPy-free component now maps authoritative
   bytes through the packaged 256-octet Varicode, rate-1/2 K=7 convolutional
   code, fldigi transmit-oriented 0/10/20/30-group interleaver, packed binary
   labels, and physical-tone mapping. MFSK32 and MFSK64 correctly share the
   logical tone sequence while exposing their distinct confirmed timing and
   bandwidth parameters.
2. **Evidence produced:** 13 new tests cover every Varicode octet, every frozen
   FEC vector, the complete short text-to-tone vector, all 16 tone labels,
   steady-state interleaving over all octets, every two-way byte split and
   representative repeated chunk sizes, repeated checkpoint restore, exact
   partial-group retention, malformed-state rejection, mode behavior, and a
   long-input 30-group memory bound. The focused encoder/oracle/wire/decoder
   set passed 42 tests. The managed full suite passed 192 tests with 6 skips
   for unavailable optional evidence.
3. **Decisions:** D-019 and D-020 were added and confirmed. No public API,
   framing, waveform, phase, or filesystem decision changed.
4. **Unresolved risks and discarded approaches:** D-010 and D-011 still block
   waveform work. Start/end framing, signal level, envelope, phase, sample
   rounding, and WAV output remain unimplemented. Reusing the decoder-oriented
   `StatefulPictureFlushEncoder` was rejected for this slice because it would
   couple the production encoder to diagnostic picture-flush semantics and
   NumPy-bearing decoder infrastructure; exact shared vectors instead guard
   the separate lightweight implementation. No Pi work was needed.
5. **Candidate state:** the Session 2 vertical slice is locally vector-correct
   and retained, while the overall encoder change remains investigative and
   changes no accepted production API behavior.
6. **Session 3 entry condition:** first create the authorized Session 2
   candidate/evidence closure commit. Then resolve and record D-010 and the
   MFSK portion of D-011 before implementing framing or PCM; use this stateful
   encoder for start, payload, termination, and flush; prove continuous phase,
   exact frames/frequencies/PCM, streaming WAV behavior, and a clearly labeled
   coupled GramPy round trip.
7. **Fold recommendation:** keep Session 3 separate. Synthesis is not yet a
   purely mechanical mapping because signal level/envelope and phase-reset
   rules are open important decisions requiring the higher-reasoning Session
   3 checkpoint.

## Session 3 decision review

Commit `4836bec079226735256232e78eeee3eadedfa47f` (`Encoding session 2
complete`) satisfies the Session 3 entry condition. The checked-in wire
specification and independent vectors agree on the complete stable framing
contract, so no early Pi exception is needed.

| Decision | Session 3 outcome | Rationale |
| --- | --- | --- |
| D-010 | Confirmed with the fldigi 4.2.12 visible start profile, a 16,384 PCM peak, and a frame-neutral 10 ms raised-cosine attack/release | The 4.2.12 leading zeros are the current pinned transmitter behavior and the receiver must already tolerate their absence in older senders. Half-scale PCM leaves deterministic headroom. A short in-symbol envelope suppresses segment-boundary clicks without changing framing duration or shaping any internal symbol transition. |
| D-011 | MFSK portion confirmed; audio/silence boundaries remain Session 6 work | A fresh zero-phase oscillator for each independently framed segment makes isolated output deterministic. Phase remains continuous across every tone transition within that segment, while the exact output-rate multiple makes every symbol boundary integral at all supported rates. |

The non-transmitted all-zero state priming described by fldigi is wire-
equivalent to the Session 2 encoder's zero-initialized convolutional and
interleaver state. In particular, it must not leave a half-filled symbol
accumulator before the visible leading zeros. The stable end contract is
`CR`/`EOT`/`CR` followed by one input bit of value one and the mode-specific
preamble count of zero bits; any final incomplete four-coded-bit group has no
wire representation and is discarded when the independently framed segment
ends.

Session 3 adds these candidate and evidence identities:

| Artifact | SHA-256 | Role |
| --- | --- | --- |
| `src/grampy/mfsk_encode.py` | `7378b93804fcb5e9e2ee3178f7e67c30273cf37bdaf005426a4deb93dbd1830a` | Framing planner/iterator, continuous-phase PCM synthesis, and canonical streaming WAV candidate |
| `tests/test_mfsk_encode_session3.py` | `3ee570d50bf8f80c67ab881ca1243de63ac1e0630ea800f142c40f80f78d12ec` | Independent framing, timing, phase, PCM, envelope, streaming, cleanup, and coupled round-trip evidence |

## Session 3 closeout

1. **Learned or changed:** the stable fldigi-compatible text frame can be
   synthesized without retaining a segment waveform or tone list. The
   Session 2 stateful encoder now feeds a one-symbol-lookahead synthesizer;
   that lookahead permits a release envelope on the final symbol while every
   PCM write remains at most one symbol. The WAV header is written and patched
   in place at the caller's exact path, with no temporary file.
2. **Evidence produced:** 13 new tests cover both modes against an independent
   complete-frame tone oracle, text-item and internal chunk invariance, exact
   logical content coordinates, all 24 supported sample rates in both modes,
   frequency span, integrated phase and a symbol-boundary PCM sample, exact
   initial PCM quantization, fixed peak/envelope behavior, one-symbol-bounded
   writes, canonical header and duration, validation-before-replacement,
   post-open write-failure cleanup, and coupled GramPy recovery of both text
   modes. The focused encoder/oracle/wire/decoder set passed 47 tests with one
   optional-fixture skip. The managed complete suite passed 205 tests with six
   skips for unavailable optional evidence. At the maximum supported rate the
   largest synthesizer write is exactly 12,288 PCM bytes (one MFSK32 symbol),
   independent of segment duration.
3. **Decisions:** D-010 is confirmed. The MFSK portion of D-011 is confirmed;
   phase behavior at audio and silence boundaries remains assigned to Session
   6. No public API or image-transition decision changed.
4. **Unresolved risks and discarded approaches:** pinned fldigi reception is
   intentionally deferred to the versioned Session 8 matrix, and the optional
   controlled WAV/SigMF fixtures remain absent on this Mac. Long-duration
   throughput and peak-memory qualification remain Session 7 work. The public
   composition API, image raster, picture transitions, copied audio, and
   silence are not implemented by this private slice. Adding envelope-only
   frames and resetting phase at internal symbols were rejected because both
   would change confirmed timing or continuous-phase wire behavior.
5. **Candidate state:** the Session 3 text-WAV slice is locally vector-correct
   and retained. The overall encoder change remains investigative and the
   private slice is not yet exported from `grampy.api`.
6. **Session 4 entry condition:** first create the authorized Session 3
   candidate/evidence closure commit. Then use the confirmed tone-span and
   sample-rate rules to implement exact `L`/`RGB` PNG normalization and
   isolated `p8`/`p4`/`p2` raster events, prove component order, frequencies,
   geometry, duration, and rejection/resource boundaries, and leave picture
   announcement whitespace and text-picture transitions for Session 5.
7. **Fold recommendation:** Session 4 may fold into the next authorized
   implementation session because image normalization and isolated raster
   events do not depend on the still-open announcement or top-level
   composition decisions. This request stops at the Session 3 boundary; its
   closure checkpoint commit awaits explicit authorization under the
   repository contract.

## Session 4 decision review

Commit `0d71e82` (`Encoding session 3 complete`) satisfies the Session 4 entry
condition. D-005 and D-012 already fix the input profile and required Pillow
dependency, and D-010/D-011 fix the carrier span and output-rate arithmetic.
No new public, wire-transition, or acceptance decision is needed for this
isolated raster slice.

| Decision | Session 4 outcome | Rationale |
| --- | --- | --- |
| D-005 / D-012 | Confirmed without amendment | Pillow decoded the exact mandatory 8-bit `L`/`RGB` PNG profile. `RGBA`, palette, non-PNG, transparency, and implicit conversion remain out of scope. |
| D-021 | Confirmed | Retaining one decoded source raster while lazily deriving grayscale or per-row RGB planes keeps raster event generation bounded by one image and one event. |

Session 4 adds these candidate and evidence identities:

| Artifact | SHA-256 | Role |
| --- | --- | --- |
| `src/grampy/picture_encode.py` | `a5312c8cfd2b216b68e80ca7c3382f8310288b7e078c9397b965e3ce1a639bd8` | Exact PNG normalization and a streaming isolated analog-raster plan. |
| `tests/test_mfsk_encode_session4.py` | `1ff97a266b551438d530e1d883969e46ffc7d0a4d75535caf98c4aca7d4b14d9` | Component-order, endpoint frequency, p8/p4/p2 timing, geometry, input-size, carrier-span, and RIFF-bound evidence. |

## Session 4 closeout

1. **Learned or changed:** a private picture component now admits only PNG
   `L` and `RGB` rasters within the exact v1 disk-size and geometry limits. It
   preserves an `L` source for grayscale or equal-RGB expansion, applies the
   specified integer RGB-to-gray formula, and serializes RGB as red, green,
   blue planes for each row. The plan emits one component event at a time with
   the exact normal-sideband frequency and output-frame duration.
2. **Evidence produced:** four focused Session 4 tests passed through the
   managed Mac runner. They cover `L`/`RGB` normalization, row order, the
   0/128/255 endpoint frequencies for both modes, p8/p4/p2 frame timings,
   4095/4096 geometry, alpha rejection, 64-MiB input rejection, invalid
   forms, carrier bounds, and an over-RIFF-limit raster plan. The managed full
   suite passed **209 tests** in 98.583 seconds with **6 expected skips**.
3. **Decisions:** D-021 was added and confirmed. D-005 and D-012 remain
   unchanged. D-013 remains open and is deliberately not inferred from this
   slice.
4. **Unresolved risks and discarded approaches:** this module intentionally
   does not generate the announcement, text flushes, 44-ms prologue, PCM, or
   post-picture flush; all remain Session 5 work. Building a pixel-interleaved
   color sequence, retaining three whole-image color planes, broad PNG
   conversion, or emitting a full event list were rejected because they would
   violate the wire order, v1 profile, or bounded-streaming aim. Pillow
   packaging metadata remains assigned to Session 7.
5. **Candidate state:** the isolated raster slice is locally vector-correct
   and retained; the overall encoder remains investigative and is not yet a
   public API candidate.
6. **Session 5 entry condition:** create the authorized Session 4
   candidate/evidence closure checkpoint. Then resolve D-013 before combining
   the confirmed text state with the picture announcement, header flush,
   44-ms low-endpoint prologue, raster, post-picture flush, and resumed text;
   prove ordered content boundaries and phase continuity without expanding the
   public composition API.
7. **Fold recommendation:** keep Session 5 separate. Its announcement
   whitespace and text-state reset/retention behavior are still important open
   integration decisions, rather than mechanical use of the isolated raster.

## Session 5 decision review

Commit `582b5d7` (`Encoding session 4 complete`) satisfies the Session 5 entry
condition. Product management confirmed the conventional fldigi announcement
and the source-derived transition behavior before implementation.

| Decision | Session 5 outcome | Rationale |
| --- | --- | --- |
| D-013 | Confirmed as `b"\nSending " + control_token`, with no generated bytes after the semicolon | The pinned controlled fixtures show fldigi inserting the leading line feed and `Sending ` before `Pic:`. The receiver scans for the complete `Pic:<width>x<height>...;` grammar; the prefix is conventional but the version-one API promises a generated `Sending Pic:` announcement. Omitting a trailing newline preserves immediate header-flush timing and leaves resumed caller text byte-exact. |
| D-022 | Confirmed as current-state header encoding and flush, phase-continuous prologue/raster, neutral post-picture flush, and unframed resumed text | These are observable fldigi wire requirements established by the pinned source comparison and controlled fixtures. A complete flush neutralizes convolutional and interleaver history, so replacing that drained private encoder with an equivalent fresh neutral state is permitted only as an output-invariant implementation detail. |

Session 5 remains a private complete-MFSK-segment slice. It does not add the
public composition API, copied audio, silence, or top-level boundary behavior
assigned to Session 6.

Session 5 adds these candidate and evidence identities:

| Artifact | SHA-256 | Role |
| --- | --- | --- |
| `src/grampy/mfsk_encode.py` | `18c52be08415c998db0f561d1a5b26c8ca51665c71d82dadcc5a819c46b77d07` | Continuous-phase streaming synthesis generalized from text symbols to picture prologue and raster frequency intervals without adding internal envelopes. |
| `src/grampy/picture_encode.py` | `e62c5101cfe1d0f7e1d78d2d2165439b57896a97f6b10b9e2afd96b8df426d84` | Exact control-token and conventional announcement construction over the Session 4 normalized raster. |
| `src/grampy/mfsk_segment_encode.py` | `1797119e3e1dc1340e3554406dd59be1959d3a05358f901aec4c1c404f3824bf` | Private ordered text/picture segment planner and WAV encoder with exact transition coordinates. |
| `tests/test_mfsk_encode_session5.py` | `23e737710f38d48bd8dbebecfd1f442691f6ca553f9cf8a0c9d00d9fee7c95bb` | Independent announcement, count, coordinate, ordering, phase, WAV, and coupled decoder evidence for Session 5. |

## Session 5 closeout

1. **Learned or changed:** one private complete-segment encoder now accepts an
   ordered snapshot of byte chunks and normalized pictures. It carries text
   state into each exact `LF`/`Sending Pic:` announcement, emits the fixed
   54-symbol MFSK32 or variable 90/91-symbol MFSK64 header flush, streams the 44 ms
   low-endpoint prologue and raster through the same oscillator, emits the
   fixed 54/90-symbol post-picture flush, and resumes byte text without new
   framing or generated whitespace. Planning records every caller-content
   start and every internal picture-transition frame coordinate.
2. **Evidence produced:** the independent Session 5 tests cover image-first,
   text-image-text, multiple-image, MFSK32, and MFSK64 layouts; exact
   announcement bytes; independently calculated symbol and frame counts;
   prologue/raster/post-flush adjacency; phase continuity across tone,
   prologue, raster, and resumed tone intervals; canonical WAV counts; and a
   coupled GramPy recovery of the header, picture, and resumed text. The
   focused managed set passed **45 tests** in 2.735 seconds. The managed full
   suite passed **214 tests** in 102.946 seconds with **6 expected skips**.
   The coupled two-component picture smoke test recovered values 0 and 249
   for transmitted 0 and 255 within its bounded estimator tolerance; exact
   event/frequency assertions, not that coupled estimate, remain the oracle.
3. **Decisions:** D-013 and D-022 were confirmed before implementation. No
   public API, top-level composition, audio, silence, or filesystem decision
   changed.
4. **Unresolved risks and discarded approaches:** pinned fldigi reception
   remains deferred to the final Session 8 matrix, and optional controlled
   waveform fixtures remain absent locally. Public `ImagePart` loading,
   `TextFilePart`, copied audio, silence, output aliases, and returned public
   timestamps remain Session 6 work. Resetting before the header flush,
   adding post-semicolon whitespace, inserting new framing after a picture,
   resetting oscillator phase, and materializing a complete raster-event list
   were rejected because they contradict confirmed wire behavior or bounded
   streaming.
5. **Candidate state:** the Session 5 complete-MFSK-segment slice is locally
   vector-correct and retained. The overall encoder remains investigative and
   the private slice is not exported from `grampy.api`.
6. **Session 6 entry condition:** first create the authorized Session 5
   candidate/evidence closure checkpoint. Then complete D-011 for MFSK,
   copied-audio, and silence boundaries before implementing the exact public
   composition API, filesystem preflight/replacement behavior, and public
   timestamps from these integer frame coordinates.
7. **Fold recommendation:** keep Session 6 separate. It introduces the public
   API and filesystem behavior and still requires an explicit decision for
   phase and sample behavior at generated-MFSK, copied-audio, and silence
   boundaries; it is not merely mechanical wrapping of this private slice.

## Session 6 decision review

Commit `9301677152225bbcb8413408903cc0c6712431c0` (`Encoding session 5
complete`) satisfies the closure-checkpoint entry condition. Its four recorded
Session 5 source and test artifact hashes match the checked-in files. The
untracked `.DS_Store` files are unrelated and are preserved.

Product management raised the decoder's historical need for spacing after
RSID and favored no implicit gap if this composition does not need one. The
RSID concern is distinct: version one emits no RSID, and its independently
framed MFSK parts carry their own start and end sequences. A gap alone cannot
announce a mode change to a receiver. The existing AC-004 contract already
requires adjacent MFSK32/MFSK64 with no implicit silence. The receiver must
select the relevant mode, and pinned fldigi reception of mixed boundaries
remains a final qualification gate rather than an assumption of success.

| Decision | Session 6 outcome | Rationale |
| --- | --- | --- |
| D-001 / D-015 / D-016 | Confirmed without amendment | The exact public types, preflight and replacement rules, and integer-frame timestamp semantics remain the Session 0 contract. |
| D-002 / D-003 / D-006 / D-007 | Confirmed without amendment | Mixed top-level parts remain caller ordered; modes use independent framing; compatible audio is copied; paths remain caller controlled. |
| D-011 | Confirmed for top-level MFSK, copied audio, and silence boundaries | Parts abut at exact frame coordinates with no implicit gap, overlap, or crossfade. MFSK oscillator state is local to each independently framed segment; audio PCM is copied unchanged; silence emits zero frames. This preserves caller-controlled duration and the already confirmed exact-audio and explicit-silence contract. |

Session 6 adds these candidate and evidence identities:

| Artifact | SHA-256 | Role |
| --- | --- | --- |
| `src/grampy/mfsk_compose.py` | `3e8361c7f5b03af5bfbac14981baabfe0b73f686e1110521ed0cf0a183933342` | Exact public composition types, preflight, audio inspection and copying, silence, frame timestamps, and output cleanup. |
| `src/grampy/mfsk_segment_encode.py` | `1a7cbe6584236ff1e0dcb71659d804ed18a8c82654930c04ffa10dc284537a28` | Bounded file-backed text and PNG sources for preflight and segment synthesis. |
| `src/grampy/picture_encode.py` | `def188575ba7064e8436516eca5971c79304ca0f46e207d27a04342b6c684845` | Malformed PNG decoder failures classified as invalid content while preserving filesystem errors. |
| `src/grampy/api.py` | `00d59716e58a78aa2ca1d3b00d7a101f168c7fd71f602bebdf5104b66c9a9928` | Public API exports alongside unchanged decoder exports. |
| `pyproject.toml` | `c718559cfbe0d995a7664fbe7eea9843f1e89425b4296dc99fe5e614d765169a` | Confirmed core Pillow dependency declared when public image support becomes importable. |
| `tests/test_mfsk_encode_session6.py` | `dc30e4b8a2e8d1fe90234526d899c0ecef7f191c1a3bc99273a8024055809303` | Public API, mixed content, adjacent mode recovery, exact PCM/timing, preflight, alias, replacement, and failure-path checks. |
| `docs/encoder/data/mfsk_encoder_pi_matrix_v1.json` | `949e471c80c5a06e7c9e2a4d368defa3c9033beab744b4e5404e0b28090b1e3b` | Final pinned-fldigi case for adjacent MFSK32/MFSK64 without an inserted gap. |
| `tests/test_mfsk_encoder_evidence.py` | `a7715cd2368405d44659b801d7c8ea698df3e249e3ef3a8b5fbccea34881798c` | Requires the new qualification case and both mode-specific receive windows. |

## Session 6 closeout

1. **Learned or changed:** `grampy.api` now exposes the exact version-one
   composition dataclasses and `encode_mfsk_wav`. The writer joins all top-level
   parts at integral frame boundaries, streams file text, normalizes images
   during preflight and writing, copies compatible WAV PCM without alteration,
   emits zero-valued silence, and returns segment/content start times from the
   planned frame coordinates. Preflight preserves an existing output; after
   writing begins, a reported failure removes the requested path unless that
   removal itself fails. Pillow is declared as a core dependency.
2. **Evidence produced:** the final managed focused encoder set passed **54
   tests** in 3.469 seconds. The managed complete suite passed **223 tests** in
   110.229 seconds with **6 expected skips**. The new Session 6 tests include
   exact adjacent-frame composition and coupled GramPy recovery of each mode
   from its declared window, raw text-file bytes, image content coordinates,
   ancillary-chunk audio copying, one-frame silence, output replacement,
   malformed input preflight, hard-link and symlink aliases, reported write
   failure cleanup, and removal-failure causality. An initial complete run
   exposed a matrix coverage test that listed all expected cases; it was
   updated for the newly added adjacent case before the passing full run.
3. **Decisions:** D-011 is complete for all top-level boundaries. D-001,
   D-002, D-003, D-006, D-007, D-015, and D-016 retain their confirmed
   contracts. The explicit no-gap qualification case was added to the final
   Pi matrix to test the decoder concern raised at session start.
4. **Unresolved risks and discarded approaches:** local GramPy recovery is
   coupled smoke evidence. Pinned fldigi recovery of the adjacent no-gap case
   and mixed audio/silence case remains Session 8 work. Version one emits no
   RSID, so automatic receiver mode changes are outside this candidate; the
   receiver must select each mode. Implicit silence and crossfading were
   rejected because they alter caller-controlled duration or copied PCM.
   Long-duration resource evidence and clean-environment package installation
   remain Session 7 work.
5. **Candidate state:** the public composition candidate is locally passing
   and remains investigative pending product acceptance and pinned external
   qualification. No commit was created because this request explicitly
   withheld commit authorization.
6. **Session 7 entry condition:** obtain product disposition and, if accepted,
   authorization for the Session 6 closure checkpoint commit. Then use this
   exact candidate to qualify long-duration memory, package installation,
   documentation, and the remaining failure/resource cases before Pi work.
7. **Fold recommendation:** keep Session 7 separate because its resource and
   packaging evidence can reveal deployment concerns not settled by this
   local functional session.

## Product correction after Session 6: whole-WAV fldigi acquisition

Product management clarified that fldigi compatibility includes automatic
MFSK32/MFSK64 mode acquisition while one mixed-mode WAV plays continuously.
The earlier Session 0 RSID exclusion and Session 6 assumption that manually
selected receiver windows suffice conflict with that outcome. Fldigi's
documented TxID/RxID facilities identify a transmitted mode when enabled, but
the Session 6 encoder does not emit RSID. The official fldigi
[RSID configuration manual](https://www.w1hkj.org/FldigiHelp/id_configuration_page.html)
documents its optional transmit and receive controls. The local 223-test result and
per-window GramPy recoveries remain valid evidence for the implemented
composition slice; they do not establish the corrected product requirement.

The Session 6 candidate is therefore **investigative and incomplete for the
corrected v1 outcome**. Its no-RSID `adjacent-modes-no-gap` Pi case remains a
diagnostic for the former slice and cannot qualify automatic mixed-mode
reception. The current Pi matrix has `rsid_enabled: false` and is marked
diagnostic-only, SHA-256
`84507885e1939b67197b96efe02ed86ed652eb1bd8249c399f2e6ffc3f57e43e`.
Session 6R0 must version a replacement before final qualification. The
Session 6 artifact hashes above describe the pre-correction local slice;
subsequent amendments must record their own candidate identities. No new
commit is authorized by this correction.

The remedial route is Session 6R0 (confirm exact RSID/API/timing behavior and
independent evidence), Session 6R1 (isolated RSID waveform), and Session 6R2
(composition and local acquisition), followed by the existing Session 7
hardening and Session 8 pinned fldigi qualification. Product management has
confirmed D-023's per-segment policy: automatically emit RSID before every
`MfskSegment`, including the first and repeated same-mode segments, without a
v1 caller opt-out or extra editorial gap. Session 6R0 subsequently verified
the exact wire sequence, guard timing, and frame-accounting contract against
the pinned fldigi v4.2.12 source already on the Pi. Isolated waveform
implementation remains Session 6R1, and continuous GramPy-candidate
reception remains Session 6R2/8. This correction supersedes the former
Session 7 entry condition in the Session 6 closeout.

## Session 6R1 closeout (2026-10-01)

1. **Scope and decisions:** confirmed the Session 6R0 oracle and D-011/D-023
   without new wire alternatives. Added only the private RSID prefix planner
   and sink writer, using immutable source-derived words, exact integer symbol
   frames, zero guards, and a separate oscillator with no MFSK envelope.
   Public composition, decoder behavior, corpus, and fixtures are unchanged.
2. **Candidate identity:** starting revision
   `a62214cf28eb0a7bd48997b938309fcafc93001b` plus
   `src/grampy/rsid_encode.py` (SHA-256
   `294a43e3ecc5047d3c8667bacdf812225c5ce0326c3c637ab2f047e5ce78c6e8`)
   and `tests/test_mfsk_encode_session6r1.py` (SHA-256
   `de31c4bbba2792d40c9fddb33a101b1f19bbeaf228e550ae30672fadef4b94a0`).
   The existing independent oracle remains unchanged.
3. **Evidence:** initial managed waveform/oracle run passed 8 tests in
   2.062 seconds. After adding the memory check, the managed encoder/evidence
   regression passed 60 tests in 6.132 seconds; frozen RSID oracle checks
   passed 3 tests in 0.016 seconds. Complete PCM equality covers both modes,
   multiple carriers, and sample-rate endpoints. All 24 rates pass exact frame
   and one-symbol write checks. Three maximum-rate extended prefixes remain
   below 256 KiB traced peak allocations. Tone, carrier, spacing, amplitude,
   phase-sample, and timing mutations disagree with the oracle. Preflight and
   sink failure checks pass. Both authoritative managed results report exit 0;
   completed session state was incorporated here and removed per AGENTS.md.
4. **Limits and disposition:** the isolated slice meets Session 6R1's local
   close condition. No public behavior is integrated and no commit is created.
   Native PCM agreement is independent of the receiver, but does not establish
   fldigi reception or platform feasibility. Pi evidence remains the planned
   whole-WAV candidate gate after integration, followed by resource hardening;
   no deployment acceptance is claimed by this isolated local result.
5. **Fold decision and next entry:** keep Session 6R2 separate because its
   composition accounting, timestamp shifts, and whole-file acquisition
   evidence are substantive. It may now integrate the passing private prefix
   before every MFSK segment, including empty text and same-mode repetitions,
   without introducing editorial silence. The full decoder regression was not
   rerun for this isolated module; encoder regressions pass and no decoder or
   active composer path changed.
