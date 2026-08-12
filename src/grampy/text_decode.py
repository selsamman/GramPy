from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Callable

import numpy as np

from .tracking import ClockAnchor, ClockTrack, FrequencyAnchor, FrequencyTrack
from .stateful_text import plan_text_epochs
from .wire import (
    SoftDeinterleaver,
    parse_varicode,
    picture_flush_tones,
    soft_viterbi_decode,
    tone_metrics_to_llrs,
)

MAX_SERIALIZED_TRACE_SYMBOLS = 4096


@dataclass(frozen=True)
class MFSKTextDecode:
    mode_segment: dict[str, Any]
    text_events: list[dict[str, Any]]
    text_summary: dict[str, Any]
    diagnostics: dict[str, Any]
    text_epochs: list[dict[str, Any]]
    decoded_bits: tuple[int, ...] = ()
    transition_clock: ClockTrack | None = None
    transition_clock_covariance: tuple[
        tuple[float, float], tuple[float, float]
    ] | None = None


def detect_mfsk_comb_hypotheses(
    samples: np.ndarray,
    *,
    input_start: int,
    sample_rate: float,
) -> list[dict[str, Any]]:
    """Return bounded, undecided text-comb hypotheses without RSID evidence.

    This is deliberately an evidence producer, not a segment coordinator.
    Orientation is retained as an unresolved pair because a spectral comb
    alone cannot distinguish the logical direction.
    """
    if len(samples) < int(round(sample_rate * 2.0)):
        return []
    magnitude = np.abs(samples)
    peak = float(np.max(magnitude, initial=0.0))
    if peak <= 0.0:
        return []
    active = np.flatnonzero(magnitude >= peak * 0.04)
    if len(active) < int(round(sample_rate)):
        return []
    active_start = int(active[0])
    active_stop = int(active[-1]) + 1
    hypotheses: list[dict[str, Any]] = []
    for mode, symbol_rate in (("MFSK32", 31.25), ("MFSK64", 62.5)):
        nominal = sample_rate / symbol_rate
        samples_per_symbol = int(round(nominal))
        if not math.isclose(nominal, samples_per_symbol, abs_tol=0.05):
            continue
        try:
            centers = _estimate_centers(
                samples[active_start:active_stop], sample_rate, symbol_rate
            )
        except ValueError:
            continue
        best: dict[str, Any] | None = None
        for center_hz in centers:
            phase, phase_score = _acquire_symbol_phase(
                samples,
                active_start,
                active_stop,
                sample_rate,
                center_hz,
                samples_per_symbol,
                symbol_rate,
            )
            first = phase
            if active_start > first:
                first += math.ceil(
                    (active_start - first) / samples_per_symbol
                ) * samples_per_symbol
            energies = _observe_tones(
                samples,
                first,
                active_stop,
                sample_rate,
                center_hz,
                samples_per_symbol,
                symbol_rate,
            )
            if len(energies) < 32:
                continue
            metrics = _log_tone_metrics(energies)
            winners = np.argmax(metrics, axis=1)
            ordered = np.sort(metrics, axis=1)
            margins = ordered[:, -1] - ordered[:, -2]
            transition_fraction = float(
                np.count_nonzero(np.diff(winners)) / max(1, len(winners) - 1)
            )
            nonadjacent_transition_fraction = float(
                np.count_nonzero(np.abs(np.diff(winners)) > 1)
                / max(1, len(winners) - 1)
            )
            unique_tones = int(len(np.unique(winners)))
            quarter_indices = np.array_split(np.arange(len(metrics)), 4)
            persistent_quarters = sum(
                len(indices) >= 4
                and float(np.median(margins[indices])) >= math.log(1.25)
                and len(np.unique(winners[indices])) >= 3
                for indices in quarter_indices
            )
            score = float(
                np.median(margins)
                + math.log1p(unique_tones)
                + 2.0 * phase_score
                + 0.25 * persistent_quarters
            )
            candidate = {
                "center_hz": float(center_hz),
                "center_uncertainty_hz": symbol_rate / 2.0,
                "phase_score": float(phase_score),
                "score": score,
                "unique_tones": unique_tones,
                "transition_fraction": transition_fraction,
                "nonadjacent_transition_fraction": (
                    nonadjacent_transition_fraction
                ),
                "persistent_quarters": persistent_quarters,
                "symbol_count": int(len(metrics)),
                "interval": {
                    "start": input_start + first,
                    "stop": input_start + active_stop,
                },
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
        if best is None:
            continue
        # Reject single/slow carriers, flat noise, and short accidental grids.
        if (
            best["unique_tones"] < 4
            or not 0.08 <= best["transition_fraction"] <= 0.98
            or best["nonadjacent_transition_fraction"] < 0.12
            or best["persistent_quarters"] < 3
            or best["phase_score"] < 0.12
        ):
            continue
        for orientation in ("normal", "reverse"):
            hypotheses.append(
                {
                    "mode": mode,
                    "orientation": orientation,
                    "center_hz": best["center_hz"],
                    "center_uncertainty_hz": best[
                        "center_uncertainty_hz"
                    ],
                    "interval": best["interval"],
                    "persistence_symbols": best["symbol_count"],
                    "score": best["score"],
                    "score_kind": "uncalibrated_mfsk_comb_persistence",
                    "evidence": {
                        "phase_score": best["phase_score"],
                        "unique_tones": best["unique_tones"],
                        "transition_fraction": best[
                            "transition_fraction"
                        ],
                        "nonadjacent_transition_fraction": best[
                            "nonadjacent_transition_fraction"
                        ],
                        "persistent_quarters": best[
                            "persistent_quarters"
                        ],
                    },
                    "source": "bounded-mfsk-comb",
                    "status": "competing",
                }
            )
    hypotheses.sort(key=lambda item: item["score"], reverse=True)
    for rank, hypothesis in enumerate(hypotheses, 1):
        hypothesis["rank"] = rank
    return hypotheses


def decode_mfsk_text(
    samples: np.ndarray,
    *,
    input_start: int,
    sample_rate: float,
    orientation_hint: str,
    trace_level: str,
    mode: str,
    center_hint_hz: float | None = None,
    persistent_tone_policy: str = "measure",
    fit_transition_clock: bool = False,
) -> MFSKTextDecode:
    if mode not in {"MFSK32", "MFSK64"}:
        raise ValueError(f"unsupported MFSK text mode: {mode}")
    if persistent_tone_policy not in {"measure", "suppress"}:
        raise ValueError("unsupported persistent tone policy")
    symbol_rate = 31.25 if mode == "MFSK32" else 62.5
    tone_spacing_hz = symbol_rate
    if not math.isclose(sample_rate / symbol_rate, round(sample_rate / symbol_rate), abs_tol=1e-9):
        raise ValueError(f"{mode} reference decoder requires an integer samples/symbol")
    samples_per_symbol = int(round(sample_rate / symbol_rate))
    peak = 0.0
    scan_block = 262_144
    for start in range(0, len(samples), scan_block):
        peak = max(
            peak,
            float(np.max(np.abs(samples[start : start + scan_block]), initial=0.0)),
        )
    if peak <= 0:
        raise ValueError(f"no {mode} signal energy found")
    active_start: int | None = None
    active_stop: int | None = None
    threshold = peak * 0.04
    for start in range(0, len(samples), scan_block):
        block = samples[start : start + scan_block]
        active = np.flatnonzero(np.abs(block) >= threshold)
        if len(active):
            if active_start is None:
                active_start = start + int(active[0])
            active_stop = start + int(active[-1]) + 1
    if active_start is None or active_stop is None:
        raise ValueError(f"no {mode} active interval found")

    candidates = (
        (orientation_hint,)
        if orientation_hint in {"normal", "reverse"}
        else ("normal", "reverse")
    )
    center_candidates = (
        [float(center_hint_hz)]
        if center_hint_hz is not None
        else _estimate_centers(
            samples[active_start:active_stop], sample_rate, tone_spacing_hz
        )
    )
    decoded_candidates = []
    acquisition_candidates = []
    for center_candidate in center_candidates:
        phase, phase_score = _acquire_symbol_phase(
            samples,
            active_start,
            active_stop,
            sample_rate,
            center_candidate,
            samples_per_symbol,
            tone_spacing_hz,
        )
        first_symbol = phase
        if active_start > first_symbol:
            first_symbol += (
                (active_start - first_symbol) // samples_per_symbol
            ) * samples_per_symbol
            if first_symbol + samples_per_symbol <= active_start:
                first_symbol += samples_per_symbol
        coarse_energies = _observe_tones(
            samples,
            first_symbol,
            active_stop,
            sample_rate,
            center_candidate,
            samples_per_symbol,
            tone_spacing_hz,
        )
        coarse_log_metrics = _log_tone_metrics(coarse_energies)
        acquisition_document = {
            "mode": mode,
            "center_hz": center_candidate,
            "center_uncertainty_hz": tone_spacing_hz / 2,
            "symbol_phase_input_sample": input_start + first_symbol,
            "symbol_phase_uncertainty_samples": max(
                1, samples_per_symbol // 16
            ),
            "phase_search_score": phase_score,
            "interval": {
                "start": input_start + active_start,
                "stop": input_start + active_stop,
            },
            "persistence_symbols": max(
                0, (active_stop - first_symbol) // samples_per_symbol
            ),
            "orientation_hypotheses": [],
            "source": "mfsk-comb-and-symbol-concentration",
        }
        acquisition_candidates.append(acquisition_document)
        for orientation in candidates:
            candidate = _decode_orientation(
                coarse_log_metrics,
                orientation,
                first_symbol,
                input_start,
                samples_per_symbol,
                retain_trace=trace_level in {"events", "full"},
                persistent_tone_policy=persistent_tone_policy,
            )
            candidate.update(
                center_hz=center_candidate,
                first_symbol=first_symbol,
                phase_score=phase_score,
                tone_metrics=coarse_log_metrics,
            )
            decoded_candidates.append(candidate)
            acquisition_document["orientation_hypotheses"].append(
                {
                    "orientation": orientation,
                    "score": candidate["score"],
                    "status": "competing",
                }
            )
    selected = max(decoded_candidates, key=lambda candidate: candidate["score"])
    for item in acquisition_candidates:
        for hypothesis in item["orientation_hypotheses"]:
            if (
                item["center_hz"] == selected["center_hz"]
                and hypothesis["orientation"] == selected["orientation"]
            ):
                hypothesis["status"] = "selected"
    center_hz = selected["center_hz"]
    first_symbol = selected["first_symbol"]
    phase_score = selected["phase_score"]
    orientation = selected["orientation"]
    input_first = input_start + first_symbol
    input_stop = input_start + min(active_stop, len(samples))
    tracking = _measure_received_tracks(
        samples,
        input_start=input_start,
        sample_rate=sample_rate,
        center_hz=center_hz,
        samples_per_symbol=samples_per_symbol,
        tone_spacing_hz=tone_spacing_hz,
    )
    frequency_track = _frequency_track_from_measurements(
        tracking, input_start=input_start, fallback_center_hz=center_hz
    )
    clock_track = _clock_track_from_measurements(
        tracking,
        input_start=input_start,
        first_symbol=first_symbol,
        samples_per_symbol=samples_per_symbol,
    )
    tracked = _observe_tracked_tones(
        samples,
        input_start=input_start,
        input_stop=input_start + active_stop,
        sample_rate=sample_rate,
        frequency_track=frequency_track,
        clock_track=clock_track,
        tone_spacing_hz=tone_spacing_hz,
    )
    tracked_candidates = []
    for candidate_orientation in candidates:
        candidate = _decode_orientation(
            tracked["log_metrics"],
            candidate_orientation,
            first_symbol,
            input_start,
            samples_per_symbol,
            intervals=tracked["intervals"],
            erased=tracked["erased"],
            retain_trace=trace_level in {"events", "full"},
            persistent_tone_policy=persistent_tone_policy,
        )
        candidate["center_hz"] = center_hz
        candidate["first_symbol"] = first_symbol
        tracked_candidates.append(candidate)
    tracked_selected = max(
        tracked_candidates, key=lambda candidate: candidate["score"]
    )
    # Tracking refines C7 evidence and may resolve orientation, while the
    # acquisition winner remains available for diagnostics.
    if tracked_selected["score"] >= selected["score"] - 1e-9:
        selected = tracked_selected
        orientation = selected["orientation"]
    events = selected["events"]
    picture_header_events = _annotate_picture_flush_tones(
        events, selected["decoded_bits_internal"], mode
    )
    transition_clock = None
    transition_clock_covariance = None
    transition_clock_evidence: dict[str, Any] = {
        "status": "not_requested",
        "operative": False,
    }
    if fit_transition_clock and picture_header_events:
        recognized_symbols = [
            event.get("provenance", {}).get("recognized_symbol")
            for event in picture_header_events
        ]
        recognized_symbols = [
            int(value) for value in recognized_symbols if value is not None
        ]
        if recognized_symbols:
            training_stop = min(min(recognized_symbols), len(tracked["log_metrics"]))
            timing_candidate = next(
                (
                    candidate
                    for candidate in tracked_candidates
                    if candidate["orientation"] == orientation
                ),
                tracked_selected,
            )
            unusable = np.asarray(tracked["erased"][:training_stop]).copy()
            persistence = np.asarray(
                timing_candidate["persistence"]["persistent_competitor"][
                    :training_stop
                ]
            )
            unusable |= persistence
            (
                transition_clock,
                transition_clock_evidence,
                transition_clock_covariance,
            ) = _fit_transition_crossover_clock(
                samples,
                input_start=input_start,
                sample_rate=sample_rate,
                frequency_track=frequency_track,
                provisional_clock=clock_track,
                tone_spacing_hz=tone_spacing_hz,
                log_metrics=tracked["log_metrics"][:training_stop],
                intervals=tracked["intervals"][:training_stop],
                erased=unusable,
            )
            transition_clock_evidence["training_symbol_interval"] = {
                "start": 0,
                "stop": training_stop,
            }
            transition_clock_evidence["training_scope"] = (
                "reliable_symbols_before_first_picture_header"
            )
            transition_clock_evidence["persistent_interference_rejected_count"] = (
                int(np.count_nonzero(persistence))
            )
        else:
            transition_clock_evidence = {
                "status": "picture_header_symbol_index_unavailable",
                "operative": False,
            }
        for event in picture_header_events:
            event.setdefault("provenance", {})[
                "transition_crossover_clock"
            ] = transition_clock_evidence
    stx_index = next(
        (i for i, event in enumerate(events) if event.get("control_role") == "STX"),
        None,
    )
    eot_index = next(
        (
            i
            for i, event in enumerate(events)
            if event.get("control_role") == "EOT"
            and (stx_index is None or i > stx_index)
        ),
        None,
    )
    payload_events = (
        events[stx_index + 1:eot_index]
        if stx_index is not None and eot_index is not None
        else [event for event in events if event["octet"] is not None]
    )
    payload_octets = [
        event["octet"]
        for event in payload_events
        if event["octet"] is not None and event.get("control_role") is None
    ]
    text = bytes(payload_octets).decode("latin-1")
    log_metrics = tracked["log_metrics"]
    probabilities = np.exp(log_metrics)
    concentration = np.max(probabilities, axis=1)

    trace: dict[str, Any] = {
        "tone_evidence": {
            "symbol_count": int(len(log_metrics)),
            "tone_count": 16,
            "metric": "normalized_log_matched_correlator_energy",
            "metric_units": "natural_log_probability",
            "normalization": "per-symbol logsumexp equals zero",
            "center_hz": center_hz,
            "tone_spacing_hz": tone_spacing_hz,
            "symbol_samples": samples_per_symbol,
            "symbol_phase_input_sample": input_first,
            "phase_search_score": phase_score,
            "acquisition_candidates": acquisition_candidates,
            "frequency_track": {
                **frequency_track.to_dict(),
                **tracking["frequency_track"],
                "operative": True,
            },
            "clock_track": {
                **clock_track.to_dict(),
                **tracking["clock_track"],
                "operative": True,
            },
            "transition_crossover_clock": transition_clock_evidence,
            "quality": {
                "concentration_kind": "winning-tone-normalized-energy",
                "median": float(np.median(concentration)),
                "p10": float(np.quantile(concentration, 0.10)),
                "weak_symbol_count": int(np.count_nonzero(tracked["erased"])),
                "erasure_count": int(np.count_nonzero(tracked["erased"])),
                "erasure_policy": tracked["erasure_policy"],
                "threshold_calibrated": False,
            },
            "persistent_tone_measurement": {
                "feature": "nonwinning_tone_occupied_12_of_trailing_16_within_3db",
                "window_symbols": selected["persistence"]["window_symbols"],
                "minimum_occupied_symbols": selected["persistence"]["minimum_occupied_symbols"],
                "occupied_within_winner_nats": selected["persistence"]["occupied_within_winner_nats"],
                "exposed_symbol_count": int(
                    np.count_nonzero(selected["persistence"]["persistent_competitor"])
                ),
                "maximum_occupancy_fraction": float(
                    np.max(
                        selected["persistence"]["maximum_occupancy_fraction"],
                        initial=0.0,
                    )
                ),
                "maximum_consecutive_run_symbols": int(
                    np.max(
                        selected["persistence"]["maximum_run_length"],
                        initial=0,
                    )
                ),
                "policy": persistent_tone_policy,
                "decision_effect": (
                    "measurement_only"
                    if persistent_tone_policy == "measure"
                    else "flagged_competitor_replaced_with_row_median"
                ),
            },
        },
        "bit_evidence": {
            "coded_llr_count": int(selected["coded_llr_count"]),
            "llr_definition": "log(P(bit=1)/P(bit=0)) via tone log-sum-exp",
            "lane_order": ["c0", "c1", "c0", "c1"],
            "erasure_count": int(np.count_nonzero(tracked["erased"])),
            "erasure_semantics": "all four coded-bit LLRs set to zero",
        },
        "fec_evidence": {
            "decoder": "64-state soft-input Viterbi",
            "generator_masks": ["0x6d", "0x4f"],
            "initial_state": selected["fec_startup"],
            "startup_hypotheses": selected["fec_startup_hypotheses"],
            "decoded_bit_count": int(selected["decoded_bit_count"]),
            "final_path_metric_gap": selected["path_metric_gap"],
            "confidence_calibrated": False,
        },
        "varicode_evidence": {
            "boundary_rule": "001-lookahead",
            "event_count": len(events),
            "invalid_count": sum(event["octet"] is None for event in events),
        },
    }
    if trace_level in {"events", "full"}:
        retained_symbols = min(
            len(selected["tone_rows"]), MAX_SERIALIZED_TRACE_SYMBOLS
        )
        trace["tone_evidence"]["symbols"] = selected["tone_rows"][
            :retained_symbols
        ]
        trace["bit_evidence"]["deinterleaved_groups"] = selected[
            "deinterleaved_groups"
        ][:retained_symbols]
        trace["fec_evidence"]["decoded_bits"] = selected["decoded_bits"][
            : retained_symbols * 2
        ]
        trace["trace_budget"] = {
            "maximum_serialized_symbol_rows": MAX_SERIALIZED_TRACE_SYMBOLS,
            "available_symbol_rows": len(selected["tone_rows"]),
            "serialized_symbol_rows": retained_symbols,
            "truncated": retained_symbols < len(selected["tone_rows"]),
        }

    text_epochs = plan_text_epochs(
        tracked["erased"],
        tracked["intervals"],
        mode=mode,
        source=(
            "rsid_and_text_evidence"
            if center_hint_hz is not None
            else "bounded_text_evidence_without_required_rsid"
        ),
    )
    for event in events:
        containing = next(
            (
                epoch
                for epoch in text_epochs
                if epoch["interval"]["start"] <= event["wire_interval"]["start"]
                and event["wire_interval"]["stop"] <= epoch["interval"]["stop"]
            ),
            None,
        )
        event["provenance"]["text_epoch"] = (
            containing["id"] if containing is not None else None
        )

    return MFSKTextDecode(
        mode_segment={
            "id": "mode-0001",
            "mode": mode,
            "orientation": orientation,
            "interval": {"start": input_first, "stop": input_stop},
            "source": "signal_inference",
            "confidence": {
                "kind": "uncalibrated_score",
                "value": selected["score"],
            },
            "acquisition_state": "locked",
            "symbol_phase_uncertainty_input_samples": 48,
            "center_hz": center_hz,
        },
        text_events=events,
        text_summary={
            "octets": payload_octets,
            "text": text,
            "framing": {
                "stx_found": stx_index is not None,
                "eot_found": eot_index is not None,
            },
        },
        diagnostics=trace,
        text_epochs=text_epochs,
        decoded_bits=selected["decoded_bits_internal"],
        transition_clock=transition_clock,
        transition_clock_covariance=transition_clock_covariance,
    )


def _annotate_picture_flush_tones(
    events: list[dict[str, Any]], decoded_bits: tuple[int, ...], mode: str
) -> list[dict[str, Any]]:
    stream = bytearray()
    event_indices: list[int] = []
    for index, event in enumerate(events):
        if event["octet"] is not None:
            stream.append(event["octet"])
            event_indices.append(index)
    header = re.compile(
        rb"Pic:[1-9][0-9]{0,3}x[1-9][0-9]{0,3}C?(?:p(?:2|4|8))?;"
    )
    header_events: list[dict[str, Any]] = []
    for match in header.finditer(bytes(stream)):
        final_event = events[event_indices[match.end() - 1]]
        header_events.append(final_event)
        decoded_bit_stop = (
            final_event.get("provenance", {})
            .get("decoded_bit_interval", {})
            .get("stop")
        )
        if decoded_bit_stop is None or decoded_bit_stop > len(decoded_bits):
            continue
        final_event.setdefault("provenance", {})[
            "picture_flush_tones"
        ] = picture_flush_tones(
            decoded_bits[: int(decoded_bit_stop)], mode
        )
    return header_events


def _estimate_center(
    samples: np.ndarray, sample_rate: float, tone_spacing_hz: float
) -> float:
    block = 16384
    count = min(96, len(samples) // block)
    if count < 4:
        raise ValueError("insufficient MFSK samples for carrier acquisition")
    start = max(0, (len(samples) - count * block) // 2)
    chunks = np.asarray(samples[start:start + count * block]).reshape(count, block)
    window = np.hanning(block)
    spectrum = np.mean(np.abs(np.fft.fft(chunks * window, axis=1)) ** 2, axis=0)
    frequencies = np.fft.fftfreq(block, 1.0 / sample_rate)
    positive = (frequencies >= 0) & (frequencies <= sample_rate / 2)
    positive_frequencies = frequencies[positive]
    log_power = np.log(spectrum[positive] + np.finfo(np.float64).tiny)
    half_span = 7.5 * tone_spacing_hz
    candidates = np.arange(
        max(200.0 + half_span, half_span),
        min(4000.0 - half_span, sample_rate / 2 - half_span) + 0.5,
        0.5,
    )
    tone_offsets = (np.arange(16) - 7.5) * tone_spacing_hz
    gap_offsets = (np.arange(15) - 7.0) * tone_spacing_hz
    scores = np.empty(len(candidates), dtype=np.float64)
    for index, center in enumerate(candidates):
        tones = np.interp(
            center + tone_offsets, positive_frequencies, log_power
        )
        gaps = np.interp(
            center + gap_offsets, positive_frequencies, log_power
        )
        scores[index] = float(np.mean(tones) - np.mean(gaps))
    if not len(scores) or not np.isfinite(scores).any():
        raise ValueError("could not estimate MFSK tone grid")
    return float(candidates[int(np.nanargmax(scores))])


def _estimate_centers(
    samples: np.ndarray, sample_rate: float, tone_spacing_hz: float
) -> list[float]:
    estimates = [
        _estimate_center(samples, sample_rate, tone_spacing_hz),
        _estimate_occupied_band_center(samples, sample_rate),
    ]
    unique: list[float] = []
    for estimate in estimates:
        if all(abs(estimate - existing) >= 1.0 for existing in unique):
            unique.append(estimate)
    return unique


def _estimate_occupied_band_center(
    samples: np.ndarray, sample_rate: float
) -> float:
    block = 4096
    count = min(160, len(samples) // block)
    if count < 4:
        raise ValueError("insufficient MFSK samples for carrier acquisition")
    start = max(0, (len(samples) - count * block) // 2)
    chunks = np.asarray(samples[start:start + count * block]).reshape(count, block)
    window = np.hanning(block)
    spectrum = np.mean(np.abs(np.fft.fft(chunks * window, axis=1)) ** 2, axis=0)
    frequencies = np.fft.fftfreq(block, 1.0 / sample_rate)
    positive = (frequencies >= 200) & (
        frequencies <= min(4000, sample_rate / 2)
    )
    candidate_frequencies = frequencies[positive]
    candidate_power = spectrum[positive]
    threshold = float(np.max(candidate_power)) * 0.015
    occupied = candidate_frequencies[candidate_power >= threshold]
    if len(occupied) < 2:
        raise ValueError("could not estimate MFSK occupied band")
    low = float(np.quantile(occupied, 0.02))
    high = float(np.quantile(occupied, 0.98))
    raw_center = (low + high) / 2
    nearest = round(raw_center)
    return float(nearest if abs(raw_center - nearest) < 3.0 else raw_center)


def _measure_received_tracks(
    samples: np.ndarray,
    *,
    input_start: int,
    sample_rate: float,
    center_hz: float,
    samples_per_symbol: int,
    tone_spacing_hz: float,
) -> dict[str, Any]:
    return _measure_received_tracks_from_reader(
        lambda start, stop: samples[start:stop],
        sample_count=len(samples),
        input_start=input_start,
        sample_rate=sample_rate,
        center_hz=center_hz,
        samples_per_symbol=samples_per_symbol,
        tone_spacing_hz=tone_spacing_hz,
    )


def plan_track_measurement_windows(
    *, sample_count: int, sample_rate: float, samples_per_symbol: int
) -> tuple[tuple[int, int], ...]:
    """Plan the bounded random-access neighborhoods used by current tracking."""
    if sample_count < 0 or sample_rate <= 0 or samples_per_symbol <= 0:
        raise ValueError("invalid track-measurement extent")
    window = max(samples_per_symbol * 32, int(round(sample_rate * 8.0)))
    starts = list(range(0, sample_count, window))
    if len(starts) > 9:
        starts = [
            int(value)
            for value in np.linspace(0, max(0, sample_count - window), 9)
        ]
    return tuple((start, min(sample_count, start + window)) for start in starts)


def plan_received_tracks_from_reader(
    reader: Callable[[int, int], np.ndarray],
    *,
    input_start: int,
    input_stop: int,
    sample_rate: float,
    mode: str,
    center_hz: float,
    orientation: str = "normal",
    phase_hint_input_sample: float | None = None,
) -> tuple[FrequencyTrack, ClockTrack, dict[str, Any]]:
    """Build P11D's compact tracks with at most nine bounded source reads."""
    if mode not in {"MFSK32", "MFSK64"}:
        raise ValueError("compact track planning requires a fixed MFSK mode")
    if input_stop <= input_start:
        raise ValueError("compact track planning requires a non-empty interval")
    symbol_rate = 31.25 if mode == "MFSK32" else 62.5
    nominal = sample_rate / symbol_rate
    if not math.isclose(nominal, round(nominal), abs_tol=1e-9):
        raise ValueError("compact track planning requires integer symbol samples")
    samples_per_symbol = int(round(nominal))
    requested_reads: list[tuple[int, int]] = []
    phase_step = max(1, samples_per_symbol // 192)
    phase_candidates = np.arange(
        0, samples_per_symbol, phase_step, dtype=np.int64
    )
    phase_score_sum = np.zeros(len(phase_candidates), dtype=np.float64)
    phase_score_count = np.zeros(len(phase_candidates), dtype=np.int64)
    phase_targets: list[np.ndarray] = []
    phase_seen: list[set[int]] = []
    sample_count = input_stop - input_start
    for phase in phase_candidates:
        targets = np.arange(
            int(phase), sample_count - samples_per_symbol,
            samples_per_symbol, dtype=np.int64,
        )
        if len(targets) > 72:
            targets = targets[
                np.linspace(0, len(targets) - 1, 72).astype(np.int64)
            ]
        phase_targets.append(targets)
        phase_seen.append(set())

    def relative_reader(start: int, stop: int) -> np.ndarray:
        absolute = (input_start + start, input_start + stop)
        requested_reads.append(absolute)
        block = np.asarray(reader(*absolute))
        for candidate_index, targets in enumerate(phase_targets):
            eligible = targets[
                (targets >= start) & (targets + samples_per_symbol <= stop)
            ]
            indices = np.asarray(
                [
                    int(value - start) for value in eligible
                    if int(value) not in phase_seen[candidate_index]
                ],
                dtype=np.int64,
            )
            if not len(indices):
                continue
            phase_seen[candidate_index].update(
                int(start + value) for value in indices
            )
            metrics = _observe_selected(
                block, indices, sample_rate, center_hz,
                samples_per_symbol, symbol_rate,
            )
            concentration = np.max(metrics, axis=1) / np.maximum(
                np.sum(metrics, axis=1), 1e-30
            )
            phase_score_sum[candidate_index] += float(np.sum(concentration))
            phase_score_count[candidate_index] += len(concentration)
        return block

    tracking = _measure_received_tracks_from_reader(
        relative_reader,
        sample_count=input_stop - input_start,
        input_start=input_start,
        sample_rate=sample_rate,
        center_hz=center_hz,
        samples_per_symbol=samples_per_symbol,
        tone_spacing_hz=symbol_rate,
    )
    locked = [
        point for point in tracking["frequency_track"]["points"]
        if point["lock_state"] == "locked"
    ]
    phase_scores = phase_score_sum / np.maximum(phase_score_count, 1)
    coarse_step = max(1, samples_per_symbol // 16)
    coarse_indices = np.flatnonzero(phase_candidates % coarse_step == 0)
    coarse_best = int(
        coarse_indices[int(np.argmax(phase_scores[coarse_indices]))]
    )
    coarse_phase = int(phase_candidates[coarse_best])
    fine_indices = np.flatnonzero(
        (phase_candidates >= max(0, coarse_phase - coarse_step))
        & (phase_candidates <= min(
            samples_per_symbol - 1, coarse_phase + coarse_step
        ))
    )
    energy_best = int(fine_indices[int(np.argmax(phase_scores[fine_indices]))])
    first_symbol = (
        int(round(phase_hint_input_sample - input_start)) % samples_per_symbol
        if phase_hint_input_sample is not None
        else int(phase_candidates[energy_best])
    )
    phase_ranking = np.argsort(phase_scores)[::-1][:12]
    frequency_track = _frequency_track_from_measurements(
        tracking, input_start=input_start, fallback_center_hz=center_hz
    )
    clock_track = _clock_track_from_measurements(
        tracking,
        input_start=input_start,
        first_symbol=first_symbol,
        samples_per_symbol=samples_per_symbol,
    )
    return frequency_track, clock_track, {
        "organization": "compact_bounded_noncausal_track_plan",
        "requested_read_intervals": [
            {"start": start, "stop": stop} for start, stop in requested_reads
        ],
        "requested_samples": sum(stop - start for start, stop in requested_reads),
        "maximum_materialized_iq_samples": max(
            (stop - start for start, stop in requested_reads), default=0
        ),
        "measurement_window_count": len(requested_reads),
        "aggregate_phase_input_sample_modulo": first_symbol,
        "aggregate_phase_grid_step_samples": phase_step,
        "aggregate_phase_score": float(np.max(phase_scores, initial=0.0)),
        "aggregate_phase_alternatives": [
            {
                "phase_input_sample_modulo": int(phase_candidates[index]),
                "score": float(phase_scores[index]),
            }
            for index in phase_ranking
        ],
        "aggregate_phase_observation_count": int(
            phase_score_count[energy_best]
        ),
        "phase_selection": (
            "supplied_acquisition_hint"
            if phase_hint_input_sample is not None
            else "bounded_aggregate_coarse_fine_score"
        ),
        "frequency_track": frequency_track.to_dict(),
        "clock_track": clock_track.to_dict(),
    }


def _measure_received_tracks_from_reader(
    reader: Callable[[int, int], np.ndarray],
    *,
    sample_count: int,
    input_start: int,
    sample_rate: float,
    center_hz: float,
    samples_per_symbol: int,
    tone_spacing_hz: float,
) -> dict[str, Any]:
    windows = plan_track_measurement_windows(
        sample_count=sample_count,
        sample_rate=sample_rate,
        samples_per_symbol=samples_per_symbol,
    )
    points = []
    for start, stop in windows:
        if stop - start < samples_per_symbol * 8:
            continue
        block = np.asarray(reader(start, stop))
        if block.ndim != 1 or len(block) != stop - start:
            raise ValueError("track reader returned the wrong sample interval")
        center_scores = []
        for candidate_center in np.arange(
            center_hz - 6.0, center_hz + 6.01, 2.0
        ):
            phase, score = _acquire_symbol_phase(
                block,
                0,
                len(block),
                sample_rate,
                float(candidate_center),
                samples_per_symbol,
                tone_spacing_hz,
            )
            center_scores.append((score, float(candidate_center), phase))
        score, measured_center, local_phase = max(center_scores)
        absolute_phase = (start + local_phase) % samples_per_symbol
        points.append(
            {
                "input_interval": {
                    "start": input_start + start,
                    "stop": input_start + stop,
                },
                "center_hz": measured_center,
                "symbol_phase_input_sample_modulo": int(absolute_phase),
                "lock_score": float(score),
            }
        )
    lock_scores = [point["lock_score"] for point in points]
    lock_threshold = (
        0.5 * float(np.median(lock_scores)) if lock_scores else 0.0
    )
    for point in points:
        point["lock_state"] = (
            "locked" if point["lock_score"] >= lock_threshold else "searching"
        )
    lock_loss_count = sum(
        previous["lock_state"] == "locked"
        and current["lock_state"] == "searching"
        for previous, current in zip(points, points[1:])
    )
    reacquisition_count = sum(
        previous["lock_state"] == "searching"
        and current["lock_state"] == "locked"
        for previous, current in zip(points, points[1:])
    )
    locked_points = [
        point for point in points if point["lock_state"] == "locked"
    ]
    if len(locked_points) >= 2:
        times = np.asarray(
            [
                (point["input_interval"]["start"] - input_start) / sample_rate
                for point in locked_points
            ],
            dtype=np.float64,
        )
        centers = np.asarray(
            [point["center_hz"] for point in locked_points], dtype=np.float64
        )
        center_slope = float(np.polyfit(times, centers, 1)[0])
        reference_phase = locked_points[len(locked_points) // 2][
            "symbol_phase_input_sample_modulo"
        ]
        phase_residuals = np.asarray(
            [
                (
                    point["symbol_phase_input_sample_modulo"]
                    - reference_phase
                    + samples_per_symbol / 2
                )
                % samples_per_symbol
                - samples_per_symbol / 2
                for point in locked_points
            ],
            dtype=np.float64,
        )
        sample_positions = times * sample_rate
        clock_error_ppm = float(
            np.polyfit(sample_positions, phase_residuals, 1)[0] * 1e6
        )
    else:
        center_slope = 0.0
        clock_error_ppm = 0.0
    return {
        "frequency_track": {
            "kind": "windowed-tone-grid-search",
            "points": points,
            "drift_hz_per_second": center_slope,
            "search_half_width_hz": 6.0,
            "lock_loss_count": lock_loss_count,
            "reacquisition_count": reacquisition_count,
            "measurement_window_count": len(windows),
            "measurement_requested_samples": sum(
                stop - start for start, stop in windows
            ),
            "measurement_maximum_block_samples": max(
                (stop - start for start, stop in windows), default=0
            ),
        },
        "clock_track": {
            "kind": "windowed-tone-concentration",
            "nominal_symbol_samples": samples_per_symbol,
            "estimated_rate_error_ppm": clock_error_ppm,
            "phase_uncertainty_input_samples": 48,
            "lock_threshold": lock_threshold,
        },
    }


def _acquire_symbol_phase(
    samples: np.ndarray,
    active_start: int,
    active_stop: int,
    sample_rate: float,
    center_hz: float,
    samples_per_symbol: int,
    tone_spacing_hz: float,
) -> tuple[int, float]:
    coarse_step = max(1, samples_per_symbol // 16)
    phases = range(0, samples_per_symbol, coarse_step)
    best_phase, best_score = max(
        (
            (phase, _phase_score(
                samples, phase, active_start, active_stop, sample_rate,
                center_hz, samples_per_symbol, tone_spacing_hz
            ))
            for phase in phases
        ),
        key=lambda item: item[1],
    )
    fine_start = max(0, best_phase - coarse_step)
    fine_stop = min(samples_per_symbol, best_phase + coarse_step + 1)
    fine_step = max(1, coarse_step // 12)
    best_phase, best_score = max(
        (
            (phase, _phase_score(
                samples, phase, active_start, active_stop, sample_rate,
                center_hz, samples_per_symbol, tone_spacing_hz
            ))
            for phase in range(fine_start, fine_stop, fine_step)
        ),
        key=lambda item: item[1],
    )
    return best_phase, float(best_score)


def _phase_score(
    samples: np.ndarray,
    phase: int,
    active_start: int,
    active_stop: int,
    sample_rate: float,
    center_hz: float,
    samples_per_symbol: int,
    tone_spacing_hz: float,
) -> float:
    first = phase + max(0, (active_start - phase) // samples_per_symbol) * samples_per_symbol
    symbol_indices = np.arange(first, active_stop - samples_per_symbol, samples_per_symbol)
    if len(symbol_indices) > 72:
        symbol_indices = symbol_indices[np.linspace(0, len(symbol_indices)-1, 72).astype(int)]
    metrics = _observe_selected(
        samples, symbol_indices, sample_rate, center_hz, samples_per_symbol,
        tone_spacing_hz,
    )
    return float(np.mean(np.max(metrics, axis=1) / np.maximum(np.sum(metrics, axis=1), 1e-30)))


def _observe_tones(
    samples: np.ndarray,
    start: int,
    stop: int,
    sample_rate: float,
    center_hz: float,
    samples_per_symbol: int,
    tone_spacing_hz: float,
) -> np.ndarray:
    indices = np.arange(start, stop - samples_per_symbol + 1, samples_per_symbol)
    return _observe_selected(
        samples, indices, sample_rate, center_hz, samples_per_symbol,
        tone_spacing_hz,
    )


def _observe_selected(
    samples: np.ndarray,
    indices: np.ndarray,
    sample_rate: float,
    center_hz: float,
    samples_per_symbol: int,
    tone_spacing_hz: float,
) -> np.ndarray:
    frequencies = center_hz + (np.arange(16) - 7.5) * tone_spacing_hz
    time_axis = np.arange(samples_per_symbol) / sample_rate
    oscillators = np.exp(-2j * np.pi * frequencies[:, None] * time_axis)
    rows = np.asarray([samples[i:i + samples_per_symbol] for i in indices])
    correlations = rows @ oscillators.T
    return np.abs(correlations) ** 2


def _logsumexp_rows(values: np.ndarray) -> np.ndarray:
    maximum = np.max(values, axis=1, keepdims=True)
    return maximum + np.log(np.sum(np.exp(values - maximum), axis=1, keepdims=True))


def _log_tone_metrics(energies: np.ndarray) -> np.ndarray:
    """Convert correlator energies to comparable normalized log metrics."""
    raw = np.log(np.asarray(energies, dtype=np.float64) + 1e-30)
    return raw - _logsumexp_rows(raw)


def _frequency_track_from_measurements(
    tracking: dict[str, Any], *, input_start: int, fallback_center_hz: float
) -> FrequencyTrack:
    locked = [
        point
        for point in tracking["frequency_track"]["points"]
        if point["lock_state"] == "locked"
    ]
    anchors = tuple(
        FrequencyAnchor(
            input_sample=(
                point["input_interval"]["start"] + point["input_interval"]["stop"]
            ) // 2,
            center_hz=point["center_hz"],
            uncertainty_hz=2.0,
            source="windowed-tone-grid-search",
        )
        for point in locked
    )
    if not anchors:
        return FrequencyTrack.fixed(
            center_hz=fallback_center_hz,
            input_sample=input_start,
            uncertainty_hz=6.0,
            source="coarse-acquisition",
        )
    return FrequencyTrack(anchors)


def _clock_track_from_measurements(
    tracking: dict[str, Any],
    *,
    input_start: int,
    first_symbol: int,
    samples_per_symbol: int,
) -> ClockTrack:
    points = [
        point
        for point in tracking["frequency_track"]["points"]
        if point["lock_state"] == "locked"
    ]
    anchors = tuple(
        ClockAnchor(
            input_sample=point["input_interval"]["start"],
            symbol_index=(
                point["input_interval"]["start"] - input_start - first_symbol
            ) / samples_per_symbol,
            uncertainty_samples=48.0,
            source="windowed-tone-concentration",
        )
        for point in points
    )
    return ClockTrack(
        epoch_input_sample=float(input_start + first_symbol),
        samples_per_symbol=float(samples_per_symbol),
        rate_error_ppm=tracking["clock_track"]["estimated_rate_error_ppm"],
        uncertainty_samples=48.0,
        anchors=anchors,
    )


def _fit_transition_crossover_clock(
    samples: np.ndarray,
    *,
    input_start: int,
    sample_rate: float,
    frequency_track: FrequencyTrack,
    provisional_clock: ClockTrack,
    tone_spacing_hz: float,
    log_metrics: np.ndarray,
    intervals: list[tuple[int, int]],
    erased: np.ndarray,
) -> tuple[
    ClockTrack | None,
    dict[str, Any],
    tuple[tuple[float, float], tuple[float, float]] | None,
]:
    """Fit one affine symbol clock from antisymmetric tone crossovers.

    Only boundaries whose adjacent winning tones differ and whose two rows are
    usable carry timing information.  Each boundary contributes the zero of
    the old-tone minus new-tone energy discriminator, then a robust weighted
    line fit combines those fractional observations into one clock.
    """
    rows = np.asarray(log_metrics, dtype=np.float64)
    if len(rows) != len(intervals) or len(erased) != len(intervals):
        raise ValueError("crossover clock evidence lengths must agree")
    if len(rows) < 3:
        return None, {"status": "insufficient_transitions", "operative": False}, None
    winners = np.argmax(rows, axis=1)
    ordered = np.sort(rows, axis=1)
    margins = ordered[:, -1] - ordered[:, -2]
    eligible = [
        index
        for index in range(len(rows) - 1)
        if not erased[index]
        and not erased[index + 1]
        and winners[index] != winners[index + 1]
        and min(margins[index], margins[index + 1]) >= math.log(1.08)
    ]
    # Evenly span the available text instead of re-measuring every transition.
    # A 128-point affine fit is strongly overdetermined while keeping bounded
    # windows and multi-picture corpus runs practical.
    maximum_boundaries = 128
    if len(eligible) > maximum_boundaries:
        retained = np.linspace(
            0, len(eligible) - 1, maximum_boundaries, dtype=np.int64
        )
        eligible = [eligible[int(index)] for index in retained]

    symbol_indices: list[float] = []
    crossings: list[float] = []
    weights: list[float] = []
    observation_records: list[dict[str, Any]] = []
    rejected_no_crossing = 0
    nominal_symbol_samples = provisional_clock.samples_per_symbol
    window_samples = max(8, int(round(nominal_symbol_samples / 2.0)))
    radius_samples = max(4, int(math.ceil(nominal_symbol_samples / 2.0)))
    for index in eligible:
        nominal_boundary = 0.5 * (
            intervals[index][1] + intervals[index + 1][0]
        )
        center_hz = float(frequency_track.center_at(nominal_boundary))
        old_frequency = center_hz + (
            float(winners[index]) - 7.5
        ) * tone_spacing_hz
        new_frequency = center_hz + (
            float(winners[index + 1]) - 7.5
        ) * tone_spacing_hz
        crossing = _tone_crossover(
            samples,
            input_start=input_start,
            nominal_boundary=nominal_boundary,
            sample_rate=sample_rate,
            old_frequency_hz=old_frequency,
            new_frequency_hz=new_frequency,
            window_samples=window_samples,
            radius_samples=radius_samples,
        )
        if crossing is None:
            rejected_no_crossing += 1
            observation_records.append(
                {
                    "symbol_index": float(index + 1),
                    "nominal_boundary_input_sample": float(nominal_boundary),
                    "old_tone": int(winners[index]),
                    "new_tone": int(winners[index + 1]),
                    "margin_log_ratio": min(
                        float(margins[index]), float(margins[index + 1])
                    ),
                    "status": "rejected_no_crossover",
                    "retained": False,
                }
            )
            continue
        symbol_indices.append(float(index + 1))
        crossings.append(crossing)
        frequency_step = abs(new_frequency - old_frequency)
        base_weight = (
            frequency_step
            * frequency_step
            * min(float(margins[index]), float(margins[index + 1]))
        )
        weights.append(base_weight)
        observation_records.append(
            {
                "symbol_index": float(index + 1),
                "nominal_boundary_input_sample": float(nominal_boundary),
                "crossover_input_sample": float(crossing),
                "old_tone": int(winners[index]),
                "new_tone": int(winners[index + 1]),
                "frequency_step_hz": float(frequency_step),
                "margin_log_ratio": min(
                    float(margins[index]), float(margins[index + 1])
                ),
                "base_weight": float(base_weight),
                "status": "measured",
            }
        )

    minimum_crossings = 8
    if len(crossings) < minimum_crossings:
        return (
            None,
            {
                "status": "insufficient_crossovers",
                "eligible_transition_count": len(eligible),
                "crossover_count": len(crossings),
                "rejected_no_crossing": rejected_no_crossing,
                "observations": observation_records,
                "operative": False,
            },
            None,
        )
    x = np.asarray(symbol_indices, dtype=np.float64)
    y = np.asarray(crossings, dtype=np.float64)
    base_weights = np.asarray(weights, dtype=np.float64)
    design = np.column_stack((np.ones(len(x), dtype=np.float64), x))
    robust_weights = base_weights.copy()
    coefficients = np.zeros(2, dtype=np.float64)
    for _ in range(6):
        root = np.sqrt(np.maximum(robust_weights, np.finfo(np.float64).tiny))
        coefficients = np.linalg.lstsq(
            design * root[:, None], y * root, rcond=None
        )[0]
        residuals = y - design @ coefficients
        median = float(np.median(residuals))
        scale = max(
            0.25,
            1.4826 * float(np.median(np.abs(residuals - median))),
        )
        huber_limit = 2.5 * scale
        huber = np.minimum(
            1.0,
            huber_limit / np.maximum(np.abs(residuals - median), 1e-12),
        )
        robust_weights = base_weights * huber
    residuals = y - design @ coefficients
    keep = np.abs(residuals - np.median(residuals)) <= max(
        nominal_symbol_samples / 8.0, 4.0 * scale
    )
    retained_mask = np.asarray(keep, dtype=bool)
    retained_x = x
    if int(np.count_nonzero(keep)) >= minimum_crossings:
        retained_x = x[keep]
        design = design[keep]
        y = y[keep]
        robust_weights = robust_weights[keep]
        root = np.sqrt(np.maximum(robust_weights, np.finfo(np.float64).tiny))
        coefficients = np.linalg.lstsq(
            design * root[:, None], y * root, rcond=None
        )[0]
        residuals = y - design @ coefficients
    else:
        retained_mask = np.ones(len(x), dtype=bool)
    normal = design.T @ (robust_weights[:, None] * design)
    degrees = max(1, len(y) - 2)
    variance = float(
        np.sum(robust_weights * np.square(residuals))
        / max(np.sum(robust_weights), np.finfo(np.float64).tiny)
    )
    covariance_array = np.linalg.pinv(normal) * variance * (
        np.sum(robust_weights) / degrees
    )
    covariance = (
        (float(covariance_array[0, 0]), float(covariance_array[0, 1])),
        (float(covariance_array[1, 0]), float(covariance_array[1, 1])),
    )
    epoch, tracked_symbol_samples = map(float, coefficients)
    rate_error_ppm = (
        tracked_symbol_samples / nominal_symbol_samples - 1.0
    ) * 1e6
    uncertainty = max(0.25, float(np.sqrt(max(0.0, variance))))
    anchors = tuple(
        ClockAnchor(
            input_sample=int(round(sample)),
            symbol_index=float(symbol),
            uncertainty_samples=uncertainty,
            source="transition_weighted_crossover",
        )
        for symbol, sample in zip(retained_x, y)
    )
    clock = ClockTrack(
        epoch_input_sample=epoch,
        samples_per_symbol=nominal_symbol_samples,
        rate_error_ppm=rate_error_ppm,
        uncertainty_samples=uncertainty,
        anchors=anchors[:64],
    )
    evidence = {
        **clock.to_dict(),
        "status": "estimated",
        "source": "transition_weighted_crossover_zero_fit",
        "tone_sequence_source": "adjacent_high_margin_tracked_winners",
        "eligible_transition_count": len(eligible),
        "crossover_count": len(crossings),
        "retained_crossover_count": int(len(y)),
        "rejected_no_crossing": rejected_no_crossing,
        "residual_sigma_input_samples": uncertainty,
        "parameter_covariance": [list(row) for row in covariance],
        "observations": observation_records,
        "operative": False,
    }
    measured_records = [
        record for record in observation_records if record["status"] == "measured"
    ]
    final_scale = max(
        0.25,
        1.4826
        * float(
            np.median(
                np.abs(
                    (np.asarray(crossings) - (
                        coefficients[0]
                        + np.asarray(symbol_indices) * coefficients[1]
                    ))
                    - np.median(
                        np.asarray(crossings)
                        - (
                            coefficients[0]
                            + np.asarray(symbol_indices) * coefficients[1]
                        )
                    )
                )
            )
        ),
    )
    for index, record in enumerate(measured_records):
        predicted = float(
            coefficients[0] + record["symbol_index"] * coefficients[1]
        )
        residual = float(record["crossover_input_sample"] - predicted)
        robust_factor = min(
            1.0, 2.5 * final_scale / max(abs(residual), 1e-12)
        )
        retained = bool(retained_mask[index])
        record.update(
            {
                "predicted_input_sample": predicted,
                "residual_input_samples": residual,
                "robust_weight": float(record["base_weight"] * robust_factor),
                "status": "retained" if retained else "rejected_outlier",
                "retained": retained,
            }
        )
    return clock, evidence, covariance


def _tone_crossover(
    samples: np.ndarray,
    *,
    input_start: int,
    nominal_boundary: float,
    sample_rate: float,
    old_frequency_hz: float,
    new_frequency_hz: float,
    window_samples: int,
    radius_samples: int,
) -> float | None:
    half_left = window_samples // 2
    half_right = window_samples - half_left
    first_center = int(math.ceil(nominal_boundary - radius_samples))
    last_center = int(math.floor(nominal_boundary + radius_samples))
    local_first = first_center - half_left - input_start
    local_stop = last_center + half_right - input_start
    if local_first < 0 or local_stop > len(samples) or last_center <= first_center:
        return None
    block = np.asarray(samples[local_first:local_stop], dtype=np.complex128)
    time = np.arange(len(block), dtype=np.float64) / sample_rate
    old = block * np.exp(-2j * np.pi * old_frequency_hz * time)
    new = block * np.exp(-2j * np.pi * new_frequency_hz * time)
    old_prefix = np.concatenate(([0.0j], np.cumsum(old)))
    new_prefix = np.concatenate(([0.0j], np.cumsum(new)))
    starts = np.arange(0, last_center - first_center + 1, dtype=np.int64)
    stops = starts + window_samples
    old_sums = old_prefix[stops] - old_prefix[starts]
    new_sums = new_prefix[stops] - new_prefix[starts]
    discriminator = np.square(np.abs(old_sums)) - np.square(np.abs(new_sums))
    crossing_indices = np.flatnonzero(
        (discriminator[:-1] >= 0.0) & (discriminator[1:] <= 0.0)
    )
    if not len(crossing_indices):
        return None
    centers = np.arange(first_center, last_center + 1, dtype=np.float64)
    slopes = (
        discriminator[crossing_indices]
        - discriminator[crossing_indices + 1]
    )
    nearest = int(crossing_indices[int(np.argmax(slopes))])
    left = float(discriminator[nearest])
    right = float(discriminator[nearest + 1])
    fraction = left / max(left - right, np.finfo(np.float64).tiny)
    return float(centers[nearest] + np.clip(fraction, 0.0, 1.0))


def _observe_tracked_tones(
    samples: np.ndarray,
    *,
    input_start: int,
    input_stop: int,
    sample_rate: float,
    frequency_track: FrequencyTrack,
    clock_track: ClockTrack,
    tone_spacing_hz: float,
) -> dict[str, Any]:
    energies: list[np.ndarray] = []
    intervals: list[tuple[int, int]] = []
    symbol = 0
    while True:
        absolute_start, absolute_stop = clock_track.interval(symbol)
        if absolute_stop > input_stop:
            break
        local_start = absolute_start - input_start
        local_stop = absolute_stop - input_start
        if local_start < 0:
            symbol += 1
            continue
        energies.append(
            _observe_tracked_tone_row(
                samples[local_start:local_stop],
                absolute_start=absolute_start,
                absolute_stop=absolute_stop,
                sample_rate=sample_rate,
                frequency_track=frequency_track,
                tone_spacing_hz=tone_spacing_hz,
            )
        )
        intervals.append((absolute_start, absolute_stop))
        symbol += 1
    if not energies:
        raise ValueError("tracked symbol clock produced no complete intervals")
    log_metrics = _log_tone_metrics(np.asarray(energies))
    ordered = np.sort(log_metrics, axis=1)
    margin = ordered[:, -1] - ordered[:, -2]
    noise_log_metric = np.median(log_metrics, axis=1)
    winner_over_noise = ordered[:, -1] - noise_log_metric
    # Deliberately conservative, uncalibrated first policy. A neutral LLR is
    # preferable to asserting a winner when the comb is flat or noise-like.
    erased = (margin < math.log(1.08)) | (winner_over_noise < math.log(1.8))
    return {
        "log_metrics": log_metrics,
        "intervals": intervals,
        "margin": margin,
        "noise_log_metric": noise_log_metric,
        "erased": erased,
        "erasure_policy": {
            "winner_runner_up_margin_min_nats": math.log(1.08),
            "winner_noise_ratio_min_nats": math.log(1.8),
        },
    }


@dataclass(frozen=True)
class StatefulToneObservation:
    symbol_index: int
    input_interval: tuple[int, int]
    log_metrics: tuple[float, ...]
    winner_runner_up_margin_nats: float
    noise_log_metric: float
    erased: bool


class FixedTrackToneObserver:
    """Chunkable C7 spike for an already established carrier and clock track."""

    SCHEMA = "grampy.fixed-track-observer-checkpoint.v1"

    def __init__(
        self,
        *,
        sample_rate: float,
        frequency_track: FrequencyTrack,
        clock_track: ClockTrack,
        tone_spacing_hz: float,
    ) -> None:
        if sample_rate <= 0 or tone_spacing_hz <= 0:
            raise ValueError("tone observer rates must be positive")
        self.sample_rate = float(sample_rate)
        self.frequency_track = frequency_track
        self.clock_track = clock_track
        self.tone_spacing_hz = float(tone_spacing_hz)
        self._next_symbol = 0
        self._buffer_start: int | None = None
        self._buffer = np.empty(0, dtype=np.complex128)
        self._expected_input_start: int | None = None
        self._maximum_retained_samples = 0

    @property
    def next_symbol_index(self) -> int:
        return self._next_symbol

    @property
    def retained_history_samples(self) -> int:
        return len(self._buffer)

    @property
    def maximum_retained_samples(self) -> int:
        return self._maximum_retained_samples

    def push(
        self, samples: np.ndarray, *, input_start: int
    ) -> tuple[StatefulToneObservation, ...]:
        values = np.asarray(samples, dtype=np.complex128)
        if values.ndim != 1:
            raise ValueError("tone observer IQ must be a flat sequence")
        input_start = int(input_start)
        if self._expected_input_start is not None and input_start != self._expected_input_start:
            raise ValueError("tone observer chunks must be contiguous")
        if self._buffer_start is None:
            self._buffer_start = input_start
        if len(values):
            self._buffer = np.concatenate((self._buffer, values))
        self._expected_input_start = input_start + len(values)

        observations: list[StatefulToneObservation] = []
        while True:
            absolute_start, absolute_stop = self.clock_track.interval(
                self._next_symbol
            )
            buffer_stop = self._buffer_start + len(self._buffer)
            if absolute_stop <= self._buffer_start:
                self._next_symbol += 1
                continue
            if absolute_start < self._buffer_start:
                raise ValueError("tone observer is missing required symbol history")
            if absolute_stop > buffer_stop:
                break
            local_start = absolute_start - self._buffer_start
            local_stop = absolute_stop - self._buffer_start
            energy = _observe_tracked_tone_row(
                self._buffer[local_start:local_stop],
                absolute_start=absolute_start,
                absolute_stop=absolute_stop,
                sample_rate=self.sample_rate,
                frequency_track=self.frequency_track,
                tone_spacing_hz=self.tone_spacing_hz,
            )
            metrics = _log_tone_metrics(energy[None, :])[0]
            ordered = np.sort(metrics)
            margin = float(ordered[-1] - ordered[-2])
            noise = float(np.median(metrics))
            observations.append(
                StatefulToneObservation(
                    symbol_index=self._next_symbol,
                    input_interval=(absolute_start, absolute_stop),
                    log_metrics=tuple(float(value) for value in metrics),
                    winner_runner_up_margin_nats=margin,
                    noise_log_metric=noise,
                    erased=(
                        margin < math.log(1.08)
                        or ordered[-1] - noise < math.log(1.8)
                    ),
                )
            )
            self._next_symbol += 1

        next_start, _ = self.clock_track.interval(self._next_symbol)
        discard_stop = min(max(next_start, self._buffer_start), buffer_stop)
        discard = discard_stop - self._buffer_start
        if discard:
            self._buffer = self._buffer[discard:].copy()
            self._buffer_start = discard_stop
        self._maximum_retained_samples = max(
            self._maximum_retained_samples, len(self._buffer)
        )
        return tuple(observations)

    def skip(self, *, input_start: int, input_stop: int) -> None:
        """Advance an established clock across a known non-text interval."""
        input_start = int(input_start)
        input_stop = int(input_stop)
        if input_stop < input_start:
            raise ValueError("tone observer skip interval is reversed")
        if self._expected_input_start is not None and input_start != self._expected_input_start:
            raise ValueError("tone observer skip must be contiguous")
        self._buffer = np.empty(0, dtype=np.complex128)
        self._buffer_start = input_stop
        self._expected_input_start = input_stop
        while True:
            symbol_start, symbol_stop = self.clock_track.interval(self._next_symbol)
            if symbol_start >= input_stop:
                break
            self._next_symbol += 1

    def checkpoint(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "configuration_digest": self._configuration_digest(),
            "next_symbol": self._next_symbol,
            "buffer_start": self._buffer_start,
            "buffer_real": self._buffer.real.tolist(),
            "buffer_imag": self._buffer.imag.tolist(),
            "expected_input_start": self._expected_input_start,
            "maximum_retained_samples": self._maximum_retained_samples,
        }

    @classmethod
    def restore(
        cls,
        checkpoint: dict[str, Any],
        *,
        sample_rate: float,
        frequency_track: FrequencyTrack,
        clock_track: ClockTrack,
        tone_spacing_hz: float,
    ) -> FixedTrackToneObserver:
        if checkpoint.get("schema") != cls.SCHEMA:
            raise ValueError("unsupported fixed-track observer checkpoint")
        instance = cls(
            sample_rate=sample_rate,
            frequency_track=frequency_track,
            clock_track=clock_track,
            tone_spacing_hz=tone_spacing_hz,
        )
        if checkpoint.get("configuration_digest") != instance._configuration_digest():
            raise ValueError("fixed-track observer configuration changed")
        real = checkpoint.get("buffer_real")
        imag = checkpoint.get("buffer_imag")
        if not isinstance(real, list) or not isinstance(imag, list) or len(real) != len(imag):
            raise ValueError("malformed fixed-track observer buffer")
        instance._buffer = np.asarray(real, dtype=np.float64) + 1j * np.asarray(
            imag, dtype=np.float64
        )
        buffer_start = checkpoint.get("buffer_start")
        expected = checkpoint.get("expected_input_start")
        instance._buffer_start = None if buffer_start is None else int(buffer_start)
        instance._expected_input_start = None if expected is None else int(expected)
        instance._next_symbol = int(checkpoint["next_symbol"])
        instance._maximum_retained_samples = int(
            checkpoint["maximum_retained_samples"]
        )
        if instance._next_symbol < 0 or instance._maximum_retained_samples < len(
            instance._buffer
        ):
            raise ValueError("malformed fixed-track observer coordinates")
        if (
            instance._buffer_start is None
            and len(instance._buffer)
            or instance._buffer_start is not None
            and instance._expected_input_start
            != instance._buffer_start + len(instance._buffer)
        ):
            raise ValueError("malformed fixed-track observer coordinates")
        return instance

    def _configuration_digest(self) -> str:
        document = {
            "sample_rate": self.sample_rate,
            "tone_spacing_hz": self.tone_spacing_hz,
            "frequency_track": self.frequency_track.to_dict(),
            "clock_track": self.clock_track.to_dict(),
        }
        encoded = json.dumps(
            document, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _observe_tracked_tone_row(
    samples: np.ndarray,
    *,
    absolute_start: int,
    absolute_stop: int,
    sample_rate: float,
    frequency_track: FrequencyTrack,
    tone_spacing_hz: float,
) -> np.ndarray:
    count = len(samples)
    if count != absolute_stop - absolute_start:
        raise ValueError("tracked tone row does not match its source interval")
    midpoint = (absolute_start + absolute_stop) // 2
    center_hz = frequency_track.center_at(midpoint)
    frequencies = center_hz + (np.arange(16) - 7.5) * tone_spacing_hz
    time_axis = np.arange(count, dtype=np.float64) / sample_rate
    oscillator = np.exp(-2j * np.pi * frequencies[:, None] * time_axis)
    return np.abs(np.asarray(samples) @ oscillator.T) ** 2


def _decode_orientation(
    metrics: np.ndarray,
    orientation: str,
    first_symbol: int,
    input_start: int,
    samples_per_symbol: int,
    *,
    intervals: list[tuple[int, int]] | None = None,
    erased: np.ndarray | None = None,
    retain_trace: bool = True,
    persistent_tone_policy: str = "measure",
) -> dict[str, Any]:
    logical_metrics = metrics if orientation == "normal" else metrics[:, ::-1]
    persistence = _measure_persistent_tones(logical_metrics)
    persistence["policy"] = persistent_tone_policy
    operative_metrics = logical_metrics.copy()
    if persistent_tone_policy == "suppress":
        flagged = np.flatnonzero(persistence["persistent_competitor"])
        tones = persistence["persistent_competitor_tone"][flagged]
        operative_metrics[flagged, tones] = np.median(
            operative_metrics[flagged], axis=1
        )
    if erased is None:
        erased = np.zeros(len(logical_metrics), dtype=bool)
    deinterleaver = SoftDeinterleaver()
    groups = [
        deinterleaver.push(
            np.zeros(4) if is_erased else tone_metrics_to_llrs(row),
            valid=not bool(is_erased),
        )
        for row, is_erased in zip(operative_metrics, erased)
    ]
    llrs = np.asarray(groups, dtype=np.float64).reshape(-1)
    fec_candidates = []
    for startup_name, initial_state in (
        ("known_zero", 0),
        ("unknown_midstream", None),
    ):
        fec_candidate = soft_viterbi_decode(llrs, initial_state=initial_state)
        parsed_candidate = parse_varicode(fec_candidate.bits)
        candidate_events = [
            _event_document(
                event,
                llrs,
                first_symbol,
                input_start,
                samples_per_symbol,
                index,
                persistence=persistence,
            )
            for index, event in enumerate(parsed_candidate)
        ]
        valid_candidate = sum(
            event["octet"] is not None for event in candidate_events
        )
        printable_candidate = sum(
            event["octet"] is not None
            and (
                32 <= event["octet"] <= 126
                or event["octet"] in {0, 2, 4, 13}
            )
            for event in candidate_events
        )
        fec_candidates.append(
            {
                "name": startup_name,
                "fec": fec_candidate,
                "events": candidate_events,
                "score": (
                    valid_candidate / max(1, len(candidate_events))
                    + printable_candidate / max(1, valid_candidate)
                ),
            }
        )
    selected_fec = max(
        fec_candidates,
        key=lambda item: (
            item["score"],
            item["name"] == "known_zero",
        ),
    )
    fec = selected_fec["fec"]
    events = selected_fec["events"]
    valid = sum(event["octet"] is not None for event in events)
    printable = sum(
        event["octet"] is not None
        and (32 <= event["octet"] <= 126 or event["octet"] in {0, 2, 4, 13})
        for event in events
    )
    language_like = sum(
        event["octet"] is not None
        and (
            event["octet"] == 32
            or 65 <= event["octet"] <= 90
            or 97 <= event["octet"] <= 122
        )
        for event in events
    )
    valid_fraction = valid / max(1, len(events))
    printable_fraction = printable / max(1, valid)
    language_like_fraction = language_like / max(1, valid)
    stx_index = next(
        (index for index, event in enumerate(events)
         if event.get("control_role") == "STX"),
        None,
    )
    eot_index = next(
        (index for index, event in reversed(list(enumerate(events)))
         if event.get("control_role") == "EOT"),
        None,
    )
    complete_framing = (
        stx_index is not None
        and eot_index is not None
        and stx_index <= 5
        and eot_index > stx_index
        and eot_index >= len(events) - 5
    )
    score = float(
        1000 * complete_framing
        + 100 * valid_fraction
        + 200 * printable_fraction
        + 200 * language_like_fraction
    )
    tone_rows = [
        {
            "symbol": index,
            "input_interval": (
                {"start": intervals[index][0], "stop": intervals[index][1]}
                if intervals is not None
                else {
                    "start": input_start + first_symbol + index * samples_per_symbol,
                    "stop": input_start + first_symbol + (index + 1) * samples_per_symbol,
                }
            ),
            "log_metrics": row.tolist(),
            "winner": int(np.argmax(row)),
            "runner_up": int(np.argsort(row)[-2]),
            "winner_runner_up_margin_nats": float(
                np.sort(row)[-1] - np.sort(row)[-2]
            ),
            "noise_log_metric": float(np.median(row)),
            "erasure": bool(erased[index]),
        }
        for index, row in enumerate(logical_metrics)
    ] if retain_trace else []
    return {
        "orientation": orientation,
        "score": score,
        "events": events,
        "coded_llr_count": len(llrs),
        "decoded_bit_count": len(fec.bits),
        "path_metric_gap": fec.path_metric_gap,
        "fec_startup": selected_fec["name"],
        "fec_startup_hypotheses": [
            {
                "assumption": item["name"],
                "score": item["score"],
                "status": (
                    "selected" if item is selected_fec else "superseded"
                ),
            }
            for item in fec_candidates
        ],
        "decoded_bits": "".join(map(str, fec.bits)) if retain_trace else "",
        "decoded_bits_internal": tuple(fec.bits),
        "deinterleaved_groups": (
            [list(map(float, group)) for group in groups] if retain_trace else []
        ),
        "tone_rows": tone_rows,
        "persistence": persistence,
    }


def _measure_persistent_tones(metrics: np.ndarray) -> dict[str, Any]:
    """Measure, but do not suppress, persistent competing tone energy.

    A tone is occupied when it is within 3 dB (natural-log power units) of
    the winning tone.  The predeclared T1 feature is a non-winning tone that
    is occupied in at least 12 of a trailing 16-symbol window.  The window is
    epoch-local and bounded; the feature never changes the supplied metrics.
    """

    rows = np.asarray(metrics, dtype=np.float64)
    if rows.ndim != 2 or rows.shape[1] != 16:
        raise ValueError("persistent-tone measurement requires Nx16 metrics")
    count = len(rows)
    if count == 0:
        return {
            "window_symbols": 16,
            "minimum_occupied_symbols": 12,
            "occupied_within_winner_nats": math.log(2.0),
            "maximum_occupancy_fraction": np.empty(0),
            "maximum_run_length": np.empty(0, dtype=np.int32),
            "persistent_competitor": np.empty(0, dtype=bool),
            "persistent_competitor_tone": np.empty(0, dtype=np.int8),
            "adjacent_competitor_gap_nats": np.empty(0),
        }
    winners = np.argmax(rows, axis=1)
    winning = np.max(rows, axis=1)
    occupied = rows >= winning[:, None] - math.log(2.0)
    window = 16
    minimum = 12
    occupancy = np.zeros_like(rows, dtype=np.int16)
    cumulative = np.vstack(
        [np.zeros((1, 16), dtype=np.int32), np.cumsum(occupied, axis=0)]
    )
    for index in range(count):
        start = max(0, index + 1 - window)
        occupancy[index] = cumulative[index + 1] - cumulative[start]
    run = np.zeros_like(rows, dtype=np.int32)
    current = np.zeros(16, dtype=np.int32)
    for index in range(count):
        current = np.where(occupied[index], current + 1, 0)
        run[index] = current
    competitor_occupancy = occupancy.copy()
    competitor_occupancy[np.arange(count), winners] = 0
    competitor_run = run.copy()
    competitor_run[np.arange(count), winners] = 0
    available = np.minimum(np.arange(1, count + 1), window)
    maximum_occupancy = np.max(competitor_occupancy, axis=1)
    competitor_tone = np.argmax(competitor_occupancy, axis=1).astype(np.int8)
    persistent = (available >= window) & (maximum_occupancy >= minimum)
    adjacent_gap = np.full(count, np.inf, dtype=np.float64)
    for delta in (-1, 1):
        adjacent = winners + delta
        valid = (adjacent >= 0) & (adjacent < 16)
        indices = np.flatnonzero(valid)
        adjacent_gap[indices] = np.minimum(
            adjacent_gap[indices],
            winning[indices] - rows[indices, adjacent[indices]],
        )
    return {
        "window_symbols": window,
        "minimum_occupied_symbols": minimum,
        "occupied_within_winner_nats": math.log(2.0),
        "maximum_occupancy_fraction": maximum_occupancy / available,
        "maximum_run_length": np.max(competitor_run, axis=1),
        "persistent_competitor": persistent,
        "persistent_competitor_tone": competitor_tone,
        "adjacent_competitor_gap_nats": adjacent_gap,
    }


def _event_document(
    event: Any,
    llrs: np.ndarray,
    first_symbol: int,
    input_start: int,
    samples_per_symbol: int,
    event_index: int,
    *,
    persistence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_symbols: list[int] = []
    for decoded_bit in range(event.start_bit, event.recognized_at_bit):
        recovered_group = decoded_bit // 2
        lanes = (0, 1) if decoded_bit % 2 == 0 else (2, 3)
        delays = (30, 20, 10, 0)
        source_symbols.extend(recovered_group - delays[lane] for lane in lanes)
    source_symbols = [symbol for symbol in source_symbols if symbol >= 0]
    if source_symbols:
        wire_start_symbol = min(source_symbols)
        recognized_symbol = max(source_symbols) + 1
    else:
        wire_start_symbol = 0
        recognized_symbol = 0
    wire_start = input_start + first_symbol + wire_start_symbol * samples_per_symbol
    wire_stop = input_start + first_symbol + recognized_symbol * samples_per_symbol
    llr_start = max(0, event.start_bit * 2)
    llr_stop = min(len(llrs), event.stop_bit * 2)
    confidence = (
        float(np.min(np.abs(llrs[llr_start:llr_stop])))
        if llr_stop > llr_start
        else 0.0
    )
    roles = {0: "NUL", 2: "STX", 4: "EOT", 13: "CR"}
    persistence_document: dict[str, Any] | None = None
    if persistence is not None and source_symbols:
        indices = np.asarray(
            sorted(set(symbol for symbol in source_symbols if symbol < len(persistence["persistent_competitor"]))),
            dtype=np.int64,
        )
        if len(indices):
            adjacent = persistence["adjacent_competitor_gap_nats"][indices]
            finite_adjacent = adjacent[np.isfinite(adjacent)]
            persistence_document = {
                "feature": "nonwinning_tone_occupied_12_of_trailing_16_within_3db",
                "exposed": bool(np.any(persistence["persistent_competitor"][indices])),
                "source_symbol_count": int(len(indices)),
                "maximum_occupancy_fraction": float(np.max(persistence["maximum_occupancy_fraction"][indices])),
                "maximum_consecutive_run_symbols": int(np.max(persistence["maximum_run_length"][indices])),
                "minimum_adjacent_competitor_gap_nats": (
                    float(np.min(finite_adjacent)) if len(finite_adjacent) else None
                ),
                "decision_effect": (
                    "measurement_only"
                    if persistence.get("policy", "measure") == "measure"
                    else "flagged_competitor_replaced_with_row_median"
                ),
            }
    document = {
        "id": f"text-{event_index + 1:04d}",
        "octet": event.octet,
        "display": (
            chr(event.octet)
            if event.octet is not None and 32 <= event.octet <= 126
            else None
        ),
        "control_role": roles.get(event.octet),
        "codeword": event.codeword,
        "wire_interval": {"start": wire_start, "stop": wire_stop},
        "recognized_at_input_sample": wire_stop,
        "confidence": {
            "kind": "minimum_absolute_input_llr",
            "value": confidence,
            "calibrated": False,
        },
        "damage_flags": ([] if event.octet is not None else ["invalid_varicode"]),
        "mode_segment": "mode-0001",
        "provenance": {
            "decoded_bit_interval": {
                "start": event.start_bit,
                "stop": event.stop_bit,
            },
            "recognized_symbol": recognized_symbol,
        },
    }
    if persistence_document is not None:
        document["provenance"]["persistent_tone_measurement"] = persistence_document
    return document
