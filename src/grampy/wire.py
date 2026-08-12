from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from .resources import load_json


GENERATOR_MASKS = (0x6D, 0x4F)

_VITERBI_NEXT_STATES = np.arange(64, dtype=np.uint8)
_VITERBI_INPUT_BITS = _VITERBI_NEXT_STATES & 1
_VITERBI_PREDECESSORS = np.stack(
    (
        _VITERBI_NEXT_STATES >> 1,
        (_VITERBI_NEXT_STATES >> 1) + 32,
    )
)
_VITERBI_BRANCH_SIGNS = np.empty((2, 64, 2), dtype=np.float64)
for _candidate in range(2):
    for _next_state in range(64):
        _encoder_state = (
            (int(_VITERBI_PREDECESSORS[_candidate, _next_state]) << 1)
            | int(_VITERBI_INPUT_BITS[_next_state])
        ) & 0x7F
        _VITERBI_BRANCH_SIGNS[_candidate, _next_state] = [
            1.0 if (_encoder_state & mask).bit_count() & 1 else -1.0
            for mask in GENERATOR_MASKS
        ]


def convolutional_encode(bits: Iterable[int], initial_state: int = 0) -> list[int]:
    if not 0 <= initial_state < 128:
        raise ValueError("initial_state must be a 7-bit value")
    state = initial_state
    output: list[int] = []
    for bit in bits:
        if bit not in (0, 1):
            raise ValueError("bits must contain only 0 or 1")
        state = ((state << 1) | bit) & 0x7F
        output.extend((state & mask).bit_count() & 1 for mask in GENERATOR_MASKS)
    return output


def fldigi_gray_encode(value: int) -> int:
    if not 0 <= value < 16:
        raise ValueError("tone label must be in [0, 15]")
    encoded = value
    for shift in range(1, 4):
        encoded ^= value >> shift
    return encoded


def fldigi_forward_interleave(coded_bits: Sequence[int]) -> list[tuple[int, ...]]:
    """Apply fldigi's four-lane, depth-ten transmit interleaver.

    Partial trailing groups are retained because fldigi carries its coded-bit
    accumulator across the text-to-picture flush boundary.
    """
    if any(bit not in (0, 1) for bit in coded_bits):
        raise ValueError("coded_bits must contain only 0 or 1")
    groups = [
        tuple(coded_bits[index : index + 4])
        for index in range(0, len(coded_bits), 4)
    ]
    output: list[tuple[int, ...]] = []
    for index, group in enumerate(groups):
        if len(group) < 4:
            output.append(group)
            continue
        output.append(
            (
                group[0],
                groups[index - 10][1] if index >= 10 else 0,
                groups[index - 20][2] if index >= 20 else 0,
                groups[index - 30][3] if index >= 30 else 0,
            )
        )
    return output


def picture_flush_tones(decoded_bits: Sequence[int], mode: str) -> list[int]:
    """Predict physical tones emitted between a picture header and prologue.

    ``decoded_bits`` ends at the exclusive decoded-bit stop of the final
    header codeword. fldigi then sends one bit followed by mode-specific zeros
    to drain its convolutional encoder and interleaver. The returned sequence
    includes only newly completed four-coded-bit symbols.
    """
    if any(bit not in (0, 1) for bit in decoded_bits):
        raise ValueError("decoded_bits must contain only 0 or 1")
    if mode == "MFSK32":
        zero_count = 107
    elif mode == "MFSK64":
        zero_count = 180
    else:
        raise ValueError(f"unsupported MFSK picture mode: {mode}")
    header_coded_count = len(convolutional_encode(decoded_bits))
    coded = convolutional_encode([*decoded_bits, 1, *([0] * zero_count)])
    groups = fldigi_forward_interleave(coded)
    first_complete_group = header_coded_count // 4
    tones: list[int] = []
    for group in groups[first_complete_group:]:
        if len(group) != 4:
            continue
        label = sum(bit << (3 - lane) for lane, bit in enumerate(group))
        tones.append(fldigi_gray_encode(label))
    return tones


class StatefulPictureFlushEncoder:
    """Compact transmitter state sufficient to reconstruct a picture flush."""

    SCHEMA = "grampy.picture-flush-encoder-checkpoint.v1"

    def __init__(self) -> None:
        self._encoder_state = 0
        self._coded_accumulator: list[int] = []
        self._raw_groups: list[tuple[int, int, int, int]] = []
        self._group_count = 0
        self._decoded_bit_count = 0

    @property
    def decoded_bit_count(self) -> int:
        return self._decoded_bit_count

    def push(self, bits: Iterable[int]) -> tuple[int, ...]:
        tones: list[int] = []
        for bit in bits:
            if bit not in (0, 1):
                raise ValueError("bits must contain only 0 or 1")
            self._encoder_state = ((self._encoder_state << 1) | bit) & 0x7F
            self._decoded_bit_count += 1
            self._coded_accumulator.extend(
                (self._encoder_state & mask).bit_count() & 1
                for mask in GENERATOR_MASKS
            )
            if len(self._coded_accumulator) == 4:
                raw = tuple(self._coded_accumulator)
                self._coded_accumulator = []
                index = self._group_count

                def prior(delay: int, lane: int) -> int:
                    target = index - delay
                    retained_start = index - len(self._raw_groups)
                    return (
                        self._raw_groups[target - retained_start][lane]
                        if target >= 0 else 0
                    )

                group = (
                    raw[0], prior(10, 1), prior(20, 2), prior(30, 3)
                )
                label = sum(value << (3 - lane) for lane, value in enumerate(group))
                tones.append(fldigi_gray_encode(label))
                self._raw_groups.append(raw)
                self._raw_groups = self._raw_groups[-30:]
                self._group_count += 1
        return tuple(tones)

    def predict_flush(self, mode: str) -> list[int]:
        if mode == "MFSK32":
            zero_count = 107
        elif mode == "MFSK64":
            zero_count = 180
        else:
            raise ValueError(f"unsupported MFSK picture mode: {mode}")
        clone = self.restore(self.checkpoint())
        return list(clone.push([1, *([0] * zero_count)]))

    def checkpoint(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "encoder_state": self._encoder_state,
            "coded_accumulator": list(self._coded_accumulator),
            "raw_groups": [list(group) for group in self._raw_groups],
            "group_count": self._group_count,
            "decoded_bit_count": self._decoded_bit_count,
        }

    @classmethod
    def restore(cls, checkpoint: dict[str, object]) -> StatefulPictureFlushEncoder:
        if checkpoint.get("schema") != cls.SCHEMA:
            raise ValueError("unsupported picture-flush encoder checkpoint")
        instance = cls()
        instance._encoder_state = int(checkpoint["encoder_state"])
        accumulator = checkpoint.get("coded_accumulator")
        groups = checkpoint.get("raw_groups")
        if not isinstance(accumulator, list) or len(accumulator) not in {0, 2}:
            raise ValueError("malformed picture-flush coded accumulator")
        if not isinstance(groups, list) or len(groups) > 30:
            raise ValueError("malformed picture-flush group history")
        instance._coded_accumulator = [int(value) for value in accumulator]
        instance._raw_groups = [tuple(int(value) for value in group) for group in groups]
        if any(len(group) != 4 for group in instance._raw_groups):
            raise ValueError("malformed picture-flush group history")
        if any(value not in (0, 1) for value in instance._coded_accumulator):
            raise ValueError("malformed picture-flush coded accumulator")
        if any(value not in (0, 1) for group in instance._raw_groups for value in group):
            raise ValueError("malformed picture-flush group history")
        instance._group_count = int(checkpoint["group_count"])
        instance._decoded_bit_count = int(checkpoint["decoded_bit_count"])
        if (
            not 0 <= instance._encoder_state < 128
            or instance._group_count < len(instance._raw_groups)
            or instance._decoded_bit_count < 0
        ):
            raise ValueError("malformed picture-flush coordinates")
        return instance


def physical_tone_to_label(tone_index: int) -> int:
    if not 0 <= tone_index < 16:
        raise ValueError("tone index must be in [0, 15]")
    for label in range(16):
        if fldigi_gray_encode(label) == tone_index:
            return label
    raise AssertionError("four-bit Gray map is not bijective")


def tone_metrics_to_llrs(metrics: Sequence[float]) -> np.ndarray:
    """Return four log(P(bit=1)/P(bit=0)) values in transmitted lane order."""
    values = np.asarray(metrics, dtype=np.float64)
    if values.shape != (16,):
        raise ValueError("tone metrics must contain exactly 16 values")
    if np.isnan(values).any() or np.isposinf(values).any():
        raise ValueError("tone metrics must not contain NaN or +infinity")

    labels = np.array(
        [physical_tone_to_label(tone) for tone in range(16)],
        dtype=np.uint8,
    )
    result = np.empty(4, dtype=np.float64)
    for lane in range(4):
        mask = 1 << (3 - lane)
        result[lane] = _logsumexp(values[(labels & mask) != 0]) - _logsumexp(
            values[(labels & mask) == 0]
        )
    return result


def _logsumexp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    if maximum == -math.inf:
        return -math.inf
    return maximum + math.log(float(np.exp(values - maximum).sum()))


class SoftDeinterleaver:
    """Inverse of fldigi's four-lane depth-ten transmit transformation."""

    def __init__(self) -> None:
        self._groups: list[tuple[float, float, float, float]] = []
        self._valid: list[tuple[bool, bool, bool, bool]] = []
        self._total_group_count = 0

    def push(
        self, group: Sequence[float], *, valid: bool = True
    ) -> tuple[float, float, float, float]:
        if len(group) != 4:
            raise ValueError("interleaver groups must contain four lanes")
        current = tuple(float(value) for value in group)
        self._groups.append(current)
        self._valid.append((valid, valid, valid, valid))
        self._total_group_count += 1
        index = len(self._groups) - 1
        # y(t)=[x0(t),x1(t-10),x2(t-20),x3(t-30)]. At receive group t,
        # the complete recoverable preinterleaver group is x(t-30).
        return (
            self._groups[index - 30][0] if index >= 30 else 0.0,
            self._groups[index - 20][1] if index >= 20 else 0.0,
            self._groups[index - 10][2] if index >= 10 else 0.0,
            self._groups[index][3],
        )

    @property
    def group_count(self) -> int:
        return self._total_group_count

    def output_validity(self) -> tuple[bool, bool, bool, bool]:
        """Return fill validity for the most recently emitted group."""
        if not self._groups:
            raise ValueError("no deinterleaver group has been emitted")
        index = len(self._groups) - 1
        return (
            self._valid[index - 30][0] if index >= 30 else False,
            self._valid[index - 20][1] if index >= 20 else False,
            self._valid[index - 10][2] if index >= 10 else False,
            self._valid[index][3],
        )

    def checkpoint(self) -> dict[str, object]:
        """Return immutable JSON-compatible state sufficient for restoration."""
        return {
            "schema": "grampy.deinterleaver-checkpoint.v1",
            "groups": [list(group) for group in self._groups[-30:]],
            "validity": [list(value) for value in self._valid[-30:]],
            "group_count": self._total_group_count,
        }

    @classmethod
    def restore(cls, checkpoint: dict[str, object]) -> SoftDeinterleaver:
        if checkpoint.get("schema") != "grampy.deinterleaver-checkpoint.v1":
            raise ValueError("unsupported deinterleaver checkpoint")
        instance = cls()
        groups = checkpoint.get("groups")
        validity = checkpoint.get("validity")
        if not isinstance(groups, list) or not isinstance(validity, list):
            raise ValueError("malformed deinterleaver checkpoint")
        if len(groups) != len(validity) or len(groups) > 30:
            raise ValueError("malformed deinterleaver checkpoint history")
        for group, valid in zip(groups, validity):
            if not isinstance(group, list) or len(group) != 4:
                raise ValueError("malformed deinterleaver group")
            if not isinstance(valid, list) or len(valid) != 4:
                raise ValueError("malformed deinterleaver validity")
            instance._groups.append(tuple(float(value) for value in group))
            instance._valid.append(tuple(bool(value) for value in valid))
        instance._total_group_count = int(checkpoint.get("group_count", len(groups)))
        if instance._total_group_count < len(groups):
            raise ValueError("malformed deinterleaver group count")
        return instance


@dataclass(frozen=True)
class ViterbiResult:
    bits: tuple[int, ...]
    path_metric_gap: float
    final_state: int


@dataclass(frozen=True)
class StatefulViterbiBit:
    """One decoded bit that has crossed the bounded traceback horizon."""

    bit: int
    decoded_bit_index: int
    deinterleaved_coded_bit_interval: tuple[int, int]
    decision_path_metric_gap: float | None


class StatefulSoftViterbiDecoder:
    """Checkpointable continuous K=7 Viterbi spike with bounded traceback.

    Ordinary ``push`` calls commit only decisions older than
    ``traceback_depth``. ``finish`` explicitly closes the current epoch and
    commits its remaining best-path tail; callers must not use it at an
    administrative chunk boundary.
    """

    SCHEMA = "grampy.viterbi-checkpoint.v1"

    def __init__(
        self, *, initial_state: int | None = 0, traceback_depth: int = 48
    ) -> None:
        if initial_state is not None and not 0 <= initial_state < 64:
            raise ValueError("initial_state must be a six-bit value")
        if traceback_depth < 1:
            raise ValueError("traceback_depth must be positive")
        self.traceback_depth = int(traceback_depth)
        self._path_metrics = (
            np.zeros(64, dtype=np.float64)
            if initial_state is None
            else np.full(64, -np.inf)
        )
        if initial_state is not None:
            self._path_metrics[initial_state] = 0.0
        self._predecessors: list[np.ndarray] = []
        self._step_count = 0
        self._committed_count = 0
        self._closed = False

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def committed_count(self) -> int:
        return self._committed_count

    @property
    def uncommitted_count(self) -> int:
        return len(self._predecessors)

    def push(self, llrs: Sequence[float]) -> tuple[StatefulViterbiBit, ...]:
        if self._closed:
            raise ValueError("cannot push after the Viterbi epoch is finished")
        values = np.asarray(llrs, dtype=np.float64)
        if values.ndim != 1 or len(values) % 2:
            raise ValueError(
                "Viterbi input must be a flat sequence of coded-bit pairs"
            )
        if np.isnan(values).any() or np.isinf(values).any():
            raise ValueError("Viterbi LLRs must be finite")
        committed: list[StatefulViterbiBit] = []
        for pair in values.reshape(-1, 2):
            (
                self._path_metrics,
                predecessors,
                _,
            ) = _advance_viterbi_survivors(self._path_metrics, pair)
            self._predecessors.append(predecessors)
            self._step_count += 1
            if len(self._predecessors) > self.traceback_depth:
                bit = self._traceback_bits()[0]
                committed.append(self._commit(bit))
        return tuple(committed)

    def finish(self) -> tuple[StatefulViterbiBit, ...]:
        """Close a protocol epoch and commit its best-path uncommitted tail."""
        if self._closed:
            return ()
        tail = self._traceback_bits()
        committed = tuple(self._commit(bit) for bit in tail)
        self._closed = True
        return committed

    def checkpoint(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "traceback_depth": self.traceback_depth,
            "path_metrics": [
                float(value) if np.isfinite(value) else None
                for value in self._path_metrics
            ],
            "predecessors": [row.tolist() for row in self._predecessors],
            "step_count": self._step_count,
            "committed_count": self._committed_count,
            "closed": self._closed,
        }

    def state_digest(self) -> str:
        encoded = json.dumps(
            self.checkpoint(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def restore(cls, checkpoint: dict[str, object]) -> StatefulSoftViterbiDecoder:
        if checkpoint.get("schema") != cls.SCHEMA:
            raise ValueError("unsupported Viterbi checkpoint")
        instance = cls(
            initial_state=0,
            traceback_depth=int(checkpoint["traceback_depth"]),
        )
        metrics = checkpoint.get("path_metrics")
        predecessors = checkpoint.get("predecessors")
        if not isinstance(metrics, list) or len(metrics) != 64:
            raise ValueError("malformed Viterbi path metrics")
        if not isinstance(predecessors, list):
            raise ValueError("malformed Viterbi survivor history")
        if len(predecessors) > instance.traceback_depth:
            raise ValueError("malformed Viterbi survivor history")
        try:
            restored_metrics = [
                -np.inf if value is None else float(value) for value in metrics
            ]
        except (TypeError, ValueError) as error:
            raise ValueError("malformed Viterbi path metrics") from error
        if any(
            value != -np.inf and not np.isfinite(value)
            for value in restored_metrics
        ):
            raise ValueError("malformed Viterbi path metrics")
        instance._path_metrics = np.asarray(restored_metrics, dtype=np.float64)
        if not np.isfinite(instance._path_metrics).any():
            raise ValueError("Viterbi checkpoint has no finite survivor")
        instance._predecessors = [
            _checkpoint_survivor_row(row, "predecessor") for row in predecessors
        ]
        if any(np.any(row > 63) for row in instance._predecessors):
            raise ValueError("malformed Viterbi predecessor history")
        instance._step_count = int(checkpoint["step_count"])
        instance._committed_count = int(checkpoint["committed_count"])
        if (
            instance._step_count < 0
            or instance._committed_count < 0
            or instance._step_count - instance._committed_count
            != len(instance._predecessors)
        ):
            raise ValueError("malformed Viterbi checkpoint coordinates")
        instance._closed = bool(checkpoint.get("closed", False))
        if instance._closed and instance._predecessors:
            raise ValueError("closed Viterbi checkpoint retains an uncommitted tail")
        return instance

    def _traceback_bits(self) -> list[int]:
        if not self._predecessors:
            return []
        state = int(np.argmax(self._path_metrics))
        decoded: list[int] = []
        for predecessors in reversed(self._predecessors):
            # The trellis transition makes the decoded input bit the least
            # significant bit of its destination state, so it need not be
            # duplicated in the checkpoint.
            decoded.append(state & 1)
            state = int(predecessors[state])
        decoded.reverse()
        return decoded

    def _commit(self, bit: int) -> StatefulViterbiBit:
        index = self._committed_count
        order = np.argsort(self._path_metrics)
        runner_up = self._path_metrics[order[-2]]
        gap = (
            float(self._path_metrics[order[-1]] - runner_up)
            if np.isfinite(runner_up)
            else None
        )
        self._predecessors.pop(0)
        self._committed_count += 1
        return StatefulViterbiBit(
            bit=bit,
            decoded_bit_index=index,
            deinterleaved_coded_bit_interval=(2 * index, 2 * (index + 1)),
            decision_path_metric_gap=gap,
        )


def _checkpoint_survivor_row(value: object, name: str) -> np.ndarray:
    if not isinstance(value, list) or len(value) != 64:
        raise ValueError(f"malformed Viterbi {name} history")
    values = np.asarray(value)
    if not np.issubdtype(values.dtype, np.integer):
        raise ValueError(f"malformed Viterbi {name} history")
    if np.any(values < 0) or np.any(values > 255):
        raise ValueError(f"malformed Viterbi {name} history")
    return values.astype(np.uint8)


def _advance_viterbi_survivors(
    path_metrics: np.ndarray, pair: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    branches = (
        _VITERBI_BRANCH_SIGNS[:, :, 0] * pair[0]
        + _VITERBI_BRANCH_SIGNS[:, :, 1] * pair[1]
    )
    candidates = path_metrics[_VITERBI_PREDECESSORS] + branches
    # The scalar reference visits the low predecessor first and replaces it
    # only on a strict improvement, so ties deterministically retain row zero.
    choose_high = candidates[1] > candidates[0]
    next_metrics = np.where(choose_high, candidates[1], candidates[0])
    predecessors = np.where(
        choose_high, _VITERBI_PREDECESSORS[1], _VITERBI_PREDECESSORS[0]
    ).astype(np.uint8)
    input_bits = _VITERBI_INPUT_BITS.copy()
    reachable = np.isfinite(next_metrics)
    predecessors[~reachable] = 0
    input_bits[~reachable] = 0
    maximum = float(np.max(next_metrics))
    if not np.isfinite(maximum):
        raise ValueError("Viterbi decoder has no finite survivor")
    return next_metrics - maximum, predecessors, input_bits


def soft_viterbi_decode(
    llrs: Sequence[float], initial_state: int | None = 0
) -> ViterbiResult:
    """Decode the fldigi K=7 rate-1/2 code from log(P(1)/P(0)) evidence."""
    values = np.asarray(llrs, dtype=np.float64)
    if values.ndim != 1 or len(values) % 2:
        raise ValueError("Viterbi input must be a flat sequence of coded-bit pairs")
    if np.isnan(values).any() or np.isinf(values).any():
        raise ValueError("Viterbi LLRs must be finite")
    if initial_state is not None and not 0 <= initial_state < 64:
        raise ValueError("initial_state must be a six-bit value")

    steps = len(values) // 2
    path_metrics = (
        np.zeros(64, dtype=np.float64)
        if initial_state is None
        else np.full(64, -np.inf)
    )
    if initial_state is not None:
        path_metrics[initial_state] = 0.0
    predecessors = np.zeros((steps, 64), dtype=np.uint8)
    input_bits = np.zeros((steps, 64), dtype=np.uint8)
    for step, pair in enumerate(values.reshape(-1, 2)):
        path_metrics, prior_states, decisions = _advance_viterbi_survivors(
            path_metrics, pair
        )
        predecessors[step] = prior_states
        input_bits[step] = decisions

    order = np.argsort(path_metrics)
    final_state = int(order[-1])
    gap = float(path_metrics[order[-1]] - path_metrics[order[-2]])
    decoded: list[int] = []
    state = final_state
    for step in range(steps - 1, -1, -1):
        decoded.append(int(input_bits[step, state]))
        state = int(predecessors[step, state])
    decoded.reverse()
    return ViterbiResult(tuple(decoded), gap, final_state)


@dataclass(frozen=True)
class VaricodeEvent:
    octet: int | None
    codeword: str
    start_bit: int
    stop_bit: int
    recognized_at_bit: int


def parse_varicode(
    bits: Sequence[int],
    encodings: Sequence[str] | None = None,
) -> tuple[VaricodeEvent, ...]:
    """Parse terminated MFSK Varicode using fldigi's ``001`` look-ahead rule."""
    if encodings is None:
        encodings = load_json("data", "mfsk_varicode.json")["encodings"]
    lookup = {encoding: octet for octet, encoding in enumerate(encodings)}
    pending = ""
    pending_start = 0
    events: list[VaricodeEvent] = []
    for index, bit in enumerate(bits):
        if bit not in (0, 1):
            raise ValueError("Varicode bits must contain only 0 or 1")
        pending += str(bit)
        if pending.endswith("001"):
            codeword = pending[:-1]
            events.append(
                VaricodeEvent(
                    octet=lookup.get(codeword),
                    codeword=codeword,
                    start_bit=pending_start,
                    stop_bit=index,
                    recognized_at_bit=index + 1,
                )
            )
            pending = "1"
            pending_start = index
    return tuple(events)
