# Automatic MFSK32 picture dispatch correction

**Request, 2026-10-03:** PM identifies skipped MFSK32 pictures in automatic
mode as an omission to fix. Keep the encoder qualification focused on credible
broadcasts and avoid unrelated decoder algorithm changes.

## Definition and baseline

The pre-change automatic pipeline dispatches text for both MFSK32 and MFSK64,
but explicitly selects only the MFSK64 text result for picture decoding.
The existing automatic-dispatch regression asserts that restriction. The
public fixed-mode MFSK32 path and lower-level picture code already exist.
This is a demonstrated orchestration/coverage gap. Source history places the
restriction in `4a24f7e` (2026-09-20, “single pass multiple images”), after the
earlier picture-decoder development. It was not a deliberate encoder limitation.

Work mode: in-place controlled wiring correction, with retained before/after
evidence and focused regression coverage. The current `pipeline.py`, its
source hash and the original Session 9 qualification remain the baseline.
User instructions prohibit commits unless requested, so this change record
and retained source snapshot provide the definition checkpoint without a commit.

The candidate dispatches picture decoding to both already decoded modes,
using the existing mode-specific decoder settings, then combines their
pictures and suppresses raster-generated false text in each mode. It must
preserve time order, unique picture/artifact/reacquisition identities and
correct compact-product links. An error in one mode must not discard valid
pictures from another. No estimator, filter, protocol, encoder, public API
shape or default configuration change is included.

## Required evidence

- Inspect the fixed-mode MFSK32 baseline and classify acquisition limitations
  separately from automatic dispatch.
- Automatic recovery of those same WAVs with the unchanged Session 9 quality
  limits; preserve the original skipped-picture records separately.
- Complete mixed MFSK32 → MFSK64 → MFSK32 broadcast with pictures and following
  text, proving order, unique file identities, usable artifact links and
  retained recovery references.
- Existing seven MFSK64 outputs remain pixel-identical, including the
  mixed-broadcast control, with ordered text retained.
- Focused dispatch/error-isolation tests and the full repository regression.
- Representative received-broadcast preservation and a proportionate Pi
  decoder subset where practical; classify any unavailable evidence explicitly.

Numerical success supports the fix; PM visual acceptance of newly recovered
MFSK32 pictures remains distinct from the frozen original v3 qualification.
Session 9's encoder source and historical results are not rewritten as if
they had contained the corrected decoder.

## Observed results

The candidate changes only `src/grampy/pipeline.py` among the 40 production
files identified by Session 8. Its SHA-256 is
`6256a56d5273f98ba02e071ee8582c6a6cafbc7c4302e9825887c3ecebcd6fba`.
The retained before-source and managed execution records are under
`.local/decoder-auto-mfsk32/`. The encoder, picture estimators, filters and
default decoder settings are unchanged.

The three fixed-mode probes without a supplied carrier recovered no pictures:
the short-recording fixed path selected the wrong carrier. That acquisition
limitation does not establish a picture-decoder failure. Automatic mode already
acquired MFSK32 and its headers correctly; passing that acquired text to the
existing picture path is the correction evaluated here.

Repeating the retained fixed-mode code with an explicit 1500-Hz carrier
recovered the p8 portrait and p4 sunset, with raw MAE 2.48/255 and 1.78/255.
The short fixed-mode p2 chart still recovered no picture. These fixed-route
acquisition/header limitations are separate from the corrected automatic path;
this change does not claim to fix them.

All ten unchanged whole-WAV inputs now pass the frozen v3 numerical and
functional requirements through the default public automatic API. MFSK32 raw
image MAE is 2.54/255 (p8 portrait), 1.87/255 (p4 sunset) and 13.34/255 (p2
chart). The seven previously recovered MFSK64 rasters remain pixel-identical.
The supplemental [scorecard](data/auto-mfsk32-pictures/qualification.json)
includes ordered caller text/announcements, geometry/count, automatic mode and
carrier acquisition, framing, artifact hashes and compact picture links.

A real default-rate MFSK32 → MFSK64 → MFSK32 round trip recovers all three
pictures and following text in order, without reusing artifact or recovery
identifiers. The full repository suite passes: **247 tests, six expected
skips**. A retained 1,800-second received broadcast also preserves its three
mode intervals, complete text summary and nine PNG hashes, and has unique
recovery epoch IDs. Its candidate execution took 99.26 seconds on the Mac;
this single run is compatibility evidence, not a paired speed comparison.

The [candidate-set visual review](data/auto-mfsk32-pictures/index.html) compares
source, the previous absent automatic output, corrected GramPy, and the original
pinned Pi fldigi outputs. All three new GramPy images are visibly recognizable;
the p2 chart retains visible blur. Numerical passing is not a claim of exact
pixels or of PM visual acceptance.

The [Pi subset](data/auto-mfsk32-pictures/pi-checks.json) also passes all three
cases: normal MFSK32 p8 portrait, difficult MFSK32 p2 chart and mixed-mode
MFSK64 photo. Raw MAE is 2.54053/255, 13.31172/255 and 1.38965/255, compared
with Mac 2.54051/255, 13.34438/255 and 1.37809/255. Pixels differ slightly
across platforms; both meet the same gate without scoring alignment offsets.
Fresh-process execution took 210.5, 91.3 and 284.7 seconds with peak RSS
496.4, 203.6 and 710.9 MB. These measurements include whole-WAV analytic-IQ
conversion, decoding, quality calculation and output; they establish successful
offline target execution, not real-time performance. No Pi installation or
installed-source replacement was performed.

The initial exploratory mixed-picture test used an 8-kHz output rate to reduce
execution cost and failed its raster quality assertion. The permanent test
uses the already frozen 48-kHz default, without weakening the quality gate.
The [retained nondefault-rate control](data/auto-mfsk32-pictures/nondefault-8khz-control.json)
classifies that separate limitation against the original automatic MFSK64
output and the pre-change MFSK32 bounded picture algorithm. This wiring fix
does not qualify all nondefault sample rates or repair their existing quality
limitations.

**Status, 2026-10-03:** accepted and closed. PM states, “I have looked at all
images and accept them.” Mac and representative Pi evaluation pass; the tested
correction is already in place. Confidence is high that the automatic omission
was a dispatch/coverage bug. The [acceptance record](../encoder/data/session9/practical-acceptance.json)
binds the decision to the frozen evidence and tested source. The historical
Session 9 qualification is preserved separately; no commit was created.
