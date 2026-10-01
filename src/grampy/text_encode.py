from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, TypeAlias

from .resources import load_json


MfskMode: TypeAlias = Literal["MFSK32", "MFSK64"]

_GENERATOR_MASKS = (0x6D, 0x4F)
_INTERLEAVER_HISTORY_GROUPS = 30


@dataclass(frozen=True)
class MfskModeParameters:
    internal_sample_rate_hz: int
    samples_per_symbol: int
    symbols_per_second: float
    tone_count: int
    bits_per_symbol: int
    tone_spacing_hz: float
    tone_span_hz: float
    interleaver_depth: int
    preamble_input_bits: int


MODE_PARAMETERS: Mapping[MfskMode, MfskModeParameters] = MappingProxyType(
    {
        "MFSK32": MfskModeParameters(
            internal_sample_rate_hz=8000,
            samples_per_symbol=256,
            symbols_per_second=31.25,
            tone_count=16,
            bits_per_symbol=4,
            tone_spacing_hz=31.25,
            tone_span_hz=468.75,
            interleaver_depth=10,
            preamble_input_bits=107,
        ),
        "MFSK64": MfskModeParameters(
            internal_sample_rate_hz=8000,
            samples_per_symbol=128,
            symbols_per_second=62.5,
            tone_count=16,
            bits_per_symbol=4,
            tone_spacing_hz=62.5,
            tone_span_hz=937.5,
            interleaver_depth=10,
            preamble_input_bits=180,
        ),
    }
)


def _load_varicode() -> tuple[tuple[int, ...], ...]:
    document = load_json("data", "mfsk_varicode.json")
    encodings = document.get("encodings")
    if not isinstance(encodings, list) or len(encodings) != 256:
        raise ValueError("packaged MFSK Varicode must contain 256 entries")
    result: list[tuple[int, ...]] = []
    for encoding in encodings:
        if not isinstance(encoding, str) or any(bit not in "01" for bit in encoding):
            raise ValueError("packaged MFSK Varicode contains an invalid codeword")
        result.append(tuple(int(bit) for bit in encoding))
    return tuple(result)


_VARICODE = _load_varicode()


def varicode_codeword(octet: int) -> tuple[int, ...]:
    if isinstance(octet, bool) or not isinstance(octet, int) or not 0 <= octet <= 255:
        raise ValueError("octet must be an integer from zero through 255")
    return _VARICODE[octet]


def physical_tone_index(binary_label: int) -> int:
    if (
        isinstance(binary_label, bool)
        or not isinstance(binary_label, int)
        or not 0 <= binary_label < 16
    ):
        raise ValueError("binary tone label must be an integer from zero through 15")
    encoded = binary_label
    for shift in range(1, 4):
        encoded ^= binary_label >> shift
    return encoded


@dataclass(frozen=True)
class TextToneCheckpoint:
    mode: MfskMode
    convolutional_state: int
    pending_coded_bits: tuple[int, ...]
    raw_group_history: tuple[tuple[int, int, int, int], ...]
    group_count: int
    input_bit_count: int
    input_octet_count: int
    tone_count: int


class StatefulTextToneEncoder:
    """Incrementally map MFSK Varicode bytes to physical tone indices.

    The encoder emits a tone only when four coded bits are available. It does
    not add start/end framing or flush pending state.
    """

    def __init__(self, mode: MfskMode) -> None:
        if mode not in MODE_PARAMETERS:
            raise ValueError(f"unsupported MFSK mode: {mode}")
        self._mode = mode
        self._convolutional_state = 0
        self._pending_coded_bits: list[int] = []
        self._raw_group_history: list[tuple[int, int, int, int]] = []
        self._group_count = 0
        self._input_bit_count = 0
        self._input_octet_count = 0
        self._tone_count = 0

    @property
    def mode(self) -> MfskMode:
        return self._mode

    @property
    def parameters(self) -> MfskModeParameters:
        return MODE_PARAMETERS[self._mode]

    def push_bytes(self, data: bytes) -> tuple[int, ...]:
        if not isinstance(data, bytes):
            raise TypeError("MFSK text input must be bytes")
        tones: list[int] = []
        for octet in data:
            for bit in _VARICODE[octet]:
                tone = self._push_bit(bit)
                if tone is not None:
                    tones.append(tone)
            self._input_octet_count += 1
        return tuple(tones)

    def push_bits(self, bits: Iterable[int]) -> tuple[int, ...]:
        values = tuple(bits)
        if any(
            isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1)
            for bit in values
        ):
            raise ValueError("input bits must contain only integer zero or one")
        tones: list[int] = []
        for bit in values:
            tone = self._push_bit(bit)
            if tone is not None:
                tones.append(tone)
        return tuple(tones)

    def checkpoint(self) -> TextToneCheckpoint:
        return TextToneCheckpoint(
            mode=self._mode,
            convolutional_state=self._convolutional_state,
            pending_coded_bits=tuple(self._pending_coded_bits),
            raw_group_history=tuple(self._raw_group_history),
            group_count=self._group_count,
            input_bit_count=self._input_bit_count,
            input_octet_count=self._input_octet_count,
            tone_count=self._tone_count,
        )

    @classmethod
    def restore(cls, checkpoint: TextToneCheckpoint) -> StatefulTextToneEncoder:
        cls._validate_checkpoint(checkpoint)
        instance = cls(checkpoint.mode)
        instance._convolutional_state = checkpoint.convolutional_state
        instance._pending_coded_bits = list(checkpoint.pending_coded_bits)
        instance._raw_group_history = list(checkpoint.raw_group_history)
        instance._group_count = checkpoint.group_count
        instance._input_bit_count = checkpoint.input_bit_count
        instance._input_octet_count = checkpoint.input_octet_count
        instance._tone_count = checkpoint.tone_count
        return instance

    def _push_bit(self, bit: int) -> int | None:
        self._convolutional_state = (
            (self._convolutional_state << 1) | bit
        ) & 0x7F
        self._input_bit_count += 1
        self._pending_coded_bits.extend(
            (self._convolutional_state & mask).bit_count() & 1
            for mask in _GENERATOR_MASKS
        )
        if len(self._pending_coded_bits) < 4:
            return None

        raw_group = tuple(self._pending_coded_bits)
        self._pending_coded_bits.clear()
        group_index = self._group_count
        retained_start = group_index - len(self._raw_group_history)

        def prior(delay: int, lane: int) -> int:
            target = group_index - delay
            if target < 0:
                return 0
            return self._raw_group_history[target - retained_start][lane]

        interleaved = (
            raw_group[0],
            prior(10, 1),
            prior(20, 2),
            prior(30, 3),
        )
        binary_label = sum(
            value << (3 - lane) for lane, value in enumerate(interleaved)
        )
        tone = physical_tone_index(binary_label)
        self._raw_group_history.append(raw_group)
        del self._raw_group_history[:-_INTERLEAVER_HISTORY_GROUPS]
        self._group_count += 1
        self._tone_count += 1
        return tone

    @staticmethod
    def _validate_checkpoint(checkpoint: TextToneCheckpoint) -> None:
        if not isinstance(checkpoint, TextToneCheckpoint):
            raise ValueError("unsupported text-tone checkpoint")
        if checkpoint.mode not in MODE_PARAMETERS:
            raise ValueError("checkpoint has an unsupported MFSK mode")
        if not 0 <= checkpoint.convolutional_state < 128:
            raise ValueError("checkpoint has an invalid convolutional state")
        if len(checkpoint.pending_coded_bits) not in (0, 2) or any(
            bit not in (0, 1) for bit in checkpoint.pending_coded_bits
        ):
            raise ValueError("checkpoint has invalid pending coded bits")
        if len(checkpoint.raw_group_history) > _INTERLEAVER_HISTORY_GROUPS or any(
            len(group) != 4 or any(bit not in (0, 1) for bit in group)
            for group in checkpoint.raw_group_history
        ):
            raise ValueError("checkpoint has invalid interleaver history")
        expected_history = min(
            checkpoint.group_count, _INTERLEAVER_HISTORY_GROUPS
        )
        if len(checkpoint.raw_group_history) != expected_history:
            raise ValueError("checkpoint interleaver history is incomplete")
        if any(
            value < 0
            for value in (
                checkpoint.group_count,
                checkpoint.input_bit_count,
                checkpoint.input_octet_count,
                checkpoint.tone_count,
            )
        ):
            raise ValueError("checkpoint counters must be non-negative")
        if checkpoint.tone_count != checkpoint.group_count:
            raise ValueError("checkpoint tone and group counts disagree")
        if 2 * checkpoint.input_bit_count != (
            4 * checkpoint.group_count + len(checkpoint.pending_coded_bits)
        ):
            raise ValueError("checkpoint coded-bit coordinates disagree")
