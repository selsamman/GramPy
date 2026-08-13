# Direct MFSK IQ Decoder — Session 1 Handoff

**Completed:** 2026-07-26  
**Scope:** reference-pipeline and harness

## Result

Session 1 establishes the standalone `radiogram.mfsk` package and
`mfsk-iq-decode` CLI. It deliberately stops at validated IQ inventory and
reports `status: partial` plus `decode-stages-pending`; acquisition and decoded
events are not fabricated.

The implemented harness provides:

- strict `ci16_le` and `cf32_le` SigMF validation;
- complete-file SHA-256 identities and deterministic run IDs;
- requested half-open input intervals and exact rational `SampleMap` support;
- explicit immediate-parent trim ancestry without changing authoritative
  supplied-IQ coordinates;
- bounded NumPy memory-map conversion and clipping/non-finite inventory;
- JSON Schemas for decoder configuration and the output manifest;
- atomic manifest publication and no persistent IQ/evidence intermediates;
- wall time, CPU time, peak RSS, bytes read/written, repeated-read, transform,
  and temporary-storage fields;
- tested convolutional encoding, fldigi Gray labeling, tone-metric-to-coded-bit
  LLR mapping, and four-lane soft deinterleaving; and
- a CLI integration test proving the output directory contains only the two
  inputs and final manifest.

The schema and event collections are intentionally extensible objects in this
session. Each later vertical slice must tighten the schema for the event type
it begins emitting.

## Measured result

The focused Session 1 suite contains eleven tests and completes in under one
second on the development machine. Full-suite results are recorded in the
implementing change/session report rather than frozen here because runtime and
skip counts depend on the locally available large corpus.

## Unresolved decisions

- No tone estimator, clock treatment, carrier/clock coupling, or Viterbi
  confidence technique is selected yet; Session 1 does not generate evidence
  capable of comparing them.
- Hashing necessarily reads the complete IQ once; inspecting a requested
  interval reads that interval a second time. The manifest exposes this as
  repeated input sample reads so later full-broadcast measurements can justify
  hash caching or fusion if needed.
- Failure diagnostics are currently returned on stderr with a nonzero exit
  before publication. A schema-valid terminal-failure manifest will be added
  when the pipeline has recoverable stage failures to distinguish from invalid
  invocation/input.
- `ci16_le` and `cf32_le` are the required first-release types. Other
  `iqprep`-supported types remain ingest extensions.

## Next vertical exit criterion

Session 2 must make controlled fixture availability repeatable and
provenance-verifiable without cutting the received corpus. It exits when the
pinned fldigi analytic-IQ text and picture artifacts are inventoried, every
available artifact hash matches `../../../mfsk_fixture_evidence.json`, missing
minimal
happy-path fixtures have a repeatable generation path, and tests skip clearly
when large local artifacts are unavailable.
