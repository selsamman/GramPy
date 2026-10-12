# Full-broadcast regression

Use this explicit long-running gate for decoder-quality and scoring changes,
alongside the relevant regular tests. It freshly decodes the four complete
broadcasts selected in `tests/fixtures/broadcast-regression.json`, scores
GramPy and the retained qualified fldigi output against the same reviewed
truth, enforces the compact baseline and produces an HTML comparison page.
It covers the selected regression corpus, not every recording in the sidecar.

The regular `tools/test-suite --suite all` does not run this gate. There is no
equivalent quick windowed scoring gate. See [test maintenance](test-maintenance.md)
for choosing the shorter tiers and proportionate acceptance evidence.

## Run

Create an owned work directory and `WORK.md` under `.local/wip/<change-id>/`.
Put this in its Mac command file:

```sh
#!/bin/sh
set -eu
.venv/bin/python tools/broadcast-regression \
  --output .local/wip/CHANGE-ID/broadcast-01
```

Invoke `tools/mac-local.sh .local/wip/CHANGE-ID/mac-command.sh` on a
network-capable execution surface as required by [AGENTS.md](../../AGENTS.md).
Each invocation requires a new output directory; previous decodes are never
reused as fresh acceptance evidence. The four-broadcast run took about 15
minutes on the October 12, 2026 Mac validation; runtime varies by platform.

The default sidecar is `tests/samples/received-corpus/`; override with
`--corpus PATH`. The policy pins the decoder configuration, scoring parameters
and fldigi build. `tests/fixtures/broadcast-baseline.json` records the required
input paths/hashes, metric bounds, scoring contracts and review-trigger image
identities. The current baseline was proposed by phase 3 and its adoption
belongs to that change's acceptance, not to a calibration command.

Preflight fails for missing or changed required data. The gate verifies complete
input coverage and rechecks input identities after decoding. Numerical checks
protect text CER/coverage, acquisition misses/false events/exact sequence,
picture detection/completion and raw/aligned error for every scored picture.
An improvement elsewhere cannot offset a per-case or per-picture regression.
Only `1e-9` comparison roundoff is allowed.

The damaged WINB capture has known reception losses. Program 459's Rotterdam
flower source image is unavailable: its detection/completion are checked and
its pixel truth is explicitly unscored. These declared limitations do not make
the broadcast run optional. Missing metrics and unexpected scoring errors fail.

## Read the result

| Exit | Meaning |
| --- | --- |
| `0` in a normal run | Numerical gate passed and tracked images are unchanged. |
| `1` | Regression, incomplete input/evidence, changed scoring contract or execution failure. |
| `2` | Invalid command usage, including an already-existing output directory. |
| `3` | Numerical checks passed, but changed images require human review. |

The output contains `result.json`, paired scorecards in `grampy/` and `fldigi/`,
fresh diagnostic decodes in `decodes/`, and `review/index.html` with copied
assets. The page shows paired scores and truth/GramPy/fldigi pictures.
`automated_passed` distinguishes numerical success from final `passed` when
visual review remains required. Follow the
[decoder validation policy](../decoder/validation.md) for plausible visual
risk that warrants review even when tracked images/scores appear unchanged.

fldigi is a comparison reference; neither a perfect-transmission assumption
nor a requirement that GramPy beat fldigi everywhere defines this gate.
Its maintained limits preserve the adopted GramPy baseline. Historical
aggregate measurements do not supply universal thresholds.

## Propose a baseline revision

Normal runs never rewrite the baseline. An explicit
`--record-baseline NEW.json` performs calibration with a new output directory
and refuses to overwrite the baseline destination. Calibration exit 0 means
evidence generation completed; its report is `calibration_requires_review`
with `passed: false`, so it is not an accepted regression run.

Identify the reason for a revision, compare old/new input coverage, scorer
contracts, configuration, per-picture scores and images, and obtain change
acceptance before promoting the baseline. Never recalibrate solely to make
a regression disappear. Record limitations and validate durable sidecar
installation. Apply the [closeout policy](test-maintenance.md) before deleting
generated evidence from the owned work directory.

The [phase 3 record](test-rationalization-phase3.md) contains the original
measurement, validation and reconstruction history for targeted lookup.
