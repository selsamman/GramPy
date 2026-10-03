# Why qualification failed despite a clean manual picture

**Current checkpoint:** the user now confirms replacing decoded-picture exact
equality with sensible scorecard-based qualification, separately from severe
tiny-image diagnosis. [The concrete proposal](qualification-proposal.md) records
calibration needs, corrected accepted-picture-setting scores, ranked hypotheses
and a ready control WAV. Earlier statements below about keeping the passing
rule unchanged describe preceding checkpoints; original failed evidence remains.

The user has separated two questions: whether exact decoded pixels are an
appropriate clean-loopback requirement, and why the original tiny fldigi images
have severe colour/content distortion. The decoder already has a multidimensional
scorecard and visual-review process; reuse it for any future quality proposal.
Changing an exact-equality rule would not resolve the tiny-image issue. See
[the recorded direction and evidence boundaries](acceptance-and-tiny-images.md).

Every image measured so far differs from its source pixels, in both fldigi and
GramPy's diagnostic decode. The tiny fixtures have higher differing-pixel
percentages than the normal-sized chart at each speed. See [the measured
comparison](decoder-comparison.md) for error magnitude as well as percentage.

The unchanged GramPy encoder can produce a WAV that fldigi decodes into a
visually clean, useful image. The user's 160×120 RGB p8 Mac decode and a replay
of the exact same WAV through the unchanged Pi receive harness establish that
for one case. The original failed qualification does not establish that GramPy
is incapable of transmitting images.

## Which WAV had the timing error?

| WAV | Audio producer and subsequent processing | Mac and Pi results |
| --- | --- | --- |
| `grampy-mfsk64-rgb-p8.wav` | Unchanged GramPy encoder | Clean, straight chart on both; nominal waveform timing |
| `fldigi-mfsk64-rgb-p8.wav` | Unchanged pinned fldigi transmitter, recorded through our Pi audio harness | Severely slanted chart on both; recorded picture periods about 0.186% too long |
| `fldigi-clock-corrected-diagnostic.wav` | A uniformly resampled copy of that fldigi recording | Clean, straight chart on both, confirmed by the user's latest PNG |

The timing fault belongs to the recorded **fldigi control**, not the native
GramPy WAV. Its origin within fldigi output, conversion and recording remains
unresolved. The failed control cannot be used to blame the receiving path.
The corrected derivative helps show that the recorded timing caused the slant;
it is not a validated fresh fldigi round-trip baseline.

## What differed between qualification and the clean manual decode?

| Condition | Original picture qualification | Clean native Mac example |
| --- | --- | --- |
| Image | 8×4 fixture | 160×120 chart |
| RGB p8 picture payload duration | 0.096 seconds | 57.6 seconds |
| Coverage | MFSK32 grayscale and MFSK64 RGB, p8/p4/p2, plus mixed composition | MFSK64 RGB p8 |
| Receiver | Pinned Pi fldigi 4.2.13 | Mac fldigi 4.2.11 |
| Acquisition | Whole-WAV playback with automatic RxID | Manual fixed-mode playback |
| Image evidence | Automatically saved PNGs | User inspected and supplied the received PNG |
| Passing rule | Exact source-pixel equality | Visually clean and useful picture |

All seven original picture checks failed exact pixel equality. Their mode
acquisition, text, picture announcements and dimensions passed. Some saved
images were incomplete or stale; diagnostic replays proved that some grayscale
saves contained the previous picture's pixels. Completed buffers also retained
real source-pixel differences, so collection alone does not explain every
failure. Receiver filtering and effective alignment reproduce the narrow-case
interiors closely, but not every live timing contribution has been isolated.

The clean native Mac PNG also differs numerically from the source. It would
fail that exact-pixel rule even though it looks good. Thus visual success and
the recorded qualification failure are compatible observations. The small
fixture and faster speeds can expose errors that are less obvious in a large
p8 image; that is a supported explanation to test, not complete qualification.
Neither manual decode establishes a pixel-perfect GramPy-to-GramPy round trip.

## The direct comparison and next step

The exact native WAV already decoded successfully on the Mac completed unchanged
Pi reception in 121 seconds. Caller text, announcement, dimensions and post-
picture text recover; the picture is visually clean and autosave equals the
completed widget. Source MAE is 13.368, close to Mac's 13.697; Pi-versus-Mac MAE
is 1.166. Both would still fail exact source-pixel equality. See
[the Pi result](manual-control-native-pi-summary.json). This establishes a useful
receive path for this case, without a transmitter-capture baseline or any audio
correction.

The user has now returned three 8×4 Mac PNGs from that original failed WAV.
They also show substantial color/content changes at p8/p4/p2; see
[the independent tiny-image comparison](mac-tiny-comparison.md). This rules out
a Pi-only fault as the sole explanation of the saved-image failures. It does
not distinguish a common fldigi save issue from distortion already present in
the completed Mac viewer. The same normal-sized chart's p4/p2 Mac saves are now
retained, along with GramPy's coupled direct-WAV decode of p8/p4/p2. All are
non-exact, with greater normal-sized average error at the faster speeds. Tiny
fixtures have higher differing-pixel percentages in both paths. Different
content, acquisition and GramPy filtering paths limit causal claims about size
alone; all original cases and measurements remain preserved.

Do not change encoder timing, receiver binaries or passing rules from the
current evidence. A reliable fresh fldigi transmitter baseline remains useful
for later comparative quality work, but need not block these direct native
receive-path comparisons. Session 9 remains open; no production PM decision
is requested at this explanatory checkpoint.
