# Automatic MFSK32 picture correction evidence

The [visual review](index.html) shows the same three MFSK32 whole-WAV cases
previously skipped by GramPy automatic mode: source, absent prior output,
corrected GramPy and the original pinned Pi fldigi reception. The page embeds
its nine PNGs; the adjacent PNG files preserve their original hashes.

- [Qualification](qualification.json): all ten unchanged practical WAVs pass
  the frozen 48-kHz v3 gate; seven MFSK64 rasters remain pixel-identical.
- [Pi subset](pi-checks.json): normal/difficult MFSK32 and mixed-mode MFSK64
  pass the same numerical and functional requirements using isolated source.
- [Received broadcast](received-broadcast.json): existing text and nine PNG
  hashes preserved in the retained 1,800-second capture.
- [Regression log](regression-execution.log): 247 tests pass, six expected
  skips; separate real mixed-picture regression also passes.
- [Source identity](source-identity.json): retained before-source hashes,
  candidate pipeline, test identities and unchanged configuration.
- [Fixed-mode probes](fixed-center-baseline.json) and
  [nondefault-rate control](nondefault-8khz-control.json): separate existing
  limitations, not passing qualification claims.

The [change record](../../auto-mfsk32-pictures-change.md) states the scope,
cause, observations and practical limits. PM accepted all reviewed images on
2026-10-03; the [acceptance record](../../../encoder/data/session9/practical-acceptance.json)
binds that decision to this evidence. Frozen numerical records retain their
execution-time pending visual status. The original Session 9 qualification is
retained separately.
