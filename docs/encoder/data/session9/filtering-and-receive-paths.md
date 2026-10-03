# Filtering and the Mac/Pi receive comparison

## What filtering means here

Picture R/G/B values are sent as brief audio tones, with tone frequency
representing the value. Fldigi filters the audio before measuring those
frequencies and turning them back into colour values. Filtering selects the
expected signal band and rejects unwanted audio. A filter combines signal
samples across time and has a finite response, so an abrupt change from one
tone to another can influence more than one recovered component even when the
input WAV has no shortwave noise.

This is audio filtering, not smoothing an already decoded PNG. Receiver
frequency estimation then introduces its own finite measurement interval,
rounding and clipping. Filter delay and transition smearing are different:
accounting for a constant delay can restore alignment, but does not automatically
recover all detail lost at rapid transitions. A separate picture-entry timing
error can amplify the effect by assigning a measurement to the wrong component.

The relevant variable is how quickly colour values change in the transmitted
sequence, not image dimensions alone. Wide constant-colour regions allow a
steady tone to persist. A single-pixel checkerboard in a large image could
also suffer from rapid transitions. Our new control images therefore compare
equal-duration transmissions with different horizontal spacing, and original
versus constant tiny content. The model supports filtering/timing contributions;
it does not independently prove that they explain every live tiny failure.

## What differs between the manual Mac and automated Pi evidence

All numerical values below are mean absolute R/G/B component errors on the
0–255 scale at the original coordinates. Equal-looking pictures can have
different scores, and equal scores need not mean equal pixels.

| Same supplied WAV | Mac fldigi 4.2.11 saved image | Pi fldigi 4.2.13 | Supported inference |
| --- | --- | --- | --- |
| Native 160×120 RGB p8 | Clean, straight; source MAE 13.697 | Clean, straight; completed/autosaved MAE 13.368 | The harness can reproduce a useful manual result. Mac/Pi image MAE is only 1.166 in this case. |
| Original recorded fldigi 160×120 p8 | Slanted; source MAE 69.666 | Slanted; source MAE 69.660; save equals completed viewer | Distortion in this control is shared and cannot be assigned to a Pi-only receive harness fault. Mac/Pi MAE is 2.043. |
| Offline clock-corrected fldigi p8 diagnostic | Straight; source MAE 13.406 | Straight; source MAE 2.706; save equals completed viewer | There is a measurable receive-path difference despite both looking useful. Mac/Pi MAE is 11.640; cause not isolated. This remains a corrected diagnostic, not a fresh qualified transmitter baseline. |
| Original 8×4 native RGB p8/p4/p2 | Substantially distorted saves; source MAE 87.802/113.177/97.771 | Completed replay pixels distorted; source MAE 44.177/105.063/96.365; saves differ from those buffers | Tiny failures are independently reproduced, but their pixels and severities are not identical. A Pi-only fault is insufficient; equivalence of the two paths is not established. |

The [native matched replay](manual-control-native-pi-summary.json), [original Mac
controls](manual-control-mac-summary.json), [corrected Mac](manual-control-clock-corrected-mac-summary.json),
[corrected Pi](manual-control-clock-corrected-pi-summary.json) and
[tiny comparison](mac-tiny-summary.json) retain those measurements.

There is also a demonstrated Pi collection problem: queued viewer updates
can complete after fldigi has directly saved its PNG. Some tiny grayscale
saves are unreadable or contain the preceding picture; completed viewer pixels
show that collection alone does not account for the remaining distortion.
This is fldigi GUI/save behavior observed under the harness, not proof that
SSH or status polling corrupts demodulation. Scheduling or playback/control
may contribute, but their effects have not been isolated.

Human presence is not the only difference. Builds differ (4.2.11 versus 4.2.13),
playback/audio paths differ, the original Pi qualification used automatic RxID
while later matched controls used fixed mode/carrier, and picture evidence is
not symmetric. We captured completed Pi buffers plus saves; Mac evidence is
user inspection plus PNGs, with no independently captured completed tiny buffer.
Manual operation still uses fldigi's receiver processing and does not inherently
disable audio filtering or guarantee save synchronization.

## Next comparison

Receive the ready original/constant/tall/wide WAV on both paths with fixed
MFSK64/1500 Hz, RxID/AFC off, and bind each displayed and saved picture to its
caller label. Compare completed viewer pixels with the save before attributing
differences to demodulation. Control fldigi version as a later comparison if
material differences remain. The evidence currently supports both a real
collection fault and additional receive-path differences; it supports neither
universal harness equivalence nor a claim that manual decoding fixes tiny images.
