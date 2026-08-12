# MFSK Received-IQ Corpus Policy

**Status:** adopted for direct-IQ decoder Session 8 and ongoing optimization

## 1. Purpose

The received-IQ corpus is durable product evidence for direct MFSK decoding.
It is expected to grow as new propagation conditions, receiver faults, and
decoder limitations are observed. This document defines storage, selection,
annotation, and admission policy for that continuing corpus.

The corpus complements fixed protocol vectors under `tests/fixtures/`,
controlled fldigi analytic-IQ fixtures under `RADIOGRAM_MFSK_FIXTURES`, and
disposable reference recordings collected for exploration. The contracts and
evidence hierarchy in `mfsk_iq_decode_implementation_spec.md` remain
authoritative.

The selection matrix deliberately includes both preferred Airspy HF+ and
entry-level RTL-SDR receptions. Only one good antenna is available, so these
are not matched receiver experiments: propagation, station, time, and program
differences confound comparisons between their absolute results. The corpus
uses the mixture to expose receiver-sensitive decoder assumptions and to
require useful behavior across the supported hardware range. Direct-decoder
and fldigi outputs remain comparable within the same immutable capture.
Receiver-subset scorecards are reported, but they must not be presented as a
controlled Airspy-versus-RTL hardware comparison.

## 2. Storage boundary and lifecycle

Large artifacts are not committed to Git. `tests/samples` remains ignored and
may be a symlink to local or cloud-backed storage. The single durable root for
received-corpus material is:

```text
tests/samples/received-corpus/
```

`tests/samples/reference-captures/` is an intake and exploration area. It may
be regenerated or deleted and is not a corpus dependency. A capture becomes
durable only through explicit promotion into `received-corpus/`.

A promotion:

1. verifies that the recording is complete enough for its claimed use;
2. computes hashes before and after copying;
3. copies the original SigMF pair and non-reproducible capture provenance into
   the durable root;
4. records source identity, hashes, byte sizes, and promotion date in the
   corpus manifest;
5. creates case annotations that refer to the durable copy; and
6. verifies that tests and cases have no intake dependency before deletion.

The durable corpus must be self-contained. It must not contain symlinks or
path references to `reference-captures`, a receiver host, temporary output, or
another artifact store. Cloud-provider history is useful recovery protection
but is not the corpus provenance model.

## 3. Program-centered durable layout

The logical corpus is organized by program rather than reception date. A
program identifies one transmitted content set: one reviewed text and one
ordered image set. Archive audio and received IQ are transmissions or
observations of that program. Multiple stations, dates, receivers, and
propagation conditions may therefore point to the same truth without
duplicating it.

Large canonical recordings remain immutable under `sources/`, keyed by
capture identity. Program transmission records refer to those source IDs.
This separates the content question ("what was sent?") from the reception
question ("what was observable in this capture?").

```text
received-corpus/
  README.md
  corpus.json
  programs/
    <program-id>/
      program.json
      truth/
        text.txt
        text-review.json
        images/
          <order>-<stable-name>.<ext>
      archive/
        audio/
          <archive-id>.wav
          <archive-id>.json
        text-drafts/
          <archive-id>-direct.txt
      transmissions/
        <transmission-id>.json
  sources/
    <capture-id>/
      capture.sigmf-data
      capture.sigmf-meta
      capture.capture.json          # when available
      capture.log                   # only when non-reproducible and useful
  cases/
    <case-id>/
      case.json
      expected.txt                  # when independently established
      annotations.json              # optional detailed event annotations
  references/
    <case-id>/<decoder-id>/...      # selected version-pinned output
  derived/
    <case-id>/<derivation-id>/...   # controlled impairment data and recipe
```

`programs` contains independent content truth, archive audio, and links to
transmissions; `sources` contains immutable received recordings; `cases`
contains small annotations and virtual intervals; `references` contains
selected decoder evidence, never automatic truth; and `derived` contains
intentionally transformed IQ with reproducible provenance.

New Airspy development/reference sources should preserve channelized CF32 once
the experimental capture profile is validated. Deterministic CI16 versions
belong under `derived`, linked to the immutable CF32 parent with the conversion
implementation/version, scale, rounding, saturation, dither policy, hashes,
and coordinate identity. They are not independent receptions and must not be
hierarchically counted as additional broadcasts. Existing native CI16 sources
remain first-class corpus evidence.

Periodic RTL-SDR capture on the good antenna should add representative program
material across both modes, text and pictures, transitions, and varied
reception conditions. The earlier weaker-antenna RTL recording remains a
useful adverse case and is identified by its antenna/capture provenance rather
than replaced.

Program picture order is explicit in `program.json`; numeric filename prefixes
are only a human-readable mirror of that order. A picture whose broadcaster
source is not yet available remains in the ordered payload with
`pixel_truth_status: missing`. Its event and geometry remain scoreable, while
pixel scoring reports `not_scored_missing_truth`. A manifest that declares
truth available but references an absent file is a corpus verification error.

Published receiver transcripts may have lost control characters during copy
and paste. Reviewed program text therefore records its normalization and
approval independently of decoder framing. Current Session 9A presentation
normalization concatenates complete received payload epochs and ignores line
wrapping. STX/EOT recovery remains decoder diagnostic evidence.

Existing date-keyed truth artifacts may remain readable during migration, but
new program material belongs below `programs/<program-id>/truth/`. Session 9A
will update `corpus.json` only after the program identities and supplied
materials are inventoried; no program/date association is inferred merely
from filename proximity.

Capture IDs and case IDs are stable identifiers, not mutable quality labels.
A suitable capture ID includes station, UTC start, and RF frequency. A case ID
adds the capability or observed condition:

```text
wrmi-20260708T133001Z-15770000
wrmi-20260708-picture-return-01
```

## 4. File-size policy

Store each canonical full IQ recording once. Short and partial cases normally
refer to half-open sample intervals in that recording:

```text
source_capture_id
start_sample
stop_sample
lead_context_samples
trail_context_samples
```

Do not materialize a separate IQ cut merely to make a test faster. A cut is
permitted only for portability, target-Pi installation, datatype conversion,
or a demonstrated runtime constraint. It retains its parent hash, exact
interval, transformation command and version, output hash, and coordinate map.

Do not preserve reproducible WAV files, corrected IQ, spectrograms, traces,
temporary arrays, or routine decoder output. Preserve the recipe and tool
version instead. An exception is allowed for independent truth, an artifact
that is expensive or impossible to reproduce, a version-specific
compatibility result, or a deliberately pinned regression result. Record its
purpose, producer/version, parent hashes, byte size, and retention status.

At the current 48 kHz `ci16_le` handoff, a 30-minute complex recording is about
345.6 MB. Preserve a small stratified set of full broadcasts rather than all
intake recordings. Before adding a large artifact, identify the previously
uncovered station, band, protocol event, impairment, severity, or truth source
that it adds.

The manifest reports total bytes by retention class. Hash verification and a
missing-file audit must be repeatable. Canonical sources and independent truth
have no automatic pruning policy; removal is an explicit corpus-version
decision.

## 5. Selection policy

Select cases for protocol and RF coverage, not merely because the current
decoder fails. “Bad decoding” is an observed outcome; fading, interference,
offset, clipping, acquisition loss, protocol damage, or a decoder defect may
be the cause.

### Protocol coverage

The corpus collectively covers:

- acquisition from noise and starts already in progress;
- opening RSID, MFSK32 text, and MFSK64 text;
- MFSK32/MFSK64 changes in both directions;
- text-to-picture alignment;
- supported grayscale/color and samples-per-component forms;
- complete, consecutive, and intentionally truncated pictures;
- picture-to-text reacquisition;
- EOT and loss of signal; and
- recovery when no nearby RSID is available.

### RF and capture coverage

Record measured values where possible, with human categories as secondary
search labels:

- carrier offset, drift, and discontinuities;
- noise or a declared SNR proxy;
- flat and selective fading, including depth and duration;
- short and long dropouts;
- narrowband, wideband, impulse, and adjacent-signal interference;
- clipping, gain changes, DC/IQ artifacts, and insufficient guard band;
- orientation ambiguity; and
- receiver, station, frequency, date, and propagation-path diversity.

For important impairments, seek clean, mild, moderate/recoverable, and
severe/ambiguous examples, including the point at which usable signal returns.
Natural cases establish realism. Controlled transformations of genuine cases
establish known offset, drift, fade, noise, dropout, and interference severity.

### Minimum initial shape

The Session 8 planning target is:

- three to five full broadcasts spanning good, ordinary, and difficult
  reception and more than one station when available;
- five to eight partial cases covering acquisition, mode/picture transitions,
  consecutive pictures, damage, and reacquisition;
- twelve to twenty short diagnostic cases covering clean anchors and distinct
  natural impairments; and
- controlled impairment grids from a few representative clean cases.

These are planning bounds, not quotas. A smaller set with complete coverage is
better than redundant clean cases. A new marginal case is admitted only when
its expected evidence gain is recorded.

## 6. Annotation and truth

Every short or partial case records:

- capability or behavior under test;
- source capture ID and hashes;
- half-open input interval and required context;
- checkpoint or hint assumptions;
- expected events and tolerances;
- annotation source and precision;
- impairment measurements and severity labels;
- direct-decoder and fldigi outcomes as separate evidence;
- why the interval is long enough; and
- why the case adds coverage.

Truth has explicit strength:

1. `authoritative`: exact broadcaster source or independently fixed vector;
2. `strong_reference`: published material, repeated-reception agreement, or
   independently measured events;
3. `compatibility_reference`: version-pinned fldigi output; or
4. `ambiguous`: reception damage prevents a defensible expected value.

Fldigi output is never promoted implicitly to ground truth. Comparisons
classify both decoders correct, a direct-decoder gap, a demonstrable
direct-decoder improvement, disagreement requiring review, or ambiguous loss.

For broadcaster images, retain the exact transmitted file when available,
its hash, program/date/order, dimensions and color mode, and any preprocessing
or fldigi conversion information. Retain both raw and alignment-corrected
comparisons: the former exposes geometry and clock errors, while the latter
better isolates component estimation and RF damage.

High-quality archive audio may be used to create a draft program transcript
with the direct decoder while picture processing is disabled. Preserve the
archive WAV, its provenance and hash, the unedited draft output, and the final
reviewed text. Once a named human review has resolved or explicitly marked
uncertain passages, the transcript is authoritative program truth by sign-off,
not by virtue of the decoder that produced the draft. Pinned fldigi decoding
is optional corroboration for disputed passages and remains compatibility
evidence unless independently reviewed.

Program truth and transmission observability are recorded independently. The
program manifest always lists the complete known text and ordered image set.
A transmission may separately classify an element as observed,
recoverable-but-missed, capture-limited, or ambiguous, with the evidence for
that classification. Failure by both direct decoding and fldigi is useful
evidence but is not by itself proof that information is absent from the
recording.

## 7. Development, regression, and acceptance

Assign every case to one primary partition:

- `development`: available for estimator and algorithm tuning;
- `regression`: stable routine checks changed only deliberately; or
- `acceptance`: held-out full broadcasts used to set and verify thresholds.

Assign repeated transmissions carefully so exact content does not leak from
development into acceptance. Repeated receptions of one program are distinct
RF cases but not independent content cases; group them by program in aggregate
reporting so they do not overweight that content. A case extensively examined
during remediation is no longer genuinely held out even if its partition
previously said `acceptance`. Include good, ordinary, and difficult full
broadcasts in acceptance where available, and acquire a new sealed program
when future tuning requires a truly unseen result. Set thresholds from the
full-broadcast baseline rather than choosing them in advance.

Metrics include event- and byte-level text accuracy, prefix/suffix behavior,
transition coordinates, damage reporting, reacquisition time, raw and aligned
image quality when truth permits, time to useful results, total runtime, peak
memory, reads, writes, and temporary storage.

## 8. Ongoing admission and review

The corpus has explicit versions. Adding a case does not silently change an
existing acceptance result. Each addition states:

- new coverage or impairment evidence;
- whether an existing case can retire without losing coverage;
- storage added;
- intended partition; and
- effect on thresholds or historical comparisons.

Periodically generate a coverage report from the manifest. It should expose
empty protocol/impairment cells, redundancy, missing truth, missing files,
hash failures, and storage by retention class. Optimization follows measured
gaps while held-out evidence remains independent.
