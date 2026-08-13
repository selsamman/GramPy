# Direct MFSK IQ Decoder Implementation Specification

**Status:** Session 11D complete; selected P11D pipeline convergence next
**Protocol authority:** `mfsk_wire_spec.md`  
**Scope:** standalone decoding of MFSK32 text, MFSK64 text, and MFSK64
grayscale and color pictures from IQ

## 1. Purpose and product outcomes

This specification defines the capabilities, observable contracts, shared
evidence, and candidate implementation techniques required for a direct MFSK
decoder. Capability boundaries in this document are independently testable
boundaries, not a required sequence of runtime passes. A later design may fuse
work, share transforms, use bounded windows, revisit earlier hypotheses with
later evidence, or expose no intermediate files.

The standalone decoder must:

- recognize RSID-governed MFSK32 and MFSK64 segments;
- decode text octets compatibly with `mfsk_wire_spec.md`;
- recognize all specified picture-header forms and decode MFSK64 grayscale and
  color rasters at 2, 4, and 8 samples per component;
- preserve text-to-picture, picture-to-text, and inter-mode transition timing;
- retain original-IQ coordinates, uncertainty, and soft evidence needed for
  diagnosis and future multi-transmission alignment and voting;
- recover predictably from starts in progress, fades, dropouts, false RSIDs,
  damaged headers, and window boundaries;
- use offline look-ahead when it materially improves results;
- be faster than real time where practical, with runtime and peak memory
  measured on the development machine and target Pi before thresholds are set;
- admit a bounded-memory organization and a future streaming organization,
  without requiring the first implementation to stream; and
- coexist with the fldigi path until standalone real-corpus acceptance.

No unmeasured accuracy, runtime, or memory threshold is made normative here.
Methodology steps 3 and 4 must define candidate-pipeline benchmarks and then
set thresholds from representative full recordings. Correct protocol vectors,
coordinate traceability, deterministic output, and explicit degradation are
non-negotiable regardless of later thresholds.

## 2. External decoder contract

### 2.1 Invocation boundary

The decoder is initially a separate Python tool and package. Its logical
invocation consumes one SigMF recording or a requested interval and produces a
machine-readable manifest plus optional raster and trace artifacts. The CLI
shape and package names remain reversible until implementation phasing, but
the data semantics in this section do not.

The decoder must be deterministic for identical input bytes, metadata,
configuration, dependency versions, and floating-point architecture. The
manifest records those inputs and a schema version.

### 2.2 Accepted IQ

Required first-release input is a SigMF metadata/data pair with:

- complex samples in `ci16_le` or `cf32_le`;
- a finite, positive sample rate;
- byte length aligned to the declared datatype;
- at least one capture record sufficient to establish the requested interval;
  and
- normal frequency orientation unless metadata or an explicit option declares
  reverse orientation.

The design must not require 48 kHz, although corrected `ci16_le` at 48 kHz is
the current primary `iqprep` handoff. Other `iqprep`-supported complex types
(`cu8`, `ci8`, big-endian integer, and big-endian float) are desirable ingest
extensions and need not affect internal algorithms.

The authoritative time coordinate is the zero-based sample index in the
supplied IQ data file. Call it `input_sample`. An `iqprep` trim annotation may
map it to an earlier recording using:

```text
original_sample = input_sample + radiogram:trim_start_sample
```

That mapping is valid only for the immediate parent named by provenance.
Repeated derivations must retain an explicit ancestry chain rather than
overloading one “original” field.

`core:sample_rate`, datatype, capture frequency/time, trim information, RSID
detections, and center estimates are evidence. RSID mode, center, timing,
confidence, code distance, and correction flags are not unquestionable truth.
Missing optional annotations must reduce available priors, not make otherwise
valid IQ undecodable.

The tool accepts:

- a complete recording;
- a half-open interval `[start_sample, stop_sample)`; or
- bounded windows supplied by a caller.

A requested output interval may require history before its start and
look-ahead after its stop. The decoder must either obtain that context, restore
a compatible checkpoint, mark the affected output as warm-up/degraded, or
reject the request with the required context stated. It must never imply full
acquisition from an arbitrary hard cut.

Optional hints may identify expected channel, center, orientation, mode, RSID,
or schedule. Each hint is tagged `authoritative`, `prior`, or `diagnostic`.
Only an authoritative user constraint may suppress competing hypotheses.

Reject malformed JSON, unsupported datatype, non-finite values, impossible
sample ranges, inconsistent file length, non-positive rate, frequencies beyond
Nyquist in the declared coordinate, and contradictory authoritative options.
Warnings cover absent capture time, absent RF frequency, uncertain orientation,
ignored low-confidence annotations, and insufficient guard band.

### 2.3 Output manifest

The manifest contains:

- input identity and cryptographic hashes;
- decoder/schema version, configuration, dependency versions, and run timing;
- input and requested intervals;
- mode segments and competing hypotheses where ambiguity remains;
- text events, picture descriptors, image artifact references, and transitions;
- estimates and confidence summaries;
- warnings, recoverable errors, and terminal failure if any; and
- optional trace-artifact references.

All event intervals are half-open and use integer `input_sample` endpoints.
Derived coordinates may be included but never replace input coordinates.
Estimated point events use a central sample plus an uncertainty interval. A
wire-event estimate and the later recognition event are separate:

```text
wire_interval: evidence-bearing transmitted interval
recognized_at_input_sample: latest input sample consumed before emission
```

Text output is an ordered sequence of octet events, not only a Unicode string.
Each event includes the octet value, display rendering if any, control role
(`STX`, `EOT`, `CR`, `NUL`, or none), wire interval, recognition position,
confidence, damage flags, mode segment, and provenance links to decoded bits.
Unknown or invalid Varicode is an explicit event and does not collapse adjacent
valid boundaries. A convenience byte stream and human text rendering may also
be emitted.

A picture event includes parsed header text, width, height, color/grayscale,
samples per component, mode, header-completion recognition point, estimated
prologue interval, estimated first-raster sample, expected component count,
observed completion, raster artifact, component confidence/damage map, and
return-to-text reacquisition interval. Raster storage is `uint8`; color
artifacts use RGB display order even though evidence retains transmitted
row-plane order.

A mode segment includes mode, orientation, half-open interval, source
(`rsid`, signal inference, hint, or continuation), confidence, supporting
events, acquisition state, and superseded alternatives. Segment endpoints are
estimates with uncertainty; they must not be presented as exact RSID endpoints.

Confidence fields have declared meaning and scale. Implementations may use
log-likelihood ratios (LLRs), log likelihoods, or calibrated probabilities
internally, but the manifest states whether a value is calibrated. Arbitrary
“percent confidence” is forbidden. Erasure, clipping, dropout, interference,
and out-of-band conditions are separate flags rather than special confidence
numbers.

Detailed traces are optional because they can be large. When requested they
use a schema-versioned NPZ or equivalent array container plus JSON metadata,
and identify shapes, dtypes, units, coordinates, and any decimation. Summary
diagnostics remain in the manifest even when traces are disabled.

## 3. Coordinate, state, and shared-evidence model

### 3.1 Coordinates

Every block consumes or produces a `SampleMap`:

```text
output coordinate -> input_sample estimate, rounding rule, uncertainty
```

Trimming is an integer offset. Frequency translation preserves sample
coordinates. FIR filtering records group delay and valid/warm-up regions.
Rational resampling records its exact input/output rate ratio, phase origin,
filter delay, endpoint rule, and inverse rounding. Variable time correction
uses a monotone piecewise mapping. Approximate maps carry an error bound.

Intervals are half-open. A floating estimate is rounded to nearest, ties to
even, only for serialization; the unrounded estimate and uncertainty remain
available during analysis. A block must not compensate delay by shifting data
without also updating the map and valid interval.

Time has two forms:

- `recorded_time = input_sample / input_sample_rate`;
- `corrected_time`, if clock correction is applied, with its mapping back to
  recorded time.

Frequency fields name their frame:

- `rf_absolute_hz`;
- `input_baseband_hz`, in the supplied IQ orientation;
- `analysis_hz`, after translation/resampling;
- `carrier_relative_hz`; and
- `tone_index` or `picture_value`.

Positive input-baseband frequency means counterclockwise complex phase.
`orientation = normal` maps increasing physical frequency to increasing text
tone index and picture intensity; `reverse` maps it oppositely. Unknown
orientation requires competing hypotheses until evidence resolves it.

### 3.2 Shared evidence records

Candidate organizations must preserve these logical records, though they may
be views, in-memory arrays, recomputable caches, or fused state:

- `RegionEvidence`: input interval, signal/noise statistics, occupied band,
  clipping/dropout/interference flags;
- `ModeHypothesis`: mode, orientation, interval distribution, prior, evidence,
  and status;
- `FrequencyTrack`: carrier estimates, uncertainty, discontinuities, source,
  and sample map;
- `ClockTrack`: nominal rate, phase, rate error, uncertainty, lock state, and
  discontinuities;
- `ToneEvidence`: one row per candidate symbol and one column per 16 tones,
  expressed as comparable log metrics, plus phase/time/frequency hypotheses;
- `BitEvidence`: coded-bit LLRs in the fldigi wire lane order, without
  discarding the supporting tone row;
- `FecEvidence`: deinterleaved inputs, survivor/path metrics, traceback
  decisions, decoded-bit confidence, and reset hypothesis;
- `TextEvidence`: Varicode boundary hypotheses, octets, invalid spans, and
  provenance;
- `TransitionHypothesis`: header, predicted prologue/raster ranges, alignment
  alternatives, and score;
- `RasterEvidence`: component estimates before clipping, `uint8` values,
  timing residuals, per-component quality, and source intervals; and
- `StateCheckpoint`: mode hypotheses, filter/tracker state, symbol phase,
  deinterleaver state, FEC survivor state, Varicode state, coordinator state,
  configuration identity, and preceding valid interval.

The minimum normal text boundary is `ToneEvidence`, not hard tone indices.
Tone-to-bit conversion retains `BitEvidence`; deinterleaving and Viterbi retain
soft values. Hard decisions may be diagnostic views. The minimum picture
boundary retains discriminator/correlation estimates before quantization and a
quality value per component.

Checkpoints are immutable, versioned, and restorable only with identical
signal transforms, mode profile, coordinate mapping, and decoder configuration.
A checkpoint states how much prior IQ it summarizes and what look-ahead was
used, preventing a non-causal checkpoint from masquerading as streaming state.

### 3.3 State and resets

State scopes are explicit:

- recording scope: provenance, sample map, global noise and candidate regions;
- mode-segment scope: orientation, mode profile, carrier/clock tracks;
- text epoch: symbol phase, interleaver, Viterbi, and Varicode state;
- picture epoch: descriptor, raster clock, component and line position; and
- acquisition hypothesis: alternative initial states retained temporarily.

An accepted RSID starts a mode-segment hypothesis; it does not prove the exact
first text symbol. Text startup may consider reset, steady-state, and
mid-transmission hypotheses. A mode change, confirmed picture transition, or
explicit discontinuity closes incompatible state. A dropout degrades lock
before it resets it. Reacquisition emits a discontinuity and keeps prior output
provenance intact.

## 4. Capability and candidate-block contracts

The numbered capabilities below cover the initial inventory in the authoring
guidelines, with closely coupled items grouped into candidate blocks. Each
block may later be split or fused.

### C1. Ingest, validate, normalize, and map coordinates

**Contract.** Consume the external input contract and requested interval.
Produce complex working samples or a lazy sample source, `SampleMap`, amplitude
scale information, valid regions, and structured warnings. Retain datatype,
clipping counts, non-finite counts, discontinuities, metadata ancestry, and
raw hashes.

**State/context.** Chunk conversion is stateless except for discontinuity
detection. Filtering/resampling state and overlap are explicit. Requested cuts
retain caller-visible and context intervals.

**Techniques.** NumPy memory mapping and vectorized datatype conversion are the
baseline. Normalize integer full scale to floating values without automatic
per-block AGC. Rational polyphase resampling (`scipy.signal.resample_poly`) is
a candidate only when a selected detector benefits enough to justify SciPy;
original-rate phase evaluation is an alternative.

**Failure/testing.** Exact fixtures cover endian/type conversion, clipping,
truncated files, metadata contradictions, chunk equivalence, resampler delay,
and coordinate round trips. Complexity is O(samples), with bounded memory.

### C2. Detect candidate signal regions

**Contract.** Produce `RegionEvidence` without deleting quiet or damaged
intervals inside an active mode segment. Regions are proposals, not trims.
Report detection latency, threshold basis, guard context, and missed/merged
region risk.

**Techniques.** Band-energy/noise-floor tracking, spectral flatness, MFSK comb
structure, and RSID priors are candidates. A coarse STFT can be shared with
carrier search. Hysteresis and minimum-duration logic are required. Existing
`iqprep` activity/noise work is reusable evidence but its trim decision is not
a decoder boundary.

**State/testing.** Retain noise history and hysteresis across chunks. Test
silence, adjacent stations, weak starts, internal fades, images whose
brightness biases frequency occupancy, and boundary splits. False-negative
cost is higher than extra candidate data.

### C3. Detect RSID and manage mode segmentation

**Contract.** Consume IQ/region evidence and optional SigMF RSID annotations.
Produce ranked `ModeHypothesis` events for MFSK32 primary code 147 and MFSK64
escape 6 plus secondary 620, including tone sequence, code distance, center,
orientation, event interval, uncertainty, and confidence. Validate the
escape/gap/secondary state sequence; do not switch on one suggestive spectrum.

**Techniques.** Adapt the validated bounded-block `iqprep` RSID detector and
its rational-resampling phase discipline. Reuse results where configuration
and interval match; otherwise annotations become priors. Joint re-evaluation
near uncertain transitions and schedule-informed priors are allowed.

**State/testing.** State includes pending escape, allowed secondary interval,
deduplication, and competing orientation. Context must cover the full primary
or escape/gap/secondary sequence plus detector filter history. Fixed RSID
vectors, synthetic timing/frequency/block cases, and the existing real MFSK64
escape regression are required.

### C4. Estimate band, carrier, orientation, and frequency drift

**Contract.** Produce occupied-band estimates and one or more
`FrequencyTrack`s with uncertainty and breakpoints. Support coarse acquisition,
fine residual estimation, and tracking; never overwrite the `iqprep` estimate.
Expose whether correction is represented as an explicit frequency-translated
sample view or only as a carrier-relative model.

**Techniques.** Candidates include shared STFT/comb fitting, RSID anchors,
tone-grid maximum likelihood, phase-increment estimates on stable tones,
robust polynomial/piecewise fits, and a low-bandwidth tracker. Picture
brightness must not be mistaken for carrier drift; during raster reception the
carrier prior should be held, jointly inferred from known mapping/range, or
updated only with defensible evidence. Existing `iqprep` center curves and
break handling are starting points.

**State/testing.** Preserve alternative tracks around discontinuities.
Required context depends on smoothing; non-causal fits state look-ahead.
Tests control offset, nonlinear drift, steps, reverse orientation,
interference, and biased image content. Metrics include residual error as a
fraction of tone spacing and calibration of reported uncertainty.

### C5. Isolate or translate the channel

**Contract.** Provide either an analysis-sample view or filter response/model
used by downstream likelihood calculations. Record passband, guard band,
stopband behavior, delay, transient regions, amplitude/phase response, and
coordinate map. Do not discard nearby evidence needed for re-centering.

**Techniques.** Complex mixing plus FIR, overlap-save FFT filtering, shared
polyphase channelization, or implicit frequency selection in correlators are
candidates. A materialized corrected-IQ file is optional, not required.

**Failure/testing.** Test adjacent interferers, insufficient Nyquist guard,
carrier-track errors, block equivalence, and phase continuity. FIR/FFT choices
are O(NK) or O(N log N), vectorizable, and bounded-window compatible.

### C6. Acquire and track symbol clock

**Contract.** Produce `ClockTrack` and candidate symbol observation intervals
in input coordinates. Each symbol has phase/rate uncertainty and lock state.
Acquisition must work after RSID, from a mid-stream cut, and after a dropout.

**Techniques.** Candidates include evaluating tone concentration over a grid of
symbol phases, maximizing transition-consistent likelihood, early/late timing
error, clock-rate search, and offline dynamic refinement. Resampling to an
integer samples/symbol is optional; direct phase evaluation avoids a permanent
resampled coordinate. Carrier and clock may be estimated jointly where their
likelihoods couple.

**State/testing.** Retain loop/search state, nominal mode rate, phase, rate
error, and lock history. Look-ahead is at least several symbols for robust
acquisition and must be measured experimentally. Synthetic cases cover every
phase, sample-clock error, slow rate change, no transitions, fades, and chunk
boundaries; real cases validate reacquisition.

### C7. Observe tones and produce soft symbol evidence

**Contract.** For every candidate text symbol, produce a 16-element
`ToneEvidence` log-metric vector in ascending logical tone order, plus noise
estimate, winning/runner-up tone, margin, normalization, and source interval.
Metrics from different symbols must be comparable or explicitly locally
normalized.

**Techniques.** Candidate estimators are FFT filter bank, matched complex
correlators, Goertzel bank, sliding DFT, and a batched matrix of oscillators.
They must evaluate the rectangular, orthogonal symbol model while tolerating
residual offset and clock uncertainty. Local searches may marginalize or
maximize across nearby carrier/phase hypotheses. Reuse transforms from C2/C4
where their resolution/window is sufficient.

**State/testing.** Filter history and oscillator phase cross chunk boundaries;
input phase continuity is observed, not regenerated. Exact tones test bin
ordering and reverse mapping. Narrow synthetic IQ controls phase, offset,
noise, fades, dropouts, adjacent tones, interference, and boundaries. Compare
candidate runtime, allocations, likelihood separation, and robustness before
selecting one. Avoiding SciPy here is preferred unless benchmarks show a clear
benefit.

### C8. Map tones to coded-bit soft evidence

**Contract.** Map each 16-tone metric row through the wire-spec Gray labels to
four coded-bit LLRs in transmitted lane order. For bit value `b`, a baseline
LLR is the log-sum-exp of tone metrics labeled 1 minus that for tones labeled
0. Preserve the tone row and allow max-log as a measured approximation.
Reverse orientation is resolved before logical labeling or represented as a
separate hypothesis.

Hard tone and bit decisions are diagnostics only. Erasures produce near-zero
LLRs with an erasure flag, not invented bits.

**Testing.** All 16 fixed mapping vectors, ties, scale offsets, extreme metrics,
and reverse orientation are exact tests. O(16) work per symbol is vectorizable
and stateless.

### C9. Deinterleave soft coded bits

**Contract.** Consume groups of four coded-bit LLRs and apply the inverse of
fldigi’s transmitted four-lane, depth-ten transformation. Produce serialized
soft coded bits with coordinate provenance spanning their dispersed source
symbols. Initial storage is neutral LLR zero, not hard zero.

**State/context.** The exact ten-stage state, group phase, fill validity, and
provenance are checkpointed. Startup output affected by neutral fill is marked.
Mid-stream acquisition may run multiple group-phase/state hypotheses until FEC
evidence resolves them. Reset only at a justified text epoch.

**Testing.** `mfsk_wire_vectors.json` is authoritative, especially the fldigi
orientation and `MJGD` example. Tests cover impulses per lane, neutral fill,
steady state, arbitrary splits, checkpoint restore, and erasures. Complexity
and storage are constant.

### C10. Recover convolutionally coded bits

**Contract.** Consume paired coded-bit LLRs in `c0`, `c1` order and decode the
rate-1/2, K=7 code defined by masks `0x6d`, `0x4f`. Produce decoded-bit
likelihood/confidence, survivor/path diagnostics, traceback provenance, and
ambiguity/damage flags. Support known-zero reset and unknown/mid-stream initial
state hypotheses.

**Techniques.** A 64-state soft-input Viterbi decoder is the baseline.
Traceback depth, normalized path metrics, terminated versus continuous
operation, forward/backward offline refinement, and confidence from survivor
separation or max-log-MAP are decision points. A NumPy-vectorized state update
should be compared with compiled/library options before adding a dependency.

**State/testing.** Checkpoint 64 path metrics and sufficient survivor history.
Streaming emits only after bounded traceback; offline decoding may revise an
uncommitted tail. Fixed encoder and soft-input vectors cover reset, erasures,
ties, burst damage, lane reversal failures, chunks, and exact tracebacks.
Complexity is O(64) per decoded bit; survivor memory is proportional to
traceback or analyzed window.

### C11. Detect Varicode boundaries and recover octets

**Contract.** Consume decoded bits with provenance and confidence, recognize
the `001` look-ahead boundary rule, remove the next-character look-ahead bit,
and map terminated codewords through `mfsk_varicode.json`. Produce octet,
invalid-codeword, and boundary events. Preserve control octets and do not
prematurely convert extended values to text.

**State/context.** Retain the current codeword bits, provenance, alternatives
near weak bits, and maximum defensible codeword length. A valid later boundary
resynchronizes after an invalid code. Reset occurs only with a new text epoch,
not at line breaks.

**Techniques/testing.** A deterministic parser is the baseline; limited
multi-hypothesis parsing around low-confidence bits is an offline refinement
candidate. All 256 table entries, `e space t`, control characters, long zero
runs, invalid words, bit flips, cut boundaries, and recovery at the next valid
boundary are exact tests. Work is O(bits).

### C12. Frame text and recognize picture headers

**Contract.** Build presentation text without losing octets, identify
CR/STX/EOT/NUL roles, and scan recovered octets for the exact wire-spec picture
grammar:

```text
Pic:<width>x<height>;
Pic:<width>x<height>C;
Pic:<width>x<height>p<samples-per-pixel>;
Pic:<width>x<height>Cp<samples-per-pixel>;
```

Accept dimensions 1–4095 and speeds 2, 4, or 8; absent speed means 8. The
`Sending ` prefix is not required. Produce a descriptor only on a complete,
valid token, retaining all contributing octet evidence and alternatives.

**State/testing.** A rolling octet window crosses chunks and damaged text.
Reject overflow, zero dimensions, unsupported speed, malformed or
low-confidence speculative headers without entering picture state. Tests cover
all grammar forms, split tokens, embedded `Pic:`, corrupted characters,
controls, and the fixed fixture headers.

### C13. Align the text-to-picture transition

**Contract.** Given a picture descriptor, mode profile, text/FEC state, and IQ,
produce ranked `TransitionHypothesis` values for prologue start and first
raster sample. Distinguish logical semicolon recovery from transmitted header
evidence and receiver recognition latency. Account for the MFSK32 1.728 s
flush, MFSK64 1.440/1.456 s alternatives, and 44 ms low-endpoint prologue as
wire behavior, while estimating actual boundaries from IQ.

**Techniques.** Predict from decoded symbol/group state, correlate for the
44 ms low-frequency prologue, inspect tone-to-continuous-raster change, and use
offline joint scoring. Do not copy fldigi’s receiver delay constant as a wire
duration. Limited alternative alignment should survive until raster evidence
separates it.

**State/testing.** Preserve partial four-bit accumulator/group phase and all
header provenance. Context begins before the header flush and extends through
enough raster to score alignment. Controlled MFSK64 color/grayscale fixtures
provide exact first-raster evidence; synthetic offsets, fades, and block cuts
test robustness.

### C14. Estimate picture frequency, intensity, and component clock

**Contract.** For each expected component interval, estimate
carrier-relative frequency and uncertainty, map it using:

```text
v_unclipped = 128 + 256 * offset_hz / bandwidth_hz
```

with sign reversed for reverse orientation, then report unclipped value,
rounding, clipped `uint8`, timing residual, quality, and input interval.
Bandwidth is 468.75 Hz for MFSK32 and 937.5 Hz for MFSK64. Component durations
are 2, 4, or 8 samples at the 8000 Hz wire reference, not necessarily integer
input samples.

**Techniques.** Candidates include phase-difference instantaneous frequency
with robust aggregation, short matched correlations over candidate values,
phase-slope regression, and joint carrier/pixel-clock fitting. A raster timing
tracker may use phase continuity and known component duration. The design must
measure bias/variance at very short p2 intervals before selecting a method.

**State/testing.** Preserve discriminator/filter history, fractional component
phase, clock-rate error, carrier prior, and alternative start alignment.
Synthetic IQ covers all values, endpoints, arbitrary phase, clock error,
noise, fades, dropouts, and boundaries. Controlled known images test mapping
and timing. Complexity should be O(samples) or a small fixed candidate factor;
full per-pixel Python loops are unacceptable without benchmark evidence.

### C15. Assemble grayscale and color rasters

**Contract.** Consume exactly `width × height` grayscale components or
`width × height × 3` color components. Map grayscale row-major. Map color as
red row, green row, blue row for each image row, then expose RGB raster order.
Produce a component confidence/damage plane and geometry/timing diagnostics.

**State/recovery.** Track component, column, row, and transmitted color plane.
Do not shift subsequent pixels silently when one component is damaged; expected
clock position determines raster index and damaged components become marked
erasures/estimates. Reject impossible allocation before entering picture mode.

**Testing.** Fixed 8×4 primary-color and grayscale vectors establish order,
endpoints, duration, and dimensions. Tests cover one-pixel images, each speed,
missing/damaged intervals, chunk splits, and allocation limits. Memory is
O(pixels) for final output; traces may be streamed or decimated.

### C16. Complete pictures and reacquire text

**Contract.** End raster reception by component count, not a delimiter.
Describe the following post-picture text flush (1.728 s MFSK32 or 1.440 s
MFSK64) as a reacquisition interval, rebuild text epoch state, and emit the
estimated first trustworthy resumed-text position. Do not require silence.

**Techniques.** Initialize neutral deinterleaver/FEC state at the known
boundary, search symbol/group phase through the flush, and use later Varicode
validity for non-causal refinement. Preserve alternative timing if raster
clock accumulation makes the endpoint uncertain.

**Testing.** Controlled fixtures and full transmissions cover immediate queued
text, idle behavior, fades at completion, component-clock error, and window
cuts. Output during warm-up is marked rather than silently trusted.

### C17. Reset, resynchronize, and recover after damage

**Contract.** A coordinator applies explicit state transitions among searching,
text acquisition, locked text, proposed picture, raster, post-picture
reacquisition, and lost. Every reset records cause, affected interval, retained
evidence, and discarded state. It may maintain a bounded number of hypotheses.

**Techniques.** Lock-quality hysteresis, checkpoint rollback, localized
non-causal re-decode, and limited beam search are candidates. Damage must first
weaken likelihoods/produce erasures; hard reset is reserved for sustained loss,
confirmed mode change, impossible state, or user boundary.

**Testing.** Inject fades, impulsive and same-tone interference, sample
dropouts, center steps, false RSIDs, invalid headers, and state-boundary cuts.
Verify deterministic recovery and no coordinate discontinuity.

### C18. Propagate confidence and support repeated transmissions

**Contract.** Preserve evidence at symbol, coded-bit, decoded-bit, octet, and
picture-component levels with source intervals. Emit alignment landmarks:
RSID events, mode boundaries, text octets/control characters, picture headers,
raster rows, and damage intervals. Assign stable event IDs within a run.

The first decoder need not perform voting. It must make later voting possible
without rereading only rendered text/images: retain calibrated or at least
monotonic soft evidence, clock/frequency tracks, event provenance, erasures,
and ancestry. Repeated runs may relate events using a separate alignment map;
they must not pretend distinct recordings share sample coordinates.

**Techniques/testing.** Sequence alignment over octets/control events,
time-warp maps over landmarks, symbol-evidence combination, FEC-level
combination, and component-level image voting remain future candidates. Tests
verify serialization round trips and that low-quality regions stay identifiable
through every logical layer.

### C19. Produce artifacts, traces, metrics, and diagnostics

**Contract.** Always produce run status, decoded summaries, segment/event
tables, warnings, elapsed time, peak resident memory where measurable, and
counts of lock loss, erasures, invalid Varicode, header rejection, clipped
pixels, and damaged components. Optional trace levels are `none`, `summary`,
`events`, and `full`.

Full text diagnostics include symbol coordinates/phase, all tone metrics,
winner/runner-up, bit LLRs, deinterleaver I/O, Viterbi metrics/decoded bits,
and Varicode boundaries. Picture diagnostics include transition candidates,
frequency/value before clipping, raster index, timing residual, and expected
versus observed duration.

**Operational constraints.** Artifact writes are atomic where practical.
Large arrays are chunked and size-estimated before creation. A configurable
budget may reduce trace detail but may not alter decoded results. Diagnostics
must identify shared/reused computations so benchmarks do not hide duplicate
analysis.

## 5. Cross-capability algorithm decisions

These decisions remain open because the wire spec does not select receiver
algorithms:

| Decision | Candidates | Evidence required | Needed by |
| --- | --- | --- | --- |
| Tone estimator | FFT/filter bank, correlators, Goertzel, sliding DFT | controlled offsets/noise/fades; real clean and interfered text; CPU/allocation benchmark | first text vertical slice |
| Clock treatment | original-rate phase search, rational resample, timing loop | phase/clock-error synthetic grid; chunk equivalence; Pi runtime | first text vertical slice |
| Carrier/clock coupling | separate tracks, joint likelihood, fast path plus refinement | drift/clock confounding cases and real transitions | robust MFSK64 |
| Drift model | global, piecewise, continuous tracker | full-record residuals, discontinuities, pictures | robust MFSK64 |
| Synchronization | single hard lock, limited hypotheses, offline forward/backward | mid-stream, false lock, dropout recovery | initial acquisition; refine later |
| Viterbi confidence | survivor margin, repeated decode perturbation, max-log-MAP | fixed soft vectors and calibration under impairments | confidence phase |
| Picture estimator | phase differences, phase slope, local correlations, hybrid | p2/p4/p8 known raster; clock error; pixel bias/variance; Pi runtime | picture slice |
| Processing extent | complete-region batch, bounded windows, targeted refinement | reference-pipeline measurements | optimization phase |

All choices remain reversible behind the logical evidence contracts, except
discarding soft evidence or coordinate ancestry; those are prohibited.
SciPy is already used by `iqprep`, but each new SciPy-dependent primitive must
show a clear accuracy, speed, or implementation-safety advantage and document
an Android-portability alternative.

## 6. Independent test obligations derived from the contracts

Fixture preparation is divided into two activities. Controlled happy-path
fixtures are prepared before or alongside reference-pipeline implementation.
The definitive received corpus is inventoried and cut only after the reference
pipeline establishes precise context needs. Together they must provide:

- independently fixed logical tests from `mfsk_wire_vectors.json` and
  `mfsk_varicode.json`;
- pinned fldigi analytic-IQ text and picture fixtures with hashes and
  independent measurements from `mfsk_fixture_evidence.json`;
- narrow synthetic IQ matrices for phase, frequency offset, clock error,
  noise, fades, dropouts, interference, orientation, and block boundaries;
- controlled impairments applied to genuine received IQ;
- short untouched real-IQ cases for RSID, clean MFSK32/MFSK64 text,
  text-picture transitions, rasters, return-to-text, mode changes, damage, and
  reacquisition; and
- full untouched transmissions for end-to-end text/images, runtime, memory,
  mode transitions, and recovery.

Every implementation milestone beyond isolated capability work must traverse
the complete applicable path from IQ to final text or raster. Proof progresses
through clean pinned fldigi partial transmissions, impaired controlled cases,
short received intervals, received partial broadcasts with transitions, and
full received broadcasts. Earlier layers are faster and more diagnosable;
later layers provide stronger product evidence.

Every short fixture records the capability under test, source hash, half-open
input interval, required lead-in/trailing context, checkpoint assumptions,
annotations and precision, expected events/tolerances, and why shortening
would or would not change the behavior. Cuts must retain filter history,
complete RSID escape sequences, acquisition context, interleaver/FEC fill,
complete header transitions, raster clock history, or explicit checkpoints as
required by the relevant contract.

The durable received-corpus layout, promotion and retention rules, selection
matrix, truth levels, partitions, and ongoing admission policy are defined in
`mfsk_received_corpus.md`. In particular, disposable reference captures are
not corpus dependencies, and short cases normally remain virtual sample
intervals into one preserved canonical source rather than duplicated IQ.

Fldigi final output is a compatibility reference, not automatic ground truth.
Comparisons classify agreement, demonstrable direct-decoder improvement, or
ambiguous damaged reception. Intermediate oracle traces may diagnose behavior
but remain version-pinned development evidence and are not copied into
Radiogram implementation code.

## 7. Operational boundary

The standalone decoder may reuse or refactor validated `iqprep` ingestion,
bounded-block RSID, center estimation, correction, and coordinate conventions.
It must not require `iqprep` to have materialized corrected IQ: a pipeline may
consume raw channel IQ plus correction maps or corrected SigMF. Shared
functions should move into importable Radiogram modules only when tests pin
their existing behavior.

The current fldigi/USB path remains unchanged. Production replacement requires
later real-corpus acceptance, target-Pi performance and memory results,
repeatable artifacts, and an explicit integration decision.

## 8. Step-2 decision log and risks

| Issue | Step-2 position | Evidence/next decision |
| --- | --- | --- |
| Decoder input | SigMF complex IQ; corrected 48 kHz `ci16_le` is primary but not mandatory | reference baseline starts at the practical handoff; later measurements price raw versus corrected entry |
| Internal rate | not fixed | benchmark original-rate and resampled candidates |
| Capability boundaries | test contracts, not runtime passes | reference pipeline uses the clearest diagnostic organization and may later fuse them |
| Soft evidence | retain tone metrics and coded-bit LLRs through FEC | representation calibration finalized with decoder experiments |
| Coordinates | supplied IQ sample is authoritative; all transforms map back | schema prototypes must prove round trips |
| RSID annotations | priors/evidence, not truth | validate or revise around each mode transition |
| Picture start | joint prediction plus waveform evidence; no fldigi delay copied as wire timing | controlled fixtures benchmark alignment methods |
| Picture pixels | retain unclipped estimate and quality per component | compare discriminator/correlation techniques |
| Damage | erasure/weak evidence before reset | impairment corpus measures recovery policy |
| Early results | internal incremental processing is desirable; external progressive output is not required initially | measure time to stable text/picture and price committed or revisable output later |
| Streaming | feasible future organization, not initial constraint | evaluate after reference-pipeline measurements |
| SD-card I/O | avoid persistent intermediate IQ and evidence files by default | report bytes read/written and peak temporary storage; compare recomputation with caching |
| Multi-transmission voting | out of initial decode, evidence contract in scope | later alignment experiments select layer(s) for combination |
| SciPy | justified use only; NumPy-first for portable core | record benchmark and portability effect per choice |

Principal risks are incorrect short-fixture context, early hard decisions,
coordinate loss through resampling/delay compensation, duplicated transforms,
image-biased carrier tracking, overfitting to clean fldigi fixtures, excessive
trace size, unnecessary SD-card writes, unbounded hypothesis growth, and
postponing picture risks behind a text-only implementation. Reference-pipeline
instrumentation and implementation phasing must show how each is retired.

## 9. Methodology boundary and next work

This document completes methodology step 2: required capabilities, observable
contracts, candidate block forms, shared information, state, coordinates,
failure behavior, candidate techniques, and test obligations are explicit.

Methodology step 3 now defines and implements one straightforward diagnostic
reference pipeline rather than attempting to select an optimal architecture
from hypothetical comparisons. It should use complete-region batch planning
with bounded in-memory reads where convenient, retain diagnostic intermediate
evidence, avoid persistent full-size intermediate files, and permit future
fusion without making each capability a permanent public pass.

The reference pipeline must report:

- accuracy and damage at each logical capability;
- time to first stable text, picture descriptor, and complete picture;
- total wall and CPU time;
- peak resident memory;
- bytes read, bytes written, and peak temporary storage;
- repeated reads and duplicated expensive transforms; and
- acquisition, transition, and recovery behavior.

Alternative fused/vectorized, bounded-window, future-streaming, hybrid
fast-path/refinement, and non-causal organizations remain documented
hypotheses. They are compared or prototyped after a working received-broadcast
baseline identifies actual costs, accuracy limitations, or product benefits.
The reference implementation must preserve soft evidence, coordinates, and
state semantics so such work is refactoring rather than protocol
reimplementation.

The optimization program has two product thresholds. The first is a
deployable standalone baseline that is as good as or better than the pinned
fldigi path on representative corpus accuracy, image quality, transitions,
and recovery while remaining operationally feasible on the target Pi.
Reaching that threshold permits an explicit pipeline-integration decision; it
does not imply that every decoder limitation has been eliminated. Subsequent
lower-yield improvements may continue against the versioned corpus after
integration without keeping replacement of the fldigi path indefinitely open.

Fldigi is a compatibility and product-quality reference, not the required
decoder architecture. Comparisons distinguish a direct-decoder regression,
equivalence, demonstrable improvement, and ambiguous RF loss. A favorable
aggregate score cannot hide a material regression in acquisition, mode
transition, picture geometry, return to text, severe-condition recovery, or
target-Pi feasibility.

### 9.1 Development-machine and target-Pi evidence

Session 9 establishes comparable full-broadcast baselines on both the
development Mac and the target Raspberry Pi 3. The Mac is the primary
profiling and Session 10 iteration environment because it permits rapid
experimentation over the corpus. The Pi is the product environment and is the
authority for deployment feasibility, memory pressure, storage behavior, and
unattended runtime.

Both platforms run the same pinned source, corpus cases, decoder
configuration, trace/output policy, and expected-result checks. Each run
records:

- wall and CPU time, peak RSS, and swap use where available;
- time to first stable text, first picture descriptor, and first complete
  picture;
- bytes read and written and peak temporary storage;
- stage-level timings sufficient to distinguish acquisition, text evidence,
  FEC/framing, raster estimation, and artifact production;
- output hashes, text/image accuracy, damage, transitions, and recovery;
- Python, NumPy, SciPy, operating-system, and architecture identity; and
- on the Pi, storage type plus temperature and throttling state.

Cross-platform result equivalence is checked before performance ratios are
interpreted. Numerical differences may be tolerated only when their effect on
events, text, pictures, transitions, confidence, and damage reporting is
understood and recorded.

Pi/Mac scaling factors are calculated per logical stage or workload, not as
one global multiplier. Python control flow, vectorized NumPy/SciPy operations,
memory-bound transforms, hashing, and artifact I/O need not scale alike.
During Session 10 these factors may estimate the likely target effect of a Mac
experiment and prioritize which candidates deserve Pi time.

Extrapolation is prioritization evidence, never acceptance evidence. Target-Pi
runtime, peak memory, storage I/O, accuracy, recovery, and unattended behavior
must be measured directly for production decisions. A material change in
vectorization, Python looping, working-set size, repeated IQ reads, parallelism,
datatype, numerical primitive, or output I/O invalidates the affected scaling
assumption until it is checked again on the Pi.

Session 9 execution established that the initial full-recording reference
organization retains several avoidable full-size NumPy arrays and reaches
multi-gigabyte peak RSS. By product-management decision, the full-broadcast
quality and performance baseline therefore runs on the development Mac only.
This is an implementation-organization limitation, not evidence that the
decoder's required state cannot fit the target. Direct Pi execution and
Pi/Mac scaling are deferred until the first bounded-memory Session 10
checkpoint. Fldigi 4.2.06 results already produced on the Pi remain
compatibility evidence for accuracy, pictures, transitions, and recovery;
fldigi real-time playback performance is not a direct-decoder benchmark.

The R5 bounded-memory checkpoint subsequently completed that deferred
measurement on 2026-07-28. Representative full WRMI July 8 MFSK32 and MFSK64
runs on the 905 MiB Pi 3 peaked at 480,912 KB and 480,432 KB RSS with zero
process swaps and completed successfully. Their run IDs, text summaries, mode
segments, and complete picture descriptors matched the Mac results; a single
MFSK64 clipped-component classification differed at a floating-point boundary
without changing geometry or completion. Runtime was 24m54s for MFSK32 and
1h06m15s for the seven-picture MFSK64 pass. The decoder is therefore
memory-feasible as an offline Pi 3 workload, but the image-heavy path is not
real-time. See
`history/mfsk-decoder/remediation/mfsk_iq_decode_remediation_r5.md` for the
complete R5 evidence.
The held-out Session 9 audit also established that a global amplitude
threshold marked 96.5% of one recording active and caused the C4 fallback to
analyze picture-era channel occupancy at 2104 Hz. The existing unhinted iqprep
RSID detector instead found the opening MFSK32 and MFSK64 change at about
1553 Hz with zero code distance. C2 region selection and C3 RSID evidence must
therefore bound and anchor C4; a whole-record fallback is diagnostic only and
is not normal acquisition.

The benchmark cadence is:

1. run meaningful candidate comparisons over the applicable corpus on the
   Mac;
2. run promising or architecturally different candidates over a
   representative Pi subset;
3. run the full Pi corpus for final target acceptance and for any major
   checkpoint whose platform behavior cannot be established by the
   representative subset.

### 9.2 Picture-boundary release criterion

Product direction on 2026-08-02 makes reliable text-to-picture boundary
acquisition a prerequisite to pipeline engineering and release. Aggregate
picture quality modestly below fldigi may be acceptable when the difference is
understood and stable. A known acquisition failure that displaces raster
components or RGB planes and produces structured color corruption is not.

The Session 10E Bates–Ward case demonstrates this risk. Current evidence says
that correcting its apparent component displacement would improve alignment
but would not explain all of its remaining error. Boundary acquisition and
raster estimation must therefore be evaluated separately rather than treating
one image metric as proof of either cause.

The focused second-opinion request is recorded in
`AI Discussions/MFSK picture boundary second opinion.md`. One-sided start
estimators are preferred. Joint inference from both the approximate picture
end and start remains a last resort after simpler waveform- and protocol-based
methods have been tested. A later open-field review of the entire decoder and
Session 10 methodology is a separate activity.

The response in
`AI Discussions/MFSK picture boundary second opinion response.md` was reviewed
against the implementation and retained evidence on 2026-08-02. Its central
diagnosis is accepted with an important correction: the transmitted prologue
does begin on the transmitter symbol grid, and the mode-blind `0.965 s`
receiver offset discards useful mode and group-phase accounting, but the
receiver's acquired `first_symbol` grid is not exact transmitter timing. On
the controlled MFSK64 fixture, the known prologue begins 60.328125 nominal
receiver symbols after the reported semicolon rather than at an integer
residue; the acquired grid is displaced by 252 input samples. Protocol
accounting is therefore a strong coarse predictor, not a sufficient
sample-accurate estimator or a valid exact-residue assertion.

The Bates-Ward MFSK32 diagnostic nevertheless strongly confirms the proposed
root mechanism. The final semicolon's decoded-bit group phase predicts 24
symbols from receiver recognition to prologue. Applying that prediction moves
the candidate raster 195 p8 components earlier than the Session 10E start:
one 180-component color plane plus the 15-component residual previously found
by bounded truth-assisted alignment. With the Session 10E measurement path,
raw MAE falls from 84.9229 to 43.2895 and aligned MAE from 63.5399 to 42.1308,
and the structured purple/green plane corruption disappears. This evidence is
diagnostic rather than a runtime truth source and does not establish the final
sub-component boundary or fldigi parity.

Product management closed Session 9 with the complete post-remediation Mac
corpus baseline plus the representative R5 Pi feasibility and parity runs.
The full Pi corpus is not an accuracy prerequisite: after structural parity,
it principally measures target runtime, thermal/storage behavior, and
unattended reliability. It remains required before final target acceptance,
but is not required to close Session 9 or Session 9A.

## 10. Recommended implementation sessions

Session boundaries are recommended handoff points, not estimates that every
item will consume exactly one context window. End each session with updated
tests, fixture provenance, measured results, unresolved decisions, and the next
vertical exit criterion so a clean session can resume from repository state.
Forward-looking methodology, ordering, and exit criteria recorded in a
handoff are recommendations informed by the session just completed. They are
not a contract for the subsequent session. At the start of each session,
review those recommendations against the repository state, new evidence,
product priorities, and available materials; explicitly retain, revise, or
replace them before implementation.
The post-Session-9 conformance audit and dependency-ordered remediation
sessions are recorded in `mfsk_iq_decode_capability_audit.md`; that audit
supersedes proceeding directly from the initial baseline to isolated
optimization.

1. **Reference-pipeline and harness.** Establish package/CLI skeleton, input
   and output schemas, coordinate mapping, fixed-vector tests, instrumentation,
   and the no-persistent-intermediate default.
2. **Controlled-IQ fixture preparation.** Inventory existing pinned fldigi
   analytic-IQ artifacts, generate only missing minimal happy-path text and
   picture cases, verify isolation and hashes, record exact expected output,
   and make their availability checks repeatable. This session does not cut
   the definitive received corpus.
3. **Controlled MFSK32 text vertical slice.** Decode a short known
   transmission from IQ through final octets, with intermediate diagnostics
   and baseline cost measurements.
4. **Received MFSK32 acquisition.** Decode a short untouched received
   interval and address carrier, clock, and damage behavior exposed by RF.
5. **MFSK64 text vertical slice.** Prove controlled and short received MFSK64
   through final text without duplicating mode-independent code.
6. **Picture transition and controlled raster.** Decode a complete known
   header, align the prologue/raster, reconstruct grayscale and color, and
   reacquire text.
7. **Received picture and transitions.** Prove real MFSK64 pictures,
   MFSK32/MFSK64 changes, text-to-picture, and return-to-text in a received
   partial broadcast.
8. **Received-corpus preparation.** With observed context requirements,
   inventory full recordings and create the minimal annotated short/partial
   fixtures, leaving originals untouched and following
   `mfsk_received_corpus.md`.
9. **Full-broadcast baseline.** Decode complete broadcasts on the development
   Mac and, once the reference organization is bounded-memory, the target Pi.
   Record accuracy, recovery, time to useful results, stage and total runtime,
   memory, reads, writes, and temporary storage. The initial Session 9
   execution is Mac-only under the decision recorded in section 9.1; direct
   Pi measurement and stage-specific Pi/Mac scaling move to the first
   bounded-memory Session 10 checkpoint and remain required before target
   acceptance.

9A. **Program truth and accuracy framework.** Reorganize the logical corpus
    around programs, where one program owns one reviewed text and ordered
    image set and may have multiple archive-audio or received-IQ
    transmissions. Preserve captures as immutable transmission artifacts
    identified by station/time rather than duplicating them under programs.
    Build reviewed text truth efficiently from high-quality archive audio,
    retaining the draft decoder output and recording explicit human sign-off;
    use pinned fldigi selectively to resolve uncertainty and later as
    compatibility evidence, not as automatic truth. Record whether each
    broadcaster image is the exact fldigi input or an earlier production
    source and preserve any known resize, crop, color, or conversion
    provenance.

    Establish a repeatable, versioned scorecard rather than a single aggregate
    accuracy number. At minimum report mode events; text insertions,
    deletions, substitutions, coverage, and recovery; picture identity,
    order, header, geometry, completion, raw per-channel error and bias,
    declared damage, and return to text; plus ambiguity and truth strength.
    Program truth and transmission observability are separate: a damaged
    capture does not change what the program contained, and a
    capture-limited element is classified only with recorded evidence. Score
    repeated transmissions separately but aggregate them hierarchically so
    repeated content does not overweight a program. Run the frozen decoder
    over the full Mac corpus to establish the first post-remediation accuracy
    baseline. See
    `history/mfsk-decoder/sessions/mfsk_iq_decode_session9a.md` for the detailed
    starting recommendations, which must be reviewed rather than adopted
    automatically when Session 9A begins.

9.5. **Fldigi receiver-technique archaeology and gap analysis.** After the
   full-broadcast baseline identifies actual quality and recovery gaps,
   inspect the pinned fldigi MFSK32/MFSK64 receive paths for techniques that
   are receiver policy rather than wire behavior. Catalogue front-end
   filtering, tone evidence, soft metrics, persistent-interferer handling,
   burst/erasure treatment, symbol synchronization, AFC/carrier tracking,
   FEC decisions, reset/recovery policy, text-picture transitions, and picture
   timing/frequency estimation. Map each technique to its fldigi source,
   problem addressed, corresponding decoder contract and current
   implementation, observed corpus evidence, proposed controlled comparison,
   and target-Pi implications. Classify it as already implemented,
   represented but incomplete, missing and promising, real-time-only,
   presentation-only, or unsupported/irrelevant. This session changes no
   decoder algorithms; it produces a ranked, evidence-backed Session 10
   candidate list. Fldigi behavior is not copied merely because it is mature,
   and presentation enhancement never replaces the evidentiary decoded
   raster. Session 9.5 completed on 2026-07-31, including a later-source audit
   through upstream tag 4.2.13; the source map, classifications, evidence,
   comparisons, Pi implications, and ranked candidates are recorded in
   `history/mfsk-decoder/sessions/mfsk_iq_decode_session9_5.md`.

10A. **Accuracy register and experiment design.** Combine the Session 9.5
     fldigi findings, current C1-C19 limitations, corpus observations, and
     original receiver ideas in the living register defined by
     `mfsk_iq_decode_accuracy_optimizations.md`. Every candidate states the
     problem, rationale, evidence, affected cases and capabilities, expected
     benefit, complexity, quality risk, runtime/memory/I/O implications,
     receiver sensitivity, dependencies, and the cheapest controlled
     experiment capable of accepting or rejecting it. Rank candidates before
     implementing substantial alternatives.

     Define the versioned overall "exceed fldigi" planning gate in this
     session. It is a reproducible aggregate derived from, not a replacement
     for, the Session 9A multidimensional scorecards. Its weights and any
     catastrophic-regression eligibility rules are explicit product-policy
     inputs. It identifies the corpus revision, direct decoder revision, and
     qualified recent fldigi version. The underlying acquisition, text,
     picture, transition, recovery, damage, truth-strength, program,
     transmission, and receiver-subset results remain visible.

     Session 10A completed on 2026-07-31. The ranked register, explicit
     experiments and acceptance rules, versioned computable fldigi gate,
     no-overwrite recent-fldigi qualification/archive workflow, and selected
     P1 Session 10B vertical are recorded in
     `mfsk_iq_decode_accuracy_optimizations.md` and
     `mfsk_fldigi_gate_policy_v1.json`.

10B. **Picture accuracy.** Work through the highest-ranked picture candidates.
     The first Session 9A Mac baseline ranks component
     estimation/calibration first, picture-header recovery and coordinator
     suppression second, and damage-diagnostic calibration third. Persistent
     raster timing/phase remains a measured follow-on candidate. The direct
     wheatear raster did not reproduce fldigi 4.2.06's abrupt lower-raster
     displacement, so that isolated artifact does not by itself reprioritize
     sample-clock correction. Promote or reject each candidate from controlled
     evidence, applicable received intervals, and then corpus regression.

10C. **Text, acquisition, and recovery accuracy.** Independently improve text
     quality after exact three-event mode-sequence acquisition on the selected
     broadcasts. Rank carrier and symbol-clock refinement,
     interference-aware soft evidence and erasures, localized competing
     hypotheses, FEC startup/offline refinement, confidence-aware Varicode
     recovery, non-text exclusion, dropout recovery, and post-transition
     reacquisition from observed errors rather than algorithm novelty.

     Session 10C completed on 2026-07-31. Persistent-tone attribution passed
     its measurement gate in all three received WRMI cases, but the bounded
     suppression variant worsened hierarchical CER and was rejected. The
     measurement remains non-operative evidence and suppression remains an
     explicit experimental configuration. T2-T6 and R1 were deferred because
     their predeclared mechanism/promotion evidence was not present. Detailed
     Session 10C evidence is recorded in
     `history/mfsk-decoder/sessions/mfsk_iq_decode_session10c.md`.

10D. **Accuracy convergence and product-potential gate.** Freeze the adopted
     candidates and rerun the complete corpus against reviewed program truth.
     The frozen direct decoder and scoring/publication run on the development
     Mac; fldigi build, controlled qualification, and corpus decoding run on
     the Raspberry Pi, which is the authority for fldigi-dependent results.
     This explicitly requires the
     Session 10A refresh/archive workflow: attempt fldigi 4.2.13 first with
     packaged 4.2.12 as the documented fallback, qualify it with the controlled
     smoke fixtures, re-decode every corpus transmission, archive the new
     reference without overwriting 4.2.06, parameterize and rerun fldigi
     scoring, and create a new gate-policy revision naming the qualified
     fldigi and frozen direct-decoder revisions. Rerun the frozen direct
     decoder over the same complete corpus and unchanged reviewed truth.

     Produce both the machine-readable planning package and a human visual
     image-review package. The latter organizes every expected picture by
     program and transmission and presents truth/reference, frozen-direct, and
     qualified-recent-fldigi rasters where available, with headers, geometry,
     completion, score status, and visible anomaly notes. Missing or
     unscoreable truth remains explicit. Product management requires this
     package alongside the current detailed scorecards and aggregate gate.

     This is a substantial long-running qualification workflow. Implement it
     as repeatable, restartable per-build and per-transmission steps with
     immutable staging, completion records, and hash verification so a failed
     build or decode does not require successful work to be repeated. Report
     long commands when started and retain their final metrics; do not weaken
     qualification or silently fall back after a failure.

     The overall "exceed fldigi" result is a project-planning trigger: when
     the direct decoder exceeds fldigi, product management may proceed to
     pipeline design or authorize a bounded set of additional accuracy
     candidates whose value or architectural interaction justifies completing
     them first. Exceeding the aggregate does not claim superiority in every
     metric, alter the detailed measurement framework, or make ambiguous RF
     loss into decoder truth.

     Session 9A closed with frozen machine-readable per-channel raster,
     damage, return-to-text, operational, truth-strength, and hierarchical
     program/decoder results. Coordinate and center error remain explicitly
     unavailable where independent transmission truth does not exist;
     decoder-produced coordinates are not reused as truth.

     Session 10D completed on 2026-08-01. Qualified fldigi reference
     `fldigi-4.2.13-pi3-aarch64-7fa6ee2e4178` scored CER 0.06009762563,
     picture recall 0.875, and aligned MAE 24.43013680/255. Frozen direct
     scored 0.1294708528, 0.8958333333, and 68.09872953/255. Gate policy v2
     failed with aggregate direct advantage -0.08247824168, seven catastrophic
     checks, and negative Airspy HF+ and RTL-SDR subsets. The exact evidence
     and visual findings are in
     `history/mfsk-decoder/sessions/mfsk_iq_decode_session10d.md`. The next
     action requires the PM choice between Session 11 pipeline design and an
     explicitly bounded Session 10E.

10E. **Optional pre-architecture accuracy work.** Implement only candidates
     explicitly selected after the 10D gate because they have unusually high
     expected product value or need resolution before pipeline organization
     can be chosen. Optimization is not an unlimited prerequisite.

     Session 10E was authorized on 2026-08-01 as a bounded raster-fidelity
     investigation. Its ordered gates are: diagnose offset, scale, estimator,
     interference, transition, and timing signatures; compare bounded
     component-window weightings; evaluate second-generation correlation and
     evidence-gated hybrid frequency estimators; and evaluate only
     waveform/protocol-derived picture-local calibration. With the selected
     estimator fixed, a bounded front-end response comparison is authorized.
     Raster-clock refinement proceeds only if residuals demonstrate a timing
     mechanism. Damage-diagnostic calibration follows selection of the final
     measurement path and does not alter raster values.

     Each vertical progresses from controlled p2/p4/p8 fixtures to selected
     received picture windows and earns a full-corpus run only after passing
     its earlier gate. Long Mac matrices use checkpointed user-run batches via
     `tools/mac-local.sh`; frequent agent polling is not the default. Frozen
     Session 10D artifacts are never overwritten. Candidate adoption remains
     an explicit product discussion after experiments and full regressions.

10F. **Picture-boundary convergence.** Resolve the release-blocking
     text-to-picture boundary before pipeline design. Retain the Session 10E
     bounded-correlation, full-window, response-matched path as the experimental
     measurement baseline while keeping production defaults unchanged until
     the combined candidate passes its gates.

     First, implement and unit-test transmitter/group-phase accounting from the
     final header event. The current receiver provenance makes the MFSK32
     recognition-to-prologue offset 24 symbols when the flush-leading decoded
     bit is even and 23 when it is odd; MFSK64's 90/91 emitted-symbol parity is
     cancelled by the corresponding recognition-evidence lane timing, yielding
     60 symbols in either case. Verify this derivation against fixed logical
     vectors and controlled transmitter fixtures rather than treating the
     arithmetic in the second-opinion response as authoritative.

     Next, treat the protocol result as a coarse boundary hypothesis and refine
     the actual prologue-to-raster change from waveform evidence. Search enough
     sub-symbol context to cover measured acquisition-grid error, use the
     mode-specific picture center/bandwidth and declared orientation, score the
     constant-tone-to-component-rate model change rather than prologue tone
     presence alone, and retain materially distinct candidates with calibrated
     ambiguity. The existing narrow prologue-tone score is not eligible for
     tuning: its long same-tone plateau is structurally degenerate and its
     raster term is incorrectly fixed to the MFSK64 band.

     Gates proceed in this order: (1) controlled MFSK64 exact-boundary
     accounting and measurement of receiver-grid error; (2) Bates protocol
     displacement and waveform-only refinement without reference-image input;
     (3) controlled MFSK32 p2/p4/p8 grayscale/color and MFSK64 group-parity
     coverage; (4) all existing received transitions with false-lock,
     uncertainty, geometry, completion, and return-to-text checks; and (5) a
     complete Mac corpus and visual package using the combined 10E+10F
     candidate. Synthetic tests include receiver-grid phase, clock error,
     carrier offset/drift, fades in the terminal plateau, a value-zero
     interferer, and leading value-zero raster components.

     Do not directly plumb the current whole-text `clock_error_ppm` or
     `frequency_track` into pictures. Those fields are currently contaminated
     by non-text intervals: the controlled MFSK64 fixture reports 552 ppm and
     Bates reports 99 ppm, so they are not the nearly free, unambiguous fixes
     claimed by the review. Picture-local or text-adjacent track evidence must
     first pass an independent calibration gate. Post-picture modular closure
     and end information remain corroborating/last-resort evidence, not the
     primary one-sided estimator.

     **Recovery checkpoint completed, 2026-08-02.** The protocol/group-phase
     diagnosis is confirmed: applying the MFSK32 `K=24` projection to Bates
     removes the structured color-plane displacement and reduces raw MAE from
     84.9229 to 43.2895. Two refinements have been evaluated and rejected as
     primary boundary estimators. A local constant-to-component change detector
     cannot identify the semantic boundary when leading components have value
     zero, because those samples are physically indistinguishable from the
     low-endpoint prologue. A transition-crossover fit over the reconstructed
     header flush is image-independent but has insufficient precision by
     itself: on Bates it reports 77 input samples of uncertainty and slightly
     regresses raw MAE to 45.1476.

     The global transition-crossover transmitter clock is now implemented. For
     each reliable decoded-text boundary whose adjacent tones differ, it finds
     the fractional zero of the
     old-tone minus new-tone energy discriminator. Weight primarily by squared
     frequency separation, select only high-margin adjacent tracked winners,
     reject erased/interfered observations, and robustly fit one affine grid
     `t(k) = epoch + k * tracked_symbol_samples` with covariance. The global
     fit does not reconstruct the whole preceding transmitted tone stream when
     the selected FEC startup is unknown-midstream. Exact reconstruction is
     confined to the header flush, where the decoded header prefix establishes
     the needed encoder/interleaver state. `_fit_transition_crossover_clock`,
     its constructed-grid unit test, and the picture-decoder inputs for the
     resulting clock and covariance are connected. Both bounded and unbounded
     pipelines carry that evidence to picture decode.

     The global clock is the primary semantic-boundary estimator because its
     evidence precedes the image and is unaffected by leading zero pixels.
     Protocol/group-phase accounting projects it to the first raster component.
     The reconstructed known flush is an independent verifier, not the primary
     fit. The local change detector is a one-sided falsifier only: modulation
     observed before the prediction proves that it is late, whereas a later
     observed transition is compatible with leading zeros and cannot move the
     boundary. Agreement between independent global-grid and flush evidence is
     reported as `boundary_overdetermined`; disagreement remains explicit.

     The final candidate measures at most 128 evenly distributed crossovers,
     robustly fits epoch/rate with covariance, uses the projected grid as the
     operative semantic start, and never averages a flush disagreement into
     that coordinate. A leading-zero synthetic case and an observable MFSK32
     p8 transition pass. Bates aligned MAE falls from the Session 10E scorecard's
     86.133 to 42.1968 with one residual component of alignment and 11.7 input
     samples of projected uncertainty.

     The complete boundary-only corpus retains picture recall 0.895833 and
     improves hierarchical aligned image MAE from Session 10E's 33.6632 to
     31.9583, versus fldigi 4.2.13 at 24.4301. Every per-case pixel-fidelity
     disadvantage is inside policy v2's 0.05 catastrophic threshold. The text
     clock's rate is not operative for raster tracking: an intermediate corpus
     run materially regressed two pictures, so the rate is published only as
     an unqualified candidate and the component clock remains nominal unless
     separately supplied accepted evidence exists.

     Subsequent visual review rejected unconditional global selection. It
     enlarged structured edge rectangles in Pikes Peak, Painting, Wheatear,
     and Comet even though aggregate aligned MAE improved. The cause is
     long-horizon projection from pre-picture text plus a verifier that could
     report but not veto disagreement; alignment compensation hid much of the
     delivered-raster defect.

     Product management accepted a temporary agreement-gated baseline on
     2026-08-02. The global coordinate is operative only when the independent
     flush prediction agrees statistically and within two components and the
     global uncertainty is within two components; otherwise the Session 10E
     correlation coordinate is selected. Final aligned/raw MAE are
     31.812942/37.795467 versus fldigi 24.430137/30.803384. The final HTML
     scorecard also reports maximum and dominant alignment compensation.
     `protocol_change` remains explicit and the legacy default is unchanged.

10G. **Unified multi-evidence picture-start estimator.** Replace the temporary
     Session 10F estimator switch with one estimator and one uncertainty model.
     Use text transitions to constrain the long-baseline transmitter epoch and
     rate, then use the exactly reconstructed header flush to estimate the
     picture-local phase while holding or strongly regularizing that rate.
     Apply the existing protocol/group-phase accounting once to project the
     combined fit to the semantic first raster component. The local modulation
     change evidence remains a one-sided constraint because a leading zero
     plateau contains no semantic-start observation.

     The implementation must expose every evidence residual, robust weight,
     rejected observation, covariance term, and protocol projection in one
     diagnostic object. It must not select among named estimators, average
     incompatible coordinates after the fact, or use image truth to choose the
     start. The Session 10F agreement selector and legacy fallback carry an
     explicit sunset and are deleted only after the unified fit passes.

     Qualification proceeds in this order: exact affine synthetic grids;
     leading-zero and leading-nonzero pictures; damaged/partial flush, drift,
     resampling, filtering, carrier error, noise, and parity cases; Bates plus
     Pikes Peak, Painting, Wheatear, and Comet; all received transitions; then
     the checkpointed complete corpus and portable visual review. Acceptance
     requires no structured edge regression, retained geometry/completion and
     return-to-text behavior, and material convergence toward qualified fldigi.
     Report raw whole-raster MAE and maximum/dominant alignment compensation
     beside aligned MAE. Aligned MAE alone cannot qualify the estimator.

     Session 11A remains blocked until Session 10G satisfies this picture gate
     and the complete decoder is substantially as accurate as the qualified
     fldigi reference, unless product management explicitly changes that
     prerequisite.

     **Technical qualification completed 2026-08-03; PM visual decision
     pending.** One robust affine fit now combines the global
     text-transition clock prior with every measurable reconstructed
     header-flush crossover. Missing or damaged local evidence changes the
     same fit's covariance; it does not select another estimator. The Session
     10F agreement selector and legacy correlation fallback are no longer
     supported, and `unified_grid` is the sole configured boundary policy.

     The four-transmission corpus retained 0.895833 picture recall and scored
     aligned/raw hierarchical MAE 31.828819/34.477195, versus the temporary
     Session 10F gate at 31.812942/37.795467 and qualified fldigi 4.2.13 at
     24.430137/30.803384. Mandatory visual review found no structured edge
     regression. Painting's purple edge strip was removed, and Bates, Pikes
     Peak, Wheatear, and Comet retained or improved raw alignment. Sicily's
     mid-picture break remains a separately classified raster-clock defect.
     See the Session 10G final handoff for per-case evidence and limitations.

11A. **Pipeline requirements, quality freeze, and cost model.** Apply
     `mfsk_iq_decode_pipeline_requirements.md`. Freeze the accepted Session 10
     revision, configuration, corpus hashes, scorecard, visual-review set, and
     known defects. Separate hard behavioral invariants, tolerance-based
     quality metrics, and observational diagnostics. Define the target-Pi
     operating evidence, including peak RSS, swap, runtime, time to first
     useful result, logical and physical I/O where measurable, temporary
     storage, determinism, coordinates, provenance, confidence, and recovery.
     Characterize each logical workload as compute-, memory-, I/O-, or
     Python-control-bound. Classify secondary goals as operational constraints,
     optimization objectives, or exploratory features and explicitly resolve
     conflicts rather than relying on priority alone.

     Session 11 does not initially promise an exact caller-supplied memory
     ceiling. Identify separable memory decisions, measure useful
     configurations, and establish at least one full-quality target-Pi
     configuration that completes representative work without swap. Automatic
     configuration from a caller memory budget remains future work.

     **Completed 2026-08-04.** Product management accepted Session 10G as the
     Session 11 no-regression baseline, without treating that decision as
     standalone-decoder promotion. Commit `aa70ec4` is the implementation
     identity. The four-transmission scorecard, input and evidence hashes,
     per-case and per-picture metrics, hard behavioral gates, narrow numerical
     tolerances, mandatory visual gate, target-Pi no-swap constraint, and Mac/Pi
     cost evidence are frozen in
     `mfsk_iq_decode_session11a_baseline.json`. The decision record and workload
     classification are in the Session 11A handoff.

     The current Mac MFSK64 path spends 72–85% of wall time in text
     acquisition/evidence/FEC/framing. R5 proves bounded Pi feasibility at
     about 481 MB RSS without swaps but predates Session 10G, so it does not
     accept the current organization on the target. Session 11B begins with
     the reference pipeline and one stateful bounded hypothesis; Session 11C
     first tests state carryover, duplicated acquisition/transform work, and
     the text-path compute/Python-control split.

11B. **Measured pipeline hypotheses.** Retain the current bounded reference
     organization as the quality oracle and cost baseline. Begin with a
     stateful bounded hypothesis that reuses acquisition and text state across
     windows, with targeted non-causal refinement evaluated as an option for
     ambiguous or damaged regions. Introduce another complete candidate only
     when measurements reveal a materially different trade-off.

     Start with an explicit, extensible design-lever register covering
     processing extent/state, sample versus evidence flow, fusion/staging,
     vectorization and parallel execution, memory/I/O, result scheduling, and
     recovery/refinement. For every lever record expected benefit, cost,
     dependencies, quality risk, disposition, and distinguishing evidence.
     Enumeration prevents accidental omission but does not require exhaustive
     combinations. For every supported hypothesis define dataflow, state
     ownership, materialized samples and evidence, recomputation,
     window/context behavior, memory-affecting controls, early results, failure
     recovery, and expected target cost.

     **Design checkpoint completed 2026-08-04.** The current independent
     180-second-core organization remains the quality oracle. The first
     candidate is one stateful bounded coordinator that carries a compact,
     versioned modem checkpoint across administrative window boundaries,
     commits only beyond a bounded look-ahead/traceback horizon, and uses
     targeted source rereads only for explicit ambiguity or damage. Complete
     picture windows remain conservative initially. The design-lever register,
     dataflow, state ownership, memory controls, recovery rules, cost
     hypothesis, and ordered 11C risks are recorded in the Session 11B
     decision document. No second complete pipeline is presently justified.

11C. **Architectural spikes.** Prototype only distinguishing risks such as
     stateful bounded-window equivalence, checkpoint restoration, transform
     and evidence reuse, caching versus recomputation, targeted-refinement
     yield, incremental versus in-memory raster artifacts, picture working
     sets, and Pi vectorization or Python-control reduction. Explicitly test
     parallelism where work is genuinely independent or native kernels release
     the Python lock; do not assume that four Pi cores imply a fourfold gain.
     Compare justified worker counts on semantic determinism, wall/CPU time,
     peak RSS, swap, I/O, temperature, throttling, and oversubscription. Do not
     implement every option as a complete decoder.

     **Checkpoint A completed 2026-08-04.** A versioned, checkpointable
     continuous Viterbi slice now retains a bounded 48-decoded-bit survivor
     horizon and shares survivor-update semantics with the batch decoder.
     Controlled adversarial splits and rollback/replay are bit-exact; combined
     deinterleaver, FEC, and Varicode restoration recovers a picture header
     across a checkpoint. The retained checkpoint is independent of recording
     duration. This retires only the controlled C9-C11 portion of boundary and
     minimum-state risk: carrier, clock, filter/tone evidence, raw-IQ guards,
     received dropouts, and transactional header-scanner state remain open.

     **Completion checkpoint B, 2026-08-04.** The stateful bounded spike now
     carries transactional C9-C12 state and source completeness, observes a
     fixed carrier/clock track across arbitrary IQ sample splits with less than
     one symbol retained, and preserves the existing offline track fit through
     at most nine bounded random-access neighborhoods. Sustained 12-symbol loss
     rolls back provisional output and begins a new explicit epoch.

     Received 60-second MFSK64 and MFSK32 intervals require 192- and 384-bit
     traceback respectively; the common supported setting is 384. All 1,855
     received event signatures and decoded-bit coordinates match the batch
     oracle. Profiling identified repeated Python-controlled Viterbi work as
     dominant. An exact vectorized trellis update reduced profiled interval
     time from 36.87 to 6.55 seconds for MFSK64 and 19.45 to 5.31 seconds for
     MFSK32 without event changes. The completed gate evidence, remaining
     trade-offs, and S1 handoff are in the Session 11C decision document.

11D. **Pareto selection.** Compare supported candidates on retained accuracy,
     wall and CPU time, peak RSS, bytes read and written, temporary storage,
     time to useful results, implementation complexity, diagnostics,
     operational risk, and extensibility. Select an explicit point from the
     Pareto frontier using product priorities; a hybrid is allowed.

     **Picture-dominant clarification, 2026-08-04.** Product selection must be
     robust for picture-heavy broadcasts, including few very large pictures.
     Treat picture/text overlap, concurrency among independent pictures,
     parallel work within one picture, and native-kernel threading as distinct
     levers. A one-picture worker does not establish picture-dominant speed if
     it only overlaps a small non-picture fraction. Before selection, profile
     picture stages and size scaling, identify serial and independently
     executable work, and measure the smallest justified concurrency or
     partitioning spike when picture cost is material. Preserve an efficient
     sequential configuration and do not construct a speculative parallel
     framework, but do not select ownership or whole-picture dependencies that
     unnecessarily foreclose later intra-picture parallelism. Report
     large-picture latency, peak RSS, swap, I/O, determinism, and Pi thermal
     behavior separately from corpus averages.

     **Completed 2026-08-05.** The selected P11D point combines S1 compact
     track planning, one transactional stateful text pass with the common
     384-bit horizon, exact vectorized Viterbi, and immutable bounded picture
     jobs. Picture FIR and component work use deterministic bounded ranges and
     the same minimal executor with one or more configured workers. Range size,
     worker count, and maximum in-flight ranges are explicit Session 11E tuning
     controls; the one-worker form is the required low-memory sequential path,
     not a separate decoder. No configuration retains a complete filtered
     large-picture window.

     Mac and Pi spikes show that two independent picture jobs can improve the
     isolated kernel by about 1.9x, while two-way intra-picture estimation
     improves 1.18x on the Mac and 1.33x on the Pi. Both are deterministic,
     but their full-pipeline memory and thermal headroom are unqualified.
     Native kernels are effectively single-threaded. The initial
     estimator-only experiments left FIR filtering serial and did not isolate
     picture-size effects, so their speed and memory values do not justify
     excluding configurable intra-picture execution. P11D includes bounded
     deterministic range dispatch; 11E tunes its worker and memory policy.
     Concurrency among separate pictures and picture/text overlap remain
     distinct optional policies. The complete Pareto table, limitations, and
     evidence hashes are in the Session 11D handoff and its machine-readable
     evidence file.

     A final bounded-range spike assigned the FIR, component estimator, and
     quality calculation together to deterministic component ranges. Filtered
     samples, frequencies, and quality arrays were exact against the
     whole-picture oracle for one, two, and four workers. Across 65,536 and
     262,144 components, two workers improved ranged wall time by 1.87–1.89x
     and four workers by 3.10–3.13x. On the larger case, one-worker ranged
     execution reduced peak RSS from 546 MB to 275 MB without a slowdown; two
     workers used 349 MB. This qualifies the configurable range-worker
     capability for the selected design while leaving Pi configuration and
     full received-picture qualification to 11E.

11E. **Pipeline convergence.** Implement and benchmark the selected
     composition. The frozen accuracy decoder and scorecards are its quality
     oracle. Iterate on cross-stage interactions until the candidate pipeline
     preserves the accepted quality within declared tolerances and is
     operationally feasible on representative target-Pi work. Automated
     scorecards cannot alone qualify architectural or final convergence:
     standardized human visual review must also reject geometric, color-plane,
     edge, and raster-clock regressions.

11F. **Capture profile decision.** Using the candidate pipeline, compare
     preserved Airspy CF32 captures with deterministic CI16 derivations of the
     exact same samples. Compare candidate channel widths and stored sample
     rates derived from sufficiently wide canonical recordings, then confirm
     the selected settings with native appliance captures. Measure acquisition,
     text, pictures, transitions, damage, runtime, memory, storage, and I/O.
     Freeze datatype, stored rate, usable channel width, scaling, rounding,
     clipping, and derivation policy as the baseline appliance profile.
     Narrower derivations cannot evaluate bandwidth already discarded by the
     stored source, so wider experimental evidence must be collected before
     this decision if widths above the current retained band remain candidates.

12. **Appliance promotion and shadow operation.** Upgrade the appliance to the
    accepted direct pipeline only after full target-Pi acceptance. Continue to
    run a qualified recent fldigi sequentially on received broadcasts and
    retain versioned comparison results. Material real-world disagreements
    become reviewed corpus-admission candidates and may drive later decoder
    iterations. The fldigi path remains available during the shadow period
    until a separate operational decision retires it.

Fldigi qualification is recurring work throughout Sessions 10-12. An upgrade
first runs controlled smoke and current-appliance compatibility checks on the
Raspberry Pi, then a
checked-in repeatable workflow re-decodes all dependent corpus artifacts
without overwriting older results. Archive decoder version/build identity,
platform/configuration, corpus revision, input hashes, outputs, detailed
scorecards, the overall planning index, and known anomalies. The product gate
normally uses the newest qualified version; pinned and historical versions
remain reproducibility and moving-target evidence.

New Airspy development/reference captures should preserve the channelized
CF32 evidence before final storage quantization, once the experimental profile
passes short hardware and pipeline validation. Existing CI16 captures remain
valid evidence. Periodic RTL-SDR captures made with the available good antenna
broaden the corpus but are not matched Airspy/RTL experiments. Direct and
fldigi results are comparable within the same immutable capture; differences
between captures from different radios remain confounded by propagation and
must not be presented as receiver-quality comparisons. Accuracy and pipeline
regressions report Airspy and RTL subsets so Airspy-oriented improvements do
not silently sacrifice the supported entry-level path.

Fixture preparation is therefore a deliberate session. It occurs twice for
different purposes: controlled fldigi IQ is prepared early to prove known
happy paths, while received-IQ cuts are prepared later after the working
pipeline reveals the history, transition context, and diagnostics they must
retain.
