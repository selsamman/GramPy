"""Complete MFSK segment planning and synthesis for the public composer.

The segment joins text state, fldigi picture transitions, analog rasters, and
one continuous-phase oscillator. File-backed text and PNGs are streamed or
loaded as needed by the top-level composition preflight and writer.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, TypeAlias

from .mfsk_encode import (
    MAX_WAV_FRAMES,
    ContinuousPhaseToneWriter,
    _CanonicalWaveWriter,
    _validate_carrier,
    _validate_sample_rate,
)
from .picture_encode import (
    NormalizedPicture,
    PictureColor,
    normalize_png,
    picture_announcement,
    plan_picture_raster,
)
from .text_encode import MODE_PARAMETERS, MfskMode, StatefulTextToneEncoder


@dataclass(frozen=True)
class TextFileSource:
    path: Path


@dataclass(frozen=True)
class ImageSource:
    path: Path
    color: PictureColor
    samples_per_pixel: int


MfskSegmentContent: TypeAlias = bytes | TextFileSource | NormalizedPicture | ImageSource

_START_CHARACTERS = b"\r\x02\r"
_END_CHARACTERS = b"\r\x04\r"
_TEXT_CHUNK_BYTES = 64 * 1024
_PROLOGUE_INTERNAL_FRAMES = 352


@dataclass(frozen=True)
class PictureTransitionPlan:
    content_index: int
    announcement: bytes
    announcement_start_frame: int
    header_flush_start_frame: int
    header_flush_symbol_count: int
    prologue_start_frame: int
    raster_start_frame: int
    raster_stop_frame: int
    post_picture_flush_start_frame: int
    post_picture_flush_stop_frame: int
    post_picture_flush_symbol_count: int


@dataclass(frozen=True)
class MfskSegmentPlan:
    mode: MfskMode
    carrier_hz: float
    sample_rate_hz: int
    frames_per_symbol: int
    frame_count: int
    content_start_frames: tuple[int, ...]
    picture_transitions: tuple[PictureTransitionPlan, ...]


@dataclass(frozen=True)
class MfskSegmentWaveResult:
    output_path: Path
    frame_count: int
    sample_rate_hz: int
    content_start_frames: tuple[int, ...]
    picture_transitions: tuple[PictureTransitionPlan, ...]

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate_hz


def _snapshot_contents(
    contents: Sequence[MfskSegmentContent],
) -> tuple[MfskSegmentContent, ...]:
    snapshot = tuple(contents)
    if not snapshot:
        raise ValueError("an MFSK segment must contain at least one content item")
    for content in snapshot:
        if not isinstance(content, (bytes, TextFileSource, NormalizedPicture, ImageSource)):
            raise TypeError("unsupported MFSK segment content")
    return snapshot


def _iter_byte_tones(
    encoder: StatefulTextToneEncoder,
    data: bytes,
) -> Iterator[int]:
    for offset in range(0, len(data), _TEXT_CHUNK_BYTES):
        yield from encoder.push_bytes(data[offset : offset + _TEXT_CHUNK_BYTES])


def _iter_file_tones(
    encoder: StatefulTextToneEncoder,
    path: Path,
) -> Iterator[int]:
    with path.open("rb") as source:
        while chunk := source.read(_TEXT_CHUNK_BYTES):
            yield from encoder.push_bytes(chunk)


def _load_picture(content: NormalizedPicture | ImageSource) -> NormalizedPicture:
    if isinstance(content, NormalizedPicture):
        return content
    return normalize_png(
        content.path,
        color=content.color,
        samples_per_pixel=content.samples_per_pixel,
    )


def _flush_tones(encoder: StatefulTextToneEncoder) -> tuple[int, ...]:
    parameters = encoder.parameters
    return (
        encoder.push_bits((1,))
        + encoder.push_bits((0 for _ in range(parameters.preamble_input_bits)))
    )


def _new_neutral_encoder(mode: MfskMode) -> StatefulTextToneEncoder:
    """Canonicalize the wire-equivalent state left by a complete flush."""
    return StatefulTextToneEncoder(mode)


def plan_mfsk_segment(
    *,
    contents: Sequence[MfskSegmentContent],
    mode: MfskMode,
    carrier_hz: float,
    sample_rate_hz: int,
) -> MfskSegmentPlan:
    """Preflight exact frame coordinates for one ordered MFSK segment."""
    snapshot = _snapshot_contents(contents)
    if mode not in MODE_PARAMETERS:
        raise ValueError(f"unsupported MFSK mode: {mode}")
    _validate_sample_rate(sample_rate_hz)
    carrier = _validate_carrier(mode, carrier_hz, sample_rate_hz)
    parameters = MODE_PARAMETERS[mode]
    frames_per_symbol = (
        parameters.samples_per_symbol
        * sample_rate_hz
        // parameters.internal_sample_rate_hz
    )
    prologue_frames = _PROLOGUE_INTERNAL_FRAMES * (sample_rate_hz // 8_000)

    encoder = StatefulTextToneEncoder(mode)
    frame_cursor = 0
    frame_cursor += len(
        encoder.push_bits((0 for _ in range(parameters.preamble_input_bits // 3)))
    ) * frames_per_symbol
    frame_cursor += len(encoder.push_bytes(_START_CHARACTERS)) * frames_per_symbol

    content_starts: list[int] = []
    transitions: list[PictureTransitionPlan] = []
    for content_index, content in enumerate(snapshot):
        content_starts.append(frame_cursor)
        if isinstance(content, bytes):
            frame_cursor += sum(
                1 for _ in _iter_byte_tones(encoder, content)
            ) * frames_per_symbol
            continue
        if isinstance(content, TextFileSource):
            frame_cursor += sum(
                1 for _ in _iter_file_tones(encoder, content.path)
            ) * frames_per_symbol
            continue

        picture = _load_picture(content)

        raster_plan = plan_picture_raster(
            picture,
            mode=mode,
            carrier_hz=carrier,
            sample_rate_hz=sample_rate_hz,
        )
        announcement = picture_announcement(picture)
        announcement_start = frame_cursor
        frame_cursor += sum(
            1 for _ in _iter_byte_tones(encoder, announcement)
        ) * frames_per_symbol
        header_flush_start = frame_cursor
        header_flush_symbol_count = len(_flush_tones(encoder))
        frame_cursor += header_flush_symbol_count * frames_per_symbol

        # The flush has driven convolutional and interleaver memory to zero;
        # any half-symbol has no wire representation.  A fresh private object
        # is the canonical form of that neutral-equivalent state.
        encoder = _new_neutral_encoder(mode)
        prologue_start = frame_cursor
        frame_cursor += prologue_frames
        raster_start = frame_cursor
        frame_cursor += raster_plan.frame_count
        raster_stop = frame_cursor

        post_flush_start = frame_cursor
        post_flush_symbol_count = len(_flush_tones(encoder))
        frame_cursor += post_flush_symbol_count * frames_per_symbol
        post_flush_stop = frame_cursor
        encoder = _new_neutral_encoder(mode)

        transitions.append(
            PictureTransitionPlan(
                content_index=content_index,
                announcement=announcement,
                announcement_start_frame=announcement_start,
                header_flush_start_frame=header_flush_start,
                header_flush_symbol_count=header_flush_symbol_count,
                prologue_start_frame=prologue_start,
                raster_start_frame=raster_start,
                raster_stop_frame=raster_stop,
                post_picture_flush_start_frame=post_flush_start,
                post_picture_flush_stop_frame=post_flush_stop,
                post_picture_flush_symbol_count=post_flush_symbol_count,
            )
        )

    frame_cursor += len(encoder.push_bytes(_END_CHARACTERS)) * frames_per_symbol
    frame_cursor += len(_flush_tones(encoder)) * frames_per_symbol
    if frame_cursor > MAX_WAV_FRAMES:
        raise ValueError("predicted MFSK segment exceeds the classic RIFF/WAVE limit")

    return MfskSegmentPlan(
        mode=mode,
        carrier_hz=carrier,
        sample_rate_hz=sample_rate_hz,
        frames_per_symbol=frames_per_symbol,
        frame_count=frame_cursor,
        content_start_frames=tuple(content_starts),
        picture_transitions=tuple(transitions),
    )


def _write_segment(
    synthesizer: ContinuousPhaseToneWriter,
    *,
    contents: tuple[MfskSegmentContent, ...],
    mode: MfskMode,
    carrier_hz: float,
    sample_rate_hz: int,
) -> None:
    parameters = MODE_PARAMETERS[mode]
    encoder = StatefulTextToneEncoder(mode)
    synthesizer.push_tones(
        encoder.push_bits((0 for _ in range(parameters.preamble_input_bits // 3)))
    )
    synthesizer.push_tones(encoder.push_bytes(_START_CHARACTERS))

    for content in contents:
        if isinstance(content, bytes):
            for offset in range(0, len(content), _TEXT_CHUNK_BYTES):
                synthesizer.push_tones(
                    encoder.push_bytes(content[offset : offset + _TEXT_CHUNK_BYTES])
                )
            continue
        if isinstance(content, TextFileSource):
            synthesizer.push_tones(_iter_file_tones(encoder, content.path))
            continue

        picture = _load_picture(content)

        synthesizer.push_tones(
            _iter_byte_tones(encoder, picture_announcement(picture))
        )
        synthesizer.push_tones(_flush_tones(encoder))
        encoder = _new_neutral_encoder(mode)

        bandwidth = parameters.tone_span_hz
        synthesizer.push_frequency(
            carrier_hz - bandwidth / 2.0,
            _PROLOGUE_INTERNAL_FRAMES * (sample_rate_hz // 8_000),
        )
        raster_plan = plan_picture_raster(
            picture,
            mode=mode,
            carrier_hz=carrier_hz,
            sample_rate_hz=sample_rate_hz,
        )
        for event in raster_plan.iter_events():
            synthesizer.push_frequency(event.frequency_hz, event.frame_count)

        synthesizer.push_tones(_flush_tones(encoder))
        encoder = _new_neutral_encoder(mode)

    synthesizer.push_tones(encoder.push_bytes(_END_CHARACTERS))
    synthesizer.push_tones(_flush_tones(encoder))


def encode_mfsk_segment_wav(
    *,
    contents: Sequence[MfskSegmentContent],
    output_path: Path,
    mode: MfskMode = "MFSK64",
    carrier_hz: float = 1500.0,
    sample_rate_hz: int = 48_000,
) -> MfskSegmentWaveResult:
    """Write one complete ordered text/picture MFSK segment to a PCM WAV."""
    snapshot = _snapshot_contents(contents)
    plan = plan_mfsk_segment(
        contents=snapshot,
        mode=mode,
        carrier_hz=carrier_hz,
        sample_rate_hz=sample_rate_hz,
    )
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
            carrier_hz=plan.carrier_hz,
            sample_rate_hz=sample_rate_hz,
        )
        _write_segment(
            synthesizer,
            contents=snapshot,
            mode=mode,
            carrier_hz=plan.carrier_hz,
            sample_rate_hz=sample_rate_hz,
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

    return MfskSegmentWaveResult(
        output_path=output_path,
        frame_count=plan.frame_count,
        sample_rate_hz=sample_rate_hz,
        content_start_frames=plan.content_start_frames,
        picture_transitions=plan.picture_transitions,
    )


__all__ = [
    "ImageSource",
    "MfskSegmentContent",
    "MfskSegmentPlan",
    "MfskSegmentWaveResult",
    "PictureTransitionPlan",
    "TextFileSource",
    "encode_mfsk_segment_wav",
    "plan_mfsk_segment",
]
