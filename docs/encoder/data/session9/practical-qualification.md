# Practical broadcast qualification — D-027

The PM explicitly directs a separate qualification using broadcast-sized
pictures, the Pi harness, and numerical screening followed by PM visual review.
Tiny-picture failures and fresh fldigi transmitter calibration are no longer
prerequisites. Their earlier evidence is retained. This run evaluates the
unchanged candidate; it makes no production encoder or decoder changes.

The [v3 matrix](../mfsk_encoder_pi_matrix_v3.json) was frozen before generating
or scoring the new outputs. The provisional engineering limits are:

- raw mean absolute component error ≤25 on the 0–255 intensity scale;
- aligned mean error ≤20, absolute channel bias ≤15;
- bounded alignment compensation ≤12 components and ≤12 offset changes;
- correct picture count and dimensions, ordered caller text and picture
  announcements, complete playback, and automatic mode/carrier acquisition.

These margins are a practical screen informed by the prior useful normal-sized
controls. They are not a calibrated universal standard or a promise that every
picture of this size will work. Source and received images remain visible at
their original coordinates. PM may reject slant, missing regions, wrong colours
or unacceptable blur despite passing averages. Pixel equality is still reported
as a diagnostic, while transmitted protocol/waveform checks remain exact.

The source set comprises two photographic images from the established broadcast
truth corpus, copied and fitted by the caller to 240×180 without modifying the
corpus, plus the previously reviewed 160×120 chart. Source hashes and caller
preprocessing are recorded. Ten complete WAVs cover grayscale and RGB at p8,
p4 and p2, plus a broadcast containing MFSK32 news text, copied audio, explicit
silence and an MFSK64 photograph at a new carrier.

Seven MFSK64 picture cases exercise both receivers. The accepted GramPy public
auto-mode decoder currently supports MFSK64 pictures; three additional MFSK32
grayscale cases therefore exercise fldigi picture interoperability and GramPy
text recovery, with that limitation explicitly reported. They cannot establish
GramPy production MFSK32 picture support.

GramPy receives an analytic IQ conversion of the entire untrimmed WAV through
`decode_iq_products`, using accepted defaults and no supplied mode, carrier,
picture start or encoder coordinates. This replaces the earlier coupled
picture-only diagnostic as the qualification path. Pi fldigi starts in BPSK31
with RxID enabled, AFC disabled and five-second polling; it plays the entire
WAV, settles for 15 seconds, and retains both the autosaved image and the
completed viewer buffer. The read-only viewer snapshot occurs after playback.

Preparation completed in ten seconds. All ten raster/prologue waveforms match
the independent source-derived recipe within 0.500–0.532 signed-PCM units and
reject a deliberate frequency mutation. Independent RSID PCM, copied audio,
explicit silence and returned frame coordinates pass. Five focused tests verify
that the quality gate rejects blank pictures, wrong geometry, excessive bias
and reordered/missing text, while allowing modest non-exact output.

The complete public GramPy run finished in 50 seconds. Pi reception finished
successfully in 1,130 seconds including transfer and retained-evidence return.
Final scoring completed in 34 seconds: **10/10 cases pass the frozen functional
and numerical screen**. All 40 retained production source hashes remain
unchanged. The first preparation attempt used a positional call
to a keyword-only API; it stopped before WAV generation and is retained with
its corrected retry. This is an experiment-script error, not an encoder failure.

Session 8's five successful text/acquisition cases remain applicable to the
unchanged candidate. This additional run replaces the tiny-picture acceptance
gate for the PM's practical scope, rather than rewriting the old v2 results.

## Result and subsequent PM decision

**Scope wording clarification (2026-10-03):** “outside production scope” in the
initial review was too broad. The automatic-mode public pipeline used here
decodes MFSK64 pictures and skips MFSK32 pictures. A fixed-mode public MFSK32
picture path exists, but was not exercised by these qualification cases.
Accordingly, the three MFSK32 rows establish fldigi picture recovery and
GramPy text recovery only. The human review labels are clarified; the frozen
matrix, raw evidence and numerical records remain unchanged.

[The portable visual review](practical-review/index.html) shows source, GramPy
and pinned Pi fldigi at native size with optional enlargement. The
[score table](practical-review/scores.md), [full qualification record](practical-review/qualification.json)
and [independent evidence/visual inspection](practical-review/inspection.json)
retain the details.

All ten Pi cases recover the expected modes/carriers, caller text, announcements,
one correctly sized picture and following text from the complete WAV. All ten
autosaves equal the completed viewer pixels; collection is working for this
set. All seven supported GramPy picture cases also recover complete pictures,
mode/carrier acquisition and ordered caller text. The additional MFSK32 cases
confirm GramPy text recovery only, as explicitly scoped before execution.

| Evidence | Observed range / result | Frozen limit |
| --- | --- | --- |
| Pi fldigi raw picture MAE | 0.604–14.108 /255 | ≤25 |
| Public GramPy raw picture MAE, seven supported cases | 0.357–11.315 /255 | ≤25 |
| Pi aligned picture MAE | 0.604–12.528 /255 | ≤20 |
| Exact transmitted raster/prologue, RSID, copied audio and silence | All checks pass | Retained exact checks |
| Saved image versus completed Pi viewer | 10/10 identical | Correct collection and geometry |

The first evaluation incorrectly checked summary octets for framing. Both
GramPy summary text and summary octets intentionally omit control characters;
canonical `text_events` retain them. That report is preserved in
`.local/session9/practical/evaluation-attempt1`; correcting the evaluator and
adding a regression check yields 10/10 passes with identical picture scores,
unchanged raw receive evidence and unchanged thresholds. Six focused gate/
protocol-reporting tests now pass. This was a reporting fault, not missing
encoder framing or a decoder failure.

**Agent visual assessment:** the photographs preserve credible subject detail,
colour and geometry. The p2 charts show blur, fine-text degradation and edge
ringing, most apparent in MFSK32 p2. The mixed-broadcast fldigi photograph has
a thin coloured strip at its left edge and slight horizontal registration
shift: raw MAE 5.714, aligned MAE 1.689. These are visible limits for PM review;
passing averages do not erase them. No severe slant or wholesale picture
corruption appears in this set.

**Disposition, 2026-10-03:** PM has viewed and accepted all images, including
the visible limits described above and the subsequently recovered MFSK32
pictures. Practical qualification under D-027 is accepted. The separate D-028
decoder correction now recovers all three MFSK32 pictures and passes the same
gate; see its [review](../../../decoder/data/auto-mfsk32-pictures/index.html).
The [acceptance record](practical-acceptance.json) binds that subsequent
decision to both frozen qualification records. Their numerical measurements,
execution-time visual status and source identities remain unchanged.

No encoder remediation is indicated by this run. No universal minimum safe
image size, bit perfection, all-rate picture quality, or repeatability across
all possible broadcast content is claimed.
