# Reference round-trip calibration before encoder remediation

**Current user decision:** decoded-picture bit perfection is to be replaced
with sensible scorecard-based qualification; numerical limits still require
calibration. The severe tiny-picture failure is independently investigated
through the concrete hypotheses and controls in [the qualification proposal](qualification-proposal.md).
This supersedes the earlier statement below that no quality-rule revision was
authorized. Exact waveform/protocol checks and original evidence remain.

**PM review checkpoint (2026-10-02):** establish a reliable, representative
fldigi-to-fldigi path before choosing a production correction. This supersedes
the earlier recommendation to proceed directly to receiver/reference changes.
No receiver replacement, pixel tolerance, encoder change, or qualification
disposition has been approved. Existing findings and failed evidence remain.

**Later user clarification:** potential revision of the bit-perfect decoded-
picture loopback expectation is a separate product-policy question from severe
tiny-picture distortion. Reuse the established decoder scorecard framework;
keep tiny failures visible and independently investigated even if a future
quality criterion changes. See [the recorded separation](acceptance-and-tiny-images.md).

The [first fresh 160×120 controls](manual-control.md) are ready: pinned fldigi
4.2.13 and unchanged GramPy WAVs carry the same RGB chart. The user decoded
them on the Mac independently of the Pi receive harness. The exact fldigi WAV
completed a same-build Pi round trip under explicit fixed-mode settings: text
and dimensions recovered, but the image is slanted. Autosave and completed
buffer match. Mac fldigi 4.2.11 recovers a visually clean native image and nearly
the same reference slant as the Pi. The reference WAV's repeated gray ramps
measure about 0.186% longer than nominal; the native WAV's match nominal timing.
The simultaneous built-in/ALSA recording attempt timed out, and an explicit
48-kHz output-device attempt failed with a memory-corruption error. Neither is
a validated capture fix. A separate offline timing correction of the original
reference WAV removes the Pi slant and reduces source MAE from 69.660 to 2.706
with unchanged reception. That strongly identifies the original WAV's time-scale
error as the cause of the slant. Next isolate and repair the fresh generation/
capture path, then establish repeatability without an offline correction.
No receiver or encoder binary or acceptance rule has changed.

Following the user's request to reconnect these experiments to the original
failure, prioritize a direct comparison: replay the exact native WAV already
received cleanly on the Mac through the unchanged Pi harness, then independently
inspect an original failed qualification WAV on the Mac. The failed fldigi
transmit-capture baseline does not need to block those receive-path tests.
See [the simplified explanation](qualification-explained.md). The later fresh
fldigi baseline is still needed for reliable comparative reference quality.

The original RGB speed WAV's independent Mac replay has now returned three
distorted 8×4 saved PNGs. A Pi-only fault is therefore insufficient; completed
Mac buffers remain unmeasured. The same known normal-sized chart at p4/p2 has
now returned, and GramPy's unchanged picture decoder has processed all three
native chart WAVs. Both paths fail exact pixels at every measured size/speed;
the tiny fixtures have higher differing-pixel percentages. GramPy's coupled
direct-WAV errors are smaller in magnitude, while both normal-sized paths'
mean errors grow at p2. See [the comparison and its method limits](decoder-comparison.md).
These descriptive figures do not replace the still-unresolved fresh reference
capture baseline or justify a production change.

## What the completed comparison actually established

The p8 controls replayed two archived fldigi-generated 8×4 WAVs into the pinned
fldigi 4.2.13 receiver. They used the same decoded source pixels as the native
candidate, and retained WAV/binary hashes, configuration, autosaves and completed
picture buffers. They were not fresh same-build transmitter/receiver round trips,
and they did not test broadcast-sized pictures. Both generation/capture and
playback/collection remain parts of the measurement chain needing calibration.

The code/observations supporting omitted final values and stale autosaves remain
valid for these runs. Their practical importance, generality across image sizes,
and appropriate remediation have not been established. Receiver filtering can
introduce expected analog image error; involvement alone does not prove that
fldigi needs a production patch. A fitted model is explanatory evidence, not a
validated reference round-trip path.

"Correct transmission" in the earlier report meant a picture waveform matching
the documented component order, frequencies and durations. It did not mean
proven end-to-end fidelity through fldigi, and should not be used to imply that.

## Investigation order

1. Generate fresh reference transmissions with the same unchanged pinned fldigi
   build used for reception. Start with text and a normal-sized p8 picture in
   a fixed mode, with RxID off. Record the actual reported versions, source and
   binary hashes, image dimensions and audio settings at both ends.
2. Add known source images of a representative size, for example 160×120:
   a diagnostic chart with smooth regions, gradients, color patches and text,
   and a photographic image. Test RGB and grayscale. These are additional
   controls; do not enlarge or replace the frozen 8×4 acceptance fixture.
3. Validate the audio harness as well as the receiver. Inspect recording and
   playback errors, sample rates, clipping, truncation and pacing. If a reference
   round trip fails, compare an independent/manual playback and completed-save
   path using unchanged fldigi before attributing the failure to receiver code.
4. Compare source, completed received picture and saved file. Check dimensions,
   picture identity/order, visual usability, alignment, color order, pixel errors
   and recovered text. Repeat fresh runs to establish consistency. Do not assume
   a useful analog picture must equal the source pixel for pixel, or invent a
   passing tolerance from one failed run.
5. Once the p8 reference path is understood and repeatable, extend to both modes
   and every retained speed, then add RxID and complete mixed WAVs. Compare the
   older pinned-transmitter controls separately so version effects are explicit.
6. Only then send the same known images through the native encoder using the
   calibrated receive path. Measure whether native results introduce defects
   beyond the fldigi reference behavior. Retain independent waveform checks and
   the original failed qualification alongside these comparisons.

## PM decisions

No new production decision is needed to perform these sidecar controls. Do not
ask PM to approve a fldigi patch or relaxed quality rule before this calibration.
If calibration establishes that the collection method must change, document and
confirm that evidence change. If an unchanged receiver cannot meet the required
quality, return with a concrete proposal about compatibility target and picture
quality, supported by the reference round trips. The encoder remains unqualified;
Session 9 remains open without an approved reject/defer disposition.
