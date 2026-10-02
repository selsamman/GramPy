# Session 8 external qualification evidence

**Disposition (2026-10-01): not qualified; Session 9 required.** The corrected
whole-WAV matrix has five passing cases and three failing picture cases. All
mode acquisitions, ordered text, announcements, and post-picture text pass.
All seven recovered images have correct dimensions but incorrect pixels.
No encoder or decoder implementation changed during this session.

| Concrete whole-WAV case | Acquisition and text | Picture pixels | Result |
| --- | --- | --- | --- |
| MFSK32 initial | Pass | — | Pass |
| MFSK64 extended initial | Pass | — | Pass |
| MFSK32 → MFSK64, no editorial gap | Pass | — | Pass |
| MFSK64 → MFSK32, no editorial gap | Pass | — | Pass |
| Repeated MFSK32, new carrier | Pass | — | Pass |
| Mixed audio/silence/MFSK32/MFSK64/color p8 | Pass | Fail | Fail |
| MFSK32 grayscale p8/p4/p2 | Pass | Fail at all speeds | Fail |
| MFSK64 RGB p8/p4/p2 | Pass | Fail at all speeds | Fail |

The receiver was pinned fldigi 4.2.13, binary SHA-256
`dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3`.
The installed candidate wheel SHA-256 is
`b0ff517be6daa4bc32afac0ac2b5914ca1eeedb785d3f28a5b72be24f09834a1`.
The generated WAV hashes are identical across both attempts. Inputs and
candidate identities are bound in [summary.json](summary.json).

- [Corrected qualification manifest](attempt2/qualification-manifest.json)
  and [schema validation](attempt2/schema-validation.json).
- [Initial harness-failure manifest](attempt1/qualification-manifest.json),
  corrected only for failure reporting/classification. Its
  [original manifest](attempt1/qualification-manifest-original.json) and
  [original schema failure](attempt1/schema-validation-original.json) remain
  preserved. Initial `AUDIOIO=3` was incompatible with ALSA-loopback replay;
  the corrected run uses the adapter's `AUDIOIO=1` and default device fields.
- [Corrected authoritative Pi wrapper result](pi-result.md),
  [initial authoritative result](pi-result-attempt1.md), and
  [focused validation result](final-score-result.md). The corrected run took
  538 seconds. Eighteen focused tests passed.
- [Candidate-set visual review](attempt2/visual-review/candidate-set-review.png)
  and [coupled diagnostic results](attempt2/visual-review/diagnostic-results.json).
  There is no accepted encoder output baseline for this new feature. The
  GramPy column uses known segment boundaries and carrier hints, and does not
  establish external acceptance. The fldigi grayscale p8 artifact is black;
  other artifacts show substantial shifts, changed colors, or missing content.
- [Pinned receiver raster source excerpt](raster-source.log) and
  [RSID apply source excerpt](receiver-source.log). Queued GUI pixel updates
  followed by direct PNG saving suggest an artifact-save race. This remains
  a hypothesis; raster acquisition/filter behavior is also unresolved.

Each attempt's `cases/` directory retains receiver logs, metadata, starting
configuration, decoded text, encoder results with integer coordinates,
compositions, adapter commands, and recovered images. The complete evidence
roots, including generated WAVs, distribution, receiver binary, full adapter
bundles, and diagnostics, remain deliberately preserved at
`.local/session8/attempt1/` and `.local/session8/evidence/`. Their transferred
Pi copies are also preserved; see each `execution.log` for its location.
This checked-in evidence subset is not a replacement for those complete
artifact roots. Manifest paths are relative to the complete root.

Both final manifests validate against the amended v2 reporting schema. Exact
artifact hashes, full-WAV intervals, case coverage, summary totals, and
zero-manual-change invariants were separately verified. Failure reporting
permits zero detected events; a passing case still requires successful runs,
detected events, passing checks, and no discrepancies. Attempt 1 discrepancies
are automation failures. Corrected picture discrepancies are unresolved.

Observed receiver mode/carrier transitions provide acquisition evidence. The
manifest's identifier codes are standardized codes of those observed modes;
RPC polling does not separately expose the raw escape/secondary detector
words. The pinned `apply` source selects MFSK64 through its extended identifier
table. Carrier estimates differ from nominal by -1 to +4 Hz, consistent with
the source's 11025/2048-Hz detector grid. The scorer's 6-Hz comparison is
receiver-acquisition corroboration; native frequency placement is checked
independently against exact RSID PCM, without that tolerance.

Session 9 should compare identical small images from the pinned transmitter,
distinguish autosaved PNGs from the fully updated viewer, and then isolate
raster timing/filter delay. It must retain all contractual picture speeds,
preserve this evidence, and confirm a corrective decision before changing
production behavior. See [the closeout](../../mfsk_wav_encoder_change.md) and
[workflow instructions](../../../../experiments/mfsk-wav-encoder/README.md).
