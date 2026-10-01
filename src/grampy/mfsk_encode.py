from __future__ import annotations

from array import array
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
import math
from pathlib import Path
import struct
import sys
from typing import BinaryIO, Protocol

from .text_encode import (
    MODE_PARAMETERS,
    MfskMode,
    StatefulTextToneEncoder,
    varicode_codeword,
)


GENERATED_PCM_PEAK = 16_384
ENVELOPE_SECONDS = 0.010
MAX_WAV_DATA_BYTES = 4_294_967_258
MAX_WAV_FRAMES = MAX_WAV_DATA_BYTES // 2

_START_CHARACTERS = b"\r\x02\r"
_END_CHARACTERS = b"\r\x04\r"
_TEXT_CHUNK_BYTES = 64 * 1024
_TWO_PI = 2.0 * math.pi


class _PcmSink(Protocol):
    def write(self, pcm: bytes) -> int: ...


@dataclass(frozen=True)
class TextSegmentWaveResult:
    output_path: Path
    frame_count: int
    sample_rate_hz: int
    content_start_frames: tuple[int, ...]

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate_hz


@dataclass(frozen=True)
class TextSegmentPlan:
    mode: MfskMode
    sample_rate_hz: int
    frames_per_symbol: int
    tone_count: int
    frame_count: int
    content_start_frames: tuple[int, ...]


def _validate_sample_rate(sample_rate_hz: int) -> None:
    if (
        isinstance(sample_rate_hz, bool)
        or not isinstance(sample_rate_hz, int)
        or not 8_000 <= sample_rate_hz <= 192_000
        or sample_rate_hz % 8_000
    ):
        raise ValueError(
            "sample rate must be an integer multiple of 8000 from 8000 through 192000"
        )


def _validate_carrier(
    mode: MfskMode,
    carrier_hz: float,
    sample_rate_hz: int,
) -> float:
    if isinstance(carrier_hz, bool) or not isinstance(carrier_hz, (int, float)):
        raise ValueError("carrier frequency must be a finite number")
    carrier = float(carrier_hz)
    if not math.isfinite(carrier):
        raise ValueError("carrier frequency must be a finite number")
    half_span = MODE_PARAMETERS[mode].tone_span_hz / 2.0
    if carrier - half_span <= 0.0 or carrier + half_span >= sample_rate_hz / 2.0:
        raise ValueError("the complete MFSK tone span must lie strictly within Nyquist")
    return carrier


def tone_frequency_hz(mode: MfskMode, carrier_hz: float, tone_index: int) -> float:
    if mode not in MODE_PARAMETERS:
        raise ValueError(f"unsupported MFSK mode: {mode}")
    if (
        isinstance(tone_index, bool)
        or not isinstance(tone_index, int)
        or not 0 <= tone_index < 16
    ):
        raise ValueError("tone index must be an integer from zero through 15")
    return carrier_hz + (tone_index - 7.5) * MODE_PARAMETERS[mode].tone_spacing_hz


def _varicode_bit_count(data: bytes) -> int:
    return sum(len(varicode_codeword(octet)) for octet in data)


def plan_text_segment(
    *,
    text_parts: Sequence[bytes],
    mode: MfskMode,
    sample_rate_hz: int,
) -> TextSegmentPlan:
    if mode not in MODE_PARAMETERS:
        raise ValueError(f"unsupported MFSK mode: {mode}")
    _validate_sample_rate(sample_rate_hz)
    parts = tuple(text_parts)
    if not parts:
        raise ValueError("a text-only MFSK segment must contain at least one text part")
    if any(not isinstance(part, bytes) for part in parts):
        raise TypeError("MFSK text parts must be bytes")

    parameters = MODE_PARAMETERS[mode]
    frames_per_symbol = (
        parameters.samples_per_symbol * sample_rate_hz
        // parameters.internal_sample_rate_hz
    )
    input_bits = (
        parameters.preamble_input_bits // 3
        + _varicode_bit_count(_START_CHARACTERS)
    )
    content_start_frames: list[int] = []
    for part in parts:
        content_start_frames.append((input_bits // 2) * frames_per_symbol)
        input_bits += _varicode_bit_count(part)
    input_bits += (
        _varicode_bit_count(_END_CHARACTERS)
        + 1
        + parameters.preamble_input_bits
    )
    tone_count = input_bits // 2
    frame_count = tone_count * frames_per_symbol
    if frame_count > MAX_WAV_FRAMES:
        raise ValueError("predicted text segment exceeds the classic RIFF/WAVE limit")
    return TextSegmentPlan(
        mode=mode,
        sample_rate_hz=sample_rate_hz,
        frames_per_symbol=frames_per_symbol,
        tone_count=tone_count,
        frame_count=frame_count,
        content_start_frames=tuple(content_start_frames),
    )


def iter_framed_text_tones(
    *,
    text_parts: Sequence[bytes],
    mode: MfskMode,
) -> Iterator[int]:
    """Yield one complete independently framed text segment.

    The caller must snapshot and validate ``text_parts`` before using this
    iterator for output. The final incomplete coded-bit group, if any, has no
    corresponding symbol and is intentionally discarded with the encoder.
    """
    encoder = StatefulTextToneEncoder(mode)
    parameters = MODE_PARAMETERS[mode]
    yield from encoder.push_bits(
        (0 for _ in range(parameters.preamble_input_bits // 3))
    )
    yield from encoder.push_bytes(_START_CHARACTERS)
    for part in text_parts:
        for offset in range(0, len(part), _TEXT_CHUNK_BYTES):
            yield from encoder.push_bytes(part[offset : offset + _TEXT_CHUNK_BYTES])
    yield from encoder.push_bytes(_END_CHARACTERS)
    yield from encoder.push_bits((1,))
    yield from encoder.push_bits((0 for _ in range(parameters.preamble_input_bits)))


class ContinuousPhaseToneWriter:
    """Convert physical MFSK tone indices to bounded, streaming PCM16 blocks."""

    def __init__(
        self,
        sink: _PcmSink,
        *,
        mode: MfskMode,
        carrier_hz: float,
        sample_rate_hz: int,
    ) -> None:
        if mode not in MODE_PARAMETERS:
            raise ValueError(f"unsupported MFSK mode: {mode}")
        _validate_sample_rate(sample_rate_hz)
        self._carrier_hz = _validate_carrier(mode, carrier_hz, sample_rate_hz)
        self._sink = sink
        self._mode = mode
        self._sample_rate_hz = sample_rate_hz
        parameters = MODE_PARAMETERS[mode]
        self._frames_per_symbol = (
            parameters.samples_per_symbol * sample_rate_hz
            // parameters.internal_sample_rate_hz
        )
        self._ramp_frames = int(round(ENVELOPE_SECONDS * sample_rate_hz))
        self._phase = 0.0
        self._pending_tone: int | None = None
        self._emitted_tones = 0
        self._accepted_tones = 0
        self._finished = False

    @property
    def phase_radians(self) -> float:
        return self._phase

    @property
    def frame_count(self) -> int:
        return self._emitted_tones * self._frames_per_symbol

    @property
    def accepted_frame_count(self) -> int:
        return self._accepted_tones * self._frames_per_symbol

    def push_tones(self, tones: Iterable[int]) -> None:
        if self._finished:
            raise ValueError("cannot write tones after the synthesizer is finished")
        for tone in tones:
            if (
                isinstance(tone, bool)
                or not isinstance(tone, int)
                or not 0 <= tone < 16
            ):
                raise ValueError("tone indices must be integers from zero through 15")
            if self._pending_tone is not None:
                self._emit_symbol(
                    self._pending_tone,
                    attack=self._emitted_tones == 0,
                    release=False,
                )
            self._pending_tone = tone
            self._accepted_tones += 1

    def finish(self) -> None:
        if self._finished:
            return
        if self._pending_tone is None:
            raise ValueError("a framed MFSK segment must emit at least one tone")
        self._emit_symbol(
            self._pending_tone,
            attack=self._emitted_tones == 0,
            release=True,
        )
        self._pending_tone = None
        self._finished = True

    def _emit_symbol(self, tone: int, *, attack: bool, release: bool) -> None:
        frequency = tone_frequency_hz(self._mode, self._carrier_hz, tone)
        phase_step = _TWO_PI * frequency / self._sample_rate_hz
        samples = array("h")
        for index in range(self._frames_per_symbol):
            gain = 1.0
            if attack and index < self._ramp_frames:
                gain *= _raised_cosine_gain(index, self._ramp_frames)
            if release and index >= self._frames_per_symbol - self._ramp_frames:
                gain *= _raised_cosine_gain(
                    self._frames_per_symbol - 1 - index,
                    self._ramp_frames,
                )
            samples.append(int(round(GENERATED_PCM_PEAK * gain * math.sin(self._phase))))
            self._phase = (self._phase + phase_step) % _TWO_PI
        if sys.byteorder != "little":
            samples.byteswap()
        self._sink.write(samples.tobytes())
        self._emitted_tones += 1


def _raised_cosine_gain(index: int, frame_count: int) -> float:
    if frame_count <= 1:
        return 1.0
    return 0.5 - 0.5 * math.cos(math.pi * index / (frame_count - 1))


class _CanonicalWaveWriter:
    def __init__(self, handle: BinaryIO, sample_rate_hz: int) -> None:
        self._handle = handle
        self._sample_rate_hz = sample_rate_hz
        self._data_bytes = 0
        self._finished = False
        self._write_exact(
            struct.pack(
                "<4sI4s4sIHHIIHH4sI",
                b"RIFF",
                36,
                b"WAVE",
                b"fmt ",
                16,
                1,
                1,
                sample_rate_hz,
                sample_rate_hz * 2,
                2,
                16,
                b"data",
                0,
            )
        )

    def write(self, pcm: bytes) -> int:
        if self._finished:
            raise ValueError("cannot write PCM after the WAV is finished")
        if len(pcm) % 2:
            raise ValueError("PCM16 writes must contain complete frames")
        if self._data_bytes + len(pcm) > MAX_WAV_DATA_BYTES:
            raise ValueError("PCM data exceeds the classic RIFF/WAVE limit")
        written = self._handle.write(pcm)
        if written != len(pcm):
            raise OSError(f"short WAV write: expected {len(pcm)} bytes, wrote {written}")
        self._data_bytes += written
        return written

    def finish(self) -> None:
        if self._finished:
            return
        self._handle.seek(4)
        self._write_exact(struct.pack("<I", 36 + self._data_bytes))
        self._handle.seek(40)
        self._write_exact(struct.pack("<I", self._data_bytes))
        self._handle.flush()
        self._finished = True

    def _write_exact(self, payload: bytes) -> None:
        written = self._handle.write(payload)
        if written != len(payload):
            raise OSError(
                f"short WAV write: expected {len(payload)} bytes, wrote {written}"
            )


def encode_text_segment_wav(
    *,
    text_parts: Sequence[bytes],
    output_path: Path,
    mode: MfskMode = "MFSK64",
    carrier_hz: float = 1500.0,
    sample_rate_hz: int = 48_000,
) -> TextSegmentWaveResult:
    """Write one complete text-only MFSK segment to a canonical PCM WAV.

    This is the private Session 3 vertical slice. The complete public
    composition API is introduced only after image, audio, and silence parts
    are implemented.
    """
    parts = tuple(text_parts)
    plan = plan_text_segment(
        text_parts=parts,
        mode=mode,
        sample_rate_hz=sample_rate_hz,
    )
    _validate_carrier(mode, carrier_hz, sample_rate_hz)
    output_path = Path(output_path)

    handle: BinaryIO | None = None
    writing_began = False
    try:
        handle = output_path.open("wb")
        writing_began = True
        wave_writer = _CanonicalWaveWriter(handle, sample_rate_hz)
        synthesizer = ContinuousPhaseToneWriter(
            wave_writer,
            mode=mode,
            carrier_hz=carrier_hz,
            sample_rate_hz=sample_rate_hz,
        )
        synthesizer.push_tones(
            iter_framed_text_tones(text_parts=parts, mode=mode)
        )
        if synthesizer.accepted_frame_count != plan.frame_count:
            raise RuntimeError("planned and encoded MFSK frame counts disagree")
        synthesizer.finish()
        if synthesizer.frame_count != plan.frame_count:
            raise RuntimeError("planned and synthesized MFSK frame counts disagree")
        wave_writer.finish()
        handle.close()
        handle = None
    except BaseException as primary:
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass
        if writing_began:
            try:
                output_path.unlink(missing_ok=True)
            except OSError as removal_error:
                raise removal_error from primary
        raise

    return TextSegmentWaveResult(
        output_path=output_path,
        frame_count=plan.frame_count,
        sample_rate_hz=sample_rate_hz,
        content_start_frames=plan.content_start_frames,
    )


__all__ = [
    "ContinuousPhaseToneWriter",
    "ENVELOPE_SECONDS",
    "GENERATED_PCM_PEAK",
    "TextSegmentPlan",
    "TextSegmentWaveResult",
    "encode_text_segment_wav",
    "iter_framed_text_tones",
    "plan_text_segment",
    "tone_frequency_hz",
]
