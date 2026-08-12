# Direct MFSK Decoding 

## Objective

Directly decode text and images from IQ files in a fashion compatible with
fldigi using MFSK32, MFSK64, MFSKpic, and RSID.

Direct decoding from IQ files creates the potential for 
more accurate decoding because of the ability to look ahead. The hope is
that decoding will be faster than FlDGI which decodes in real-time. Finally 
the application will use error correction by voting over multiple transmissions.
Doing so requires alignment and the decoding can provide timing information on
decoded data that can be used for alignment in case of fades etc.

## Constraints

The implementation should use python with numpy and scipy though scipy 
should be used only when it provides a clear advantage as it may not be 
possible when the platform is ported to Andoid (see
`../product/futurePlatforms.md`)

While the ideal implementation would be something that is streamable that 
should not be a hard constraint but rather a nice to have. Still where 
possible implementing over windows of data is preferred.

fldigi is a necessary resource but it must not be used in a way that would
force adoption of its license. Therefore, use a protocol-documentation process
that records fldigi's externally observable behavior without copying its code
or prose. Source-derived rules should identify the pinned fldigi version,
source file, function, and constant from which the behavior was determined.
Keep the fldigi checkout under the ignored `.local/reference/` tree; commit
only original Radiogram specifications, vectors, and implementation.

This is a new tool and is not to disturb the existing pipeline. When it is
unit tested, decisions will be made about how to roll it into the pipeline.

The work will produce two specifications:

1. A wire-protocol specification for MFSK32, MFSK64, and MFSKpic. The
   circa-2000 MFSK16 specification and January 2001 article are the published
   baseline. The wire spec must identify where fldigi matches, extends,
   resolves an ambiguity in, or differs from that baseline. The current stable
   fldigi release is the primary interoperability reference; the version used
   by Radiogram's existing reference path is a compatibility reference.
2. An implementation specification organized around required capabilities,
   their contracts, candidate implementation techniques, and alternative
   pipeline organizations. It must not assume that the independently testable
   capability boundaries become sequential runtime passes or materialized
   intermediate files. Shared analysis, fused processing, non-causal
   look-ahead, bounded windows, and streaming options should remain possible.
   A straightforward reference pipeline should first provide a working and
   measured baseline; alternatives are then evaluated for accuracy, speed,
   memory, I/O, portability, and complexity before replacing its organization.

## Methodology

The steps are as follows:

1 Create the wire spec for MFSK32, MFSK64, and MFSKpic. While MFSK16 is
documented in
https://www.arrl.org/mfsk-spec and written about in https://www.arrl.org/files/file/Technology/tis/info/pdf/0101033.pdf
there does not appear to be a formal spec for MFSK64 or MFSKpic, so their
behavior will have to be documented from fldigi. Version-pinned controlled
fldigi fixtures and independently established vectors validate deterministic
wire behavior. Received transmissions validate later decoder interoperability
and transport robustness rather than redefine the nominal protocol.
* The spec should be a protocol rather than an implementation spec
* Should include all timing and encoding tables.
* Where fldigi differs from the arrl.org spec those differences should be noted.
* Each rule should distinguish published behavior, common behavior across the
  pinned fldigi versions, version-specific behavior, capture-confirmed behavior,
  derived values, and unresolved questions.

2 Create the implementation spec by enumerating all capabilities decoding will
require, their observable contracts, and possible implementation techniques.
Benefit from the work already done in iqprep, which covers RSID, alignment of
frequency, and tone center, without assuming iqprep's sequential implementation
is the best decoder organization.

3 Define and implement one straightforward, diagnostic reference pipeline.
Preserve the capability contracts, soft evidence, and original-IQ coordinates,
but do not attempt to select an optimal organization before measurements
exist. Validate the reference pipeline through progressively more realistic
complete-pipeline cases, culminating in received broadcasts. Instrument it for
accuracy, time to first stable result, total runtime, peak memory, bytes read,
bytes written, temporary storage, repeated sample reads, and expensive
computations.

Record alternative fused, staged, bounded-window, streaming, hybrid, and
non-causal organizations as hypotheses and likely refactoring points. Do not
fully design or select among them until the working reference pipeline provides
cost and accuracy evidence.

4 Prepare decoder fixtures in layers. Independently fixed vectors and narrow
synthetic-IQ cases remain capability tests. Pinned fldigi-generated partial
transmissions, controlled impairments, short received-broadcast intervals,
received partial broadcasts containing transitions, and complete broadcasts
must each exercise the complete applicable path from IQ through final text or
image output.

5 After the reference pipeline completes a received-broadcast baseline,
compare and prototype alternative organizations using measured evidence.
Optimize only where accuracy, time to useful results, total runtime, memory,
SD-card I/O, recovery behavior, or future product capability justifies the
additional complexity.

Do not inventory, cut, or annotate the definitive real-IQ corpus during the
wire-spec phase. The capabilities specification and reference-pipeline plan
must first identify observable contracts, required state history, processing
boundaries, and diagnostics. Those decisions may change how much lead-in,
transition context, or damaged-signal history each fixture needs. Preserve
existing full recordings in place until that work is complete.

Controlled fldigi-generated IQ preparation may occur before the definitive
received-IQ corpus is cut. These fixtures have known content and are needed to
prove complete-pipeline happy paths. Their preparation session must verify
generator isolation, provenance, hashes, expected text or raster content, and
independent measurement; it must not silently become an inventory or editing
pass over the definitive received corpus.

Real IQ is the primary interoperability and end-to-end acceptance corpus.
Synthetic IQ is limited to narrow DSP tests where an exact physical condition
must be controlled, such as symbol phase, frequency error, sample-clock error,
noise, fades, dropouts, and block boundaries. Derived real-IQ cases may apply
controlled impairments to genuine transmissions. Wire-protocol correctness
must also use independently established fixed vectors; a transmitter and
decoder based on the same interpretation must not be their own sole authority.

Shortwave Radiogram is assumed to distribute fldigi-generated audio to the
transmitting station. Under that operating model the station is a transport,
not an independent MFSK protocol implementation. Version-pinned fldigi
fixtures may therefore provide the primary evidence for deterministic wire
behavior such as coding, framing, picture headers, component order, and pixel
mapping. Received IQ confirms that actual distributed audio is compatible with
that behavior and supplies evidence for tuning offset, drift, filtering,
fading, interference, dropouts, and end-to-end decoder acceptance. It is not
necessary to re-prove every deterministic wire rule from received IQ or to
rebroadcast controlled fixtures over RF.

The evidence hierarchy is:

1. Independently fixed protocol vectors at the relevant logical boundary.
2. Narrow synthetic-IQ DSP tests.
3. Pinned fldigi-generated partial transmissions proving clean
   complete-pipeline text and picture paths.
4. Controlled impairments applied to pinned analytic IQ or genuine received
   IQ, as appropriate to the condition being tested.
5. Short, untouched received-IQ fixtures with diagnostic checkpoints.
6. Received partial broadcasts containing mode and picture transitions.
7. Full, untouched transmissions for text, images, mode changes, recovery,
   time to useful results, total runtime, memory, and I/O acceptance.

The first two classes isolate logical or DSP capabilities. Classes three
through seven provide progressively stronger complete-pipeline proof. A
capability unit test is necessary for diagnosis but is not by itself a product
milestone.

Controlled-fixture acceptance requires more than a successful generator exit.
Each fixture must record the selected mode and carrier readback, pinned
generator identity, input and waveform hashes, recorder-overrun status, and an
independent decode or measurement appropriate to the claimed rule. Fixture
generation must begin from an isolated process/configuration state so a stale
fldigi XML-RPC process cannot accept commands intended for a new run.

## Phase Boundaries

The wire-spec phase produces `mfsk_wire_spec.md` and its machine-readable
companions. It does not select a decoder architecture or construct the final
received-IQ corpus.

The next phase creates and exercises the implementation specification in this
order:

1. Enumerate decoder capabilities and observable contracts.
2. Identify information that must be preserved or shared among capabilities.
3. Define a straightforward diagnostic reference pipeline and its
   instrumentation without presuming that capability boundaries must remain
   runtime passes.
4. Prepare the controlled happy-path fixtures needed for implementation, then
   implement complete vertical slices through text and pictures.
5. Use the working pipeline's context requirements to define the received-IQ
   corpus inventory, cuts, annotations, impairment cases, and acceptance
   metrics.
6. Establish a partial- and full-broadcast accuracy and operational-cost
   baseline.
7. Compare and prototype fused, staged, streaming, bounded-window, hybrid, and
   non-causal alternatives where the measurements show a worthwhile product
   benefit.

The product questions governing optimization are:

1. Can stable text or picture results be delivered before final processing
   completes, and what complexity and schedule cost would that add?
2. What are time to first useful result and total completion time, and which
   independently adoptable optimizations improve them?
3. How many bytes are read and written, especially persistent and temporary
   SD-card writes that affect storage longevity?

Whether the implementation uses chunks, sequential passes, fused processing,
or complete-region batch work is an internal design choice evaluated against
those product outcomes.

## Example Structure of Spec
The following is an organizational example, not a source of normative protocol
values. Values must be verified during the wire-spec investigation.

1. PHYSICAL LAYER (PHY)
- Define the continuous-phase frequency shift keying (CPFSK) modulation rules.
- Detail the exact mathematical relationship between the sample clock, baud rates, tone spacings, and total bandwidth for the published MFSK16 baseline and the target MFSK32 and MFSK64 modes.
- Explain the physical necessity of sample-buffer phase continuity to prevent harmonic splatter.

2. DATA LINK LAYER (DLL)
- Specify the Forward Error Correction (FEC) engine using the NASA standard
  convolutional code (Rate = 1/2, Constraint Length K = 7). State the exact
  shift-register equations and bit order because polynomial notation and
  coefficient orientation vary between sources.
- Define the structural logic and dimensions of the diagonal interleaver matrix used to disperse burst errors.
- Document the Gray code mapping rules used to translate 4-bit symbols into the 16 physical tone indices.

3. PRESENTATION LAYER
- Document the bit-level token structure of the IZ8BLY Varicode character encoding system. Provide the structural algorithm for how variable-length bit strings terminate (the '00' delimiter rule).

4. IN-BAND CONTROL & ECOSYSTEM EXTENSIONS (The fldigi Gaps)
- RSID: Reference the existing validated Radiogram RSID behavior and document
  only the mode-control relationship needed by the direct decoder. Do not
  duplicate it using unverified example parameters.
- MFSKpic: Document the exact string parsing hooks ("Pic:WWWxHHH;" and "Pic:WWWxHHHC;") that trigger the receiver's state machine to shift from Varicode text to analog-style raster pixel decoding. Define how tone frequencies map linearly to pixel intensity (Grayscale) and sequential color sub-lines (RGB).
  Use code with caution.
