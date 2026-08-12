from __future__ import annotations

import copy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Sequence

from .resources import load_json


@dataclass(frozen=True)
class StatefulVaricodeEvent:
    octet: int | None
    codeword: str
    start_bit: int
    stop_bit: int
    recognized_at_bit: int
    confidence: float
    source_bit_interval: tuple[int, int]
    source_input_interval: tuple[int, int] | None
    source_input_complete: bool


class StatefulVaricodeParser:
    """Checkpointable implementation of the MFSK ``001`` look-ahead parser."""

    def __init__(self, encodings: Sequence[str] | None = None) -> None:
        if encodings is None:
            encodings = load_json("data", "mfsk_varicode.json")["encodings"]
        self._lookup = {encoding: octet for octet, encoding in enumerate(encodings)}
        self._pending = ""
        self._pending_confidence: list[float] = []
        self._pending_source_intervals: list[tuple[int, int] | None] = []
        self._pending_source_complete: list[bool] = []
        self._pending_start = 0
        self._consumed = 0

    def push(
        self,
        bits: Sequence[int],
        confidences: Sequence[float] | None = None,
        *,
        source_intervals: Sequence[tuple[int, int] | None] | None = None,
        source_complete: Sequence[bool] | None = None,
    ) -> tuple[StatefulVaricodeEvent, ...]:
        if confidences is None:
            confidences = [1.0] * len(bits)
        if source_intervals is None:
            source_intervals = [None] * len(bits)
        if source_complete is None:
            source_complete = [interval is not None for interval in source_intervals]
        if len(bits) != len(confidences):
            raise ValueError("Varicode bits and confidences must have equal length")
        if len(bits) != len(source_intervals):
            raise ValueError(
                "Varicode bits and source intervals must have equal length"
            )
        if len(bits) != len(source_complete):
            raise ValueError(
                "Varicode bits and source completeness must have equal length"
            )
        events: list[StatefulVaricodeEvent] = []
        for bit, confidence, source_interval, interval_complete in zip(
            bits, confidences, source_intervals, source_complete
        ):
            if bit not in (0, 1):
                raise ValueError("Varicode bits must contain only 0 or 1")
            if source_interval is not None and (
                len(source_interval) != 2
                or int(source_interval[0]) >= int(source_interval[1])
            ):
                raise ValueError("invalid Varicode source interval")
            index = self._consumed
            self._consumed += 1
            self._pending += str(bit)
            self._pending_confidence.append(float(confidence))
            self._pending_source_intervals.append(
                None
                if source_interval is None
                else (int(source_interval[0]), int(source_interval[1]))
            )
            self._pending_source_complete.append(bool(interval_complete))
            if len(self._pending) > 128:
                self._pending = self._pending[-2:]
                self._pending_confidence = self._pending_confidence[-2:]
                self._pending_source_intervals = (
                    self._pending_source_intervals[-2:]
                )
                self._pending_source_complete = self._pending_source_complete[-2:]
                self._pending_start = index - 1
            if self._pending.endswith("001"):
                codeword = self._pending[:-1]
                contributing = [
                    interval
                    for interval in self._pending_source_intervals[:-1]
                    if interval is not None
                ]
                events.append(
                    StatefulVaricodeEvent(
                        octet=self._lookup.get(codeword),
                        codeword=codeword,
                        start_bit=self._pending_start,
                        stop_bit=index,
                        recognized_at_bit=index + 1,
                        confidence=min(self._pending_confidence[:-1], default=0.0),
                        source_bit_interval=(self._pending_start, index),
                        source_input_interval=(
                            (
                                min(interval[0] for interval in contributing),
                                max(interval[1] for interval in contributing),
                            )
                            if contributing
                            else None
                        ),
                        source_input_complete=(
                            bool(contributing)
                            and all(self._pending_source_complete[:-1])
                        ),
                    )
                )
                self._pending = "1"
                self._pending_confidence = [self._pending_confidence[-1]]
                self._pending_source_intervals = [
                    self._pending_source_intervals[-1]
                ]
                self._pending_source_complete = [
                    self._pending_source_complete[-1]
                ]
                self._pending_start = index
        return tuple(events)

    def checkpoint(self) -> dict[str, Any]:
        return {
            "schema": "grampy.varicode-checkpoint.v2",
            "pending": self._pending,
            "pending_confidence": list(self._pending_confidence),
            "pending_source_intervals": [
                list(interval) if interval is not None else None
                for interval in self._pending_source_intervals
            ],
            "pending_source_complete": list(self._pending_source_complete),
            "pending_start": self._pending_start,
            "consumed_bits": self._consumed,
        }

    def restore(self, checkpoint: dict[str, Any]) -> None:
        schema = checkpoint.get("schema")
        if schema not in {
            "grampy.varicode-checkpoint.v1",
            "grampy.varicode-checkpoint.v2",
        }:
            raise ValueError("unsupported Varicode checkpoint")
        pending = checkpoint.get("pending")
        confidence = checkpoint.get("pending_confidence")
        if not isinstance(pending, str) or re.fullmatch("[01]*", pending) is None:
            raise ValueError("malformed Varicode pending bits")
        if not isinstance(confidence, list) or len(confidence) != len(pending):
            raise ValueError("malformed Varicode confidence state")
        self._pending = pending
        self._pending_confidence = [float(value) for value in confidence]
        source_intervals = checkpoint.get("pending_source_intervals")
        source_complete = checkpoint.get("pending_source_complete")
        if schema.endswith(".v1"):
            self._pending_source_intervals = [None] * len(pending)
            self._pending_source_complete = [False] * len(pending)
        else:
            if not isinstance(source_intervals, list) or len(
                source_intervals
            ) != len(pending):
                raise ValueError("malformed Varicode source intervals")
            self._pending_source_intervals = []
            for interval in source_intervals:
                if interval is None:
                    self._pending_source_intervals.append(None)
                elif (
                    isinstance(interval, list)
                    and len(interval) == 2
                    and int(interval[0]) < int(interval[1])
                ):
                    self._pending_source_intervals.append(
                        (int(interval[0]), int(interval[1]))
                    )
                else:
                    raise ValueError("malformed Varicode source intervals")
            if not isinstance(source_complete, list) or len(
                source_complete
            ) != len(pending):
                raise ValueError("malformed Varicode source completeness")
            self._pending_source_complete = [
                bool(value) for value in source_complete
            ]
        self._pending_start = int(checkpoint["pending_start"])
        self._consumed = int(checkpoint["consumed_bits"])


_PICTURE_HEADER = re.compile(
    rb"Pic:(?P<width>[0-9]{1,4})x(?P<height>[0-9]{1,4})"
    rb"(?P<color>C)?(?:p(?P<speed>[0-9]+))?;"
)


class PictureHeaderScanner:
    """Rolling confidence-aware exact header scanner."""

    def __init__(self, *, minimum_confidence: float = 0.25) -> None:
        self._events: list[dict[str, Any]] = []
        self._seen_headers: set[tuple[str, ...]] = set()
        self.minimum_confidence = minimum_confidence

    def push(self, events: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
        self._events.extend(events)
        self._events = self._events[-96:]
        data = bytes(
            event["octet"] if event.get("octet") is not None else 0
            for event in self._events
        )
        accepted: list[dict[str, Any]] = []
        rejected = 0
        for match in _PICTURE_HEADER.finditer(data):
            width = int(match.group("width"))
            height = int(match.group("height"))
            speed = int(match.group("speed") or 8)
            source = self._events[match.start():match.end()]
            signature = tuple(str(item["id"]) for item in source)
            if signature in self._seen_headers:
                continue
            self._seen_headers.add(signature)
            confidence = min(
                (float(item.get("confidence", {}).get("value", 0.0)) for item in source),
                default=0.0,
            )
            damaged = any(item.get("damage_flags") for item in source)
            if (
                not 1 <= width <= 4095
                or not 1 <= height <= 4095
                or speed not in {2, 4, 8}
                or damaged
            ):
                rejected += 1
                continue
            accepted.append(
                {
                    "header_text": match.group().decode("ascii"),
                    "width": width,
                    "height": height,
                    "color": match.group("color") is not None,
                    "samples_per_component": speed,
                    "confidence": {
                        "kind": "minimum_contributing_octet_confidence",
                        "value": confidence,
                        "calibrated": False,
                        "support": (
                            "strong"
                            if confidence >= self.minimum_confidence
                            else "weak_exact_grammar"
                        ),
                        "acceptance_basis": (
                            "exact_grammar_and_no_damaged_octets"
                        ),
                    },
                    "header_event_ids": [item["id"] for item in source],
                    "source_input_interval": _event_source_span(source),
                }
            )
        return accepted, rejected

    def checkpoint(self) -> dict[str, Any]:
        return {
            "schema": "grampy.picture-header-checkpoint.v1",
            "minimum_confidence": self.minimum_confidence,
            "events": copy.deepcopy(self._events),
            "seen_headers": [list(signature) for signature in self._seen_headers],
        }

    @classmethod
    def restore(cls, checkpoint: dict[str, Any]) -> PictureHeaderScanner:
        if (
            checkpoint.get("schema")
            != "grampy.picture-header-checkpoint.v1"
        ):
            raise ValueError("unsupported picture-header checkpoint")
        events = checkpoint.get("events")
        seen = checkpoint.get("seen_headers")
        if not isinstance(events, list) or len(events) > 96:
            raise ValueError("malformed picture-header event history")
        if not isinstance(seen, list) or any(
            not isinstance(signature, list) for signature in seen
        ):
            raise ValueError("malformed picture-header signature history")
        instance = cls(
            minimum_confidence=float(checkpoint["minimum_confidence"])
        )
        instance._events = copy.deepcopy(events)
        instance._seen_headers = {
            tuple(str(item) for item in signature) for signature in seen
        }
        return instance


def _event_source_span(
    events: Sequence[dict[str, Any]],
) -> dict[str, int] | None:
    intervals: list[tuple[int, int]] = []
    for event in events:
        value = event.get("source_input_interval", event.get("wire_interval"))
        if isinstance(value, dict):
            start, stop = value.get("start"), value.get("stop")
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            start, stop = value
        else:
            continue
        if start is not None and stop is not None and int(start) < int(stop):
            intervals.append((int(start), int(stop)))
    if not intervals:
        return None
    return {
        "start": min(interval[0] for interval in intervals),
        "stop": max(interval[1] for interval in intervals),
    }


def plan_text_epochs(
    erased: Sequence[bool],
    intervals: Sequence[tuple[int, int]],
    *,
    mode: str,
    source: str,
    sustained_loss_symbols: int = 12,
) -> list[dict[str, Any]]:
    """Plan deterministic reference epochs separated by sustained evidence loss."""
    if len(erased) != len(intervals):
        raise ValueError("erasure flags and symbol intervals must have equal length")
    if not intervals:
        return []
    cuts = [0]
    run_start: int | None = None
    losses: list[tuple[int, int]] = []
    for index, flag in enumerate(erased):
        if flag and run_start is None:
            run_start = index
        if not flag and run_start is not None:
            if index - run_start >= sustained_loss_symbols:
                losses.append((run_start, index))
                cuts.extend((run_start, index))
            run_start = None
    if run_start is not None and len(erased) - run_start >= sustained_loss_symbols:
        losses.append((run_start, len(erased)))
        cuts.append(run_start)
    cuts.append(len(erased))
    cuts = sorted(set(cuts))
    epochs: list[dict[str, Any]] = []
    for start, stop in zip(cuts, cuts[1:]):
        if start == stop or all(erased[start:stop]):
            continue
        epoch_id = f"text-epoch-{len(epochs) + 1:04d}"
        reset = "user_interval_start" if not epochs else "sustained_signal_loss"
        epochs.append(
            {
                "id": epoch_id,
                "mode": mode,
                "interval": {
                    "start": intervals[start][0],
                    "stop": intervals[stop - 1][1],
                },
                "coordinator_states": ["searching", "text_acquisition", "locked_text"],
                "start_evidence": source,
                "state_assumptions": {
                    "deinterleaver": "neutral_fill",
                    "fec_initial_state": "unknown" if epochs else "known_zero_or_unknown_ranked",
                    "varicode": "empty_pending_word",
                },
                "fill_warmup_interval": {
                    "start": intervals[start][0],
                    "stop": intervals[min(stop - 1, start + 30)][1],
                },
                "committed_interval": {
                    "start": intervals[min(stop - 1, start + 30)][1],
                    "stop": intervals[stop - 1][1],
                },
                "uncommitted_tail": {
                    "start": intervals[max(start, stop - 35)][0],
                    "stop": intervals[stop - 1][1],
                },
                "retained_state": ["frequency_track", "clock_track", "tone_evidence"],
                "discarded_state": ["deinterleaver", "fec_survivors", "varicode"],
                "start_reset_cause": reset,
                "end_reset_cause": (
                    "sustained_signal_loss"
                    if any(loss_start == stop for loss_start, _ in losses)
                    else "requested_interval_stop"
                ),
                "hypotheses": {
                    "group_phase_count": 4,
                    "fec_startup_count": 2,
                    "bounded_total": 8,
                    "status": "ranked_reference_search",
                },
            }
        )
    return epochs
