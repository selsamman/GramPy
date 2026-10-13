# October 13 sidecar audit closeout

See the [audit](../../../operations/sidecar-audit-20261013.md) for current
findings and the [sidecar policy](../../../operations/sidecar-maintenance.md)
for ongoing operation. This directory stores non-content evidence only.

- `disposition.json`: identities and explicit dispositions for all 382 original
  sidecar files, 281 structured/visual tracked artifacts and 166 final actions.
- `retired-recipes.json`: source identities, sample intervals and decoder
  configurations for retired development outputs; payloads are not preserved here.
- `retirement-result.json`: verified promotion/canonical-input checks and actual
  retirement outcome. Initial bulk execution was rejected by approval review;
  the revised copy-first, prevalidated retirement completed successfully.
- `content-matches.json`: exact-line provenance leads, represented by source
  paths, sizes and hashes only. These are leads, not a provenance certificate.

The managed validation run completed with exit 0 in 218 seconds:

- Checkout-only selection: 240 tests passed in 56.561 seconds with an absent
  sidecar override and a guard rejecting sidecar content opens.
- Full regular selection: 254 tests passed with no skips in 156.497 seconds.
- All 88 accepted broadcast input identities matched the baseline.
- Missing/corrupt expectation inputs, missing/corrupt inventory inputs, optional
  history selection and escaping inventory paths were checked.
- The full inventory was verified before a final non-content quality-series
  promotion; final verification passed all 303 files with no failures, and
  all 59 promotion identities matched their recorded final destinations.
- The post-audit exact-line scan found no external broadcast text matches in
  tracked or new repository files; its provenance limits remain documented.

The authoritative receipts are [validation-result.md](validation-result.md)
and [final-integrity-result.md](final-integrity-result.md). The complete
reviewed sidecar has 303 files: 246 required and 57 optional historical files.
All numerical acceptance limits, decoder code and required recordings are unchanged.
The native preparation record and non-content quality-series example were
promoted into Git after recorded provenance review. Their original relative
paths describe historical runs, not current runnable workspace assumptions.
Owned WIP was removed after preserving these findings and verification receipts.

No commits, pushes, remote Pi changes, Git history rewrite or S3 publication
were performed. Previous S3 releases must remain available until replacement
installation is verified. Older Git commits still contain externalized content.
