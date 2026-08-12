from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from .rsid import RsidDetection, detect_rsid

from .sigmf import SigmfRecording
from .text_decode import detect_mfsk_comb_hypotheses
from .tracking import FrequencyAnchor, FrequencyTrack


@dataclass(frozen=True)
class RegionEvidence:
    id: str
    interval_start: int
    interval_stop: int
    role: str
    threshold_basis: str
    guard_before_samples: int
    guard_after_samples: int
    detection_latency_samples: int
    occupied_low_hz: float
    occupied_high_hz: float
    signal_statistic_db: float
    noise_statistic_db: float | None
    clipping: bool | None
    dropout: bool | None
    interference: bool | None
    missed_merged_risk: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "interval": {"start": self.interval_start, "stop": self.interval_stop},
            "role": self.role,
            "threshold_basis": self.threshold_basis,
            "guard_context": {
                "before_samples": self.guard_before_samples,
                "after_samples": self.guard_after_samples,
            },
            "detection_latency_samples": self.detection_latency_samples,
            "band_statistics": {
                "occupied_low_hz": self.occupied_low_hz,
                "occupied_high_hz": self.occupied_high_hz,
                "signal_statistic_db": self.signal_statistic_db,
                "noise_statistic_db": self.noise_statistic_db,
            },
            "flags": {
                "clipping": self.clipping,
                "dropout": self.dropout,
                "interference": self.interference,
            },
            "missed_merged_risk": self.missed_merged_risk,
        }


@dataclass(frozen=True)
class AcquisitionResult:
    regions: tuple[RegionEvidence, ...]
    mode_hypotheses: tuple[dict[str, Any], ...]
    mode_segments: tuple[dict[str, Any], ...]
    frequency_tracks: tuple[FrequencyTrack, ...]


def acquire_modes(
    recording: SigmfRecording,
    *,
    threshold_db: float = 10.0,
    search_low_hz: float = 300.0,
    search_high_hz: float = 3000.0,
) -> AcquisitionResult:
    """Run the shared bounded RSID detector and form initial C2-C4 evidence."""
    detections = detect_rsid(
        data_path=recording.data_path,
        datatype=recording.datatype,
        sample_rate=int(recording.sample_rate),
        start_sample=recording.requested_start,
        stop_sample=recording.requested_stop,
        nominal_center_hz=1582.0,
        threshold_db=threshold_db,
        search_low_hz=search_low_hz,
        search_high_hz=search_high_hz,
        mode_hint=None,
    )
    relevant = [item for item in detections if item.mode in {"MFSK32", "MFSK64"}]
    hypotheses: tuple[dict[str, Any], ...] = tuple(
        _mode_hypothesis(item, event_order=index + 1)
        for index, item in enumerate(relevant)
    )
    if not relevant:
        comb_hypotheses: list[dict[str, Any]] = []
        for block_start, block in recording.iter_complex64(262_144):
            comb_hypotheses.extend(
                detect_mfsk_comb_hypotheses(
                    block,
                    input_start=block_start,
                    sample_rate=recording.sample_rate,
                )
            )
        hypotheses = tuple(
            _comb_mode_hypothesis(item, event_order=index + 1)
            for index, item in enumerate(comb_hypotheses)
        )
    regions = tuple(_region_for_detection(recording, item, index) for index, item in enumerate(relevant))
    segments = tuple(_segments(relevant, recording.requested_start, recording.requested_stop))
    tracks = (FrequencyTrack(
        tuple(
            FrequencyAnchor(
                input_sample=item.sample_start + item.sample_count // 2,
                center_hz=item.center_hz,
                uncertainty_hz=item.uncertainty_hz,
                source=f"rsid:{item.rsid_code}",
            )
            for item in relevant
        ),
        breakpoints=tuple(item.sample_start for item in relevant[1:]),
    ),) if relevant else ()
    return AcquisitionResult(regions, hypotheses, segments, tracks)


def _comb_mode_hypothesis(
    item: dict[str, Any], *, event_order: int
) -> dict[str, Any]:
    return {
        "id": _stable_id(
            "comb-mode-hypothesis",
            item["interval"]["start"],
            item["mode"],
            item["orientation"],
        ),
        "event_order": event_order,
        "rank": item["rank"],
        "mode": item["mode"],
        "orientation": item["orientation"],
        "event_interval": item["interval"],
        "interval_uncertainty_samples": max(
            1, item["interval"]["stop"] - item["interval"]["start"]
        ),
        "prior": {"kind": "missing-rsid", "log_weight": 0.0},
        "confidence": {
            "kind": item["score_kind"],
            "value": item["score"],
            "calibrated": False,
        },
        "evidence": {
            "source": item["source"],
            "center_hz": item["center_hz"],
            "center_uncertainty_hz": item["center_uncertainty_hz"],
            "persistence_symbols": item["persistence_symbols"],
            **item["evidence"],
        },
        "status": "competing",
    }


def _mode_hypothesis(item: RsidDetection, *, event_order: int) -> dict[str, Any]:
    event_id = _stable_id("mode-hypothesis", item.sample_start, item.mode, item.rsid_code)
    return {
        "id": event_id,
        "event_order": event_order,
        "rank": 1,
        "mode": item.mode,
        "orientation": item.orientation,
        "event_interval": {
            "start": item.sample_start,
            "stop": item.sample_start + item.sample_count,
        },
        "interval_uncertainty_samples": max(1, item.sample_count // 15),
        "prior": {"kind": "unhinted", "log_weight": 0.0},
        "confidence": {
            "kind": "detector_snr_db",
            "value": item.confidence_db,
            "calibrated": False,
        },
        "evidence": {
            "source": "shared-bounded-rsid-detector",
            "rsid_code": item.rsid_code,
            "code_distance": item.rsid_code_distance,
            "tones": item.tones,
            "center_hz": item.center_hz,
            "center_uncertainty_hz": item.uncertainty_hz,
        },
        "status": "accepted",
    }


def _region_for_detection(
    recording: SigmfRecording, item: RsidDetection, index: int
) -> RegionEvidence:
    guard = int(round(recording.sample_rate * 0.75))
    start = max(recording.requested_start, item.sample_start - guard)
    stop = min(recording.requested_stop, item.sample_start + item.sample_count + guard)
    half_band = 8.0 * 11025.0 / 1024.0
    return RegionEvidence(
        id=_stable_id("region", item.sample_start, index),
        interval_start=start,
        interval_stop=stop,
        role="rsid_acquisition",
        threshold_basis="validated RSID codeword distance <= 2 and detector SNR threshold",
        guard_before_samples=item.sample_start - start,
        guard_after_samples=stop - item.sample_start - item.sample_count,
        detection_latency_samples=item.sample_count,
        occupied_low_hz=item.center_hz - half_band,
        occupied_high_hz=item.center_hz + half_band,
        signal_statistic_db=item.confidence_db,
        noise_statistic_db=None,
        clipping=None,
        dropout=None,
        interference=None,
        missed_merged_risk="RSID-only proposal; text without a nearby RSID may be missed",
    )


def _segments(
    detections: list[RsidDetection], requested_start: int, requested_stop: int
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, item in enumerate(detections):
        start = item.sample_start + item.sample_count
        stop = detections[index + 1].sample_start if index + 1 < len(detections) else requested_stop
        if stop <= start:
            continue
        result.append({
            "id": _stable_id("mode-segment", item.sample_start, item.mode),
            "mode": item.mode,
            "orientation": item.orientation,
            "interval": {"start": start, "stop": stop},
            "endpoint_uncertainty_samples": item.sample_count,
            "source": "rsid",
            "confidence": {
                "kind": "detector_snr_db",
                "value": item.confidence_db,
                "calibrated": False,
            },
            "supporting_events": [
                _stable_id("mode-hypothesis", item.sample_start, item.mode, item.rsid_code)
            ],
            "acquisition_state": "candidate",
            "symbol_phase_uncertainty_input_samples": item.sample_count // 15,
            "superseded_alternatives": [],
            "center_hz": item.center_hz,
            "frequency_track": 0,
        })
    return result


def _stable_id(*parts: object) -> str:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]
