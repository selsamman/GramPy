from __future__ import annotations

import copy
from dataclasses import dataclass, replace
import hashlib
import json
from typing import Any, Sequence

import numpy as np

from .stateful_text import PictureHeaderScanner, StatefulVaricodeParser
from .text_decode import (
    FixedTrackToneObserver,
    MFSKTextDecode,
    StatefulToneObservation,
    _tone_crossover,
    plan_received_tracks_from_reader,
)
from .tracking import ClockAnchor, ClockTrack, FrequencyTrack
from .wire import (
    SoftDeinterleaver,
    StatefulPictureFlushEncoder,
    StatefulSoftViterbiDecoder,
    tone_metrics_to_llrs,
)


@dataclass(frozen=True)
class StatefulTextResult:
    text_events: tuple[dict[str, Any], ...]
    picture_headers: tuple[dict[str, Any], ...]
    reset_events: tuple[dict[str, Any], ...]


def adapt_stateful_text_events(
    events: Sequence[dict[str, Any]],
    *,
    mode_segment_id: str,
    clock_track: ClockTrack,
    transition_clock_evidence: dict[str, Any] | None = None,
    id_offset: int = 0,
) -> list[dict[str, Any]]:
    """Map compact receiver events onto the frozen public event contract."""
    roles = {0: "NUL", 2: "STX", 4: "EOT", 13: "CR"}
    public: list[dict[str, Any]] = []
    for index, source in enumerate(events, id_offset + 1):
        source_clock_document = source.get("p11d_clock_track")
        event_clock = (
            ClockTrack(
                epoch_input_sample=float(source_clock_document["epoch_input_sample"]),
                samples_per_symbol=float(source_clock_document["nominal_symbol_samples"]),
                rate_error_ppm=float(source_clock_document["estimated_rate_error_ppm"]),
                uncertainty_samples=float(source_clock_document["phase_uncertainty_input_samples"]),
            )
            if source_clock_document is not None else clock_track
        )
        decision_stop = source.get("decision_available_at_input_sample")
        start_bit = int(source["source_bit_interval"]["start"])
        stop_bit = int(source["source_bit_interval"]["stop"])
        recognized_at_bit = int(source.get("recognized_at_bit", stop_bit))
        source_symbols: list[int] = []
        for decoded_bit in range(start_bit, recognized_at_bit):
            recovered_group = decoded_bit // 2
            lanes = (0, 1) if decoded_bit % 2 == 0 else (2, 3)
            delays = (30, 20, 10, 0)
            source_symbols.extend(
                recovered_group - delays[lane] for lane in lanes
            )
        source_symbols = [symbol for symbol in source_symbols if symbol >= 0]
        wire_start_symbol = min(source_symbols) if source_symbols else 0
        recognized_symbol = max(source_symbols) + 1 if source_symbols else 0
        epoch = int(round(event_clock.epoch_input_sample))
        nominal = int(round(event_clock.samples_per_symbol))
        wire_start = epoch + wire_start_symbol * nominal
        wire_stop = epoch + recognized_symbol * nominal
        octet = source.get("octet")
        provenance: dict[str, Any] = {
            "decoded_bit_interval": {
                "start": start_bit,
                "stop": stop_bit,
            },
            "recognized_symbol": recognized_symbol,
            "text_epoch": f"text-epoch-{int(source.get('p11d_text_epoch', source['text_epoch'])):06d}",
            "source_coordinate_status": source["source_coordinate_status"],
            "decision_available_at_input_sample": decision_stop,
        }
        if source.get("picture_flush_tones") is not None:
            provenance["picture_flush_tones"] = list(
                source["picture_flush_tones"]
            )
        event_transition_evidence = source.get(
            "p11d_transition_clock_evidence", transition_clock_evidence
        )
        if event_transition_evidence is not None:
            provenance["transition_crossover_clock"] = event_transition_evidence
        public.append(
            {
                "id": f"text-{index:06d}",
                "octet": octet,
                "display": (
                    chr(octet)
                    if octet is not None and 32 <= int(octet) <= 126 else None
                ),
                "control_role": roles.get(octet),
                "codeword": source["codeword"],
                "wire_interval": {"start": wire_start, "stop": wire_stop},
                "recognized_at_input_sample": wire_stop,
                "confidence": {
                    "kind": "normalized_viterbi_decision_path_metric_gap",
                    "value": float(source["confidence"]["value"]),
                    "calibrated": False,
                },
                "damage_flags": list(source["damage_flags"]),
                "mode_segment": mode_segment_id,
                "provenance": provenance,
            }
        )
    return public


def decode_p11d_text_region(
    reader: Any,
    *,
    input_start: int,
    input_stop: int,
    sample_rate: float,
    mode: str,
    center_hz: float,
    orientation: str,
    block_samples: int,
    initial_state: int | None = 0,
    mode_segment_id: str = "mode-p11d-0001",
    phase_hint_input_sample: float | None = None,
) -> MFSKTextDecode:
    """Decode one established fixed-mode region with the selected P11D path."""
    if orientation not in {"normal", "reverse"}:
        raise ValueError("P11D text region requires a fixed orientation")
    if block_samples < 1:
        raise ValueError("P11D text block size must be positive")
    initial_planning_stop = min(
        input_stop, input_start + int(round(180.0 * sample_rate))
    )
    frequency_track, clock_track, track_diagnostics = (
        plan_received_tracks_from_reader(
            reader,
            input_start=input_start,
            input_stop=initial_planning_stop,
            sample_rate=sample_rate,
            mode=mode,
            center_hz=center_hz,
            orientation=orientation,
            phase_hint_input_sample=phase_hint_input_sample,
        )
    )
    track_diagnostics["planning_scope"] = "initial_text_epoch"
    track_diagnostics["planned_segment_interval"] = {
        "start": input_start,
        "stop": input_stop,
    }
    tone_spacing = 31.25 if mode == "MFSK32" else 62.5
    coarse_frequency = FrequencyTrack.fixed(
        center_hz=center_hz, input_sample=input_start,
        uncertainty_hz=tone_spacing / 2.0, source="coarse_acquisition",
    )
    coarse_clock = ClockTrack(
        epoch_input_sample=clock_track.epoch_input_sample,
        samples_per_symbol=clock_track.samples_per_symbol,
        rate_error_ppm=0.0,
        uncertainty_samples=clock_track.uncertainty_samples,
    )
    candidates: dict[str, dict[str, Any]] = {}
    for name, candidate_frequency, candidate_clock in (
        ("coarse", coarse_frequency, coarse_clock),
        ("tracked", frequency_track, clock_track),
    ):
        candidates[name] = {
            "name": name,
            "acquisition_center_hz": float(center_hz),
            "frequency_track": candidate_frequency,
            "clock_track": candidate_clock,
            "receiver": P11DTextEvidencePass(
                sample_rate=sample_rate,
                tone_spacing_hz=tone_spacing,
                frequency_track=candidate_frequency,
                clock_track=candidate_clock,
                orientation=orientation,
                initial_state=initial_state,
                erasure_policy=("none" if name == "coarse" else "measure"),
            ),
            "raw_events": [],
            "raw_headers": [],
            "reset_events": [],
            "public_epoch": 1,
            "completed_pass_diagnostics": [],
            "track_epochs": [],
        }
    _push_candidates_with_picture_rollbacks(
        reader,
        candidates=candidates,
        input_start=input_start,
        input_stop=input_stop,
        sample_rate=sample_rate,
        block_samples=block_samples,
    )
    for candidate in candidates.values():
        tail = candidate["receiver"].close_epoch(
            "caller_cut", affected_interval=(input_start, input_stop), reopen=False
        )
        _append_candidate_result(candidate, tail)
        first_header_stop = next(
            (
                int(header["source_input_interval"]["stop"])
                for header in candidate["raw_headers"]
                if header.get("source_input_interval") is not None
            ),
            input_stop,
        )
        (
            candidate["transition_clock"],
            candidate["transition_clock_evidence"],
            candidate["transition_clock_covariance"],
        ) = candidate["receiver"].transition_clock_before(first_header_stop)
        candidate["events"] = adapt_stateful_text_events(
            candidate["raw_events"],
            mode_segment_id=mode_segment_id,
            clock_track=candidate["clock_track"],
            transition_clock_evidence=(
                candidate["transition_clock_evidence"]
                if candidate["transition_clock"] is not None else None
            ),
        )
        candidate["score"] = _public_text_candidate_score(candidate["events"])
    selected_name = (
        "tracked"
        if candidates["tracked"]["score"] >= candidates["coarse"]["score"] + 2.0
        else "coarse"
    )
    selected = candidates[selected_name]
    raw_headers = selected["raw_headers"]
    reset_events = selected["reset_events"]
    receiver = selected["receiver"]
    frequency_track = selected["frequency_track"]
    clock_track = selected["clock_track"]
    selected_header_stop = next(
        (
            int(header["source_input_interval"]["stop"])
            for header in raw_headers
            if header.get("source_input_interval") is not None
        ),
        input_stop,
    )
    compatibility_core = int(round(180.0 * sample_rate))
    compatibility_context = int(round(8.0 * sample_rate))
    compatibility_core_start = input_start + (
        (max(0, selected_header_stop - input_start) // compatibility_core)
        * compatibility_core
    )
    transition_training_start = max(
        input_start, compatibility_core_start - compatibility_context
    )
    timing_candidate = candidates["tracked"]
    (
        tracked_transition_clock,
        tracked_transition_evidence,
        tracked_transition_covariance,
    ) = timing_candidate["receiver"].transition_clock_before(
        selected_header_stop, input_start=transition_training_start
    )
    tracked_transition_evidence["training_input_interval"] = {
        "start": transition_training_start,
        "stop": selected_header_stop,
    }
    transition_clock = tracked_transition_clock or clock_track
    transition_clock_evidence = tracked_transition_evidence
    transition_clock_covariance = tracked_transition_covariance
    events = adapt_stateful_text_events(
        selected["raw_events"],
        mode_segment_id=mode_segment_id,
        clock_track=clock_track,
        transition_clock_evidence=(
            transition_clock_evidence
            if tracked_transition_clock is not None else None
        ),
    )
    events = _merge_candidate_picture_headers(
        events,
        [
            candidate["events"]
            for name, candidate in candidates.items()
            if name != selected_name
        ],
        sample_rate=sample_rate,
    )
    stx = next(
        (index for index, event in enumerate(events) if event["control_role"] == "STX"),
        None,
    )
    eot = next(
        (
            index for index, event in enumerate(events)
            if event["control_role"] == "EOT" and (stx is None or index > stx)
        ),
        None,
    )
    payload = (
        events[stx + 1:eot]
        if stx is not None and eot is not None else events
    )
    octets = [
        event["octet"] for event in payload
        if event["octet"] is not None and event["control_role"] is None
    ]
    diagnostics = _combined_pass_diagnostics(selected)
    epoch_interval = {
        "start": input_start,
        "stop": input_stop,
    }
    return MFSKTextDecode(
        mode_segment={
            "id": mode_segment_id,
            "mode": mode,
            "orientation": orientation,
            "interval": epoch_interval,
            "source": "rsid_and_p11d_compact_tracks",
            "confidence": {"kind": "accepted_acquisition_segment", "value": 1.0},
            "acquisition_state": "locked",
            "symbol_phase_uncertainty_input_samples": (
                clock_track.uncertainty_samples
            ),
            "center_hz": float(center_hz),
        },
        text_events=events,
        text_summary={
            "octets": octets,
            "text": bytes(octets).decode("latin-1"),
            "framing": {"stx_found": stx is not None, "eot_found": eot is not None},
        },
        diagnostics={
            "bounded_organization": {
                "kind": "p11d_compact_tracks_one_sequential_text_pass",
                "maximum_materialized_iq_samples": max(
                    block_samples,
                    track_diagnostics["maximum_materialized_iq_samples"],
                ),
                "track_planning": track_diagnostics,
                "text_pass": diagnostics,
                "track_hypotheses": {
                    name: {
                        "score": candidate["score"],
                        "event_count": len(candidate["events"]),
                        "frequency_track": candidate["frequency_track"].to_dict(),
                        "clock_track": candidate["clock_track"].to_dict(),
                        "selected": name == selected_name,
                    }
                    for name, candidate in candidates.items()
                },
                "reset_events": reset_events,
                "picture_headers": raw_headers,
            },
            "tone_evidence": {
                "symbol_count": diagnostics["observation_count"],
                "frequency_track": frequency_track.to_dict(),
                "clock_track": clock_track.to_dict(),
                "transition_crossover_clock": {
                    **transition_clock_evidence,
                    "operative": tracked_transition_clock is not None,
                },
            },
            "bit_evidence": {"erasure_count": diagnostics["erasure_count"]},
            "fec_evidence": {
                "decoder": "64-state stateful soft-input Viterbi",
                "initial_state": "known_zero" if initial_state == 0 else "unknown",
                "traceback_depth": 384,
                "coded_llr_count": 4 * diagnostics["observation_count"],
                "decoded_bit_count": 2 * diagnostics["observation_count"],
            },
            "varicode_evidence": {
                "event_count": len(events),
                "invalid_count": sum(event["octet"] is None for event in events),
            },
        },
        text_epochs=[{
            "id": "text-epoch-000001",
            "mode": mode,
            "interval": epoch_interval,
            "start_evidence": "accepted_mode_segment_and_compact_track_plan",
            "end_reset_cause": "caller_cut",
            "retained_state": [
                "frequency_track", "clock_track", "tone_observer",
                "deinterleaver", "fec_survivors", "varicode", "header_scanner",
            ],
        }],
        decoded_bits=(),
        transition_clock=transition_clock,
        transition_clock_covariance=transition_clock_covariance,
    )


def _push_candidates_with_picture_rollbacks(
    reader: Any,
    *,
    candidates: dict[str, dict[str, Any]],
    input_start: int,
    input_stop: int,
    sample_rate: float,
    block_samples: int,
) -> None:
    """Close text epochs at delayed picture decisions using bounded replay."""
    chunk_samples = min(int(block_samples), max(1, int(round(sample_rate))))
    rollback_extent = int(round(6.0 * sample_rate))
    snapshots: list[dict[str, Any]] = []
    cursor = input_start
    while cursor < input_stop:
        snapshots.append({
            "cursor": cursor,
            "receivers": {
                name: candidate["receiver"].checkpoint()
                for name, candidate in candidates.items()
            },
            "lengths": {
                name: (
                    len(candidate["raw_events"]),
                    len(candidate["raw_headers"]),
                    len(candidate["reset_events"]),
                )
                for name, candidate in candidates.items()
            },
        })
        snapshots = [
            item for item in snapshots
            if item["cursor"] >= cursor - rollback_extent
        ]
        stop = min(input_stop, cursor + chunk_samples)
        samples = reader(cursor, stop)
        discovered: list[dict[str, Any]] = []
        for candidate in candidates.values():
            result = candidate["receiver"].push(samples, input_start=cursor)
            _append_candidate_result(candidate, result)
            discovered.extend(result.picture_headers)
        cursor = stop
        if not discovered:
            continue
        header = min(
            discovered,
            key=lambda item: int(item["source_input_interval"]["stop"]),
        )
        header_stop = int(header["source_input_interval"]["stop"])
        raster_start = min(input_stop, header_stop + int(round(sample_rate)))
        component_count = (
            int(header["width"]) * int(header["height"])
            * (3 if header["color"] else 1)
        )
        raster_samples = int(round(
            component_count * int(header["samples_per_component"])
            * sample_rate / 8000.0
        ))
        raster_stop = min(input_stop, raster_start + raster_samples)
        eligible = [item for item in snapshots if item["cursor"] <= raster_start]
        if not eligible:
            raise ValueError("picture decision exceeded the bounded rollback extent")
        snapshot = eligible[-1]
        replay_start = int(snapshot["cursor"])
        for name, candidate in candidates.items():
            candidate["receiver"] = P11DTextEvidencePass.restore(
                snapshot["receivers"][name],
                frequency_track=candidate["frequency_track"],
                clock_track=candidate["clock_track"],
            )
            event_count, header_count, reset_count = snapshot["lengths"][name]
            del candidate["raw_events"][event_count:]
            del candidate["raw_headers"][header_count:]
            del candidate["reset_events"][reset_count:]
        if raster_start > replay_start:
            prefix = reader(replay_start, raster_start)
            for candidate in candidates.values():
                result = candidate["receiver"].push(
                    prefix, input_start=replay_start
                )
                _append_candidate_result(candidate, result)
        for candidate in candidates.values():
            _, transition_evidence, _ = (
                candidate["receiver"].transition_clock_before(header_stop)
            )
            tail = candidate["receiver"].close_epoch(
                "picture",
                affected_interval=(raster_start, raster_stop),
                reopen=False,
                initial_state=None,
            )
            _append_candidate_result(candidate, tail)
            for event in reversed(candidate["raw_events"]):
                if int(event["p11d_text_epoch"]) != int(candidate["public_epoch"]):
                    break
                if event.get("octet") == 59:
                    event["p11d_transition_clock_evidence"] = transition_evidence
                    break
            candidate["completed_pass_diagnostics"].append(
                candidate["receiver"].diagnostics()
            )
        _restart_candidates_after_picture(
            reader,
            candidates=candidates,
            input_start=raster_stop,
            input_stop=input_stop,
            sample_rate=sample_rate,
        )
        cursor = raster_stop
        snapshots = []


def _merge_candidate_picture_headers(
    selected_events: list[dict[str, Any]],
    alternate_event_sets: Sequence[list[dict[str, Any]]],
    *,
    sample_rate: float,
) -> list[dict[str, Any]]:
    """Union exact headers without mixing the hypotheses' payload text."""
    from .picture_decode import parse_picture_headers

    merged = list(selected_events)
    accepted, _ = parse_picture_headers(merged)
    for alternate_events in alternate_event_sets:
        descriptors, _ = parse_picture_headers(alternate_events)
        by_id = {event["id"]: event for event in alternate_events}
        for descriptor in descriptors:
            completion = int(descriptor["header_completed_at_input_sample"])
            duplicate = any(
                item["header_text"] == descriptor["header_text"]
                and abs(
                    int(item["header_completed_at_input_sample"]) - completion
                ) <= int(round(2.0 * sample_rate))
                for item in accepted
            )
            if duplicate:
                continue
            merged.extend(
                copy.deepcopy(by_id[event_id])
                for event_id in descriptor["header_event_ids"]
            )
            accepted.append(descriptor)
    merged.sort(key=lambda item: int(item["recognized_at_input_sample"]))
    for index, event in enumerate(merged, 1):
        event["id"] = f"text-{index:06d}"
    return merged


def _append_candidate_result(
    candidate: dict[str, Any], result: StatefulTextResult
) -> None:
    clock = candidate["clock_track"].to_dict()
    for source in result.text_events:
        event = copy.deepcopy(source)
        event["p11d_clock_track"] = clock
        event["p11d_text_epoch"] = int(candidate["public_epoch"])
        candidate["raw_events"].append(event)
    candidate["raw_headers"].extend(copy.deepcopy(result.picture_headers))
    candidate["reset_events"].extend(copy.deepcopy(result.reset_events))


def _restart_candidates_after_picture(
    reader: Any,
    *,
    candidates: dict[str, dict[str, Any]],
    input_start: int,
    input_stop: int,
    sample_rate: float,
) -> None:
    if input_start >= input_stop:
        return
    local_stop = min(input_stop, input_start + int(round(8.0 * sample_rate)))
    representative = candidates["tracked"]
    mode = representative["receiver"].mode
    orientation = representative["receiver"].orientation
    center = float(representative["acquisition_center_hz"])
    frequency, clock, diagnostics = plan_received_tracks_from_reader(
        reader,
        input_start=input_start,
        input_stop=local_stop,
        sample_rate=sample_rate,
        mode=mode,
        center_hz=center,
        orientation=orientation,
    )
    tone_spacing = 31.25 if mode == "MFSK32" else 62.5
    coarse_frequency = FrequencyTrack.fixed(
        center_hz=center,
        input_sample=input_start,
        uncertainty_hz=tone_spacing / 2.0,
        source="post_picture_coarse_reacquisition",
    )
    coarse_clock = ClockTrack(
        epoch_input_sample=clock.epoch_input_sample,
        samples_per_symbol=clock.samples_per_symbol,
        rate_error_ppm=0.0,
        uncertainty_samples=clock.uncertainty_samples,
    )
    for name, candidate in candidates.items():
        candidate_frequency = coarse_frequency if name == "coarse" else frequency
        candidate_clock = coarse_clock if name == "coarse" else clock
        candidate["public_epoch"] += 1
        candidate["frequency_track"] = candidate_frequency
        candidate["clock_track"] = candidate_clock
        candidate["track_epochs"].append({
            "start": input_start,
            "frequency_track": candidate_frequency.to_dict(),
            "clock_track": candidate_clock.to_dict(),
            "planning": diagnostics,
        })
        candidate["receiver"] = P11DTextEvidencePass(
            sample_rate=sample_rate,
            tone_spacing_hz=tone_spacing,
            frequency_track=candidate_frequency,
            clock_track=candidate_clock,
            orientation=orientation,
            initial_state=None,
            erasure_policy=("none" if name == "coarse" else "measure"),
        )


def _combined_pass_diagnostics(candidate: dict[str, Any]) -> dict[str, Any]:
    rows = [
        *candidate["completed_pass_diagnostics"],
        candidate["receiver"].diagnostics(),
    ]
    latest = copy.deepcopy(rows[-1])
    for key in (
        "requested_samples", "chunk_count", "rollback_count",
        "observation_count", "erasure_count",
    ):
        latest[key] = sum(int(row[key]) for row in rows)
    latest["maximum_retained_iq_samples"] = max(
        int(row["maximum_retained_iq_samples"]) for row in rows
    )
    latest["picture_epoch_count"] = len(rows) - 1
    return latest


def _public_text_candidate_score(events: Sequence[dict[str, Any]]) -> float:
    valid = [event for event in events if event["octet"] is not None]
    printable = [
        event for event in valid
        if 32 <= event["octet"] <= 126 or event["octet"] in {0, 2, 4, 13}
    ]
    language_like = [
        event for event in valid
        if event["octet"] == 32
        or 65 <= event["octet"] <= 90
        or 97 <= event["octet"] <= 122
    ]
    stx = next(
        (index for index, event in enumerate(events) if event["control_role"] == "STX"),
        None,
    )
    eot = next(
        (index for index, event in reversed(list(enumerate(events)))
         if event["control_role"] == "EOT"),
        None,
    )
    complete = (
        stx is not None and eot is not None and stx <= 5
        and eot > stx and eot >= len(events) - 5
    )
    return float(
        1000 * complete
        + 100 * len(valid) / max(1, len(events))
        + 200 * len(printable) / max(1, len(valid))
        + 200 * len(language_like) / max(1, len(valid))
    )


def _fit_precomputed_transition_clock(
    records: Sequence[dict[str, float | int | None]],
    *,
    nominal_symbol_samples: float,
) -> tuple[
    ClockTrack | None,
    dict[str, Any],
    tuple[tuple[float, float], tuple[float, float]] | None,
]:
    measured = [
        record for record in records
        if record.get("crossover_input_sample") is not None
    ]
    if len(measured) < 8:
        return None, {
            "status": "insufficient_crossovers",
            "eligible_transition_count": len(records),
            "crossover_count": len(measured),
            "operative": False,
        }, None
    x = np.asarray([record["symbol_index"] for record in measured], dtype=np.float64)
    y = np.asarray(
        [record["crossover_input_sample"] for record in measured], dtype=np.float64
    )
    base_weights = np.asarray(
        [record["base_weight"] for record in measured], dtype=np.float64
    )
    design = np.column_stack((np.ones(len(x), dtype=np.float64), x))
    robust_weights = base_weights.copy()
    coefficients = np.zeros(2, dtype=np.float64)
    scale = 0.25
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
        huber = np.minimum(
            1.0,
            2.5 * scale
            / np.maximum(np.abs(residuals - median), 1e-12),
        )
        robust_weights = base_weights * huber
    residuals = y - design @ coefficients
    keep = np.abs(residuals - np.median(residuals)) <= max(
        nominal_symbol_samples / 8.0, 4.0 * scale
    )
    retained_x = x
    if int(np.count_nonzero(keep)) >= 8:
        retained_x = x[keep]
        design = design[keep]
        y = y[keep]
        robust_weights = robust_weights[keep]
        root = np.sqrt(np.maximum(robust_weights, np.finfo(np.float64).tiny))
        coefficients = np.linalg.lstsq(
            design * root[:, None], y * root, rcond=None
        )[0]
        residuals = y - design @ coefficients
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
    uncertainty = max(0.25, float(np.sqrt(max(0.0, variance))))
    clock = ClockTrack(
        epoch_input_sample=epoch,
        samples_per_symbol=float(nominal_symbol_samples),
        rate_error_ppm=(
            tracked_symbol_samples / nominal_symbol_samples - 1.0
        ) * 1e6,
        uncertainty_samples=uncertainty,
        anchors=tuple(
            ClockAnchor(
                input_sample=int(round(sample)),
                symbol_index=float(symbol),
                uncertainty_samples=uncertainty,
                source="transition_weighted_crossover",
            )
            for symbol, sample in zip(retained_x, y)
        )[:64],
    )
    return clock, {
        **clock.to_dict(),
        "status": "estimated",
        "source": "compact_precomputed_transition_crossovers",
        "eligible_transition_count": len(records),
        "crossover_count": len(measured),
        "retained_crossover_count": len(y),
        "residual_sigma_input_samples": uncertainty,
        "parameter_covariance": [list(row) for row in covariance],
        "operative": True,
    }, covariance


class P11DTextEvidencePass:
    """One sequential, transactional C7-C12 pass over established tracks."""

    SCHEMA = "grampy.p11d-text-pass-checkpoint.v1"

    def __init__(
        self,
        *,
        sample_rate: float,
        tone_spacing_hz: float,
        frequency_track: FrequencyTrack,
        clock_track: ClockTrack,
        orientation: str,
        initial_state: int | None = 0,
        traceback_depth: int = 384,
        sustained_loss_symbols: int = 12,
        erasure_policy: str = "measure",
    ) -> None:
        if traceback_depth != 384:
            raise ValueError("P11D requires the qualified 384-bit horizon")
        if erasure_policy not in {"measure", "none"}:
            raise ValueError("P11D text erasure policy is invalid")
        self.sample_rate = float(sample_rate)
        self.tone_spacing_hz = float(tone_spacing_hz)
        self.frequency_track = frequency_track
        self.clock_track = clock_track
        self.orientation = orientation
        self.erasure_policy = erasure_policy
        self.mode = "MFSK32" if tone_spacing_hz == 31.25 else "MFSK64"
        self._observer = FixedTrackToneObserver(
            sample_rate=sample_rate,
            frequency_track=frequency_track,
            clock_track=clock_track,
            tone_spacing_hz=tone_spacing_hz,
        )
        self._receiver = StatefulBoundedTextReceiver(
            orientation=orientation,
            initial_state=initial_state,
            traceback_depth=traceback_depth,
            sustained_loss_symbols=sustained_loss_symbols,
            mode=self.mode,
        )
        self._requested_samples = 0
        self._chunk_count = 0
        self._rollback_count = 0
        self._observation_count = 0
        self._erasure_count = 0
        self._crossover_records: list[dict[str, float | int | None]] = []
        self._crossover_tail_start: int | None = None
        self._crossover_tail = np.empty(0, dtype=np.complex128)
        self._previous_observation: StatefulToneObservation | None = None

    @property
    def epoch(self) -> int:
        return self._receiver.epoch

    def push(self, samples: np.ndarray, *, input_start: int) -> StatefulTextResult:
        checkpoint = self.checkpoint()
        try:
            observations = self._observer.push(samples, input_start=input_start)
            if self.erasure_policy == "none":
                observations = tuple(
                    replace(observation, erased=False)
                    for observation in observations
                )
            self._record_crossovers(
                samples, input_start=input_start, observations=observations
            )
            result = self._receiver.push(observations)
        except BaseException:
            rollbacks = self._rollback_count + 1
            self._restore_in_place(checkpoint)
            self._rollback_count = rollbacks
            raise
        self._requested_samples += len(samples)
        self._chunk_count += 1
        self._observation_count += len(observations)
        self._erasure_count += sum(bool(item.erased) for item in observations)
        return result

    def close_epoch(
        self,
        cause: str,
        *,
        affected_interval: tuple[int, int] | None = None,
        reopen: bool = True,
        initial_state: int | None = None,
    ) -> StatefulTextResult:
        return self._receiver.close_epoch(
            cause,
            affected_interval=affected_interval,
            reopen=reopen,
            initial_state=initial_state,
        )

    def skip_picture_interval(self, *, input_start: int, input_stop: int) -> None:
        """Advance compact carrier/clock state without treating raster as text."""
        self._observer.skip(input_start=input_start, input_stop=input_stop)
        self._requested_samples += input_stop - input_start
        self._crossover_tail_start = None
        self._crossover_tail = np.empty(0, dtype=np.complex128)
        self._previous_observation = None

    def checkpoint(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "configuration": {
                "sample_rate": self.sample_rate,
                "tone_spacing_hz": self.tone_spacing_hz,
                "orientation": self.orientation,
                "mode": self.mode,
                "erasure_policy": self.erasure_policy,
                "frequency_track": self.frequency_track.to_dict(),
                "clock_track": self.clock_track.to_dict(),
            },
            "observer": self._observer.checkpoint(),
            "receiver": self._receiver.checkpoint(),
            "accounting": {
                "requested_samples": self._requested_samples,
                "chunk_count": self._chunk_count,
                "rollback_count": self._rollback_count,
                "observation_count": self._observation_count,
                "erasure_count": self._erasure_count,
            },
            "transition_crossovers": copy.deepcopy(self._crossover_records),
            "transition_crossover_stream": {
                "tail_start": self._crossover_tail_start,
                "tail_real": self._crossover_tail.real.tolist(),
                "tail_imag": self._crossover_tail.imag.tolist(),
                "previous_observation": (
                    None
                    if self._previous_observation is None
                    else {
                        "symbol_index": int(
                            self._previous_observation.symbol_index
                        ),
                        "input_interval": [
                            int(value) for value in
                            self._previous_observation.input_interval
                        ],
                        "log_metrics": [
                            float(value) for value in
                            self._previous_observation.log_metrics
                        ],
                        "winner_runner_up_margin_nats": (
                            self._previous_observation
                            .winner_runner_up_margin_nats
                        ),
                        "noise_log_metric": (
                            self._previous_observation.noise_log_metric
                        ),
                        "erased": bool(self._previous_observation.erased),
                    }
                ),
            },
        }

    def state_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.checkpoint(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

    @classmethod
    def restore(
        cls,
        checkpoint: dict[str, Any],
        *,
        frequency_track: FrequencyTrack,
        clock_track: ClockTrack,
    ) -> P11DTextEvidencePass:
        if checkpoint.get("schema") != cls.SCHEMA:
            raise ValueError("unsupported P11D text-pass checkpoint")
        configuration = checkpoint["configuration"]
        instance = cls(
            sample_rate=float(configuration["sample_rate"]),
            tone_spacing_hz=float(configuration["tone_spacing_hz"]),
            frequency_track=frequency_track,
            clock_track=clock_track,
            orientation=str(configuration["orientation"]),
            initial_state=checkpoint["receiver"].get("initial_state"),
            traceback_depth=int(checkpoint["receiver"]["traceback_depth"]),
            sustained_loss_symbols=int(
                checkpoint["receiver"]["sustained_loss_symbols"]
            ),
            erasure_policy=str(configuration.get("erasure_policy", "measure")),
        )
        instance._restore_in_place(checkpoint)
        return instance

    def diagnostics(self) -> dict[str, Any]:
        return {
            "organization": "one_sequential_transactional_text_evidence_pass",
            "traceback_depth": 384,
            "requested_samples": self._requested_samples,
            "chunk_count": self._chunk_count,
            "rollback_count": self._rollback_count,
            "observation_count": self._observation_count,
            "erasure_count": self._erasure_count,
            "erasure_policy": self.erasure_policy,
            "maximum_retained_iq_samples": self._observer.maximum_retained_samples,
            "uncommitted_decoded_bits": self._receiver.uncommitted_decoded_bits,
            "epoch": self._receiver.epoch,
            "state_digest": self.state_digest(),
        }

    def transition_clock_before(
        self, input_stop: int, *, input_start: int | None = None
    ) -> tuple[
        ClockTrack | None,
        dict[str, Any],
        tuple[tuple[float, float], tuple[float, float]] | None,
    ]:
        eligible = [
            record for record in self._crossover_records
            if (
                input_start is None
                or float(record["nominal_boundary_input_sample"]) >= input_start
            )
            and float(record["nominal_boundary_input_sample"]) <= input_stop
        ]
        if len(eligible) > 128:
            indices = np.linspace(0, len(eligible) - 1, 128, dtype=np.int64)
            eligible = [eligible[int(index)] for index in indices]
        return _fit_precomputed_transition_clock(
            eligible, nominal_symbol_samples=self.clock_track.samples_per_symbol
        )

    def _restore_in_place(self, checkpoint: dict[str, Any]) -> None:
        configuration = checkpoint.get("configuration", {})
        if configuration.get("frequency_track") != self.frequency_track.to_dict():
            raise ValueError("P11D frequency track changed")
        if configuration.get("clock_track") != self.clock_track.to_dict():
            raise ValueError("P11D clock track changed")
        self._observer = FixedTrackToneObserver.restore(
            checkpoint["observer"],
            sample_rate=self.sample_rate,
            frequency_track=self.frequency_track,
            clock_track=self.clock_track,
            tone_spacing_hz=self.tone_spacing_hz,
        )
        self._receiver = StatefulBoundedTextReceiver.restore(
            checkpoint["receiver"]
        )
        accounting = checkpoint["accounting"]
        self._requested_samples = int(accounting["requested_samples"])
        self._chunk_count = int(accounting["chunk_count"])
        self._rollback_count = int(accounting["rollback_count"])
        self._observation_count = int(accounting.get("observation_count", 0))
        self._erasure_count = int(accounting.get("erasure_count", 0))
        self._crossover_records = copy.deepcopy(
            checkpoint.get("transition_crossovers", [])
        )
        stream = checkpoint.get("transition_crossover_stream", {})
        tail_real = stream.get("tail_real", [])
        tail_imag = stream.get("tail_imag", [])
        self._crossover_tail = np.asarray(
            tail_real, dtype=np.float64
        ) + 1j * np.asarray(tail_imag, dtype=np.float64)
        tail_start = stream.get("tail_start")
        self._crossover_tail_start = (
            None if tail_start is None else int(tail_start)
        )
        previous = stream.get("previous_observation")
        self._previous_observation = (
            None
            if previous is None
            else StatefulToneObservation(
                symbol_index=int(previous["symbol_index"]),
                input_interval=tuple(previous["input_interval"]),
                log_metrics=tuple(previous["log_metrics"]),
                winner_runner_up_margin_nats=float(
                    previous["winner_runner_up_margin_nats"]
                ),
                noise_log_metric=float(previous["noise_log_metric"]),
                erased=bool(previous["erased"]),
            )
        )

    def _record_crossovers(
        self,
        samples: np.ndarray,
        *,
        input_start: int,
        observations: Sequence[Any],
    ) -> None:
        values = np.asarray(samples, dtype=np.complex128)
        if len(self._crossover_tail):
            if self._crossover_tail_start is None:
                raise AssertionError("transition tail has no source coordinate")
            analysis_samples = np.concatenate((self._crossover_tail, values))
            analysis_start = self._crossover_tail_start
        else:
            analysis_samples = values
            analysis_start = input_start
        sequence = list(observations)
        if self._previous_observation is not None:
            sequence.insert(0, self._previous_observation)
        for previous, current in zip(sequence, sequence[1:]):
            if previous.erased or current.erased:
                continue
            previous_metrics = np.asarray(previous.log_metrics, dtype=np.float64)
            current_metrics = np.asarray(current.log_metrics, dtype=np.float64)
            previous_ordered = np.sort(previous_metrics)
            current_ordered = np.sort(current_metrics)
            margin = min(
                float(previous_ordered[-1] - previous_ordered[-2]),
                float(current_ordered[-1] - current_ordered[-2]),
            )
            old_tone = int(np.argmax(previous_metrics))
            new_tone = int(np.argmax(current_metrics))
            if old_tone == new_tone or margin < np.log(1.08):
                continue
            nominal_boundary = 0.5 * (
                previous.input_interval[1] + current.input_interval[0]
            )
            center_hz = float(self.frequency_track.center_at(nominal_boundary))
            old_frequency = center_hz + (old_tone - 7.5) * self.tone_spacing_hz
            new_frequency = center_hz + (new_tone - 7.5) * self.tone_spacing_hz
            nominal = self.clock_track.samples_per_symbol
            crossing = _tone_crossover(
                analysis_samples,
                input_start=analysis_start,
                nominal_boundary=nominal_boundary,
                sample_rate=self.sample_rate,
                old_frequency_hz=old_frequency,
                new_frequency_hz=new_frequency,
                window_samples=max(8, int(round(nominal / 2.0))),
                radius_samples=max(4, int(np.ceil(nominal / 2.0))),
            )
            self._crossover_records.append({
                "symbol_index": int(current.symbol_index),
                "nominal_boundary_input_sample": float(nominal_boundary),
                "crossover_input_sample": (
                    None if crossing is None else float(crossing)
                ),
                "old_tone": old_tone,
                "new_tone": new_tone,
                "margin_log_ratio": margin,
                "base_weight": float(
                    abs(new_frequency - old_frequency) ** 2 * margin
                ),
            })
        if len(self._crossover_records) > 32_768:
            self._crossover_records = self._crossover_records[-32_768:]
        if observations:
            self._previous_observation = observations[-1]
        retain = min(len(analysis_samples), int(np.ceil(
            2.0 * self.clock_track.samples_per_symbol
        )))
        self._crossover_tail = analysis_samples[-retain:].copy()
        self._crossover_tail_start = analysis_start + len(analysis_samples) - retain


class StatefulBoundedTextReceiver:
    """Transactional C9-C12 spike driven by committed C7 tone observations."""

    SCHEMA = "grampy.stateful-text-receiver-checkpoint.v1"

    def __init__(
        self,
        *,
        orientation: str,
        initial_state: int | None = 0,
        traceback_depth: int = 384,
        sustained_loss_symbols: int = 12,
        mode: str | None = None,
    ) -> None:
        if orientation not in {"normal", "reverse"}:
            raise ValueError("stateful text receiver requires a fixed orientation")
        if sustained_loss_symbols < 1:
            raise ValueError("sustained-loss threshold must be positive")
        self.orientation = orientation
        self.traceback_depth = int(traceback_depth)
        self.sustained_loss_symbols = int(sustained_loss_symbols)
        self.initial_state = initial_state
        if mode not in {None, "MFSK32", "MFSK64"}:
            raise ValueError("stateful text receiver mode is invalid")
        self.mode = mode
        self._epoch = 1
        self._event_count = 0
        self._reset_modem(initial_state=initial_state)
        self._loss_count = 0
        self._loss_start: int | None = None
        self._loss_stop: int | None = None
        self._loss_declared = False
        self._safe_modem: dict[str, Any] | None = None
        self._provisional_events: list[dict[str, Any]] = []
        self._provisional_headers: list[dict[str, Any]] = []

    @property
    def epoch(self) -> int:
        return self._epoch

    @property
    def uncommitted_decoded_bits(self) -> int:
        return self._viterbi.uncommitted_count

    def push(self, observations: Sequence[Any]) -> StatefulTextResult:
        text_events: list[dict[str, Any]] = []
        picture_headers: list[dict[str, Any]] = []
        reset_events: list[dict[str, Any]] = []
        for observation in observations:
            interval = tuple(int(value) for value in observation.input_interval)
            erased = bool(observation.erased)
            if erased:
                if self._loss_count == 0:
                    self._safe_modem = self._modem_checkpoint()
                    self._loss_start = interval[0]
                    self._provisional_events = []
                    self._provisional_headers = []
                self._loss_count += 1
                self._loss_stop = interval[1]
                if self._loss_count < self.sustained_loss_symbols:
                    events, headers = self._process(observation)
                    self._provisional_events.extend(events)
                    self._provisional_headers.extend(headers)
                elif self._loss_count == self.sustained_loss_symbols:
                    if self._safe_modem is None:
                        raise AssertionError("loss transaction has no safe checkpoint")
                    self._restore_modem(self._safe_modem)
                    self._provisional_events = []
                    self._provisional_headers = []
                    self._loss_declared = True
                    reset_events.append(
                        {
                            "cause": "sustained_signal_loss",
                            "affected_interval": {
                                "start": self._loss_start,
                                "stop": self._loss_stop,
                            },
                            "discarded_state": [
                                "deinterleaver",
                                "fec_survivors",
                                "varicode",
                                "picture_header_scanner",
                                "provisional_events",
                            ],
                            "prior_epoch": self._epoch,
                        }
                    )
                continue

            if self._loss_declared:
                self._epoch += 1
                reset_events.append(
                    {
                        "cause": "signal_recovered",
                        "affected_interval": {
                            "start": self._loss_start,
                            "stop": self._loss_stop,
                        },
                        "new_epoch": self._epoch,
                        "fec_initial_state": "unknown_midstream",
                    }
                )
                self._reset_modem(initial_state=None)
                self._clear_loss()
            elif self._loss_count:
                events, headers = self._process(observation)
                self._provisional_events.extend(events)
                self._provisional_headers.extend(headers)
                text_events.extend(self._provisional_events)
                picture_headers.extend(self._provisional_headers)
                self._clear_loss()
                continue

            events, headers = self._process(observation)
            text_events.extend(events)
            picture_headers.extend(headers)
        return StatefulTextResult(
            tuple(text_events), tuple(picture_headers), tuple(reset_events)
        )

    def finish_epoch(self) -> StatefulTextResult:
        committed = self._viterbi.finish()
        events, headers = self._frame_bits(committed, decision_stop=None)
        return StatefulTextResult(tuple(events), tuple(headers), ())

    def close_epoch(
        self,
        cause: str,
        *,
        affected_interval: tuple[int, int] | None = None,
        reopen: bool = True,
        initial_state: int | None = None,
    ) -> StatefulTextResult:
        """Commit an epoch tail only at a semantic P11D boundary.

        Administrative input chunks must use :meth:`push` and checkpoints;
        they are deliberately not accepted as closure causes.
        """
        if cause not in {"picture", "mode_change", "sustained_loss", "caller_cut"}:
            raise ValueError("unsupported text epoch closure cause")
        tail = self.finish_epoch()
        reset = {
            "cause": cause,
            "prior_epoch": self._epoch,
            "affected_interval": (
                {"start": affected_interval[0], "stop": affected_interval[1]}
                if affected_interval is not None else None
            ),
            "committed_tail_event_count": len(tail.text_events),
        }
        if reopen:
            self._epoch += 1
            self._reset_modem(initial_state=initial_state)
            self._clear_loss()
            reset["new_epoch"] = self._epoch
            reset["fec_initial_state"] = (
                "known_zero" if initial_state == 0 else "unknown_midstream"
            )
        return StatefulTextResult(
            tail.text_events,
            tail.picture_headers,
            (reset,),
        )

    def checkpoint(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "orientation": self.orientation,
            "traceback_depth": self.traceback_depth,
            "initial_state": self.initial_state,
            "mode": self.mode,
            "sustained_loss_symbols": self.sustained_loss_symbols,
            "epoch": self._epoch,
            "event_count": self._event_count,
            "modem": self._modem_checkpoint(),
            "loss_count": self._loss_count,
            "loss_start": self._loss_start,
            "loss_stop": self._loss_stop,
            "loss_declared": self._loss_declared,
            "safe_modem": copy.deepcopy(self._safe_modem),
            "provisional_events": copy.deepcopy(self._provisional_events),
            "provisional_headers": copy.deepcopy(self._provisional_headers),
        }

    def state_digest(self) -> str:
        encoded = json.dumps(
            self.checkpoint(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def restore(cls, checkpoint: dict[str, Any]) -> StatefulBoundedTextReceiver:
        if checkpoint.get("schema") != cls.SCHEMA:
            raise ValueError("unsupported stateful text receiver checkpoint")
        instance = cls(
            orientation=str(checkpoint["orientation"]),
            initial_state=checkpoint.get("initial_state"),
            traceback_depth=int(checkpoint["traceback_depth"]),
            sustained_loss_symbols=int(checkpoint["sustained_loss_symbols"]),
            mode=checkpoint.get("mode"),
        )
        instance._epoch = int(checkpoint["epoch"])
        instance._event_count = int(checkpoint["event_count"])
        instance._restore_modem(checkpoint["modem"])
        instance._loss_count = int(checkpoint["loss_count"])
        instance._loss_start = checkpoint.get("loss_start")
        instance._loss_stop = checkpoint.get("loss_stop")
        instance._loss_declared = bool(checkpoint["loss_declared"])
        instance._safe_modem = copy.deepcopy(checkpoint.get("safe_modem"))
        instance._provisional_events = copy.deepcopy(
            checkpoint["provisional_events"]
        )
        instance._provisional_headers = copy.deepcopy(
            checkpoint["provisional_headers"]
        )
        return instance

    def _process(
        self, observation: Any
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        interval = tuple(int(value) for value in observation.input_interval)
        metrics = np.asarray(observation.log_metrics, dtype=np.float64)
        if metrics.shape != (16,):
            raise ValueError("stateful receiver requires sixteen-tone evidence")
        if self.orientation == "reverse":
            metrics = metrics[::-1]
        group = self._deinterleaver.push(
            np.zeros(4) if observation.erased else tone_metrics_to_llrs(metrics),
            valid=not bool(observation.erased),
        )
        self._tone_intervals.append(interval)
        self._tone_intervals = self._tone_intervals[-31:]
        lane_intervals: list[tuple[int, int] | None] = []
        for delay in (30, 20, 10, 0):
            lane_intervals.append(
                self._tone_intervals[-1 - delay]
                if len(self._tone_intervals) > delay
                else None
            )
        for lanes in ((0, 1), (2, 3)):
            contributing = [
                lane_intervals[lane]
                for lane in lanes
                if lane_intervals[lane] is not None
            ]
            self._uncommitted_source_spans.append(
                (
                    (
                        min(value[0] for value in contributing),
                        max(value[1] for value in contributing),
                    )
                    if contributing
                    else interval,
                    len(contributing) == len(lanes),
                )
            )
        committed = self._viterbi.push(group)
        return self._frame_bits(committed, decision_stop=interval[1])

    def _frame_bits(
        self, committed: Sequence[Any], *, decision_stop: int | None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        source_intervals = []
        source_complete = []
        for _ in committed:
            if not self._uncommitted_source_spans:
                raise AssertionError("committed FEC bit has no source span")
            (start, stop), complete = self._uncommitted_source_spans.pop(0)
            source_intervals.append((start, stop))
            source_complete.append(complete)
        events: list[dict[str, Any]] = []
        headers: list[dict[str, Any]] = []
        for committed_item, source_interval, complete in zip(
            committed, source_intervals, source_complete
        ):
            flush_before = self._flush_encoder.checkpoint()
            flush_complete_before = self._flush_state_complete
            self._flush_encoder.push([committed_item.bit])
            self._flush_bits_since_reset += 1
            if self._flush_bits_since_reset >= 60:
                self._flush_state_complete = True
            confidence = (
                0.0
                if committed_item.decision_path_metric_gap is None
                else committed_item.decision_path_metric_gap
                / (1.0 + committed_item.decision_path_metric_gap)
            )
            parsed = self._parser.push(
                [committed_item.bit],
                [confidence],
                source_intervals=[source_interval],
                source_complete=[complete],
            )
            for item in parsed:
                self._event_count += 1
                event = {
                    "id": f"text-{self._event_count:06d}",
                    "octet": item.octet,
                    "codeword": item.codeword,
                    "confidence": {
                        "value": item.confidence,
                        "calibrated": False,
                    },
                    "damage_flags": [] if item.octet is not None else ["invalid_varicode"],
                    "source_bit_interval": {
                        "start": item.source_bit_interval[0],
                        "stop": item.source_bit_interval[1],
                    },
                    "recognized_at_bit": item.recognized_at_bit,
                    "source_input_interval": (
                        {
                            "start": item.source_input_interval[0],
                            "stop": item.source_input_interval[1],
                        }
                        if item.source_input_interval is not None
                        else None
                    ),
                    "source_coordinate_status": (
                        "complete"
                        if item.source_input_complete
                        else "partial_deinterleaver_fill"
                    ),
                    "text_epoch": self._epoch,
                    "decision_available_at_input_sample": decision_stop,
                }
                events.append(event)
                accepted, _ = self._scanner.push([event])
                for header in accepted:
                    header["text_epoch"] = self._epoch
                    header["header_decoded_bit_stop"] = item.source_bit_interval[1]
                    if self.mode is not None and flush_complete_before:
                        tones = StatefulPictureFlushEncoder.restore(
                            flush_before
                        ).predict_flush(self.mode)
                        header["picture_flush_tones"] = tones
                        event["picture_flush_tones"] = tones
                    else:
                        header["picture_flush_tones"] = None
                    headers.append(header)
        return events, headers

    def _reset_modem(self, *, initial_state: int | None) -> None:
        self._deinterleaver = SoftDeinterleaver()
        self._viterbi = StatefulSoftViterbiDecoder(
            initial_state=initial_state, traceback_depth=self.traceback_depth
        )
        self._parser = StatefulVaricodeParser()
        self._scanner = PictureHeaderScanner()
        self._flush_encoder = StatefulPictureFlushEncoder()
        self._flush_bits_since_reset = 0
        self._flush_state_complete = initial_state == 0
        self._tone_intervals: list[tuple[int, int]] = []
        self._uncommitted_source_spans: list[
            tuple[tuple[int, int], bool]
        ] = []

    def _modem_checkpoint(self) -> dict[str, Any]:
        return {
            "deinterleaver": self._deinterleaver.checkpoint(),
            "viterbi": self._viterbi.checkpoint(),
            "varicode": self._parser.checkpoint(),
            "header_scanner": self._scanner.checkpoint(),
            "flush_encoder": self._flush_encoder.checkpoint(),
            "flush_bits_since_reset": self._flush_bits_since_reset,
            "flush_state_complete": self._flush_state_complete,
            "tone_intervals": [list(value) for value in self._tone_intervals],
            "uncommitted_source_spans": [
                [value[0][0], value[0][1], value[1]]
                for value in self._uncommitted_source_spans
            ],
            "event_count": self._event_count,
        }

    def _restore_modem(self, checkpoint: dict[str, Any]) -> None:
        self._deinterleaver = SoftDeinterleaver.restore(checkpoint["deinterleaver"])
        self._viterbi = StatefulSoftViterbiDecoder.restore(checkpoint["viterbi"])
        self._parser = StatefulVaricodeParser()
        self._parser.restore(checkpoint["varicode"])
        self._scanner = PictureHeaderScanner.restore(checkpoint["header_scanner"])
        self._flush_encoder = StatefulPictureFlushEncoder.restore(
            checkpoint.get("flush_encoder", StatefulPictureFlushEncoder().checkpoint())
        )
        self._flush_bits_since_reset = int(checkpoint.get("flush_bits_since_reset", 0))
        self._flush_state_complete = bool(
            checkpoint.get("flush_state_complete", self.initial_state == 0)
        )
        self._tone_intervals = [
            (int(value[0]), int(value[1]))
            for value in checkpoint["tone_intervals"]
        ]
        self._uncommitted_source_spans = [
            ((int(value[0]), int(value[1])), bool(value[2]))
            for value in checkpoint["uncommitted_source_spans"]
        ]
        self._event_count = int(checkpoint["event_count"])

    def _clear_loss(self) -> None:
        self._loss_count = 0
        self._loss_start = None
        self._loss_stop = None
        self._loss_declared = False
        self._safe_modem = None
        self._provisional_events = []
        self._provisional_headers = []


@dataclass(frozen=True)
class _TraceToneObservation:
    input_interval: tuple[int, int]
    log_metrics: tuple[float, ...]
    erased: bool


def compare_stateful_text_decode(
    decoded: Any, *, chunk_symbols: int = 137, traceback_depth: int = 48
) -> dict[str, Any]:
    """Compare a traced complete-region decode with the stateful C9-C12 spike."""
    if chunk_symbols < 1:
        raise ValueError("chunk_symbols must be positive")
    rows = decoded.diagnostics.get("tone_evidence", {}).get("symbols", [])
    available = decoded.diagnostics.get("tone_evidence", {}).get(
        "symbol_count", 0
    )
    if len(rows) != available:
        raise ValueError("comparison requires an untruncated full tone trace")
    startup = decoded.diagnostics["fec_evidence"]["initial_state"]
    receiver = StatefulBoundedTextReceiver(
        orientation=decoded.mode_segment["orientation"],
        initial_state=0 if startup == "known_zero" else None,
        traceback_depth=traceback_depth,
    )
    stateful_events: list[dict[str, Any]] = []
    stateful_headers: list[dict[str, Any]] = []
    resets: list[dict[str, Any]] = []
    maximum_uncommitted = 0
    for start in range(0, len(rows), chunk_symbols):
        observations = []
        for row in rows[start : start + chunk_symbols]:
            interval = row["input_interval"]
            observations.append(
                _TraceToneObservation(
                    input_interval=(int(interval["start"]), int(interval["stop"])),
                    log_metrics=tuple(float(value) for value in row["log_metrics"]),
                    erased=bool(row["erasure"]),
                )
            )
        result = receiver.push(observations)
        stateful_events.extend(result.text_events)
        stateful_headers.extend(result.picture_headers)
        resets.extend(result.reset_events)
        maximum_uncommitted = max(
            maximum_uncommitted, receiver.uncommitted_decoded_bits
        )
        receiver = StatefulBoundedTextReceiver.restore(receiver.checkpoint())
    tail = receiver.finish_epoch()
    stateful_events.extend(tail.text_events)
    stateful_headers.extend(tail.picture_headers)

    reference_signatures = [
        (
            event["octet"],
            event["codeword"],
            event["provenance"]["decoded_bit_interval"]["start"],
            event["provenance"]["decoded_bit_interval"]["stop"],
        )
        for event in decoded.text_events
    ]
    stateful_signatures = [
        (
            event["octet"],
            event["codeword"],
            event["source_bit_interval"]["start"],
            event["source_bit_interval"]["stop"],
        )
        for event in stateful_events
    ]
    coordinate_containment = 0
    for reference, stateful in zip(decoded.text_events, stateful_events):
        source = stateful.get("source_input_interval")
        wire = reference["wire_interval"]
        if (
            source is not None
            and source["start"] <= wire["start"]
            and wire["stop"] <= source["stop"]
        ):
            coordinate_containment += 1
    return {
        "reference_event_count": len(reference_signatures),
        "stateful_event_count": len(stateful_signatures),
        "event_signatures_exact": stateful_signatures == reference_signatures,
        "matching_signature_prefix": next(
            (
                index
                for index, pair in enumerate(
                    zip(reference_signatures, stateful_signatures)
                )
                if pair[0] != pair[1]
            ),
            min(len(reference_signatures), len(stateful_signatures)),
        ),
        "coordinate_containment_count": coordinate_containment,
        "picture_headers": [item["header_text"] for item in stateful_headers],
        "reset_events": resets,
        "maximum_uncommitted_decoded_bits": maximum_uncommitted,
        "traceback_depth": traceback_depth,
        "final_state_digest": receiver.state_digest(),
    }
