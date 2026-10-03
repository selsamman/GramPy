# Native MFSK WAV encoder

The accepted encoder creates credible 48-kHz broadcast WAVs containing
MFSK32/MFSK64 text, PNG pictures, compatible audio and silence. It is a
library component in `radiogrampy`, with no fldigi runtime dependency.

Read the [API guide](api.md) to use it, [contracts](contracts.md) for stable
behavior, [design](design.md) for implementation boundaries, and
[validation](validation.md) for regression and receive qualification. The
[production baseline](production-baseline.md) identifies the accepted source,
quality scope, package and Pi performance measurements.

The [Session 10 closeout](session10-closeout.md) records final packaging and
deliberate evidence preservation. The completed
[change record](mfsk_wav_encoder_change.md) and
[implementation plan](mfsk_wav_encoder_plan.md) retain development history;
they are not required as operational API instructions. Future behavior changes
follow [Change Management v1](../operations/change-management-v1.md).
