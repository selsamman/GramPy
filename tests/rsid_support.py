from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import tempfile

from grampy.rsid import encode_rsid


SAMPLE_RATE = 48_000


class synthetic_rsid_sigmf:
    def __init__(self, *, code: int = 147) -> None:
        self.code = code
        self.sample_count = SAMPLE_RATE * (6 if code == 620 else 3)
        self.tmp: tempfile.TemporaryDirectory[str] | None = None

    def __enter__(self) -> "SigmfPaths":
        self.tmp = tempfile.TemporaryDirectory(prefix="grampy-rsid-test-")
        root = Path(self.tmp.name)
        paths = SigmfPaths(root / "input.sigmf-meta", root / "input.sigmf-data")
        paths.meta.write_text(
            json.dumps(
                {
                    "global": {
                        "core:datatype": "ci16_le",
                        "core:sample_rate": SAMPLE_RATE,
                        "core:version": "1.0.0",
                    },
                    "captures": [{"core:sample_start": 0}],
                }
            ),
            encoding="utf-8",
        )
        paths.data.write_bytes(synthetic_rsid_bytes(self.sample_count, code=self.code))
        return paths

    def __exit__(self, *args: object) -> None:
        if self.tmp is not None:
            self.tmp.cleanup()


class SigmfPaths:
    def __init__(self, meta: Path, data: Path) -> None:
        self.meta = meta
        self.data = data


def synthetic_rsid_bytes(
    sample_count: int,
    *,
    code: int = 147,
    center_hz: float = 1582.0,
) -> bytes:
    baud = 11025.0 / 1024.0
    symbol_samples = round(SAMPLE_RATE / baud)
    transmissions = [(SAMPLE_RATE // 2, encode_rsid(code))]
    if code == 620:
        transmissions = [
            (SAMPLE_RATE // 2, encode_rsid(6)),
            (SAMPLE_RATE // 2 + 25 * symbol_samples, encode_rsid(code)),
        ]
    encoded = bytearray()
    for index in range(sample_count):
        active = next(
            (
                (start, tones)
                for start, tones in transmissions
                if start <= index < start + symbol_samples * len(tones)
            ),
            None,
        )
        if active is None:
            encoded.extend(b"\0\0\0\0")
            continue
        start, tones = active
        tone = tones[(index - start) // symbol_samples]
        phase = 2.0 * math.pi * (center_hz + (tone - 7.0) * baud) * index / SAMPLE_RATE
        encoded.extend(struct.pack("<hh", round(12_000 * math.cos(phase)), round(12_000 * math.sin(phase))))
    return bytes(encoded)
