# MFSK IQ Decode Design-Specification Guidelines

## 1. Purpose

The MFSK IQ decode design specification will define how Radiogram can directly
decode MFSK32 text, MFSK64 text, and MFSK pictures from IQ recordings. It will
use the completed wire-protocol investigation as its protocol authority while
remaining independent of any single decoder architecture.

The design specification should cover:

- required decoder capabilities;
- candidate processing-block contracts;
- shared information and coordinate models;
- alternative complete pipeline organizations;
- validation and corpus requirements;
- implementation phasing;
- operational integration; and
- unresolved decisions and risks.

The specification must not assume that independently testable capabilities
become separate sequential runtime passes. A production design may fuse
capabilities, share analysis, retain state across boundaries, operate over
bounded windows, use non-causal look-ahead, or materialize no intermediate
files.

The intended progression is:

```text
capabilities
    -> candidate processing-block contracts
        -> alternative complete pipelines
            -> evidence-based implementation phases
```

## 2. Goals and Acceptance Criteria

State the intended product outcomes before selecting algorithms or a pipeline.
At minimum, address:

- MFSK32 and MFSK64 text decoding;
- MFSK64 grayscale and color picture decoding;
- RSID-driven mode recognition and segmentation;
- text-to-picture, picture-to-text, and inter-mode transitions;
- compatibility with the fldigi behavior defined in `mfsk_wire_spec.md`;
- decoding accuracy under representative received-signal conditions;
- performance faster than real time where practical;
- use of offline look-ahead where it materially improves accuracy;
- memory use and bounded-window feasibility;
- future streaming feasibility without making it an initial hard constraint;
- preservation of information needed for multi-transmission alignment and
  voting;
- Python, NumPy, and justified SciPy use;
- portability concerns, including potential future Android constraints; and
- coexistence with the current Radiogram pipeline until standalone acceptance.

Define measurable acceptance criteria where evidence permits. When thresholds
depend on corpus analysis or experiments not yet performed, identify the
measurement and decision process rather than inventing a value.

## 3. Input and Output Contracts

Define the externally observable contract of the decoder tool independently of
its internal organization.

### 3.1 Inputs

Address:

- supported IQ representations and sample data types;
- sample rate and center-frequency metadata;
- sideband and frequency-orientation conventions;
- recording start time and source provenance;
- permissible missing or uncertain metadata;
- full-recording, segment, and bounded-window inputs;
- channel-selection and expected-signal hints;
- optional prior RSID or schedule information; and
- validation and rejection of inconsistent inputs.

### 3.2 Outputs

Address:

- decoded text and control-character treatment;
- image dimensions, color mode, component speed, and raster data;
- detected modes and segment boundaries;
- original-IQ sample positions for significant events;
- frequency, timing, and drift estimates;
- confidence, likelihood, erasure, and damage information;
- warnings, recoverable errors, and terminal failures;
- machine-readable diagnostics;
- human-oriented summaries; and
- provenance linking outputs to input intervals and decoder configuration.

The output contract should distinguish an estimated transmitted event position
from the later sample or processing time at which the decoder recognizes that
event.

## 4. Capability Model

Capabilities describe what the decoder must be able to accomplish. They are
not, by themselves, a runtime block diagram.

The specification should evaluate at least these capabilities:

1. IQ and metadata validation.
2. Input normalization and sample-format conversion.
3. Signal-presence and candidate-region detection.
4. RSID detection and mode segmentation.
5. Coarse carrier and occupied-band estimation.
6. Fine carrier-offset estimation.
7. Frequency-drift estimation and tracking.
8. Band isolation, frequency translation, or channelization.
9. Symbol-clock acquisition and tracking.
10. MFSK tone observation.
11. Soft symbol-evidence or tone-likelihood production.
12. Hard symbol decisions where needed.
13. Diagonal deinterleaving.
14. Viterbi and convolutional-code recovery.
15. Varicode boundary detection and octet recovery.
16. Text framing and control-character handling.
17. Picture-header recognition.
18. Text-to-picture transition alignment.
19. Picture-raster frequency and intensity estimation.
20. Grayscale and color image assembly.
21. Picture completion and return-to-text acquisition.
22. Reset, resynchronization, and recovery after damage.
23. Confidence and erasure propagation.
24. Multi-transmission alignment and voting support.
25. Artifact, trace, metric, and diagnostic production.

The specification may combine, divide, or add capabilities as analysis
requires. It should explain to the PM any material changes to 
this initial inventory.

## 5. Candidate Processing-Block Contracts

The design specification needs more detail than a capability summary but must
avoid prematurely fixing a sequential pipeline. For each capability, define
one or more candidate processing-block contracts.

A capability states what must be possible. A processing block describes a
contract by which that capability could participate in a design. One block may
serve several capabilities, and one capability may have multiple candidate
block forms.

For every candidate block, document:

- purpose and responsibilities;
- required inputs;
- produced information;
- data types, units, coordinate systems, and array shapes;
- state retained between calls or windows;
- required history and look-ahead;
- initialization and reset conditions;
- synchronization and reacquisition behavior;
- uncertainty, confidence, or likelihood representation;
- information that must not be discarded;
- expected failure and degradation modes;
- batch, bounded-window, and streaming compatibility;
- computational complexity and likely vectorization;
- memory characteristics;
- candidate algorithms and library dependencies;
- independently testable behavior;
- diagnostics needed to validate it; and
- opportunities and tradeoffs for fusion with adjacent blocks.

Processing-block contracts are analytical tools. They do not require the
implementation to expose each block as a public API, separate pass, process, or
materialized intermediate artifact. They should not strictly assume that 
they consume samples and output augmented samples. Depending on the pipeline 
they might, for example, produce a map that allows subsequent processing to 
interpret existing samples.


## 6. Shared Evidence Model

Define how information is represented and preserved across capabilities and
candidate pipelines. Pipeline comparisons are not meaningful unless they state
which evidence they retain, transform, summarize, or discard.

The shared model should consider:

- original-IQ sample positions;
- transformed or resampled sample positions;
- time intervals and uncertainty;
- absolute and carrier-relative frequencies;
- frequency estimates and uncertainty;
- symbol timing, phase, and timing uncertainty;
- per-tone energy or likelihood vectors;
- hard decisions and their supporting soft evidence;
- erasures and damaged intervals;
- competing mode or segmentation hypotheses;
- FEC path metrics;
- decoded-octet provenance;
- picture-component confidence;
- transition hypotheses;
- state checkpoints; and
- relationships among outputs from repeated transmissions.

The specification should identify the minimum evidence that must survive each
boundary to support downstream refinement, diagnostics, and future
multi-transmission voting.

## 7. State and Coordinate Model

Define coordinate and state conventions before designing pipelines. At minimum,
cover:

- the authoritative original-IQ sample coordinate;
- mappings through trimming, filtering, resampling, and delay compensation;
- interval endpoint and rounding conventions;
- original versus corrected time;
- absolute, tuned, baseband, and carrier-relative frequency;
- normal and reverse frequency orientation;
- segment and mode-transition boundaries;
- estimated wire-event positions versus decoder-recognition latency;
- state initialization and warm-up;
- state checkpointing and restoration;
- reset and resynchronization;
- history required before a requested output interval; and
- look-ahead required after it.

Every processing block that changes coordinates must provide a mapping back to
the original IQ. Approximate mappings must include their uncertainty and
rounding behavior.

## 8. Pipeline Alternatives

Construct and compare multiple complete pipeline organizations from the
capabilities and candidate block contracts. Do not select a design merely
because it resembles the existing sequential `iqprep` implementation.

Pipeline candidates should include, where credible:

- a staged batch pipeline;
- a fused or heavily vectorized batch decoder;
- a bounded-window or chunked pipeline;
- a streamable pipeline that would not require an iq capture to be complete;
- a hybrid fast path with targeted refinement around uncertain regions; and
- a non-causal offline approach that revisits acquisition, tracking, or
  transitions using later evidence.

For every complete alternative, evaluate:

- any impact on decoding accuracy;
- acquisition and recovery behavior;
- information preserved and discarded;
- runtime and vectorization potential;
- memory consumption;
- latency;
- window-boundary behavior;
- state complexity;
- testability and diagnostic visibility;
- implementation complexity and risk;
- dependency and portability implications;
- reuse of validated `iqprep` assets;
- suitability for text, pictures, and transitions; and
- suitability for future multi-transmission alignment and voting.

Explicitly identify shared computations. Avoid pipeline descriptions that
silently repeat expensive transforms, filtering, spectral analysis, or timing
estimation.

## 9. Algorithm Decision Points

Some algorithm choices should remain open until experiments provide evidence.
The specification should identify these decisions, their alternatives, and how
they will be resolved.

Possible decision points include:

- FFT filter bank, sliding DFT, Goertzel, matched correlators, or other tone
  estimators;
- resampling versus timing-phase evaluation at the original rate;
- explicit frequency correction versus carrier-relative tone models;
- global, piecewise, or continuously tracked drift models;
- independent versus joint carrier and symbol-clock estimation;
- hard versus soft synchronization;
- hard tones versus per-tone likelihoods;
- Viterbi traceback and confidence strategies;
- single-hypothesis versus limited multi-hypothesis transitions;
- raster estimation from instantaneous frequency versus local correlation;
- full-record processing versus bounded-window refinement; and
- CPU, memory, portability, and dependency tradeoffs.

For each decision, record:

- competing options;
- anticipated benefits and risks;
- evidence required;
- fixture or benchmark requirements;
- decision deadline or implementation phase; and
- what remains reversible after the decision.

## 10. Validation and Corpus Requirements

Derive corpus composition from capability and pipeline contracts. Do not cut
fixtures merely because a convenient signal is visible at a location.

The specification should determine:

- which capability or pipeline behavior each fixture validates;
- required lead-in, trailing context, and state history;
- required mode and transition context;
- annotation events and their precision;
- coordinate system used by annotations;
- expected outputs and tolerances;
- damaged cases and expected recovery behavior;
- performance-measurement intervals; and
- whether a fixture may be shortened without changing the tested behavior.

Use the appropriate evidence class:

1. Independently fixed protocol vectors for deterministic logical behavior.
2. Pinned fldigi audio or analytic-IQ fixtures for controlled wire behavior.
3. Synthetic IQ for narrow DSP conditions requiring exact control.
4. Controlled impairments applied to genuine received IQ.
5. Short untouched received-IQ fixtures for development and diagnostics.
6. Full untouched transmissions for end-to-end accuracy, images, transitions,
   runtime, and memory acceptance.

Received IQ validates acquisition, tracking, interference tolerance,
transport robustness, and end-to-end interoperability. It must not redefine
nominal wire parameters already established by the wire specification.

## 11. Implementation Phasing

Phase implementation around risk retirement and usable vertical capability,
not simply around constructing processing blocks in presumed pipeline order.

For each phase, specify:

- questions and risks addressed;
- minimum implementation scope;
- supported modes and content;
- artifacts and diagnostics produced;
- fixtures and test classes;
- accuracy and performance measurements;
- exit criteria;
- decisions made at completion; and
- decisions deliberately deferred.

An early phase may use MFSK32 as a simpler technical checkpoint, but MFSK32
alone is not a useful project outcome. The implementation plan should reach a
meaningful MFSK64 text-and-picture vertical slice early enough to expose
transition, image, accuracy, and performance risks.

Possible phase categories include:

1. Contract and vector harness.
2. Initial vertical text decode.
3. MFSK64 acquisition and robust text decode.
4. Picture transition and raster vertical slice.
5. Tracking, damaged-signal recovery, and confidence propagation.
6. Pipeline optimization and bounded-window behavior.
7. Real-corpus and full-transmission acceptance.
8. Multi-transmission alignment and voting preparation or implementation.

These are categories to evaluate, not a predetermined schedule.

## 12. Operational Integration

The design should remain a separate tool with its own contracts until it is
validated. Address:

- package organization under `src`;
- the command-line wrapper;
- configuration and defaults;
- machine-readable output formats;
- optional diagnostic artifacts;
- use and adaptation of `iqprep` building blocks;
- dependencies and deployment on the Pi;
- temporary storage and memory limits;
- deterministic and repeatable execution;
- performance instrumentation;
- coexistence with the current fldigi-based path; and
- criteria for later pipeline integration or replacement.

Do not make production integration a prerequisite for proving the standalone
decoder.

## 13. Risks, Assumptions, and Decision Log

Maintain an explicit decision log within or beside the design specification.
For each material issue, record:

- the question;
- current assumptions;
- alternatives;
- evidence already available;
- additional evidence required;
- impact of a wrong choice;
- phase by which the decision is needed; and
- final decision and rationale when resolved.

Important initial risks include:

- premature conversion of capability boundaries into sequential passes;
- loss of soft evidence needed by FEC or later refinement;
- loss of original-IQ coordinate traceability;
- insufficient context in short fixtures;
- repeated expensive signal analysis across blocks;
- algorithms that are accurate but too slow or memory-intensive;
- early hard decisions that prevent recovery after fades;
- dependency choices that impede future portability;
- overfitting to clean fldigi-derived fixtures; and
- delaying MFSK64 picture work behind an MFSK32-only implementation.

## 14. Relationship to Existing Artifacts

The design specification should treat these as inputs:

- `direct_decode.md` for project intent, methodology, evidence hierarchy, and
  phase boundaries;
- `mfsk_wire_spec.md` for the normative MFSK32, MFSK64, and picture wire
  behavior;
- `mfsk_wire_vectors.json` for fixed coding, interleaving, timing, framing, and
  picture vectors;
- `mfsk_varicode.json` for the complete Varicode table;
- `mfsk_fixture_evidence.json` for controlled-fixture provenance and measured
  outcomes;
- the existing `iqprep` specifications, implementation, tests, and experiment
  results for reusable capabilities and lessons; and
- the existing RSID implementation and evidence, which should be referenced
  rather than independently reinvented.

The design specification may challenge implementation choices in existing
tools, but it should not silently change established wire-protocol facts.

## 15. Completion Standard

The design specification is ready to guide implementation when:

- all required capabilities have observable contracts;
- candidate processing blocks describe required information, state, and
  failure behavior;
- shared evidence and coordinate models are explicit;
- multiple complete pipeline organizations have been compared;
- significant algorithm decisions have an evidence plan;
- corpus and annotation requirements follow from the proposed designs;
- implementation phases retire the largest risks and reach MFSK64 pictures
  early enough;
- operational boundaries and integration criteria are defined; and
- unresolved decisions are visible, owned by a phase, and do not silently
  constrain the architecture.
