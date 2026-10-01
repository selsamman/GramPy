# Native MFSK WAV Encoder Project Plan

## Purpose

Build a supported GramPy API that composes MFSK32 and MFSK64 text and images,
existing audio, and explicit silence into an interoperable mono WAV file. The
encoder is native Python and has no fldigi runtime dependency. Pinned fldigi on
the Pi remains the final independent interoperability reference.

The requirements and public API are defined before implementation because they
state what the project is building. Detailed design is enriched session by
session. Each session begins by confirming the important design decisions it
needs and records newly confirmed decisions in this plan before implementation.

The plan follows `docs/operations/change-management-v1.md`. Sessions are
bounded work packets, not acceptance boundaries. At each closeout, decide
whether the next session still needs an independent reasoning context or has
become mechanical enough to fold into the current session.

The active definition, evidence baseline, acceptance cases, and session
closeouts are maintained in `docs/encoder/mfsk_wav_encoder_change.md`.

## Product requirements

### Functional requirements

The first supported release must:

1. Create one mono, 16-bit PCM WAV at an exact caller-supplied output path.
2. Compose an ordered sequence containing:
   - independently framed MFSK32 or MFSK64 segments;
   - existing compatible WAV audio; and
   - explicit periods of silence.
3. Allow each MFSK segment to select its own mode and carrier, so one output
   WAV may contain MFSK32 text, MFSK64 text and pictures, and non-MFSK audio.
4. Allow an MFSK segment to contain ordered byte text, byte text read from a
   file, and one or more images. Text may continue after each image.
5. Encode the documented fldigi-compatible Varicode, convolutional code,
   interleaver, Gray mapping, framing, continuous-phase tones, picture
   announcements, picture prologues, raster order, and post-picture flushes.
6. Support grayscale and RGB PNG input without resizing and picture speeds
   `p8`, `p4`, and `p2`.
7. Write incrementally so memory use is bounded independently of output WAV
   duration.
8. Return the start timestamp of every caller-supplied top-level segment and
   every caller-supplied item within an MFSK segment, plus the overall output
   duration. Internal framing and transition events are not returned.
9. Replace an existing output when encoding begins and remove the output path
   if encoding reports failure. The encoder does not create temporary files.
10. Give the caller complete control over every input path and the exact output
    path without platform-specific directory or storage assumptions.
11. Run on macOS and Linux without a GUI, sound device, subprocess modem, or
    network service.
12. Produce representative text and pictures that the pinned fldigi receiver
    on the Pi can recover during final qualification.

### Explicit exclusions

The first release does not include:

- live sound-device transmission;
- RF or channel simulation;
- bit-for-bit equality with a particular fldigi WAV;
- RSID generation;
- reverse-sideband transmission;
- automatic image resizing, alpha compositing, or editorial image processing;
- seamless modem changes inside one framed MFSK segment; or
- MFSK modes other than MFSK32 and MFSK64.

Mode changes are represented by adjacent, independently framed `MfskSegment`
objects. Callers insert `SilencePart` explicitly when they require spacing.

## Exact public Python API

The following is the required version-one API in `grampy.api`. Session 0 may
correct a contradiction discovered while baselining, but implementation must
not silently reshape this API. Later changes require an explicit requirements
amendment in this plan and product approval.

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence, Self, TypeAlias

MfskMode: TypeAlias = Literal["MFSK32", "MFSK64"]
PictureColor: TypeAlias = Literal["color", "grayscale"]
PictureSpeed: TypeAlias = Literal[2, 4, 8]


@dataclass(frozen=True)
class TextPart:
    data: bytes

    @classmethod
    def from_text(
        cls,
        text: str,
        *,
        encoding: str = "utf-8",
    ) -> Self: ...


@dataclass(frozen=True)
class TextFilePart:
    path: Path


@dataclass(frozen=True)
class ImagePart:
    path: Path
    color: PictureColor = "color"
    samples_per_pixel: PictureSpeed = 8


MfskPart: TypeAlias = TextPart | TextFilePart | ImagePart


@dataclass(frozen=True)
class MfskSegment:
    parts: Sequence[MfskPart]
    mode: MfskMode = "MFSK64"
    carrier_hz: float = 1500.0


@dataclass(frozen=True)
class AudioPart:
    path: Path


@dataclass(frozen=True)
class SilencePart:
    duration_seconds: float


OutputPart: TypeAlias = MfskSegment | AudioPart | SilencePart


@dataclass(frozen=True)
class EncodeConfig:
    sample_rate_hz: int = 48000


@dataclass(frozen=True)
class ContentStart:
    content_index: int
    start_seconds: float


@dataclass(frozen=True)
class SegmentStart:
    input_index: int
    start_seconds: float
    contents: tuple[ContentStart, ...]


@dataclass(frozen=True)
class EncodeResult:
    output_path: Path
    duration_seconds: float
    segments: tuple[SegmentStart, ...]


def encode_mfsk_wav(
    *,
    parts: Sequence[OutputPart],
    output_path: Path,
    config: EncodeConfig | None = None,
) -> EncodeResult: ...
```

### API semantics

- `parts` must be nonempty. An `MfskSegment` must also have nonempty `parts`.
- `TextPart.data` is the authoritative transmitted octet sequence. All 256
  byte values are accepted and mapped through the packaged MFSK Varicode table.
- `TextPart.from_text` performs strict `str.encode(encoding)`. It does not
  normalize newlines, replace characters, or add framing text.
- `TextFilePart` reads the named file as bytes without newline or character
  conversion.
- `ImagePart` accepts a PNG file. `color="color"` converts supported PNG color
  forms to RGB. `color="grayscale"` uses existing grayscale values or fldigi's
  documented 31% red, 61% green, and 8% blue integer conversion. Images with
  alpha or transparency are rejected rather than implicitly composited.
- Images retain their source dimensions and must satisfy the documented wire
  limits. The encoder never resizes them.
- Each `MfskSegment` emits a complete start, payload, and end sequence. An
  image causes the encoder to create its `Sending Pic:` announcement and all
  required transitions; callers do not supply the picture header themselves.
- `AudioPart` accepts mono, 16-bit PCM WAV with the same sample rate as the
  output. Version one does not resample, remix, normalize, or preserve source
  metadata chunks; incompatible audio is rejected.
- `SilencePart.duration_seconds` must map to an integral output frame count.
- `EncodeConfig.sample_rate_hz` must be a positive multiple of 8000. Carrier
  and picture frequencies must remain below Nyquist.
- Output is canonical mono signed 16-bit PCM WAV. The output parent directory
  must already exist.
- The exact `output_path` is opened for writing, replacing any existing file.
  If encoding raises an error, the encoder closes and removes `output_path`
  before propagating the error. It does not create temporary files and
  therefore does not require a temporary-file root in the API.
- Forced process termination, interpreter failure, or machine failure can
  interrupt cleanup and is outside the no-partial-file guarantee. The API
  guarantees cleanup for failures it reports to its caller.
- Invalid values or incompatible content raise `ValueError`; filesystem
  failures retain their normal `OSError` subclasses. Missing encoder image
  support reports a clear dependency error rather than substituting another
  image implementation.
- Every `SegmentStart` reports the start timestamp of the corresponding item
  in top-level `parts`; `input_index` is its zero-based index.
- For an `MfskSegment`, `contents` reports the start of every caller-supplied
  `TextPart`, `TextFilePart`, or `ImagePart`; `content_index` is its zero-based
  index in `MfskSegment.parts`. Audio and silence segments have empty
  `contents`.
- An image content timestamp is the start of its automatically generated
  picture announcement, because that is the first output attributable to the
  supplied image. Generated framing, flush, prologue, raster, and termination
  boundaries are intentionally not returned.
- Timestamps are seconds from the beginning of the completed WAV and are
  derived from exact internal frame coordinates.

The API uses caller-owned file paths for every file input and for the single
output. It neither selects a working directory nor relocates inputs or output.
This leaves storage, staging, cleanup, and hosting policy entirely to the API
consumer.

### Session 0 contract clarifications

Session 0 confirmed the public names, types, field order, defaults, and
function signature above without change. The following clarifications are
part of the version-one contract; they close ambiguities found during the
baseline review rather than add encoder features.

- The encoder snapshots the two caller-supplied `Sequence` objects at entry so
  later mutation cannot change the active composition. The dataclasses remain
  shallowly frozen; callers are responsible for not mutating referenced file
  contents during a call.
- Predictable validation is a preflight operation. An existing output is not
  touched when preflight reports an invalid value, incompatible input,
  unavailable input, output/input alias, or RIFF-size overflow. Once preflight
  succeeds and output writing begins, the exact output path is truncated or
  created. A subsequently reported failure removes that new path and does not
  restore a replaced file. If the removal operation itself fails for an
  external filesystem reason, its `OSError` is raised from the original
  failure and the residual path is reported; this is the sole reported-failure
  case in which path removal cannot be guaranteed.
- `output_path` must not identify the same filesystem object as any
  `TextFilePart`, `ImagePart`, or `AudioPart`, including through a symlink or
  hard link. This is rejected during preflight so opening the output cannot
  destroy an input.
- Empty `TextPart.data` and empty `TextFilePart` files are valid. They add no
  payload bytes but retain their logical content boundary. `AudioPart` must
  contain at least one complete audio frame. `SilencePart.duration_seconds`
  must be finite and strictly positive, and its product with the output sample
  rate must be an integer frame count. Numeric booleans are not accepted.
- Modes, colors, and speeds accept only the literal values in the API.
  `carrier_hz` must be finite, and the complete sixteen-tone span must be
  strictly above 0 Hz and strictly below Nyquist. This also bounds all picture
  frequencies.
- A text or text-file content timestamp is the output-frame coordinate at
  which its first octet is offered to the stateful text encoder. It is a
  logical boundary: adjacent empty items may share a timestamp, and encoder or
  interleaver history means it need not identify a uniquely attributable PCM
  sample. An image timestamp retains the already specified, audible boundary
  at the start of its generated announcement. An MFSK top-level timestamp is
  the first frame of that segment's start framing; audio and silence timestamps
  are their first copied or zero frame. The output duration is the final frame
  count divided by the sample rate. All returned seconds are computed once
  from these integer frame coordinates.
- `TextPart.from_text` retains normal strict `str.encode` errors, including
  `LookupError` for an unknown codec and `UnicodeEncodeError` for an
  unrepresentable character. Invalid encoder configuration or content is
  otherwise reported as `ValueError`; filesystem failures remain `OSError`
  subclasses.

### Session 0 supported forms and resource limits

Version one uses these exact input and container bounds:

- A PNG must decode as 8-bit `L` or 8-bit `RGB`, have no alpha or `tRNS`
  transparency, be at most 64 MiB on disk, and have width and height each in
  the inclusive range 1 through 4095. Palette, packed-bilevel, 16-bit,
  floating-point, and other PNG modes are rejected rather than silently
  converted. Gamma, ICC, and other editorial metadata do not transform sample
  values. For color output, `L` expands to equal RGB components. For grayscale
  output, `L` is unchanged and `RGB` becomes
  `(31 * R + 61 * G + 8 * B) // 100`.
- Pillow is a core runtime dependency of the distribution. PNG support is a
  required version-one capability, so an optional encoder extra would make
  the base public API only conditionally functional.
- An audio input must be a classic RIFF/WAVE file with format tag 1 (integer
  PCM), one channel, 16 bits per sample, the configured sample rate, at least
  one complete frame, and no truncated declared audio data. RF64,
  WAVE_FORMAT_EXTENSIBLE, compressed WAV, and malformed or partial frames are
  rejected. PCM frame bytes are copied unchanged; ancillary chunks are not.
- `sample_rate_hz` is an integer multiple of 8000 in the inclusive range 8000
  through 192,000. This is an explicit operational and resource ceiling, not
  merely the much larger arithmetic limit of a RIFF header. Final
  qualification uses 48,000 Hz.
- Output is classic 44-byte-header RIFF/WAVE PCM, not RF64. Its data chunk is
  limited to 4,294,967,258 bytes, or 2,147,483,629 mono frames, so the RIFF
  chunk size remains representable. Preflight rejects any composition whose
  exact predicted frame count exceeds that limit.
- There is no additional fixed byte limit for text, text files, audio, or the
  number of caller-supplied parts. Their aggregate encoded duration is bounded
  by the output-frame ceiling. Encoder working memory must be fixed-size for
  generated text, audio copying, and silence, plus one decoded image and the
  returned timestamp records. It may therefore scale with the largest allowed
  image and the number of caller-supplied items, but not with total WAV
  duration or audio/text-file length.

## Initial component design

This is the initial component boundary, not a complete design:

1. **Input inspection** validates the complete composition before writing.
2. **Composition sequencer** expands top-level MFSK, audio, and silence parts
   and expands each MFSK segment into framing, text, picture transitions, and
   termination events.
3. **Stateful text encoder** performs Varicode, convolutional coding,
   interleaving, Gray mapping, and tone selection without losing state at text
   or image boundaries.
4. **Picture encoder** loads and normalizes PNG pixels, constructs the picture
   announcement, and emits prologue and raster frequency-duration events.
5. **Continuous-phase synthesizer** converts MFSK tone and picture events to
   PCM while retaining phase within one MFSK segment.
6. **WAV composer** copies compatible audio, inserts silence, streams generated
   PCM directly to the exact requested path, records input start times, and
   removes that path after a reported failure.
7. **Evidence adapters** compare intermediate events with independent vectors,
   use GramPy's decoder as a development smoke test, and perform final pinned
   fldigi qualification on the Pi.

Private module names, helper classes, buffer sizes, vectorization strategy,
and internal event representation remain implementation details unless they
affect a public requirement, wire compatibility, resource bound, or acceptance
evidence.

## Design governance

### Important design decisions

A decision is important and must be confirmed at a session start when it can
affect any of the following:

- the public API or its semantics;
- emitted wire behavior or the chosen fldigi compatibility profile;
- state retention or reset across text, images, modes, audio, or files;
- frequency, timing, phase, signal level, or PCM conversion;
- output replacement and reported-failure cleanup behavior;
- memory, disk, or streaming bounds;
- runtime dependencies or supported platforms; or
- the validity or independence of acceptance evidence.

Examples of implementation details that do not require product confirmation
are private helper names, internal buffer sizes within an accepted bound,
equivalent NumPy versus scalar loops, local test-fixture organization, and
refactors that preserve the approved API, wire events, resources, and evidence.

### Session-start checkpoint

Before implementation in every session:

1. Read this plan, the active change record, relevant wire-spec sections, and
   the prior closeout.
2. List the important decisions required by that session.
3. Mark each decision **confirmed**, **provisional experiment**, or **blocked**.
4. Obtain product confirmation for new or changed important decisions.
5. Update the design-decision register in this plan before writing production
   code affected by the decision.

A session may investigate alternatives before confirmation, but it must keep
them in a sidecar or test-only form. It may not let a provisional experiment
silently become public behavior.

### Design-decision register

| ID | Decision | Status | Session responsible |
| --- | --- | --- | --- |
| D-001 | The version-one public API and filesystem semantics are those specified above, including the Session 0 preflight, alias, failure, and timestamp clarifications. | Confirmed with explicit clarifications | 0 |
| D-002 | One output may compose independent MFSK32/MFSK64 segments, compatible audio WAVs, and explicit silence. | Confirmed | 0 |
| D-003 | Mode changes use independently framed `MfskSegment` objects; no implicit RSID or seamless modem switch is emitted. | Confirmed | 0 |
| D-004 | Byte input is authoritative; string conversion is explicit strict encoding and file text is read as raw bytes. Empty byte items are permitted and normal strict codec errors are retained. | Confirmed with explicit clarifications | 0 |
| D-005 | PNG paths are the version-one image input; only the Session 0 `L`/`RGB` profile is accepted, alpha is rejected, and no resizing occurs. | Confirmed with narrowed input profile | 0 |
| D-006 | Existing audio must satisfy the Session 0 classic PCM profile at the output rate; GramPy performs no v1 audio conversion. | Confirmed with exact container profile | 0 |
| D-007 | GramPy uses only caller-supplied local input and output paths and makes no storage or platform directory choices. Output aliases of inputs are rejected. | Confirmed with safety clarification | 0 |
| D-008 | Routine development uses the checked-in independent vectors and frozen fixture evidence; GramPy decode is a smoke test, not independent acceptance. Session 1 must prove mutation sensitivity before the harness becomes an oracle. | Confirmed; harness coverage remains Session 1 work | 0–1 |
| D-009 | Pinned fldigi reception is consolidated into final Pi qualification, using qualified reference `fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`; an earlier targeted Pi experiment occurs only when a contradiction threatens the design. Controlled transmitter fixtures remain pinned separately to fldigi 4.2.12. | Confirmed with exact reference identity | 0–1 |
| D-010 | Exact fldigi start-framing profile, fixed generated-PCM signal level, and start/stop envelope. | Open | 3 |
| D-011 | Phase reset and sample-boundary rules between top-level composition parts. | Open | 3 and 6 |
| D-012 | Pillow is a core runtime dependency because PNG transmission is mandatory in the version-one API. | Confirmed | 0 |
| D-013 | Exact conventional whitespace surrounding the automatically generated picture announcement. | Open | 5 |
| D-014 | Version one uses the exact PNG, audio, sample-rate, classic-RIFF, and memory bounds in the Session 0 resource profile. | Confirmed | 0 |
| D-015 | Validation precedes output replacement; output/input aliases are rejected; after writing begins, a reported failure removes the new output and does not restore replaced content. | Confirmed | 0 |
| D-016 | Returned timestamp floats are derived from integer output-frame coordinates using the logical and audible boundaries defined in the Session 0 clarification. | Confirmed | 0 |
| D-017 | The offline encoder oracle remains test-only and independent of production encoder modules. It binds the frozen vector, Varicode, fixture-evidence, and RGB-source hashes; exact candidate events outrank coupled GramPy round trips; and tone, timing, and RGB-order mutation rejection is mandatory. | Confirmed | 1 |
| D-018 | Final interoperability uses the versioned 48-kHz Pi matrix and qualification-manifest schema under `docs/encoder/data/`, with explicit receiver-mode windows, complete artifact hashes, and discrepancy classification. The receiver remains `fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178`; no Pi run occurs in Session 1. | Confirmed | 1 and 8 |

New important decisions are appended to this table. Rejected alternatives and
their decisive evidence remain in the active change record so later sessions
do not unknowingly repeat them.

## Reasoning and session policy

Use **Sol with high reasoning** where a plausible local success can conceal a
protocol, state-machine, API, or interoperability error. Use **Terra with
medium or low reasoning** for bounded implementation after governing behavior
and the acceptance oracle are fixed.

Every session ends with:

1. what was learned or changed;
2. evidence produced and its location;
3. decisions added or changed in this plan;
4. unresolved risks and discarded approaches;
5. whether the candidate is accepted, rejected, or still investigative;
6. the exact entry condition for the next session; and
7. a recommendation to keep the next session separate or fold it in.

Do not spend a lower-reasoning session rediscovering an unsettled important
decision. Escalate it into a focused Sol investigation. Do not keep a
high-reasoning session open merely for mechanical cleanup.

## Validation strategy and fldigi placement

Running fldigi is operationally expensive because the qualified installation
is on the Pi and is not easy to automate. It is therefore not a gate for each
intermediate session.

Intermediate development uses three evidence layers:

1. independent checked-in Varicode, FEC, interleaver, framing, timing, picture,
   and tone vectors;
2. exact waveform measurements and mutation tests that prove the harness can
   reject known defects; and
3. GramPy decode as an end-to-end smoke test, explicitly treated as coupled
   evidence rather than independent proof.

Pinned fldigi reception occurs after the feature-complete local candidate is
stable. This minimizes Pi setup and transfer work and lets one qualification
matrix cover text, images, mixed modes, audio composition boundaries, and
return-to-text behavior. A targeted earlier Pi experiment is justified only
when local evidence contradicts the wire specification or when a decision
would otherwise force substantial architecture based on an unverified fldigi
behavior. That exception is approved and scoped at the relevant session start.

## Session plan

### Session 0 — Confirm requirements, API, and baseline

**Suggested model:** Sol, high reasoning.

Confirm what is being built before implementation.

Deliverables:

- an active change record naming the source revision, independent wire
  vectors, frozen fixture evidence, pinned fldigi reference, and Pi workflow;
- product confirmation or explicit amendment of every version-one API type,
  field, default, and semantic in this plan;
- confirmation of D-001 through D-009 and a decision on D-012;
- exact initial resource limits and supported image/audio forms;
- acceptance cases covering mixed MFSK32/MFSK64, text files, images, inserted
  audio, silence, exact output-path handling, and returned segment timing; and
- unresolved design questions assigned to later sessions.

Close when the requirements and API can serve as an implementation contract.
Do not design private classes or algorithms beyond what is necessary to expose
a contradiction in that contract.

**Fold decision:** Fold Session 1 only if all independent evidence is already
available locally and the harness work is plainly mechanical.

### Session 1 — Offline evidence harness

**Suggested model:** Sol, high reasoning.

Build an oracle that does not require a live Pi or accept self-decoding as
proof.

Deliverables:

- exact checks for Varicode, FEC, interleaving, tone indices, framing counts,
  picture headers, prologue timing, raster order, and pixel frequencies;
- frozen reference-WAV measurements where existing fixture evidence supports
  them;
- a proof that deliberate tone, timing, and RGB-order defects are rejected;
- a local GramPy round-trip smoke-test convention clearly labeled as coupled;
  and
- the final Pi/fldigi qualification matrix and artifact manifest format,
  without requiring fldigi to run in this session.

Close when Sessions 2–7 can make progress locally and Session 8 has a precise
external test procedure.

**Fold decision:** Fold Session 2 if no evidence gap needs a separate
investigation.

### Session 2 — Text-to-tone vertical slice

**Suggested model:** Terra, medium reasoning, with Sol review if state behavior
diverges from the vectors.

Implement byte text to physical tone indices without WAV synthesis.

Deliverables:

- stateful Varicode/FEC/interleaver/tone encoding;
- MFSK32 and MFSK64 parameters;
- exact tests against every applicable vector;
- chunk-boundary equivalence tests; and
- recorded partial-group and state-checkpoint behavior.

Close when tone sequences are deterministic and vector-correct.

**Fold decision:** Fold Session 3 if synthesis is a pure mapping from confirmed
frequency-duration events.

### Session 3 — Framed, continuous-phase text WAV

**Suggested model:** Sol, high reasoning for D-010 and D-011; Terra, medium
reasoning after those decisions are recorded.

Implement complete text-only MFSK segments and the streaming PCM sink.

Deliverables:

- confirmed D-010 and the MFSK portion of D-011;
- start framing, text payload, termination, and flush;
- phase-continuous synthesis at every supported output rate;
- a fixed, documented signal level and accepted start/stop envelope;
- streaming canonical WAV output; and
- duration, frame, frequency, phase, PCM, and local round-trip tests.

Close when text-only segments satisfy offline evidence and GramPy smoke tests.

**Fold decision:** Fold Session 4 if image normalization is independent of
unsettled transmitter state.

### Session 4 — Image input and raster slice

**Suggested model:** Terra, medium reasoning.

Implement PNG normalization and isolated picture raster events without the
text-to-picture transition.

Deliverables:

- confirmed PNG dependency and alpha-rejection behavior;
- grayscale and RGB normalization;
- row-major grayscale and per-row R/G/B plane serialization;
- `p8`, `p4`, and `p2` timing;
- exact frequency tests for component values 0, 128, and 255; and
- image duration, output-size, geometry, and resource validation.

Close when known images produce exact component order, frequency, and duration.

**Fold decision:** Fold Session 5 if picture-announcement whitespace and flush
state are the only remaining integration decisions.

### Session 5 — Picture transitions and ordered MFSK content

**Suggested model:** Sol, high reasoning.

Integrate text, generated picture announcements, flushes, the 44 ms prologue,
rasters, post-picture flushes, and resumed text.

Deliverables:

- confirmed D-013 and all state-reset/retention decisions;
- correct picture-header construction;
- phase continuity across text, prologue, raster, and resumed text;
- exact transition coordinates and symbol counts;
- image-first, text-image-text, multiple-image, MFSK32, and MFSK64 cases; and
- local GramPy recovery of the expected ordered content.

Close when a complete MFSK segment satisfies the offline evidence harness.

**Fold decision:** Fold Session 6 if top-level composition is now mechanical.

### Session 6 — Mixed-mode, audio, and silence composition

**Suggested model:** Sol, medium reasoning to confirm composition boundaries;
Terra, medium reasoning for implementation.

Complete the exact public composition API.

Deliverables:

- completed D-011 for all top-level part boundaries;
- adjacent independently framed MFSK32 and MFSK64 segments;
- exact copying of compatible `AudioPart` PCM;
- exact `SilencePart` frame generation;
- `TextFilePart`, exact input paths, and exact output-path behavior;
- replacement of an existing output and removal of the output after a
  reported failure, without temporary files;
- top-level `SegmentStart` timestamps for every input part;
- nested `ContentStart` timestamps for every caller-supplied MFSK content
  item, without exposing internal event timing; and
- `encode_mfsk_wav` conformance tests.

Close when every required public API form works locally without fldigi.

**Fold decision:** Fold Session 7 if packaging and resource tests require no
design changes.

### Session 7 — Packaging and local hardening

**Suggested model:** Terra, medium reasoning.

Make the feature-complete candidate repeatable and bounded before consuming Pi
qualification effort.

Deliverables:

- package exports and encoder dependency metadata;
- API documentation and executable examples;
- a thin CLI only if product management retains it in scope;
- bounded-memory evidence for long text, large images, audio, and silence;
- exact agreement between returned start timestamps and the completed WAV;
- reported interruption, disk failure, invalid input, no-partial-file, and
  existing-output replacement tests;
- full local encoder and decoder regression results; and
- the candidate WAV matrix and transfer manifest for Session 8.

Close when there are no known local failures and no open important design
decision that fldigi cannot answer directly.

**Fold decision:** Keep Session 8 separate unless Pi/fldigi execution is already
prepared and only requires launching the accepted matrix.

### Session 8 — Final Pi/fldigi interoperability qualification

**Suggested model:** Sol, high reasoning.

Use the Pi once the local candidate is feature-complete. Run all Pi work through
the repository-managed Pi wrapper and preserve authoritative result records.

Deliverables:

- pinned fldigi recovery of representative MFSK32 and MFSK64 text;
- grayscale and RGB recovery at every picture speed retained in the contract;
- text recovery after pictures and recovery across the selected mixed-mode
  composition cases;
- exact pixel comparisons where fldigi artifacts permit them;
- candidate-set visual review only where objective evidence cannot exclude a
  meaningful defect;
- hashes, configuration, fldigi identity, logs, and received artifacts; and
- classification of every discrepancy as implementation defect, reference
  behavior, harness issue, or unresolved risk.

Close when the external evidence supports acceptance or identifies a bounded
remediation. Do not normalize an unexplained discrepancy merely because the
GramPy decoder accepts the WAV.

**Fold decision:** If all cases pass, fold Session 9 into closeout. If not,
keep remediation separate so the original external evidence remains clear.

### Session 9 — Conditional interoperability remediation

**Suggested model:** Sol, high reasoning for diagnosis; Terra, medium reasoning
only after the corrective design decision is confirmed.

This session is skipped when Session 8 passes.

Deliverables when needed:

- a minimal explanation of each failed qualification case;
- an updated decision-register entry before production changes;
- focused candidate changes rather than broad decoder/encoder rewrites;
- local regression and mutation evidence; and
- rerun of the affected Pi/fldigi matrix followed by the required broader
  checks if the change could affect other cases.

Close when the candidate either qualifies or is explicitly rejected/deferred.

**Fold decision:** Fold Session 10 only after qualification evidence is final.

### Session 10 — Acceptance, integration, and closeout

**Suggested model:** Sol, high reasoning for acceptance; Terra, low or medium
reasoning for mechanical documentation cleanup after acceptance.

Deliverables:

- an explicit product acceptance decision against every requirement;
- final golden-vector, waveform, local regression, and fldigi evidence;
- measured time, peak memory, WAV size, and platform feasibility;
- durable API, architecture, validation, CLI-if-retained, and production
  baseline documentation;
- cleanup or deliberate preservation of investigation artifacts.

Close when accepted behavior can be maintained without using this plan as the
operational API guide.

## Optional follow-on changes

Treat each item as a new change request after the core encoder is accepted.

| Capability | Suggested reasoning | Why separate |
| --- | --- | --- |
| RSID generation and composition | Sol, high | Separate wire protocol and receiver-acquisition consequences |
| Reverse-sideband transmission | Sol, high | Documented behavior lacks accepted controlled-transmitter evidence |
| Live audio-device output | Sol, high initially | Real-time buffering and device behavior differ from file synthesis |
| Channel/noise simulation | Sol, high | Changes test meaning and requires independently justified models |
| Additional MFSK modes | Sol, high | Each mode requires parameters, vectors, and interoperability evidence |
| Audio resampling or remixing | Sol for contract; Terra for implementation | Introduces quality, clipping, filter, and duration semantics |
| Performance tuning | Terra, medium unless output changes | Optimize measured bottlenecks while preserving accepted behavior |

## Plan-level completion criteria

The core project is complete when:

1. the exact public API creates a canonical WAV at the exact output path from
   ordered MFSK32/MFSK64 segments, PNG pictures, compatible audio, and silence;
2. returned start timestamps for every supplied segment and MFSK content item
   exactly match the completed WAV timeline;
3. independent vectors validate bit, symbol, frequency, timing, framing, and
   raster transformations;
4. pinned fldigi independently recovers representative text, grayscale images,
   RGB images, and text after images;
5. mixed-mode and audio boundaries have explicit, tested semantics;
6. memory and disk use remain bounded and predictable;
7. a reported encoding failure removes the requested output, including when it
   replaced an existing file, and the encoder creates no temporary files;
8. the full decoder regression suite remains acceptable;
9. the API consumer controls all input paths and the exact output path without
   platform-specific directory assumptions; and
10. the accepted contract, limitations, and evidence are durable outside this
    project plan.
