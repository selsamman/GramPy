# MFSK WAV encoder API

Use `grampy.api` to compose a canonical mono, signed-16-bit PCM WAV from
MFSK text or PNG content, compatible PCM WAV audio, and explicit silence.
The encoder has no fldigi runtime dependency.

The required and qualified broadcast rate is **48,000 Hz**, the default in
`EncodeConfig`. Supplied audio must also be 48-kHz mono PCM16. Other rates
accepted by the configuration validator are compatibility behavior, not a
receive-quality commitment. Use representative broadcast-sized pictures;
tiny diagnostic rasters are outside the accepted quality scope. See the
[production baseline](production-baseline.md) for the acceptance and limits.

```python
from pathlib import Path

from grampy.api import (
    AudioPart,
    ImagePart,
    MfskSegment,
    SilencePart,
    TextPart,
    encode_mfsk_wav,
)

result = encode_mfsk_wav(
    parts=(
        MfskSegment((TextPart.from_text("FIRST"),), "MFSK32", 1400.0),
        SilencePart(0.25),
        AudioPart(Path("marker.wav")),
        MfskSegment(
            (TextPart.from_text("PICTURE\n"), ImagePart(Path("image.png"))),
            "MFSK64",
            1600.0,
        ),
    ),
    output_path=Path("transmission.wav"),
)
```

`TextPart` transmits its bytes exactly. `TextPart.from_text` uses strict
encoding. `TextFilePart` reads byte content without newline conversion.
`ImagePart` accepts only the documented 8-bit `L` and `RGB` PNG profile;
Pillow is a required package dependency. `AudioPart` accepts only nonempty,
mono PCM16 RIFF/WAVE audio at the configured rate and copies its data frames
without conversion. `SilencePart` must have an integral frame duration.

Every `MfskSegment` is independently framed and automatically begins with an
RSID prefix at its own carrier, including the first and repeated same-mode
segments. The API supplies no opt-out or implicit editorial gap. At the
default 48 kHz rate the prefix occupies 111,450 frames for MFSK32 and 222,900
for MFSK64. Use `SilencePart` to add a caller-controlled gap.

`EncodeResult.segments` contains a `SegmentStart` for every top-level input
item. `SegmentStart.contents` contains one `ContentStart` for each supplied
MFSK content item. All timestamps are exact frame coordinates divided by the
sample rate; an MFSK segment timestamp begins at its RSID lead guard, while a
content timestamp begins after its complete RSID prefix and MFSK framing.

The encoder validates predictable failures before opening the output. After
writing starts, a reported error closes and removes the exact output path; it
does not use a temporary file or restore a replaced file. File-system errors
remain `OSError` subclasses and invalid content/configuration raises
`ValueError`. Forced process or machine termination is outside this cleanup
guarantee.

The public encoder API is deliberately library-only in version one. A command
line encoder would need its own input-document and lifecycle contract, so it
is not included in the `radiogrampy` console scripts.
