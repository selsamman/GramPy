# Native MFSK WAV encoder active change record

**Change ID:** `mfsk-wav-encoder-v1`  
**Status:** active — definition complete; restore-point commit pending  
**Session 0 completed:** 2026-10-01  
**Accepted production behavior changed:** no

## Request and boundary

Build the native, streaming MFSK WAV encoder defined in
`mfsk_wav_encoder_plan.md`. The product outcome is one caller-directed mono
16-bit PCM WAV composed from independently framed MFSK32/MFSK64 content,
compatible audio, and explicit silence, with exact caller-content start times.
The encoder must interoperate with pinned fldigi and must not depend on fldigi
at runtime.

This record covers the full encoder change through acceptance and closeout.
Session 0 only defines the contract and acceptance cases. It deliberately
changes no production source, package metadata, tests, fixtures, or generated
artifacts.

Change Management v1 calls for a definition restore-point commit. Repository
instructions prohibit creating a commit without an explicit request, so that
checkpoint remains pending and is an entry condition for implementation work.

In scope and exclusions are the product requirements and explicit exclusions
in the plan. In particular, v1 excludes RSID, reverse-sideband transmission,
live sound output, channel simulation, image editing, audio conversion, and
additional MFSK modes. A CLI is not part of the confirmed v1 contract and
requires a later explicit scope decision.

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
part of Git. Session 1 must inventory them with the existing fixture tooling;
missing artifacts are an evidence gap to fill, not a reason to regenerate and
silently repin expected hashes.

The current Pi scripts generate transmitter fixtures or exercise historical
decoder paths. They do not constitute the encoder's final receive-
qualification matrix. Session 1 must specify that matrix and its artifact
manifest; before Session 8, a reusable checked-in `tools/pi-*.sh` workflow must
run it through `tools/pi-remote.sh` and record the pinned receiver identity,
configuration, input/output hashes, logs, recovered text, and images.

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

These are requirements-level cases. Sessions 1–7 must turn the applicable
cases into executable tests and evidence without weakening their oracles.
Session 8 supplies the independent fldigi outcomes. Exact wire assertions use
the frozen evidence above, not values generated by the candidate.

| ID | Case and input | Required evidence |
| --- | --- | --- |
| AC-001 | Import every specified encoder alias, dataclass, and function from `grampy.api`; inspect field order, frozen behavior, defaults, annotations, and keyword-only function signature. | Exact API-surface test; existing decoder exports remain available. |
| AC-002 | Encode all 256 possible octets, representative empty/nonempty `TextPart`s, strict UTF-8 text, a failing strict codec conversion, and an unknown codec. | Exact Varicode/FEC/interleaver/tone vectors where applicable; normal `str.encode` exceptions; no byte normalization or inserted text. |
| AC-003 | Read text files containing CRLF, lone CR, NUL, `0xff`, no final newline, and an empty file. | Transmitted octets exactly equal file bytes; file paths are caller-controlled; content boundaries follow the integer-frame rule. |
| AC-004 | Compose adjacent independently framed MFSK32 and MFSK64 text segments at different valid carriers. | Each has its own confirmed start/end framing and mode timing; no RSID or implicit silence; pinned fldigi recovers both in the qualification composition. |
| AC-005 | In both modes, encode an 8-bit `L` PNG as grayscale and color and an 8-bit `RGB` PNG as color and grayscale, including values 0, 128, and 255. | Exact dimensions, component bytes, grayscale floor arithmetic, row order, RGB row-plane order, frequencies, and duration. |
| AC-006 | Exercise grayscale and color pictures at `samples_per_pixel` 8, 4, and 2, retaining dimensions. | Exact announcement suffix, raster frame count, and pixel frequency/duration vectors; final Pi matrix recovers each retained speed. |
| AC-007 | Encode image-first, text-image-text, multiple-image, and text-after-final-image MFSK segments. | Announcement, flush, prologue, raster, post-picture flush, resumed text, and content timestamps occur in exact order; GramPy decode is labeled smoke evidence. |
| AC-008 | Insert a compatible audio WAV between generated MFSK and silence parts. Include ancillary source chunks. | Source PCM frame bytes appear unchanged at the exact returned start frame; output contains only canonical header/data; subsequent coordinates remain exact. |
| AC-009 | Insert positive silence values that map to integral frame counts, including one frame, and reject zero, negative, NaN, infinity, and non-integral-frame durations. | Exact zero frames and duration/timestamps for valid cases; `ValueError` and no output mutation for invalid cases. |
| AC-010 | Supply a mixed composition of MFSK32 text-file content, silence, compatible audio, and MFSK64 text–RGB-image–text. | One canonical mono PCM WAV in caller order; all top-level and nested indices are zero-based and complete; integer frame coordinates agree with every returned second value and final duration. |
| AC-011 | Encode successfully to a new exact path and over an existing regular file whose parent already exists. | No alternate or temporary path is created; existing content is replaced only after preflight; `EncodeResult.output_path` equals the caller-supplied path. |
| AC-012 | Cause preflight failures with a missing input, malformed PNG/WAV, incompatible audio, invalid carrier/rate/mode/color/speed, oversized PNG, invalid dimensions, and predicted RIFF overflow while an existing output is present. | `ValueError` for invalid content/configuration or the original `OSError` subclass for filesystem failure; existing output bytes remain unchanged. Boundary arithmetic for the RIFF ceiling is tested without writing a multi-gigabyte fixture. |
| AC-013 | Inject a reported read, synthesis, or output-write failure after output writing has begun, both for a new path and a replaced path; separately inject output-removal failure. | With normal cleanup, handles close, the requested output is absent, the prior file is not restored, and the primary failure propagates. If removal itself fails, its `OSError` is raised from the primary failure and the residual path is reported. No temporary file exists. |
| AC-014 | Make output equal to or alias each input kind by identical spelling, relative/absolute spelling, symlink, and hard link. | Preflight rejects every existing-object alias and preserves all input bytes and any existing output. |
| AC-015 | Validate `L`, `RGB`, alpha, `tRNS`, palette, bilevel, 16-bit, non-PNG, zero dimension/malformed, 4095-by-4095, 4096-wide/high, 64-MiB, and over-64-MiB image boundaries. | Only the exact v1 profile passes; rejection never resizes, composites, applies color metadata, or opens the output. Large valid-image evidence records peak memory. |
| AC-016 | Validate classic PCM mono/16-bit/rate-matched nonempty WAV plus stereo, 8/24/32-bit, rate mismatch, float/compressed, extensible, RF64, empty, truncated, and partial-frame inputs. | Only the exact v1 audio profile passes; valid PCM bytes are unchanged; all incompatible content fails in preflight. |
| AC-017 | Exercise minimum/maximum supported sample rate, nonmultiples of 8000, numeric booleans, carrier lower/upper strict boundaries, and one-step-inside valid carriers for both modes. | Exact `ValueError` boundary behavior and frequency calculations; 48 kHz remains the operational qualification rate. |
| AC-018 | Encode long text-file, long audio, and long silence cases with chunk boundaries deliberately crossing Varicode, convolutional, PCM-copy, and sink-buffer boundaries. | Output is invariant to chunking; peak working memory follows fixed buffers plus one decoded image and result records, not duration or file length; measured time, memory, I/O, and predicted/output byte counts are recorded. |
| AC-019 | Install the built distribution in a clean Python 3.11+ environment and use the public API on macOS and Linux without GUI, audio device, modem subprocess, or network. | Pillow arrives as a core dependency; PNG and text/audio composition work; imports and decoder regressions pass. |
| AC-020 | Run the final 48-kHz candidate matrix through managed Pi execution and qualified receiver `fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`. | Recovered MFSK32/MFSK64 text, grayscale/RGB images at p8/p4/p2, text after pictures, and selected mixed-mode boundaries; exact pixels where artifacts permit, otherwise scoped candidate-set visual review; full hashes, identity, config, logs, and discrepancy classification. |
| AC-021 | Run the complete existing decoder regression suite against the unchanged accepted decoder configuration. | No unexplained decoder/API regression; any changed score or artifact requires its own explicit evaluation rather than being absorbed into this feature. |

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
