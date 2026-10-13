# Sidecar and committed evidence audit

Date: October 13, 2026. The reviewed inventory records the source revision.
Scope: 382 original sidecar files, 281 tracked structured/visual evidence
artifacts, test dependencies and supplementary tracked text/assertion scans.
This is a working-tree provenance and maintenance audit, not a rewrite of Git
history or a determination of third-party publication rights.

## Resulting storage boundary

Git holds independently authored code, protocol vectors, small native evidence,
recipes, case definitions and non-content acceptance metadata. Broadcast-origin
and uncertain-origin content stays external regardless of size, including
derivatives and copied expectations. Large native artifacts also stay external.
The [maintenance guide](sidecar-maintenance.md) defines the native fixture size
budget, test selections, required/optional inventory and S3 handoff.

The reviewed installed sidecar has **303 files, 2,802,512,767 bytes** excluding
Finder metadata: **246 required files, 2,378,911,886 bytes**, and **57 optional
archive files, 423,600,881 bytes**. The original installation had
3,157,711,466 bytes. Net reduction is **355,198,699 bytes**, about 355 MB;
these are logical file sizes, not a measurement of physically freed disk space.

## Dispositions

| Original group | Decision and retained value |
| --- | --- |
| `received-corpus/` | Preserve canonical RF, broadcast truth and receiver references. Source/reference identities and broadcast acceptance inputs are unchanged. Update its native README to the current GramPy policy. |
| `reference-captures/` | Retire duplicate September 23 intake after matching canonical counterparts. Discard the unused derived diagnostic WAV and metadata. Preserve the text manifest externally under `archive/intake-products/`; promote the non-content quality series example into Git. |
| `controlled-mfsk-v1/` | Preserve accepted independently generated transmissions externally for size. Git already contains project-authored source vectors, expectations and independent validation identities. No fixture replacement or repinning was needed. |
| Controlled `.tar.gz` | Retain the exact accepted 25 MB bundle under `archive/distribution/`, explicitly optional. Tests consume the extracted fixtures. |
| `quality-calibration/` | Retire unused development decodes from canonical July 8 RF. Preserve source identities, intervals and decoder configurations in the recipe record. |
| `stage5-performance/` | Retire unused decode/product copies of canonical September 23 RF. Preserve source identities, intervals and decoder configurations; current performance assertions remain in tests. |
| `provenance/20261012-local-cleanup/` | Separate optional history under `archive/20261012-local-cleanup/`. Preserve unique September 19 RF and historical waveforms; none is a current normal-test dependency. |
| Historical wheel | Discard the unused 166 KB generated package. Preserve its identity and package/source/validation records in Git; do not promise an identical-byte rebuilt wheel. |
| Qualified receiver executable | Retain the 67 MB pinned historical binary as optional large software evidence, not a runtime fixture or something maintainers must install for normal tests. |

107 duplicate or unneeded development files were discarded, totaling
358,696,021 bytes. 59 promotions/relocations were verified before originals
were retired. The net sidecar reduction differs because previously committed
broadcast-derived evidence was moved into it.

## Corrections to committed evidence and tests

29 committed artifacts were externalized: broadcast photograph/card derivatives,
combined HTML/image review pages and a historical test inventory containing
copied assertion content. They remain byte-identical in
`tests/samples/archive/repo-evidence/`, with their original directory hierarchy.
Markdown now links to those external artifacts rather than embedding their
content in the repository. Numeric qualification results remain in Git.

56 native visual artifacts examined during promotion were retained in Git after
reviewing their documented independently authored primary-colour vectors and
diagnostic chart. The native basis is the checked-in fixture generator, Session
8 composition/source records and Session 9's manual-control source description.
Native chart outputs and lab-pattern receiver comparisons are distinct from the
photograph/card cases sourced from the broadcast corpus. Uncertain historical
content is kept externally, without claiming independent provenance.

The native historical `prepared.json` was promoted to
`docs/encoder/data/session9/prepared.json` after reviewing the checked-in
`session9_broadcast.py` preparation recipe. Its framing labels are authored by
that recipe; it contains artifact identities and numerical checks, not original
photo pixels or received broadcast passages. The small quality-series example is also promoted to
`docs/decoder/data/received-quality-series-example.json`; its reviewed schema
contains engineering configuration, formulas, identities and aggregate numeric
measurements, without broadcast payload. Project-authored received-case
definitions are now in `tests/fixtures/received-cases.json`. Copied broadcast
header strings stay in external case records; the historical seed retains only
their non-content geometry.

Two received test modules embedded three broadcast text expectations. Their
exact original expectations now live in
`tests/samples/regression-expectations/heldout-text.json`, bound by a committed
path/hash/size manifest. Tests still check the same substrings, acquisition and
epoch behavior. Missing or altered expectation data fails. No decoder code,
accepted numerical threshold or required signal recording was changed.

## Verification and remaining handoff

Validation results are recorded in the
[audit closeout](../provenance/changes/20261013-sidecar-audit/README.md).
The full inventory verifier includes optional history. Checkout-only regression
is exercised with an absent sidecar override and a guard rejecting actual
sidecar file opens. The complete regular suite exercises both external tiers.
All 88 broadcast acceptance input identities are checked against the current
baseline. A new fifteen-minute broadcast decode is unnecessary for this storage
audit because the decoder, selected input bytes and quality limits are unchanged.

The local sidecar is ready for a **new versioned S3 handoff**. S3 was not modified.
Maintain the previous release until the new required directories and optional
archive are installed and verified elsewhere. The legacy corpus-only packaging
tools do not cover the whole sidecar. Include the new external expectation file
when distributing the received tier.

Previously committed externalized material still exists in older Git commits.
Removing historical objects would require a separately authorized history
cleanup and coordinated publication; this audit does not do that. It also does
not imply that an exact-line text scan proves the provenance of every historical
sentence. The reviewed artifact identities, conservative decisions and known
inline-content corrections are recorded explicitly rather than inferred from
filenames or from successful tests.

The [disposition ledger](../provenance/changes/20261013-sidecar-audit/disposition.json)
records every original sidecar file, the structured/visual evidence review and
each move/deletion. The [installed inventory](../../tests/fixtures/sidecar-v1.json)
records current destinations and hashes. Earlier cleanup receipts remain
historical snapshots; this audit supersedes their old path/retention statements.
