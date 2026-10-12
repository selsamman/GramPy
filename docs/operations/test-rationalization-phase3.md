# Phase 3: full-broadcast quality regression

Date: 2026-10-12. Status: validated and prepared for user review; no phase 3
commit. Production source baseline: `634a563`. Numerical limits remain
proposed until this phase is accepted.

Current operating instructions are in [full-broadcast regression](broadcast-regression.md).
This record preserves the phase's investigation and validation evidence.

## Maintained acceptance workflow

`tools/broadcast-regression` decodes each complete capture afresh with the
production automatic MFSK32/MFSK64 pipeline. It reuses the existing program
scorer, which now accepts a single automatic-mode diagnostic manifest as well
as the historical pair of fixed-mode manifests. Decoder code is unchanged.

The versioned policy selects four broadcasts, spanning programs 456, 458 and
459, WRMI and WINB, and ordinary and impaired reception. All have retained
reviewed text, picture references and qualified fldigi 4.2.13 Pi results.
The independent picture truth for program 459, picture 8 (`rotterdam-flower`,
145×198 colour), is unavailable;
its detection remains checked and its missing pixel truth remains explicit.
This does not make the broadcast test optional or skipped.

The workflow verifies source IQ and metadata against the corpus inventory,
picture truth against its recorded hashes, the qualified receiver binary
identity, and all selected input hashes against the regression baseline.
Changed, absent or uncomputable evidence fails the run. An existing output
directory is rejected, so a previous decode cannot masquerade as a fresh run.

It writes diagnostic decodes, paired GramPy/fldigi program scorecards,
`result.json`, and a portable `review/index.html` with copied images. The page
shows paired scores and truth/GramPy/fldigi pictures. Reviewing the page is
optional for unchanged images; changed images require review under the
existing decoder validation policy, even if their numerical scores improve.

## Limits and their meaning

Historical aggregate MAE figures and the former planning gate are evidence,
not current numerical acceptance limits. This phase establishes a proposed
no-deterioration baseline using the current accepted decoder configuration.
It must be reviewed with this phase before adoption. It does not retroactively
assert that the full-corpus scores were the original August acceptance limits.

The gate checks text CER and reference coverage, acquisition misses/false
events/exact sequence, picture detection and completion, and raw and aligned
MAE for every scored picture. Improvements in another capture or picture do
not offset a regression. Numerical comparisons allow only `1e-9` roundoff;
this is not a quality allowance. Missing/nonfinite metrics fail. fldigi is
scored against the same truth and retained as a comparison; the gate does not
claim fldigi is perfect or require GramPy to beat it everywhere.

The weak WINB recording has known reception losses: current GramPy recovers
three of eight expected pictures, while the pinned fldigi reference recovers
two. Its regression bound preserves that recovery level and the quality of
the recovered pictures. A passing gate does not mean perfect text or complete
picture recovery on damaged input. Newly recovered pictures trigger visual
review; missing any previously required measurement fails.

Fresh calibration measurements (rounded here; exact per-picture bounds are
in `tests/fixtures/broadcast-baseline.json`):

| Capture | Text CER: GramPy / fldigi | Pictures: GramPy / fldigi / expected | Aligned MAE: GramPy / fldigi |
| --- | --- | --- | --- |
| WRMI July 8 | 7.347% / 5.912% | 8 / 8 / 8 | 38.0250 / 34.4697 |
| WINB July 18 | 35.836% / 22.023% | 3 / 2 / 8 | 62.2080 / 56.9439 |
| WRMI July 22 | 1.612% / 0.868% | 8 / 8 / 8 | 10.4454 / 6.8594 |
| WRMI July 29 | 4.392% / 0.672% | 11 / 11 / 11 | 11.4128 / 6.9191 |

These measurements establish transparent limits for future regression checks. July 29 has
ten pixel-scored pictures and one explicitly missing source image.

The compact baseline preserves input identities, per-case/per-picture limits,
PNG identities for review triggering, source revision and source hashes.
The scoring algorithms and alignment parameters are bound as well: a changed
scoring contract requires explicit requalification rather than silently making
an old limit easier to pass.
Full diagnostic runs and copied review assets are reproducible outputs rather
than permanent test dependencies. The baseline lives in Git; source recordings,
truth and pinned receiver outputs live in the received-corpus sidecar.
The baseline's `inputs` map lists the 88 required corpus files explicitly.
The existing corpus packager archives the entire received-corpus tree,
including these qualified reference directories; they must accompany a
sidecar handoff. No retained `.local` session folder is a test dependency.

## Running and revising

Use a managed Mac batch containing:

```sh
.venv/bin/python tools/broadcast-regression --output .local/broadcast-check-UNIQUE
```

`--corpus` overrides the received sidecar location. Normal runs read the
checked-in policy and baseline; they never update either. Exit 0 means the
automated gate passed and images are unchanged; exit 1 means failure or
incomplete evidence; exit 3 means numerical checks passed but changed images
require human review. Inspect `result.json` and the HTML page for the decision.
Human approval is recorded through normal change review, not an automatic
baseline rewrite or a command-line bypass.

To propose a new baseline, use an explicit `--record-baseline NEW.json` with
a new output directory. This calibration mode refuses to overwrite an existing
baseline and reports `calibration_requires_review`, `passed: false`. Its exit
0 means calibration completed, not regression acceptance. Review changes in
inputs, decoder behavior, scores and images before replacing the committed
baseline. Never recalibrate merely to hide a failing regression.

This is an explicit long-running acceptance workflow, separate from the
shorter `tools/test-suite --suite received` structural checks. Unit CI remains
independent of external recordings and does not claim broadcast acceptance.
Run the broadcast gate for changes that affect decoder quality or scoring;
use the existing change-management process to select proportionate checks
for changes outside those areas.

## Validation

Four complete 1,800-second captures were decoded during calibration, then
decoded afresh again for regression acceptance. Calibration completed in
911 seconds. The second managed batch, including the full standard suite,
completed in 1,077 seconds with exit 0.

- Standard suite: 254 passed in 155.005 seconds, zero skips or exclusions.
- New gate contract checks: six passed; final rerun includes rejection of
  an uncomputable picture score. Missing corpus, changed same-size IQ, changed
  truth/reference identity, lost/nonfinite metrics, per-picture degradation
  and required visual review all have failure-path coverage.
- Full-broadcast regression: `computable: true`, `automated_passed: true`,
  `passed: true`, no failures, all 30 tracked PNG identities unchanged.
- Final crosscheck: exact stored metrics and all 88 input identities match
  the proposed baseline. The final metric extractor accepts every retained
  scorecard under its stricter uncomputable-score check.
- HTML bundle: 35 expected picture rows and 93 available image assets, all
  relative references resolving inside the portable review directory. The
  page contains the passing verdict and paired scores. Automated browser
  preview was unavailable because this environment blocks local file URLs;
  the generated document and its assets were checked directly.

The baseline was compacted from the fresh calibration scorecards using the
final metric contract, with scoring parameters verified against the explicit
policy. It was then tested by the independent second decode run. It binds
the accepted decoder tree's source revision plus the working source hashes;
the scorer extension is part of this reviewed change.

Durable evidence:

- [Calibration completion](data/test-rationalization-phase3-calibration-result.md)
- [Standard suite and fresh regression completion](data/test-rationalization-phase3-result.md)
- [Final contract and artifact checks](data/test-rationalization-phase3-closeout-result.md)
- [Compact regression result](data/broadcast-regression-result.json)
- [Proposed baseline](../../tests/fixtures/broadcast-baseline.json)
- [Versioned policy](../../tests/fixtures/broadcast-regression.json)

Raw command logs and reproducible output bundles remain under
`.local/phase3-validation/`, `.local/phase3-calibration/` and
`.local/phase3-acceptance/` for this review. Completed managed session
directories were removed after their authoritative records were retained.
The ordinary and controlled fixture suites and the decoder implementation
remain intact. Phases 4 and 5 remain separate review steps.
