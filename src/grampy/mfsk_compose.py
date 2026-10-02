"""Public, frame-exact composition of MFSK, copied audio, and silence."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import stat
import struct
from typing import BinaryIO, Literal, Self, Sequence, TypeAlias

from .mfsk_encode import (
    MAX_WAV_FRAMES,
    ContinuousPhaseToneWriter,
    _CanonicalWaveWriter,
    _validate_sample_rate,
)
from .mfsk_segment_encode import (
    ImageSource,
    MfskSegmentContent,
    MfskSegmentPlan,
    TextFileSource,
    _write_segment,
    plan_mfsk_segment,
)
from .text_encode import MODE_PARAMETERS, MfskMode


PictureColor: TypeAlias = Literal["color", "grayscale"]
PictureSpeed: TypeAlias = Literal[2, 4, 8]
_COPY_BYTES = 64 * 1024
_ZERO_BYTES = bytes(_COPY_BYTES)


@dataclass(frozen=True)
class TextPart:
    data: bytes

    @classmethod
    def from_text(cls, text: str, *, encoding: str = "utf-8") -> Self:
        return cls(text.encode(encoding))


@dataclass(frozen=True)
class TextFilePart:
    path: Path


@dataclass(frozen=True)
class ImagePart:
    path: Path
    color: PictureColor = "color"
    samples_per_pixel: PictureSpeed = 8


MfskPart: TypeAlias = TextPart | TextFilePart | ImagePart


@dataclass(frozen=True)
class MfskSegment:
    parts: Sequence[MfskPart]
    mode: MfskMode = "MFSK64"
    carrier_hz: float = 1500.0


@dataclass(frozen=True)
class AudioPart:
    path: Path


@dataclass(frozen=True)
class SilencePart:
    duration_seconds: float


OutputPart: TypeAlias = MfskSegment | AudioPart | SilencePart


@dataclass(frozen=True)
class EncodeConfig:
    sample_rate_hz: int = 48000


@dataclass(frozen=True)
class ContentStart:
    content_index: int
    start_seconds: float


@dataclass(frozen=True)
class SegmentStart:
    input_index: int
    start_seconds: float
    contents: tuple[ContentStart, ...]


@dataclass(frozen=True)
class EncodeResult:
    output_path: Path
    duration_seconds: float
    segments: tuple[SegmentStart, ...]


@dataclass(frozen=True)
class _AudioPlan:
    path: Path
    data_offset: int
    data_bytes: int

    @property
    def frame_count(self) -> int:
        return self.data_bytes // 2


@dataclass(frozen=True)
class _CompositionItem:
    contents: tuple[MfskSegmentContent, ...] | None
    mfsk_plan: MfskSegmentPlan | None
    audio_plan: _AudioPlan | None
    frame_count: int


def _read_exact(source: BinaryIO, length: int) -> bytes:
    payload = source.read(length)
    if len(payload) != length:
        raise ValueError("truncated WAV input")
    return payload


def _inspect_audio(path: Path, sample_rate_hz: int) -> _AudioPlan:
    with path.open("rb") as source:
        source.seek(0, 2)
        file_size = source.tell()
        source.seek(0)
        if file_size < 12:
            raise ValueError("audio input must be a classic RIFF/WAVE file")
        riff, declared_size, wave = struct.unpack("<4sI4s", _read_exact(source, 12))
        if riff != b"RIFF" or wave != b"WAVE":
            raise ValueError("audio input must be a classic RIFF/WAVE file")
        riff_end = declared_size + 8
        if riff_end > file_size or riff_end < 12:
            raise ValueError("truncated or invalid RIFF/WAVE input")

        format_found = False
        data: _AudioPlan | None = None
        while source.tell() < riff_end:
            if riff_end - source.tell() < 8:
                raise ValueError("partial WAV chunk header")
            chunk_id, chunk_size = struct.unpack("<4sI", _read_exact(source, 8))
            chunk_start = source.tell()
            chunk_end = chunk_start + chunk_size
            padded_end = chunk_end + (chunk_size & 1)
            if padded_end > riff_end:
                raise ValueError("truncated WAV chunk")
            if chunk_id == b"fmt ":
                if format_found or chunk_size < 16:
                    raise ValueError("invalid WAV format chunk")
                tag, channels, rate, byte_rate, block_align, bits = struct.unpack(
                    "<HHIIHH", _read_exact(source, 16)
                )
                if (
                    tag != 1
                    or channels != 1
                    or rate != sample_rate_hz
                    or byte_rate != rate * 2
                    or block_align != 2
                    or bits != 16
                ):
                    raise ValueError("audio input must be mono PCM16 at the output rate")
                format_found = True
            elif chunk_id == b"data":
                if data is not None or chunk_size == 0 or chunk_size & 1:
                    raise ValueError("audio input must contain one nonempty complete data chunk")
                data = _AudioPlan(path, chunk_start, chunk_size)
            source.seek(padded_end)
        if not format_found or data is None:
            raise ValueError("audio input needs format and nonempty PCM data chunks")
        return data


def _silence_frames(duration_seconds: float, sample_rate_hz: int) -> int:
    if (
        isinstance(duration_seconds, bool)
        or not isinstance(duration_seconds, (int, float))
        or not math.isfinite(float(duration_seconds))
        or duration_seconds <= 0
    ):
        raise ValueError("silence duration must be finite and strictly positive")
    frames = duration_seconds * sample_rate_hz
    if not math.isfinite(frames) or not float(frames).is_integer():
        raise ValueError("silence duration must map to an integral frame count")
    return int(frames)


def _snapshot_parts(parts: Sequence[OutputPart]) -> tuple[OutputPart, ...]:
    try:
        snapshot = tuple(parts)
    except TypeError as error:
        raise ValueError("parts must be a nonempty sequence") from error
    if not snapshot:
        raise ValueError("parts must be nonempty")
    frozen: list[OutputPart] = []
    for part in snapshot:
        if isinstance(part, MfskSegment):
            try:
                nested = tuple(part.parts)
            except TypeError as error:
                raise ValueError("MFSK parts must be a nonempty sequence") from error
            if not nested:
                raise ValueError("MFSK parts must be nonempty")
            frozen.append(MfskSegment(nested, part.mode, part.carrier_hz))
        else:
            frozen.append(part)
    return tuple(frozen)


def _path(value: Path) -> Path:
    try:
        return Path(value)
    except (TypeError, ValueError) as error:
        raise ValueError("input and output paths must be filesystem paths") from error


def _preflight(
    parts: tuple[OutputPart, ...],
    output_path: Path,
    sample_rate_hz: int,
) -> tuple[tuple[_CompositionItem, ...], tuple[SegmentStart, ...], int]:
    _validate_sample_rate(sample_rate_hz)
    if not stat.S_ISDIR(output_path.parent.stat().st_mode):
        raise NotADirectoryError(output_path.parent)
    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(output_path)

    items: list[_CompositionItem] = []
    starts: list[SegmentStart] = []
    cursor = 0
    for input_index, part in enumerate(parts):
        content_starts: tuple[ContentStart, ...] = ()
        if isinstance(part, MfskSegment):
            if not isinstance(part.mode, str) or part.mode not in MODE_PARAMETERS:
                raise ValueError("unsupported MFSK mode")
            sources: list[MfskSegmentContent] = []
            for content in part.parts:
                if isinstance(content, TextPart):
                    if not isinstance(content.data, bytes):
                        raise ValueError("TextPart.data must be bytes")
                    sources.append(content.data)
                elif isinstance(content, TextFilePart):
                    path = _path(content.path)
                    _reject_alias(output_path, path)
                    sources.append(TextFileSource(path))
                elif isinstance(content, ImagePart):
                    path = _path(content.path)
                    _reject_alias(output_path, path)
                    sources.append(ImageSource(path, content.color, content.samples_per_pixel))
                else:
                    raise ValueError("unsupported MFSK content item")
            contents = tuple(sources)
            mfsk_plan = plan_mfsk_segment(
                contents=contents,
                mode=part.mode,
                carrier_hz=part.carrier_hz,
                sample_rate_hz=sample_rate_hz,
            )
            frame_count = mfsk_plan.frame_count
            content_starts = tuple(
                ContentStart(i, (cursor + frame) / sample_rate_hz)
                for i, frame in enumerate(mfsk_plan.content_start_frames)
            )
            item = _CompositionItem(contents, mfsk_plan, None, frame_count)
        elif isinstance(part, AudioPart):
            path = _path(part.path)
            _reject_alias(output_path, path)
            audio_plan = _inspect_audio(path, sample_rate_hz)
            frame_count = audio_plan.frame_count
            item = _CompositionItem(None, None, audio_plan, frame_count)
        elif isinstance(part, SilencePart):
            frame_count = _silence_frames(part.duration_seconds, sample_rate_hz)
            item = _CompositionItem(None, None, None, frame_count)
        else:
            raise ValueError("unsupported output part")
        starts.append(SegmentStart(input_index, cursor / sample_rate_hz, content_starts))
        cursor += frame_count
        if cursor > MAX_WAV_FRAMES:
            raise ValueError("predicted composition exceeds the classic RIFF/WAVE limit")
        items.append(item)
    return tuple(items), tuple(starts), cursor


def _reject_alias(output_path: Path, input_path: Path) -> None:
    # stat resolves both hard links and symlinks. Opening the source here also
    # reports missing and inaccessible inputs before output replacement.
    input_stat = input_path.stat()
    try:
        output_stat = output_path.stat()
    except FileNotFoundError:
        return
    if (input_stat.st_dev, input_stat.st_ino) == (output_stat.st_dev, output_stat.st_ino):
        raise ValueError("output path aliases an input path")


def _copy_audio(writer: _CanonicalWaveWriter, audio: _AudioPlan) -> None:
    with audio.path.open("rb") as source:
        source.seek(audio.data_offset)
        remaining = audio.data_bytes
        while remaining:
            chunk = source.read(min(_COPY_BYTES, remaining))
            if not chunk:
                raise ValueError("audio input became truncated during encoding")
            writer.write(chunk)
            remaining -= len(chunk)


def _write_silence(writer: _CanonicalWaveWriter, frame_count: int) -> None:
    remaining = frame_count * 2
    while remaining:
        length = min(_COPY_BYTES, remaining)
        writer.write(_ZERO_BYTES[:length])
        remaining -= length


def encode_mfsk_wav(
    *,
    parts: Sequence[OutputPart],
    output_path: Path,
    config: EncodeConfig | None = None,
) -> EncodeResult:
    """Compose one canonical mono PCM WAV at the caller's exact output path."""
    snapshot = _snapshot_parts(parts)
    if config is None:
        config = EncodeConfig()
    elif not isinstance(config, EncodeConfig):
        raise ValueError("config must be an EncodeConfig")
    output_path = _path(output_path)
    items, starts, total_frames = _preflight(
        snapshot, output_path, config.sample_rate_hz
    )

    handle: BinaryIO | None = None
    writing_began = False
    try:
        handle = output_path.open("wb")
        writing_began = True
        writer = _CanonicalWaveWriter(handle, config.sample_rate_hz)
        for item in items:
            if item.mfsk_plan is not None:
                plan = item.mfsk_plan
                if item.contents is None:
                    raise RuntimeError("missing planned MFSK contents")
                synthesizer = ContinuousPhaseToneWriter(
                    writer,
                    mode=plan.mode,
                    carrier_hz=plan.carrier_hz,
                    sample_rate_hz=config.sample_rate_hz,
                )
                _write_segment(
                    synthesizer,
                    contents=item.contents,
                    mode=plan.mode,
                    carrier_hz=plan.carrier_hz,
                    sample_rate_hz=config.sample_rate_hz,
                )
                if synthesizer.accepted_frame_count != plan.frame_count:
                    raise RuntimeError("planned and encoded MFSK frame counts disagree")
                synthesizer.finish()
                if synthesizer.frame_count != plan.frame_count:
                    raise RuntimeError("planned and synthesized MFSK frame counts disagree")
            elif item.audio_plan is not None:
                _copy_audio(writer, item.audio_plan)
            else:
                _write_silence(writer, item.frame_count)
        writer.finish()
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

    return EncodeResult(output_path, total_frames / config.sample_rate_hz, starts)


__all__ = [
    "AudioPart", "ContentStart", "EncodeConfig", "EncodeResult", "ImagePart",
    "MfskMode", "MfskPart", "MfskSegment", "OutputPart", "PictureColor",
    "PictureSpeed", "SegmentStart", "SilencePart", "TextFilePart", "TextPart",
    "encode_mfsk_wav",
]
