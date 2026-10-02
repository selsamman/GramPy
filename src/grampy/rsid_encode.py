"""Private, isolated RSID prefix synthesis from the pinned fldigi contract.

No decoder code or runtime oracle file is used. The public composer emits this
prefix before every independently framed MFSK segment.
"""

from array import array
from dataclasses import dataclass
import math
import sys

from .mfsk_encode import _PcmSink, _validate_carrier, _validate_sample_rate
from .text_encode import MfskMode


_SPACING_HZ = 11025 / 1024
_PCM_PEAK = 16384
_WORDS = {
    "MFSK32": (0, 7, 13, 9, 14, 14, 4, 10, 3, 10, 9, 4, 0, 13, 3),
    "escape": (0, 0, 2, 14, 4, 14, 6, 2, 12, 8, 4, 12, 10, 8, 6),
    "MFSK64": (9, 15, 1, 12, 4, 10, 10, 7, 2, 9, 2, 4, 7, 15, 12),
}


@dataclass(frozen=True)
class _RsidPrefixPlan:
    mode: MfskMode
    carrier_hz: float
    sample_rate_hz: int
    frames_per_symbol: int
    frame_count: int


def _plan_rsid_prefix(
    *, mode: MfskMode, carrier_hz: float, sample_rate_hz: int,
) -> _RsidPrefixPlan:
    if mode not in ("MFSK32", "MFSK64"):
        raise ValueError(f"unsupported MFSK mode: {mode}")
    _validate_sample_rate(sample_rate_hz)
    # Retain the segment's complete MFSK-span validation, which also contains
    # the narrower RSID span (including its asymmetric +8 spacing endpoint).
    carrier = _validate_carrier(mode, carrier_hz, sample_rate_hz)
    period = sample_rate_hz * 1024 // 11025
    return _RsidPrefixPlan(
        mode, carrier, sample_rate_hz, period,
        period * (25 if mode == "MFSK32" else 50),
    )


def _write_rsid_prefix(
    sink: _PcmSink, *, mode: MfskMode, carrier_hz: float, sample_rate_hz: int,
) -> int:
    """Write little-endian PCM in one-symbol blocks; return frames written.

    Validate before touching the sink. Propagate sink failures, including short
    writes; file ownership and cleanup remain the composer's responsibility.
    Each word starts at phase zero, advances before sampling, and retains
    phase across its fifteen tones. Guards are exact zero frames.
    """
    plan = _plan_rsid_prefix(
        mode=mode, carrier_hz=carrier_hz, sample_rate_hz=sample_rate_hz,
    )
    zeros = bytes(2 * plan.frames_per_symbol)
    written_frames = 0

    def write(payload: bytes) -> None:
        nonlocal written_frames
        count = sink.write(payload)
        if count != len(payload):
            raise OSError(f"short RSID write: expected {len(payload)} bytes, wrote {count}")
        written_frames += len(payload) // 2

    def silence(periods: int) -> None:
        for _ in range(periods):
            write(zeros)

    def word(tones: tuple[int, ...]) -> None:
        phase = 0.0
        for tone in tones:
            step = math.tau * (plan.carrier_hz + (tone - 7) * _SPACING_HZ) / sample_rate_hz
            samples = array("h")
            for _ in range(plan.frames_per_symbol):
                phase = (phase + step) % math.tau
                samples.append(round(_PCM_PEAK * math.sin(phase)))
            if sys.byteorder != "little":
                samples.byteswap()
            write(samples.tobytes())

    silence(5)
    word(_WORDS["MFSK32"] if mode == "MFSK32" else _WORDS["escape"])
    if mode == "MFSK64":
        silence(10)
        word(_WORDS["MFSK64"])
    silence(5)
    if written_frames != plan.frame_count:
        raise RuntimeError("planned and emitted RSID frame counts disagree")
    return written_frames
