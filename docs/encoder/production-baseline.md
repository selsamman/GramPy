# Accepted native encoder baseline

The product outcome is credible **48-kHz mono PCM16 broadcast WAVs** from
ordered text, PNG pictures, compatible audio and silence. PM accepted all
practical images on 2026-10-03 and confirmed that other sample rates are not
qualification requirements. The public API is library-only in `radiogrampy`
0.1.3, with Pillow as a base dependency and no fldigi runtime dependency.

## Source and artifact identity

The final local wheel is identified by
[package.json](data/session10/package.json), including all 32 Python module
hashes, dependencies, scripts and wheel checksum. The eight packaged data/type
files are verified separately in
[package-data-checks.json](data/session10/package-data-checks.json).
The accepted automatic decoder dispatch is pipeline SHA-256
`6256a56d5273f98ba02e071ee8582c6a6cafbc7c4302e9825887c3ecebcd6fba`.
Its decoder defaults, filters and estimators are unchanged.

The Session 10 packaging audit separately corrects grayscale PNGs requested
as color: components now follow R/G/B row planes rather than repeating each
pixel three times. Independent component-order expectations and exact public
WAV equivalence for L/RGB sources protect this correction in both modes and
all speeds. Full-size 240x180 equivalence is recorded in
[large-l-color-checks.json](data/session10/large-l-color-checks.json).
The practical accepted source images are RGB; their original WAVs are
preserved byte for byte in
[accepted-waveform-preservation.json](data/session10/accepted-waveform-preservation.json).

## Receive-quality acceptance

The [PM acceptance record](data/session9/practical-acceptance.json) binds the
original ten-case practical qualification and separately evaluated MFSK32
dispatch correction. All ten unchanged WAVs pass in pinned Pi fldigi and the
public automatic GramPy decoder, including three MFSK32 grayscale pictures.
Seven earlier MFSK64 rasters remain pixel-identical after the decoder
correction. Geometry/count, ordered text/announcements and automatic complete
WAV mode/carrier acquisition pass. Reviewed blur and the narrow colored border
in one fldigi mixed photograph are accepted within this practical scope.

The accepted screen is raw MAE ≤25/255, aligned MAE ≤20/255, absolute channel
bias ≤15/255, alignment offset ≤12 components and ≤12 changes, followed by
PM review. The examples are 240x180 and 160x120, with p8/p4/p2 grayscale in
both modes, RGB in MFSK64, and mixed MFSK32 text/audio/silence/MFSK64 picture.
This is practical case-set acceptance, not a promise of bit-perfect decoded
pixels or a universally safe minimum image size. Exact transmitted protocol,
waveform, copied PCM, silence and timestamp checks remain requirements.

Tiny-image quality, other-rate picture quality, fresh fldigi transmitter
capture calibration, reverse-sideband, live audio, image editing, audio
conversion, additional modes and an encoder CLI are outside this baseline.
The existing API accepts a broader rate range for compatibility; that does
not require or imply receive qualification at 8 kHz.

## Validation, performance and maintenance

Final installed-wheel regression is in
[installed-wheel-regression.json](data/session10/installed-wheel-regression.json).
The prior accepted source regression, received-broadcast text/nine-PNG
preservation and representative Pi decoder subset are retained in the
[decoder change record](../decoder/auto-mfsk32-pictures-change.md).

The final Pi encoder timing, memory and WAV-size estimates are in the
[Session 10 evidence index](data/session10/README.md). Measure encoder CPU and
wall time separately from emitted broadcast duration; decoder/receiver times
are not encoder performance. The benchmark uses an isolated wheel install,
two fresh-process samples per case, default 48 kHz and no receiver. Peak RSS
includes interpreter and imports; normal file writes are timed without a
cold-storage or `fsync` guarantee.

Use [API](api.md), [contracts](contracts.md), [design](design.md) and
[validation](validation.md) as operational guidance. Future changes follow
[Change Management v1](../operations/change-management-v1.md). Historical
experiments, original failed/accepted records, machine-local evidence and
the external corpus are deliberately preserved. Publication, deployment and
commits are separate from this local packaging closeout.
