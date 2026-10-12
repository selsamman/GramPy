# Test rationalization: phase 1

Date: 2026-10-11. Status: validated and staged for user review; no phase commit
has been created. Based on the
[coverage audit](test-coverage-audit.md) at `2126385`.

## Five-phase plan

1. Rationalize redundant tests and separate historical workflow contracts from
   current product validation. This document records that change.
2. Repair required controlled-fixture coverage and centralize sidecar integrity.
3. Establish repeatable real-corpus decoder quality acceptance with approved
   cases/limits and explicit failing exit status for incomplete/failed runs.
4. Document test creation, replacement/retirement and phase closeout retention.
   Validation must be reproducible from a checkout plus documented retrievable
   dependencies; required data must have a durable home and temporary outputs
   must have a deletion point.
5. Execute the resulting `.local` retention/deletion decisions.

Review and commit each phase separately before starting the next. These phases
are checkpoints in this maintenance effort, not modifications to the general
change-management process. No runtime algorithms, fixture identities or quality
limits change in phase 1.

## Changes and assertion destinations

| Previous check | Action | Coverage retained |
| --- | --- | --- |
| R3 parser chunk/checkpoint provenance | Consolidate into 11C parser checkpoint method | Both calls with and without input coordinates, whole/split equality, confidence 0.8, increasing source-bit intervals, increasing supplied input intervals. |
| Wire-vector Varicode table structure | Consolidate into encoder independent-oracle method | Schema, 256 unique codes, start/end/termination rules, every fixed octet from the old test plus the survivor's additional octets. Production encoder mapping tests remain distinct. |
| Wire-vector fixture metadata claims | Consolidate into fixture-inventory matrix method | Schema, four entries/unique IDs, complete artifacts, valid hash syntax, transmitted/decoded text equality and recorded receiver-image claims. These remain provenance checks, not a live receiver decode. |
| Frozen reference WAV measurements | Retire constant-only method | The independent-oracle identity method still pins the full evidence document hash and packaged copy. The removed method read saved constants, never WAVs; no current waveform measurement is lost. The six missing actual-fixture checks remain a phase 2 gap. |
| v1 matrix/schema and v2 draft contract | Move unchanged assertions into explicit historical workflow tests | v1 input hashes, composition/case coverage, schema/sample-record validation and v2 RxID policy all remain runnable alongside historical reproduction. They no longer count as current product regression checks. |
| Package/API/docs combined method | Remove editorial phrase assertions and rename | Package name, Python support, Pillow dependency, public exports and absence of an encoder CLI entry point remain. Prose wording is handled by documentation review. |

The historical methods are in
[`test_historical_contracts.py`](../../experiments/mfsk-wav-encoder/test_historical_contracts.py).
The current standard suite gains
[`test_mfsk_practical_qualification.py`](../../tests/test_mfsk_practical_qualification.py):

- Required mode/colour/speed coverage, unique cases and mixed-composition case
  in the frozen maintained v3 matrix.
- The existing scoped numerical limits and geometry/text/acquisition/visual
  requirements, without promoting them to universal corpus thresholds.
- Actual receive-harness invocation/configuration: the full supplied WAV,
  initial unrelated mode, continuous RxID, no AFC/manual mode changes, and
  preserved recorded interval/input identity. Subprocesses are mocked; the
  tests do not run fldigi or claim receiver quality.
- Rejection of changed input before the receive adapter executes.

The original v3 matrix remains frozen, including its original MFSK64 picture
scope. Later MFSK32 acceptance is recorded separately and is not rewritten by
this phase.

## Deliberately deferred

The six missing-fixture methods still skip. Quality comparisons and reference
data validation are phase 2/3 work. The estimator-relative-ranking assertion
needs a justified replacement acceptance bound and is not weakened here.
Supported estimator, local boundary guard, waveform, state, memory and file
safety tests remain. There is no wholesale session-file renaming or deletion.

The pre-change audit/inventory remains an immutable assessment of `2126385`;
it is not regenerated to erase the original findings. This record maps the
completed phase 1 changes to that baseline.

## Validation

Run using the repository virtualenv and managed Mac wrapper. The phase batch
runs both:

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m unittest discover -s experiments/mfsk-wav-encoder -p 'test_*.py'
```

The standard suite contains 245 methods (248 originally, seven removed
or moved, four current-workflow methods added). The explicit historical/workflow
suite contains 14 methods: the three moved contracts plus five existing
qualification integrity tests and six practical gate sensitivity tests.

Final validation passed: **239 standard methods passed, six known fixture
skips, zero failures/errors**, in 144.701 seconds. All **14 explicit workflow
methods passed** in 0.976 seconds. The managed command completed with exit
status zero after 147 seconds; see its
[completion record](data/test-rationalization-phase1-result.md).

The three historical method bodies were also checked against the originals
and are unchanged. Syntax, documentation links, source-method counts and diff
whitespace were verified. An initial run exposed a removed constant still
needed by another test and a subprocess mock that interfered with host
identification; both were corrected, focused checks passed, and the full run
above validates the final code.

A successful unit run still does not establish real-corpus quality acceptance;
that remains the priority for phase 3.
