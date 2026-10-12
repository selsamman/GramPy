# Regenerated fixture candidate check

Date: 2026-10-12. Source revision: `12b4e92` (phase 1).
Status: initial candidate investigation complete; replacement fixtures are
**not accepted** and phase 2 repair is not complete.

This is the initial investigation record. Subsequent reconstruction and
independent validation are recorded in
[phase 2](test-rationalization-phase2.md).

## Result

All four regenerated IQ candidates decode successfully with the current
GramPy pipeline. The two text cases recover their known text exactly. The two
picture cases recover the expected announcement text and complete 8x4 rasters,
with 32 grayscale or 96 colour components and the expected artifact shapes.
These existing checks do not measure picture fidelity against independent
source images or fldigi receiver output.

The six existing tests were then run with the candidates in the expected
directory layout: **six failures, zero errors, zero skips**. Their committed
expectations were left unchanged. These are expected investigation results,
not an accepted passing regression suite.

| Existing check | Candidate behavior | Why the current test fails |
| --- | --- | --- |
| Controlled MFSK32 text | Exact expected text/octets; mode, framing, carrier, event coordinates and diagnostic assertions pass | IQ identity differs. |
| Controlled MFSK64 text | Exact expected text/octets; mode, carrier, symbol/tone timing and intermediate-file assertions pass | IQ identity differs. |
| Controlled grayscale picture | Expected header, 8x4 shape, 32 components and completion pass | IQ identity differs; old raster sample position differs by 60,855 samples. |
| Controlled colour picture | Expected header, colour flag, 96 components, shape, completion and 69,120-sample return-to-text interval pass | Old raster position differs by 87,363 samples; the test expects a non-operative boundary predictor and an old prologue offset. |
| Bounded MFSK32 text | Exact expected text and materialized-sample bound pass | The test expects compact `p11d` routing, but its default `supported_hybrid` configuration intentionally selects the overlapping-window MFSK32 path. |
| Fixture integrity | All required candidate WAV/IQ/metadata files are present | All twelve artifact hashes differ from the original committed identities. |

## How failures were separated

An ordinary run of each unchanged test stops at its first failed assertion.
A separate diagnostic pass collected the remaining assertion failures, reusing
the same five actual decode results (four ordinary decodes and one forced
bounded-threshold decode). It did not change a test source file, expected hash,
sample position or decoder configuration. The diagnostic pass is not counted
as a successful unittest run: its purpose is to expose checks hidden by the
first failure.

The six methods completed that diagnostic pass without execution errors.
There were 193 successful direct assertions and eleven failed direct assertions:
five identity assertions and six behavior/timing assertions. The two integrity
assertions cover all twelve mismatched artifacts. Assertion counts include
per-event loop iterations; they are not independent case counts.

Candidate inputs were read through temporary directory links, rather than
copied or installed as accepted fixtures. All input hashes and the committed
evidence bytes were checked again afterward and remained unchanged. The
experiment used the repository virtualenv and managed Mac wrapper. A first
diagnostic report exposed nested unittest assertion bookkeeping ambiguity; the
final run corrected that accounting and records only assertions invoked by the
test methods.

Compact [machine-readable findings](data/fixture-candidate-probe.json) contain
artifact identities, actual decoding results and failed assertion locations.
The [managed completion record](data/fixture-candidate-probe-result.md) confirms
the experiment completed with exit status zero. That exit status means the
investigation completed; the six original tests still failed as stated above.
Machine paths and the reproduction harness remain private in `.local`.

## What is stale, and what remains uncertain

**Recording coordinates:** the tests subtract 48,000 samples from the original
WAV positions, accounting for a one-second leading trim. The regenerated IQ
metadata records zero guard trimming. The WAV hashes also differ, so changing
the trim convention alone is not established as the full explanation. Sample
positions must be independently measured for whichever recordings are adopted.

**Boundary predictor:** current accepted decoding uses the operative unified
global-text/local-header-flush grid. The colour test's `operative == false`
assumption describes earlier behavior. Its old exact 252-sample prologue-offset
assertion combines that earlier predictor with the original recording's timing.
It should be replaced with a check of the maintained boundary contract and
independently established candidate timing, not updated from GramPy's own
answer alone.

**Bounded path:** `_p11d_compact_text_enabled` explicitly enables compact text
for opt-in `p11d`, or default `supported_hybrid` with fixed MFSK64. The existing
bounded test uses MFSK32 with the default organization but asserts compact-path
labels. This contradicts the routing contract already protected in
`test_supported_hybrid_routes_only_qualified_mfsk64_to_p11d`. Decide whether
the repaired integration test is meant to protect the default MFSK32 bounded
fallback, the explicit compact opt-in, or both. This experiment exercised the
default bounded fallback; it did not test the explicit compact opt-in.

## Next work for phase 2

1. Independently validate the candidate WAVs/transmitted content, source images
   and relevant timing on the Pi; decide which fixtures merit adoption.
2. Preserve accepted inputs and provenance in the documented sidecar, with a
   strict availability/hash check. Only then repin identities deliberately.
3. Repair the picture assertions around maintained behavior and independently
   reviewed coordinates. Preserve source-truth picture coverage where required.
4. Repair bounded-path integration so its configuration and expected route agree.

No decoder code, repository tests, committed expected hashes, corpus files or
candidate recordings were changed. No commit was created for this experiment.
