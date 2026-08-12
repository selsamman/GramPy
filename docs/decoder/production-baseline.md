# Accepted decoder baseline

## Identity

The accepted picture-decoding baseline was approved on 2026-08-09 in commit
`68b03b48bb3d511c1ae56e7eb64e3d80a21ab467`.

| Dimension | Accepted value |
|---|---|
| Pipeline organization | `supported_hybrid` |
| Picture filter | `response_matched` |
| Picture estimator | `bounded_correlation` |
| Component window | `full_hann` |
| Picture boundary estimator | `unified_grid` |
| Persistent-tone policy | `measure` |
| Reference decoder | pinned fldigi 4.2.13 Pi build |

## Acceptance evidence

The approved candidate used the received corpus, reviewed image truth, and
the pinned fldigi reference. Relative to the preceding accepted rectangular
bounded-correlation configuration, it reduced hierarchical raw image MAE from
34.3240 to 31.8286 and aligned image MAE from 31.7798 to 29.0702. Picture
recall and text CER were unchanged. The closely matched full-window FFT
candidate was not selected because its quality margin was negligible and its
measured cost was higher.

The detailed decision, diagnostics, scorecards, and visual candidate-set
review were distilled into the versioned contracts and validation guidance in
this repository. They are evidence for this baseline, not normal bootstrap
documentation.

## Use in future changes

Treat this document as the meaning of “accepted production baseline” for
decoder-quality work until a later accepted change replaces it. A candidate
must name its precise delta from this configuration, source revision, corpus
and truth revision, reference decoder, and measured platform. Follow the
repository-wide [change-management process](../operations/change-management-v1.md)
for evaluation and closure.
