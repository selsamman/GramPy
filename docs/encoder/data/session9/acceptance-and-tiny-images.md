# Separate loopback acceptance from tiny-picture failures

**Later direction:** the user has now confirmed replacing decoded-picture bit
perfection with sensible scorecard-based acceptance. Specific numerical limits
are not yet calibrated. [The qualification proposal](qualification-proposal.md)
and updated D-026 supersede this checkpoint's earlier "possible revision" status,
while preserving the separation from severe tiny-picture diagnosis.

**User steering, 2026-10-02:** decoder development already established a
scorecard for picture quality. The clean-loopback expectation of exact source
pixels may need reconsideration, but that product-policy question is separate
from the severe distortion of the tiny fldigi images. Preserve both questions
and their original evidence; do not use one to close the other.

| Question | Established evidence | Confidence and remaining work | PM decision |
| --- | --- | --- | --- |
| Is exact source-pixel equality a suitable decoded-picture loopback requirement? | Every measured save/diagnostic differs from source pixels, including visually useful normal-sized images. Tiny intensity differences and slight alignment shifts can cause high exact-mismatch percentages. | High confidence in the measured non-equality; no proof that equality is impossible or that all differences are unavoidable. Prepare any criterion proposal with existing scoring methods and a reliable reference baseline. | A future explicit acceptance-policy decision. The user's observation is not approval of a new threshold. |
| Why do original 8×4 fldigi outputs have severe colour/content distortion? | Original Pi evidence, completed Pi buffers and independent Mac saves retain substantial distortion. Some Pi autosaves are stale or incomplete; completed buffers also differ substantially. Independent native waveform checks find no raster-recipe defect in those retained intervals. | High confidence that tiny fldigi output failures are substantive and cannot be explained solely by a Pi-only harness fault. Contributions of filtering, alignment, saving and acquisition remain incompletely isolated. GramPy's coupled tiny diagnostic has different, generally smaller errors. | Diagnose first. Any production remedy or minimum supported image-size decision must follow concrete evidence. Relaxing exact equality does not dispose of this issue. |

## Reuse the decoder scorecard framework

The existing [decoder validation guidance](../../../decoder/validation.md) and
[accepted decoder baseline](../../../decoder/production-baseline.md) already
provide the evaluation approach. The scoring implementation reports raw
whole-raster/per-channel MAE, RMSE, bias, exact component fraction and PSNR,
plus bounded component alignment and the compensation required. Program
scorecards retain picture identity/order, headers, geometry, completion, text
recovery and truth provenance. Image-related changes require candidate-set
visual review, including cases where alignment could conceal a localized defect.

Reuse those measurements and review practices when preparing a loopback
criterion proposal. Do not import historical shortwave-corpus thresholds as
loopback acceptance limits, or create a new subjective scoring system merely
because an exact-pixel check failed. Exact encoder protocol, waveform order,
frequency, phase and duration evidence remains distinct from decoded-image
fidelity and should retain its existing checks.

The recent GramPy WAV comparison is a diagnostic using low-level picture-decoder
defaults (`fft_peak`, `center_crop`, `current_wide`), not the accepted decoder
configuration (`bounded_correlation`, `full_hann`, `response_matched`). Its
known-start/mode method and tiny/large filter-path differences are already
recorded. It is not the existing production decoder scorecard, a qualified
decoder ranking, or a basis for choosing a new quality tolerance.

## Work and disposition

Keep severe tiny-picture diagnosis as a separate Session 9 work item, using the
original fixtures and retained failures. Any quality acceptance proposal must
also show those cases explicitly rather than hide them in a large-image average
or substitute a larger fixture. The separate fldigi-recording clock/capture
problem remains a reference-calibration issue.

No passing criteria, fixtures, encoder/decoder implementation or accepted
baseline change at this checkpoint. No new PM approval is requested now.
Session 9 remains open; a future criterion change needs its own concrete,
reviewable decision, independently of the tiny-picture diagnosis.
