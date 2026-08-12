# GramPy Extraction Boundary

This record fixes the intended boundary for the GramPy breakout. It is the
source of truth for Phases 2–4 of `grampy_breakout_plan.md`; implementation
details may change, but an exception to an ownership decision below requires
an explicit update here.

## Ownership

| Area | Owner after breakout | Decision |
| --- | --- | --- |
| Direct MFSK IQ decode implementation | GramPy | Move all modules now under `src/radiogram/mfsk/`, including the SigMF adapter, pipeline, text and picture decode, tracking, wire protocol, accuracy, corpus, and fixture-support code. |
| Public callable interface | GramPy | Add `grampy.api` as the only interface used by Radiogram. It will expose `DecodeConfig` and `decode_iq(...)`; its exact input/result types will be defined with the implementation. `cli.py` remains an adapter, not the library API. |
| RSID support used by acquisition | GramPy | Copy the minimal self-contained `RsidDetection`, `detect_rsid`, and their required helpers from `radiogram.iqprep` into GramPy. GramPy must not import `radiogram.iqprep`. |
| `iqprep` command and capture preprocessing | Radiogram, temporary | Keep it in Radiogram for the breakout transition. It is not a GramPy dependency and is planned for removal before Radiogram production. |
| Radio discovery, configuration, capture, and daemon operation | Radiogram | Retain. |
| Received corpus | GramPy test support | Move the durable `received-corpus` test corpus. It remains unversioned and is installed by GramPy's future corpus setup tool. Do not move general Radiogram capture samples. |
| Controlled fldigi fixture artifacts | GramPy test support | Move fixture evidence, generation/verification support, and their test contracts. Large generated artifacts remain local and are not committed. |
| Radiogram operational sample/iqprep regressions | Radiogram | Retain the `iqprep` sample artifacts and tests as long as `iqprep` remains. |

## Migration inventory

The following items must receive a move/retain/retire disposition during
Phase 2. The default disposition shown here is the current decision.

| Item | Disposition |
| --- | --- |
| `src/radiogram/mfsk/` | Move to GramPy. |
| `tests/test_mfsk_*.py`, `tests/test_analyze_mfsk_color_fixture.py`, and MFSK-only test helpers | Move to GramPy; split helpers shared with an `iqprep` test only when necessary. |
| `tests/fixtures/mfsk/` | Move to GramPy. |
| `tests/samples/received-corpus/` | Move as a temporary local copy, then install through GramPy's corpus tool. |
| `src/radiogram/schemas/mfsk-decode-*.json` | Move to GramPy package data. |
| `docs/decoder/` MFSK specifications, contracts, validation, corpus material, and decoder data | Move to GramPy, after separating non-decoder product/operations references. |
| `tools/mfsk-*`, `tools/analyze-mfsk-color-fixture`, and MFSK fixture-generation scripts | Move to GramPy unless explicitly identified as a Radiogram deployment/integration tool. |
| `tools/pi-test-mfsk-r5.sh` | Move or replace with GramPy's managed test entry point. |
| `tools/pi-test-iqprep-*` and `tests/iqprep/` | Retain in Radiogram while `iqprep` remains. |
| `tools/decode-reference-captures`, release/deploy scripts, and radio operations documentation | Retain in Radiogram unless a later review identifies a decoder-only portion. |
| `history/` records | Retain in Radiogram for now; copy only the evidence needed for GramPy documentation, rather than moving the full project history. |

## Required technical changes in GramPy

- Replace decoder reads of `docs/decoder/data/mfsk_varicode.json` with package
  resources.
- Replace decoder reads of `src/radiogram/schemas/mfsk-decode-*.json` with
  package resources.
- Replace CLI defaults based on repository-root paths with package resources
  or explicit command-line arguments. Local fixture roots may remain
  configurable, but must default relative to the GramPy checkout only in
  development tooling.
- Remove `radiogram.*` imports and output assumptions from moved modules and
  tools.
- Test the installed GramPy wheel, not only the source or editable checkout,
  to prove schemas and decoder data are packaged correctly.

## Compatibility decisions to make before moving output contracts

Existing decoder manifests, terminal-failure documents, scorecards, fixture
evidence, and checkpoints use `grampy.*` schema identifiers. Phase 2
chooses corresponding `grampy.*` identifiers. GramPy has not yet been
published, so there is no external compatibility promise to preserve. The
initial public release will document these as new contracts; any later rename
requires an explicit versioned compatibility and migration policy.

## Transitional integration contract

Before the temporary `GramPy` symlink is removed, Radiogram will install the
sibling GramPy checkout as an editable development dependency and use only
`grampy.api`. Decoder tests live in GramPy. Radiogram keeps focused integration
tests covering the production call path.

After removing the symlink, reinstall the same GramPy checkout by its real
path and rerun both suites. This is the required proof that the decoder was
moved intact and that Radiogram is not accidentally using leftover
`grampy` source. The local editable dependency is temporary and is
replaced by the published, pinned GramPy wheel in Phase 7.
