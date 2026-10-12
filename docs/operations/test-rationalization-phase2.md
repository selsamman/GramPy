# Test rationalization: phase 2

Date: 2026-10-12. Status: committed as `634a563`; original validation records
below are preserved. Baseline: `12b4e92`.

## Result and scope

The missing controlled-fixture coverage is rebuilt around four versioned
recordings in `tests/samples/controlled-mfsk-v1/`. Current fixture identities
are in [`controlled-v1.json`](../../tests/fixtures/mfsk/controlled-v1.json).
Original wire-spec fixture evidence in `docs/decoder/data/` and the packaged
copy are preserved unchanged; changing their hashes would falsely associate
old measurements with new recordings.

The standard tests no longer reference `.local` for fixture input or accept a
missing required recording as a skip. The supported runner selects `unit`,
`controlled`, `received` or `all`, reports explicit selection/exclusion counts,
and fails if a selected test skips. Controlled/all runs first verify every
maintained WAV/IQ/metadata hash and the committed source image. Direct full
unittest discovery also fails on missing required inputs.

CI and generic package release explicitly select the checkout-only unit tier.
This avoids requiring private large recordings in public CI while making its
scope visible. Neither that unit tier nor this controlled fixture tier is the
real-corpus quality acceptance gate planned for phase 3.

## Independent validation before adoption

The retained candidates originated from the pinned fldigi transmitter build
at commit `b0032cabb70dc670064ed7561b9a626010a5e4ae`, binary hash
`de63a235e959e01e31ab05045fd703d59d3ee74017b64d9b254e8f48cb0d6e9c`.
Their WAVs match the retained Pi recordings and generation metadata. Candidate
inputs were not overwritten or regenerated on the Pi.

Each whole candidate WAV was independently received using the qualified fldigi
4.2.13 binary with hash
`dd30f86caae1edb5d2998acedb47a3a7b348b727bf6303af1e2f822f549966f3`.
The current adapter's hash is
`130fe71cef0bbc5585f9cdf74c423cd94999ee34720b277a09814c06d046a211`;
it differs from the older runbook's adapter, and its actual identity is recorded
rather than assumed. Fixed mode matched each controlled transmitter, RxID/AFC
were off, carrier was 1500 Hz, audio used ALSA loopback/plug, and the adapter
waited 15 seconds after playback. This is controlled-transmission validation,
not automatic mixed-mode qualification.

All four independent receivers completed successfully, recovered the known
framed text and picture announcements, and produced one readable 8x4 RGB
image for each picture case. Raw fldigi output contains control framing and
some unframed post-transmission noise; known content was verified within its
STX/EOT frame, not by treating every displayed character as payload.

All four IQ files were then reproduced **byte-for-byte** from their WAVs with:

```python
pcm = raw_int16.astype(numpy.float32) / 32768
iq = scipy.signal.hilbert(pcm).astype("<c8")
```

A double-precision cross-check differed only by at most 2.66e-7 in complex
amplitude. The historical conversion precision explains that difference; the
float32 recipe exactly matches every adopted candidate IQ file. Metadata was
made portable by replacing its original absolute WAV source path with
`transmission.wav`; the new metadata identity is deliberately recorded. IQ and
WAV bytes were preserved.

Picture timing was established using the independent source-image/WAV analyzer,
which imports no GramPy decoder. It fits the known p8 source frequencies to
the recorded signal using the committed normative PPM input.

| Picture | Independently measured raster start | GramPy start | Difference | Source-frequency RMSE |
| --- | ---: | ---: | ---: | ---: |
| Grayscale | 797149 | 797140 | -9 samples | 7.2681 Hz |
| Colour | 862072 | 862075 | +3 samples | 11.3270 Hz |

The colour waveform agrees with RGB row-plane transmission order (11.327 Hz
RMSE), while wrong pixel-interleaved and whole-image-plane interpretations are
approximately 463 and 469 Hz RMSE. These are independent waveform checks, not
values obtained by repinning GramPy's own reported coordinates.

Compact [validation evidence](data/controlled-fixture-validation.json) binds
receiver runs and artifacts to the adopted WAVs. Machine paths and raw receiver
diagnostics remain private until the phase-closeout retention pass.

## Reconstructed checks

| Purpose | Current check |
| --- | --- |
| Independent printable MFSK32/MFSK64 decoding | Exact known text/octets, mode/carrier/tone checks and available event-coordinate/framing assertions. |
| Grayscale picture transition | Header, exact geometry/components, completeness, independently measured start within the original 48-sample tolerance, and source-image pixels. |
| Colour row-plane assembly and return to text | Same independent timing/geometry checks, source-image RGB pixels, operative maintained predictor, independently measured prologue, and the original 69,120-sample return-to-text interval. |
| Bounded text integration | Both current default routes: MFSK32 overlapping bounded fallback and MFSK64 compact bounded path. Both require complete frames containing exact known printable payload and bounded materialization diagnostics. |
| Fixture availability/integrity | Strict preflight of all required WAV/IQ/metadata files and source image; no missing-data skip. |

Source-image fidelity is additional coverage that the original controlled
picture tests did not exercise. The proposed maximum pixel error is 8/255,
an explicit small-fixture engineering margin consistent with existing p8
coupled checks, not a universal received-image threshold. Observed maxima are
5 for grayscale and 8 for colour; mean errors are 1.22 and 1.18. The unchanged
48-sample timing limit corresponds to one p8 component at 48 kHz.

The old bounded test implicitly requested the default MFSK32 route but asserted
compact-path labels. It is replaced by two tests matching the maintained routing
contract. The compact path retains unframed leading noise; payload validation
uses STX/EOT framing and excludes declared NUL/CR protocol controls, as the
display/payload contract does. The MFSK32 fallback also retains its original
exact display-summary assertion. Decoder behavior was not changed to obtain
a pass.

## Installation and maintenance

[`tests/README.md`](../../tests/README.md) describes tier selection and the
portable archive, whose immutable SHA-256 is committed in the new fixture
manifest. Supply `controlled-mfsk-v1-20261012.tar.gz` with the existing samples
sidecar handoff. Verify that hash, unpack into an absent directory, and run the
controlled suite before relying on coverage.

To validate future candidate picture WAVs independently, run the checked-in
analyzer through a managed Mac batch, adding `--grayscale` for the gray case:

```sh
.venv/bin/python tools/analyze-mfsk-color-fixture \
  --wav CANDIDATE.wav --ppm tests/fixtures/mfsk/primary-color-8x4.ppm \
  --output ANALYSIS.json
```

Transmitter generation recipes and known input text are retained in
`tools/pi-generate-controlled-mfsk-fixtures.sh`; its final historical inventory
check does not accept a new bundle automatically. Independently receive the
candidate WAV with the pinned receiver using the managed Pi runbook, verify
source/content/identity and conversion, then publish a separately versioned
package and deliberate manifest update. New physical captures need not have
the old hashes or recording coordinates. Never silently repin a failed test.

New unit checks exercise missing-file and changed-file rejection and prove
that a selected suite cannot accept skipped tests. Missing original broadcast
image truth remains a scoring-policy condition, distinct from missing decoding
input. The existing scorer tests for explicitly unavailable truth remain.

## Validation checkpoint

Final validation completed with the repository virtualenv and managed Mac
wrapper:

| Check | Result |
| --- | --- |
| Freshly unpacked portable archive, controlled tier | 7 passed; no skips; 14.833 seconds. |
| Controlled tier with required inputs absent | Exit status 1 before decoding, as required. |
| Unit tier with both sidecars absent | 234 passed; no skips; 55.315 seconds; 14 other-tier methods explicitly excluded. |
| Complete installed-data tier | 248 passed; no skips or exclusions; 160.194 seconds. |
| Explicit historical/workflow tier | 14 passed; no skips; 0.982 seconds. |

The [managed completion record](data/test-rationalization-phase2-result.md)
reports exit status zero for the validation batch, including its expected
missing-input failure. The same recorded package and candidate WAV identities
were verified; old fixture evidence hashes remained unchanged. Syntax,
documentation links and diff whitespace were also checked.

No decoder source, accepted algorithm
configuration, historical pins, existing received corpus or original candidate
bytes were changed. Phase 3 quality-gate enforcement remains outstanding.
