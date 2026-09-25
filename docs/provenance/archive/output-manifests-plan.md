# Compact broadcast and quality outputs: implementation plan

**Status:** completed, 2026-09-24. This archived document records the staged
definition and acceptance of the compact output contract. Current usage is
documented in `docs/decoder/api.md` and `docs/decoder/cli.md`.

## Goal and baseline

Produce two small, independently useful outputs from one SigMF decode:

- `text.manifest.json` contains readable broadcast text, MFSK mode intervals,
  ordered pictures, and their association with adjacent text. It does not infer
  program titles or use a supplied synopsis to label segments.
- `quality.manifest.json` contains three aligned, one-second series: measured
  post-AGC signal level, measured post-AGC noise level, and a proxy for decode
  quality. It is graph data, not a diagnosis or ground-truth accuracy score.

The current CLI writes a single development manifest with all text events.
The 2026-09-23 full-broadcast reference in the ignored corpus has 28,800,000
CF32 samples at 16 kHz (1,800 seconds), three detected MFSK mode intervals,
and nine decoded pictures. Its 11 MB development manifest reports 2,771.26
seconds of decode wall time on Linux ARM64; that timer excludes separately
timed manifest file publication. It is a compatibility reference and an
on-device historical timing, not a same-machine Mac performance baseline or
independent program truth. The
complete capture was supplied as `.local/regression/sampleFullRun`; canonical
files are now under `tests/samples/received-corpus/`, while the original
intake folder, including diagnostic WAV files, is under
`tests/samples/reference-captures/sampleFullRun-20260923/`.

Acceptance must preserve decoded text, picture output, sample coordinates,
partial-result reporting, and existing `decode_iq`/CLI behavior. Generated
product files should not contain character events, raw octets, tone rows,
component arrays, or large inline rasters. The development manifest remains
available explicitly for investigations. The appliance's normal product path
must not create the development manifest.

## Shared identity and time axis

Both new files use the same deterministic `run_id`, input SHA-256 hashes,
sample rate, requested half-open sample interval, and output schema version.
Original IQ sample positions are authoritative. Seconds are derived as
`(sample - requested_start_sample) / sample_rate_hz`; capture UTC time can be
derived from SigMF `core:datetime` when present. A UI may align the files only
when run ID, input hashes, and requested interval match.

Quality points are anchored at the requested interval start. Point `i` covers
`[start + floor(i * sample_rate_hz),
 min(stop, start + floor((i + 1) * sample_rate_hz)))`. For the supplied full
capture there are exactly 1,800 points. The final point of a partial interval
may be shorter. The **output cadence is fixed at one second** in v1; spectral
snapshots may be taken more often and summarized into that second. Missing
measurements use JSON `null`, never zero or an invented quality value.

## `text.manifest.json` shape

Schema identifier: `grampy-text-manifest.v1`.

```json
{
  "schema": "grampy-text-manifest.v1",
  "run_id": "<24-hex-id>",
  "status": "complete",
  "decoder": {"version": "<version>", "configuration": {"mode": "auto"}},
  "input": {
    "metadata_sha256": "<sha256>",
    "data_sha256": "<sha256>",
    "sample_rate_hz": 16000,
    "requested_interval": {"start": 0, "stop": 28800000}
  },
  "mode_segments": [
    {
      "id": "<stable-id>",
      "mode": "MFSK64",
      "interval": {"start": 0, "stop": 1000},
      "items": [
        {
          "id": "<stable-id>",
          "kind": "text",
          "interval": {"start": 100, "stop": 900},
          "framing": "complete_stx_eot",
          "frame_id": "<stable-frame-id>",
          "text": "Readable broadcast text",
          "unmapped_event_count": 0
        },
        {
          "id": "<stable-id>",
          "kind": "picture",
          "interval": {"start": 900, "stop": 1000},
          "associated_text_item_id": "<stable-id>",
          "artifact": {"kind": "png_uint8_raster", "path": "pictures/raster-0001.png", "sha256": "<sha256>"},
          "header_text": "Pic:165x210C;",
          "width": 165,
          "height": 210,
          "color": true,
          "complete": true
        }
      ]
    }
  ],
  "omitted_unframed": [
    {"interval": {"start": 0, "stop": 99}, "reason": "before_stx", "character_count": 12}
  ],
  "warnings": []
}
```

The values above illustrate structure, not expected sample coordinates; the
real `decoder.configuration` contains the complete effective configuration.
A mode segment is a detected MFSK32/MFSK64 interval, not a program article.
Within it, items are ordered by wire time. Text is a JSON string containing
decoded characters, not an octet list. Picture items link to portable PNG
artifacts and to the nearest preceding text item in the same mode segment when
that association is supported by the decoded transition. A picture without
supporting text has `associated_text_item_id: null`.
Text chunks on both sides of a picture may share `frame_id` and the completed
frame status; an item need not contain an entire STX/EOT frame by itself.
Small existing inline rasters remain supported as `inline_uint8_raster` items
until artifact publication is consolidated in the integration stage.

Complete STX/EOT payloads are display text. Material confidently outside a
complete frame is summarized in `omitted_unframed`; uncertain or incomplete
material is retained as a text item with `framing: "uncertain"` or
`"incomplete"`, so possible broadcast content is not silently discarded.
Invalid Varicode events have no invented replacement character. Interpret
valid UTF-8 octet sequences as Unicode text, including curly quotes and
accented letters. Preserve undecodable individual octets with the Latin-1
mapping so damaged or legacy text is not silently replaced or discarded.
Serialize the resulting text as UTF-8 JSON; optional presentation normalization
belongs in the UI. The diagnostic manifest retains its existing Latin-1
mapping. Stable IDs and relative artifact paths must survive moving the output
package together.

## `quality.manifest.json` shape

Schema identifier: `grampy-quality-manifest.v1`.

```json
{
  "schema": "grampy-quality-manifest.v1",
  "run_id": "<same-run-id>",
  "status": "complete",
  "decoder": {"version": "<version>", "configuration": {"mode": "auto"}},
  "input": {
    "metadata_sha256": "<sha256>",
    "data_sha256": "<sha256>",
    "sample_rate_hz": 16000,
    "requested_interval": {"start": 0, "stop": 32000}
  },
  "grid": {"origin_sample": 0, "interval_seconds": 1, "point_count": 2},
  "columns": ["signal_dbfs", "noise_dbfs", "decode_confidence"],
  "points": [[-31.275, -45.125, 0.923], [null, -43.500, null]],
  "methods": {
    "signal_noise": {"id": "<versioned-method>", "calibrated_rf_power": false},
    "decode_confidence": {"id": "<versioned-method>", "calibrated_error_probability": false}
  },
  "exceptions": [],
  "warnings": []
}
```

The two-point example illustrates a short requested interval; the supplied
full capture requires 1,800 points. The points array is the compact transport
form; its column order is fixed by the schema. Round published dB and
confidence values to three decimal places, and target under 100 KB of compact
JSON for a complete 30-minute capture.
`signal_dbfs` is estimated signal-only power after subtracting the estimated
noise contribution; `noise_dbfs` is the estimated noise power expressed over
the *same effective bandwidth*. These are measurements of stored post-AGC IQ,
not calibrated antenna power. `signal_dbfs - noise_dbfs` is an SNR-like
ratio when both are available. An interferer inside the signal band can make
that ratio optimistic; method metadata and exceptions must disclose such
limits. Automatic gain control can change both levels and is intentionally
not removed.

`decode_confidence` is a unitless 0-to-1 **estimate of output fidelity for
the active task**. It is not measured accuracy for this particular broadcast
or a probability that every character or pixel is correct. Equal signal/noise
levels can yield different confidence in MFSK32 and MFSK64 because the modes
and decoder decisions differ. Signal and noise are measured independently of
decoded content. Evidence is assigned by wire or component sample intervals,
not delayed recognition time. Insufficient evidence yields `null`, and a
required missing artifact generates a warning.

Stage 4 implements `reference-fidelity-proxy.v1`, a small formula anchored to
independent program 456 truth in the received corpus. In a text second,
`V` is the overlap-weighted number of valid emitted characters, `A` is the
overlap-weighted number of all non-control character events, and `M` is the
sum of valid-character decision margins. The margin is
`1-exp(-minimum_absolute_input_llr)` or the clamped normalized Viterbi metric
gap, according to the event's recorded kind. The score is
`clamp((0.79*V + 0.257*M)/A, 0, 1)`. Invalid Varicode events increase `A`
without increasing `V`. At least two effective events are required. The
0.79 base reflects that the decoder can emit a correct character despite
weak soft-decision margins; invalid characters still lower the score.

For picture seconds, `C` is the fraction of components decoded outside the
representable range and `R` is the fraction differing from their channel's
3×3 spatial median by more than 40 on the 0–255 pixel scale. The score is
`clamp(1 - 0.4*C - 0.4*R, 0, 1)` when at least 20 components are available.
The spatial check catches some in-range speckle missed by clipping. A picture
being incomplete does not penalize earlier components; completeness is
separately represented in the text manifest. Component evidence may be inline
or read from the existing NPZ artifact; integration can discard that artifact
after the compact score is computed. The spatial calculation uses the decoded
component values and picture dimensions; it does not reread the IQ or require
an additional image dependency.

The preliminary fit used two 60–67 second MFSK32/MFSK64 text slices and
three complete images from program 456. Five-second text windows were scored
by alignment to approved source text; holding out one mode at a time gave
mean absolute error 0.046 and 0.069 for separately fitted formulas. The fixed
pooled formula's errors on those same slices were 0.080 and 0.049, compared
with 0.255 and 0.453 for the original raw-margin scores. For images, five-second
windows were compared with source pixels using `1 - mean_absolute_error/255`.
Holding out each complete image in turn gave mean absolute error
0.011–0.016 with clipping and spatial outliers, compared with 0.025–0.047
for clipping alone. The two fitted coefficients were close to 0.4 and are
rounded to that value. The fixed score's error on the three saved image slices
was 0.010–0.013, with positive per-image correlations of 0.976–0.990.
These are small, related samples, not a guarantee across stations or programs.
The reference images are strong source references but their status as exact
transmitter input remains pending verification. The output still has one point
per second and can be noisier than the five-second calibration windows.

The saved picture `quality_hz` array is saturated at 93,750 Hz and every
component has `unstable_frequency=true`; neither field distinguishes good
and bad regions in the full-broadcast reference. This method excludes them.
Missing component evidence leaves picture confidence `null` and makes the
product partial. Ordinary seconds without decoder evidence also remain
`null`; they do not generate per-second exceptions. The method can still miss
a plausible but wrong character, a silent omission with no emitted event, or
an in-range wrong pixel. Consumer color
thresholds should be checked against additional programs before deployment.
Structured image displacement or color errors can score too highly when they
do not produce clipping or isolated spatial outliers. The full saved run has
1,621 scored seconds and 179 `null` seconds in a 44.3 KB compact file; its
nine picture median scores range from 0.857 to 0.980. A high value is not a
literal percentage of correct pixels.

## Measurement strategy and performance gate

Start with a simple sparse IQ analyzer using bounded reads and windowed FFTs.
The detected center frequency and mode may locate the occupied band, but
character validity or confidence must not influence signal/noise measurement.
Measure active signal energy in its band and a local noise floor outside it,
with guard bands against leakage. Record method version, FFT size/window,
frequency bands, snapshot cadence, aggregation rule, and coverage. A drifting
signal must be followed or flagged; a fixed band must not report drift as a
fade. In-band interference is a known limit of a simple noise-floor estimate.

Benchmark one, two, and four spectral snapshots per second on the same full
capture. They mean 1,800, 3,600, and 7,200 transforms respectively for a
30-minute run, all yielding 1,800 published points. Select the lowest cadence
that still reveals known fades/interference without unstable one-snapshot
outliers. Compare incremental wall time, CPU, peak RSS, and input bytes on the
development machine. A separate sparse pass is the initial implementation
because it keeps acquisition and decode logic simple; share an existing FFT
pass only if measured savings justify the added coupling. Do not assert an SNR
or runtime target from transform counts alone.

The initial quality pass reads the stored IQ but must not alter IQ samples,
acquisition decisions, symbol tracking, FEC, picture assembly, or decoder
state. Sharing the existing FFT stream is a later optimization candidate with
a wider regression scope, not a prerequisite for the first product release.

Stage 3 implements `sparse-iq-band-power.v1` as a separate read-only pass. A
4,096-sample Hann FFT (or the largest power of two within half a second for
lower sample rates) samples each one-second interval. The MFSK32/MFSK64
signal bands are 531.25/1,062.5 Hz wide, based on the 16-tone ranges plus
one tone-spacing margin at each edge. The estimator searches centers within
125 Hz of the mode center supplied by acquisition. Its noise reference uses
available 500 Hz shoulders outside the entire search range, with a 100 Hz
guard. A median periodogram estimate, corrected for the exponential-bin
median, sets the matched-band noise power. Subtracting that power from the
signal band gives `signal_dbfs`; an excess less than four noise standard
deviations is `null`. This routine unresolved result needs no exception entry;
`exceptions` records measurement failures such as invalid IQ or unavailable
reference bands. Snapshot powers are aggregated
by median in linear units, then converted to dB. The measured levels are
relative to the stored IQ scale. The 125 Hz search covers moderate drift; a
larger shift, an in-band interferer, or a strong adjacent signal can bias the
estimate. The stage 3 output left `decode_confidence` as `null` and the
quality status `partial`; stage 4 now fills supported intervals.

On the supplied 30-minute Mac capture, one, two, and four snapshots per second
each produced 1,800 output points in 0.64, 0.66, and 1.33 seconds of analysis
wall time respectively. CPU times were 0.36, 0.54, and 1.03 seconds; logical
IQ reads were 59, 118, and 236 MB. Peak process RSS was approximately 187,
276, and 283 MB, including the loaded diagnostic reference and mapped input.
At the four-snapshot default, 7,200 windows of 4,096 CF32 samples request
235,929,600 logical IQ bytes, roughly one additional read of the 230.4 MB
capture by volume. Adjacent windows overlap slightly. This is a separate
read-only analysis pass, not another MFSK decode.
The one-snapshot result resolved signal in 1,690 seconds and noise in all
1,800; four snapshots resolved signal in 1,691 seconds. Among seconds where
both produced a signal value, the median absolute difference was 0.335 dB;
the noise median difference was 0.595 dB, with larger differences near
transitions. Four snapshots per second is the v1 default: its windows cover
nearly the whole second, while the measured incremental CPU cost remains about
one second for the full capture. Fewer snapshots remain available if a
resource-constrained consumer later justifies trading within-second coverage
for lower I/O. These figures measure the additional analysis pass, not a full
decoder rerun. A target Pi check is useful for the first appliance integration,
but is not a library release gate.

## Compatible API and CLI evolution

Keep `grampy.api.decode_iq(...)` and its `grampy-decode-manifest.v1` return
value unchanged. Add a new public `decode_iq_products(...)` with the same
input, interval, configuration, and artifact arguments. It returns a typed
`DecodeProducts` result containing `text_manifest`, `quality_manifest`, and
optional `diagnostic_manifest`; one call performs one decode. Give the new
call an `include_diagnostic_manifest: bool = False` option. With the default,
the legacy combined document is neither assembled nor returned. With `True`,
the same decode also returns the existing validated v1 diagnostic document.
The product call must expose partial outcomes and warnings rather than claim
complete output for a failed stage. A file writer may serialize the two
product dictionaries atomically one file at a time; readers verify their
shared run and input identity before combining them.

Add CLI `--out-text-manifest` and `--out-quality-manifest` paths. Keep the
existing `--out-manifest` invocation working. An invocation with both new
paths and no `--out-manifest` writes only the two compact JSON files and image
artifacts; this is the appliance production form. Supplying `--out-manifest`
explicitly requests the legacy diagnostic file, either alone as today or
alongside the new files. Requesting all three outputs must not run the decoder
twice. Large PNGs remain separate artifacts. Do not create an empty legacy
file as a placeholder. Internal character events still needed for framing and
picture detection may be computed transiently; skipping the large document
does not promise to avoid that decode work. Measure saved serialization time,
write bytes, and peak memory rather than assuming a runtime improvement.

The two compact manifests retain input hashes, decoder version,
configuration identity, and run ID so a diagnostic rerun can select the same
recording and settings. Reproduction may also depend on retaining the original
decoder build and dependencies; a rerun after code changes is not guaranteed
to reproduce a byte-identical development manifest.

## Stages and acceptance

1. **Fixture and baseline.** Promote the matched appliance capture, metadata,
   completion record, existing decoder manifest, text, PNGs, and component
   evidence into the ignored received corpus. Exclude reproducible WAV files.
   Hash every retained file, verify the SigMF pair against the manifest, and
   register a full-broadcast case. Record existing decode time and output
   inventory. Appliance `decoded.txt` and decoded images are compatibility
   references, not independent truth.
2. **Text product.** Define and validate the text schema, then build ordered
   text and picture items from decoder internals. Verify mode order, nine
   pictures, stable links, framing/uncertainty handling, and readable content
   on short virtual intervals and controlled fixtures. Reserve the full case
   for integrated acceptance. Compare content with the saved reference without
   assuming exact agreement is truth. Keep `decode_iq` behavior unchanged.
3. **Reception quality.** Measure post-AGC signal and noise independently of
   decode decisions. Run the cadence and implementation-cost comparison above;
   verify behavior on quiet, fading, drifting, and interfered intervals as
   available. Add an explicitly unavailable result where a signal cannot be
   identified. Do not call an unvalidated contrast estimate calibrated SNR.
4. **Decode quality.** Define and version a confidence proxy using text and
   image evidence. Produce exactly the same one-second grid as reception
   quality, including `null` values and reasons. Compare against controlled
   fixture truth and reviewed received cases before choosing color thresholds.
   High reception with low decode confidence must remain representable.
5. **Integrate and close.** Add the new API and CLI paths without duplicate
   decoding; validate both JSON schemas, failure publication, artifact links,
   and cross-file identity. Run the legacy `decode_iq` output path once and
   the new product path once on the supplied full capture, sequentially on
   the same development machine with the same decoder version, configuration,
   and artifact settings. The product run is the full-broadcast acceptance;
   the legacy run is its performance baseline. Compare total and per-stage
   wall/CPU time, peak RSS, bytes read/written, and output sizes, reporting
   both absolute and percentage changes. The saved
   ARM64 timing remains historical context only. An optional representative Pi
   check can inform the first appliance deployment when a target is available;
   it is not required for the generic library or PyPI release. If that check
   reveals a resource problem, investigate the affected path before appliance
   deployment.
   After acceptance, update `README.md`,
   `docs/decoder/{api,cli,design,contracts,validation,production-baseline}.md`
   as applicable, add a concise closeout, and move this active plan to
   `docs/provenance/archive/`. Archive only after the new behavior is accepted.

## Proportionate regression and full acceptance

This is an output and measurement change, not an intended change to MFSK
decoding. Routine regression should use small deterministic tests for schema,
framing, one-second sample bins (including partial final bins), missing data,
image-to-text links, and compatibility of `decode_iq`. Short virtual IQ cases
from the existing corpus should cover MFSK32 text, the MFSK32-to-MFSK64
change, at least one image and return to text, the closing mode change, and a
weak or drifting interval. Reuse the canonical full IQ through case intervals;
do not materialize or preserve cut recordings.

At integrated acceptance, decode the supplied complete 30-minute broadcast
**once per candidate release** with the product path, after one same-machine
legacy baseline run. Check
that its text and nine picture outputs, mode order, status, and warnings do
not regress against the pinned decoder reference; check that both new files
share identity, contain 1,800 aligned quality points, omit the legacy file
by default, and represent picture and no-lock intervals honestly. Compare the
new run's decode, quality pass, serialization, and total wall time, CPU, peak
RSS, and I/O with that legacy baseline. This product run is a compatibility
and integration gate;
the saved appliance decode is not independent truth and cannot by itself
validate SNR calibration or true character accuracy.

Run the existing relevant test suite before acceptance. The new IQ pass makes
bounded, read-only accesses and does not change decoder decisions. Existing
Pi 3 evidence establishes that the decoder runs on the target architecture;
stage 5 needs no Pi-specific correctness gate. A short Pi cost check is
optional for the first appliance consumer because its storage and memory are
more constrained than the development machine. Any later refactor that shares
spectra with acquisition must requalify the affected decoder path instead of
relying solely on these output-focused tests.

## Closeout

Stages 1–4 were committed separately. Stage 5 added `decode_iq_products`,
two compact CLI output paths, opt-in diagnostic assembly, and schema-aware
atomic publication without changing the MFSK decode algorithms. The paired
Mac runs on the canonical 1,800-second capture took 133.19 seconds for the
legacy diagnostic path and 134.05 seconds for compact products. Compact JSON
was 131,215 bytes against 16,073,902 bytes for the diagnostic JSON. All
18 artifact hashes matched; three mode intervals, nine linked pictures, 35
text items, shared identity, and 1,800 aligned quality rows were verified.
Signal, noise, and confidence were available for 1,691, 1,800, and 1,621
seconds respectively. The full suite passed 169 tests with six skips.
A short real-capture invocation requesting all three files published matching
partial documents with a shared run ID and 20 quality rows from one decode.

The compact path adds 235,929,600 logical IQ bytes read for sparse spectral
measurement. The paired wall-time difference was +0.86 seconds (+0.6%),
while published bytes including artifacts fell by 69.2%. Maximum RSS rose
from 398.2 MB to 556.2 MB on macOS; its separate peak memory-footprint
figure fell from 274.6 MB to 253.7 MB. This is a resource observation for
appliance qualification, not a change in decode correctness. The shared
decode stages have the same implementation in both paths; the compact-only
contract omits development timing diagnostics, so independent per-stage
candidate timings were not recorded in the product file. The stage 3 isolated
spectral-pass benchmark measured 1.33 seconds wall and 1.03 seconds CPU at
the selected four snapshots per second. The paired whole-command timing is
the relevant production-path cost. No Pi test was required for generic
library acceptance; appliance-specific cost can be checked before deployment.
