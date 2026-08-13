Direct MFSK and FLDigi Image Decoder Roadmap

Existing foundation

The current Python NumPy/SciPy pipeline already provides:

* RTL-SDR IQ ingestion
* channel extraction and resampling
* carrier-frequency alignment
* frequency-drift correction
* MFSK tonal-center alignment
* tonal-center drift correction
* RSID detection and target-mode identification

The new decoder should consume the corrected IQ directly. USB audio generation and FLDigi remain available only as a reference path.

corrected IQ
├── direct MFSK decoder
├── direct FLDigi image decoder
└── USB demodulation → FLDigi reference output

Phase 1: Gather specifications

Use the published MFSK specification as the primary authority for:

* tone count and spacing
* symbol duration
* tone-to-bit mapping
* Gray coding
* convolutional coding
* interleaving
* varicode
* mode-specific parameters

Use FLDigi source only to resolve ambiguities or interoperability details.

For FLDigi images:

1. Gather the public image-mode documentation.
2. Have Codex inspect only the FLDigi image transmit and receive paths.
3. Produce a concise behavioral specification covering:
    * image-header syntax
    * transition delay
    * frequency-to-intensity mapping
    * grayscale and color ordering
    * pixel rate
    * image start and end behavior
    * return to text reception
    * receiver filtering and sampling behavior

Every source-derived rule should identify the relevant FLDigi file, function, and constant.

Phase 2: Write the implementation specification

Before coding, define:

* corrected-IQ input contract
* internal sample rate
* mode-parameter structure
* tone detector
* symbol-timing recovery
* soft-decision representation
* deinterleaver
* Viterbi decoder
* varicode parser
* text and image receiver state machine
* image FM discriminator
* image pixel clock and raster assembly
* diagnostic outputs
* reset and mode-change behavior

Peer-review this document for protocol correctness and engineering coherence.

Phase 3: Implement one MFSK mode

Start with MFSK32.

Implement:

corrected IQ
→ tone filter bank or correlators
→ symbol timing
→ per-tone soft metrics
→ Gray/bit soft metrics
→ deinterleaving
→ Viterbi decoding
→ varicode parsing
→ decoded text

Keep each stage independently testable.

Required diagnostics:

* absolute sample position
* selected symbol phase
* energy for every tone
* winning and second-place tones
* confidence metric
* soft-bit metrics
* Viterbi path metric
* decoded bitstream
* decoded characters

Phase 4: Validate text decoding

Use existing IQ recordings as the primary corpus.

For each recording, compare:

corrected IQ → direct decoder
corrected IQ → USB/Lua → FLDigi

Validate:

* exact text where reception is clean
* behavior during fades and dropouts
* mode initialization after RSID
* startup latency
* recovery after corrupted symbols
* agreement with FLDigi where FLDigi is clearly correct

Use synthetic signals only for narrow unit tests of individual stages.

Phase 5: Implement image-header handling

Extend the decoded-text parser to recognize FLDigi image announcements such as:

Pic:WWWxHHH;
Pic:WWWxHHHC;

The parser should produce an image descriptor containing:

* width
* height
* grayscale or color
* exact corrected-IQ sample position associated with the completed header

The decoder coordinator then schedules the transition into image reception using the documented or source-derived delay.

Phase 6: Implement FLDigi image reception

The image payload branches directly from corrected IQ rather than from the MFSK FEC path.

Implement:

corrected IQ
→ image-channel filtering
→ instantaneous-frequency discriminator
→ frequency-to-intensity mapping
→ pixel-clock sampling
→ grayscale or color component assembly
→ raster image

Support one image format first, preferably the format most common in Shortwave Radiogram recordings.

Required diagnostics:

* image-start sample
* discriminator frequency
* unscaled pixel estimate
* final 0–255 intensity
* pixel and line indices
* accumulated timing error
* expected versus observed image duration

Phase 7: Validate image decoding

Compare the direct decoder with images produced by FLDigi from the same corrected IQ.

Evaluate:

* dimensions
* starting alignment
* horizontal and vertical geometry
* image slant
* grayscale range
* color-channel order
* pixel-level differences
* behavior during dropouts
* transition back to text

Do not require pixel-perfect agreement initially. The transmitted image is an analog intensity raster, so small numeric differences may be harmless.

The acceptance target is equal or better visible reconstruction than FLDigi from the same IQ.

Phase 8: Add remaining modes

Once MFSK32 is stable:

* move all mode constants into parameter profiles
* add the other required MFSK modes
* verify interleaver and timing differences
* connect RSID results to decoder-profile selection
* test mode changes within one recording

Avoid duplicating mode-specific algorithms unless the specification genuinely requires different behavior.

Phase 9: Integration and cleanup

Integrate the direct decoder into the existing pipeline.

Final outputs should include:

* decoded text
* reconstructed images
* timestamps or source-sample positions
* selected MFSK mode
* confidence and diagnostic summary
* optional detailed trace files

Keep the FLDigi path available as a regression oracle until the direct decoder has been validated across a substantial recording corpus.

Immediate next actions

1. Add the FLDigi checkout under a gitignored reference-source directory.
2. Give Codex a narrowly scoped image-path archaeology assignment.
3. Assemble the published MFSK and FLDigi image documents.
4. Draft the implementation specification.
5. Peer-review it before generating decoder code.
6. Implement MFSK32 text reception first.
7. Add image-header detection and direct image decoding.

## Radiogram-project comments after the IQ-preprocessor and RSID work

The roadmap is directionally sound. The following comments preserve lessons
from implementing Phases 0–4 of `iqprep`, comparing against fldigi 4.2.06, and
validating RSID identification on the July 8 WRMI 15770 IQ recording. They are
inputs to the more formal design review, not yet a decoder specification.

### Clarify the existing input contract

The direct decoder should not claim responsibility for RTL-SDR ingestion or
channel extraction unless those stages are deliberately moved into its scope.
The current practical boundary is a corrected SigMF IQ pair produced by
`iqprep`, normally `ci16_le` at 48 kHz, with the desired signal translated so
its received center is approximately 1500 Hz and its estimated drift is
flattened. Capture, decimation, and DC-dodge tuning remain upstream concerns.

The decoder must consume SigMF annotations as provenance rather than treating
them as perfect truth. In particular, center estimates, RSID timing, mode,
confidence, and codeword distance are measured values with uncertainty. Every
decoder output and trace should retain both output-relative and original-input
sample positions so results can be aligned with the fldigi reference path.

### Add an oracle-and-fixture phase before decoder implementation

Before implementing MFSK32, build a repeatable differential harness around the
exact fldigi version used by the production/reference path (currently 4.2.06).
The RSID investigation showed that final text or mode output is not sufficient
for diagnosis. Temporary fldigi instrumentation should be able to emit, for a
short selected interval:

* input sample position and modem symbol timing;
* per-tone energies or metrics;
* winning tone and runner-up;
* deinterleaver input and output;
* convolutional/Viterbi input metrics and decoded bits;
* varicode boundaries and emitted characters;
* image-state transitions and pixel-clock state when image work begins.

This instrumentation is a development oracle, not production code. Pin the
source revision and record any patch used to produce traces. Start with short
WRMI clips around known clean text and mode transitions; reserve full-broadcast
runs for integration acceptance.

### Do not allow self-consistent synthetic tests to be the only authority

Synthetic signals remain essential because they are fast and permit controlled
timing error, frequency error, fading, noise, and bit corruption. However, each
coding layer must also have independently fixed vectors from a published
specification, fldigi, or another implementation. The first RSID encoder and
its synthetic fixture shared the wrong GF(16) polynomial (`0x13` rather than
fldigi's `0x19`), so all synthetic tests passed while real codewords failed.

For native MFSK work, independently preserve vectors for at least:

* tone-number to coded-bit/Gray mapping;
* interleaver permutations and reset state;
* convolutional encoder output and puncturing, if applicable;
* soft-input Viterbi results, including erasures and ties;
* varicode bit patterns and character boundaries;
* complete short over-the-air tone-to-text examples.

Fixture generation and decoder implementation should not silently share the
same helper functions for the property being tested.

### Keep symbol extraction and protocol interpretation separate

The decoder stages proposed in Phase 3 are the right general decomposition, but
their interfaces should be explicit and serializable. A useful working split is:

```text
corrected complex IQ
→ channel filtering / level normalization
→ residual-center and symbol-clock tracking
→ per-symbol tone likelihoods
→ tone/Gray-to-soft-bit mapping
→ deinterleaving
→ FEC/Viterbi decoding
→ varicode/framing
→ text events and image-control events
```

The RSID failure occurred after correct tone extraction: the tone sequence was
interpreted with the wrong finite-field arithmetic. A future MFSK failure must
likewise be attributable to a specific stage rather than appearing only as bad
text. Preserve soft metrics as long as possible; avoid reducing them to hard
tone or bit decisions before the FEC layer requires it. Define how low-confidence
symbols become erasures or weak metrics rather than inventing behavior later.

### Treat synchronization and reset behavior as first-class design work

Nominal baud rate and corrected center do not eliminate synchronization. The
implementation specification should define acquisition and tracking of:

* residual carrier/center error after `iqprep`;
* symbol phase and clock drift;
* filter and interleaver latency;
* FEC traceback latency;
* startup state when entering in the middle of a transmission;
* state reset at RSID, mode change, image transition, dropout, and reacquisition.

RSID already demonstrates that mode control is stateful: MFSK64 is identified
by escape code 6, a defined silent gap, and secondary code 620. The coordinator
should consume validated RSID events through an explicit state machine and
should not change mode solely because a single spectral pattern looks plausible.

### Use both small real-corpus regressions and full-decode acceptance

The testing pyramid should contain three distinct levels:

1. tiny deterministic unit vectors for individual DSP and coding stages;
2. short real-IQ corpus windows with exact intermediate and final expectations;
3. full WRMI broadcast decoding for text, images, mode transitions, and recovery.

The RSID regression uses only seconds 523–551 of the July 8 recording yet proves
the real escape/secondary MFSK64 path. Native MFSK development should follow the
same pattern: extract the smallest clean interval that exercises one behavior,
then retain the full broadcast as the end-to-end acceptance test.

Comparisons with fldigi should distinguish three cases: both agree; the direct
decoder is demonstrably better; or the reference is ambiguous because reception
is damaged. Do not automatically make fldigi's final text ground truth when the
intermediate signal evidence shows that fldigi was wrong.

### Refine the image acceptance goals

Visible equality is a reasonable first image milestone, but it may not be the
ultimate acceptance condition for this project. The longer-term steganographic
and Reed–Solomon payload work may require highly repeatable or bit-accurate pixel
recovery. The formal plan should therefore separate milestones:

1. correct header, dimensions, channel order, raster geometry, and visibly good
   reconstruction;
2. quantified pixel differences against fldigi and controlled transmitted
   images;
3. recovery accuracy sufficient for the embedded payload/error-correction use
   case.

Confirm image announcement syntax, transition delay, pixel rate, discriminator
mapping, color ordering, and return-to-text behavior from the pinned fldigi
source before making the examples in this roadmap normative. Image reception
should branch from the corrected signal at the documented transition point, but
the transition event itself will normally originate in decoded MFSK text.

### Recommended order for the formal follow-on project

For the next-session design work, a slightly refined order is recommended:

1. freeze the corrected-IQ and annotation input contract;
2. document MFSK32 parameters from primary specifications and fldigi 4.2.06;
3. build the fldigi intermediate-trace oracle and select one clean WRMI text
   clip;
4. define serializable interfaces and diagnostics for every receiver stage;
5. assemble independent coding vectors before writing the matching decoder
   stage;
6. implement and validate MFSK32 incrementally through exact text;
7. add the text/image coordinator and source-derived image behavioral spec;
8. implement one common image format and progress through the staged image
   acceptance goals;
9. parameterize MFSK64 and other required modes only after the shared pipeline
   is stable;
10. retain fldigi as a regression oracle until a substantial real corpus and
    full-broadcast acceptance suite pass consistently.

This work remains a substantial multi-session project, but the RSID exercise
increases confidence in feasibility: corrected real IQ yielded exact RSID tone
sequences, fldigi could be instrumented as an effective independent oracle, and
the failure was isolated cleanly at the protocol-interpretation layer. It also
reinforces that progress should be measured stage by stage rather than by
attempting a complete decoder in one implementation pass.
