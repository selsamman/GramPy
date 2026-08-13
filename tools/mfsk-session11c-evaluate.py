#!/usr/bin/env python3
from __future__ import annotations

import argparse
import cProfile
from datetime import datetime, timezone
import json
from pathlib import Path
import pstats
import resource
import sys
import tempfile
import time

from grampy.sigmf import SigmfRecording
from grampy.stateful_pipeline import compare_stateful_text_decode
from grampy.text_decode import decode_mfsk_text


CASES = (
    {
        "id": "wrmi-20260708-mfsk64-text",
        "source": "wrmi-20260708T133006Z-15770000",
        "mode": "MFSK64",
        "start": 570 * 48_000,
        "stop": 630 * 48_000,
    },
    {
        "id": "wrmi-20260715-mfsk32-text",
        "source": "wrmi-20260715T133007Z-15770000",
        "mode": "MFSK32",
        "start": 90 * 48_000,
        "stop": 150 * 48_000,
    },
)
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the bounded Session 11C received-IQ equivalence spikes."
    )
    parser.add_argument(
        "--samples-root",
        type=Path,
        default=Path("tests/samples"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    results = []
    for case in CASES:
        stem = (
            args.samples_root
            / "received-corpus"
            / "sources"
            / case["source"]
            / "capture"
        )
        meta = stem.with_suffix(".sigmf-meta")
        data = stem.with_suffix(".sigmf-data")
        if not meta.is_file() or not data.is_file():
            raise FileNotFoundError(f"missing received source for {case['id']}: {stem}")
        recording = SigmfRecording.open(
            meta,
            data,
            start_sample=case["start"],
            stop_sample=case["stop"],
        )
        samples = recording.read_complex64(case["start"], case["stop"])
        profiler = cProfile.Profile()
        started = time.perf_counter()
        profiler.enable()
        decoded = decode_mfsk_text(
            samples,
            input_start=case["start"],
            sample_rate=recording.sample_rate,
            orientation_hint="unknown",
            trace_level="full",
            mode=case["mode"],
            fit_transition_clock=False,
        )
        profiler.disable()
        reference_seconds = time.perf_counter() - started

        trials = []
        for traceback_depth in (48, 96, 192, 384, 768, 1536, 4096, 8192):
            started = time.perf_counter()
            comparison = compare_stateful_text_decode(
                decoded, traceback_depth=traceback_depth
            )
            trials.append(
                {
                    "traceback_depth": traceback_depth,
                    "wall_seconds": time.perf_counter() - started,
                    "comparison": comparison,
                }
            )
            if comparison["event_signatures_exact"]:
                break
        selected_trial = trials[-1]
        results.append(
            {
                **case,
                "reference_wall_seconds": reference_seconds,
                "stateful_c9_c12_replay_wall_seconds": selected_trial[
                    "wall_seconds"
                ],
                "selected_orientation": decoded.mode_segment["orientation"],
                "selected_fec_startup": decoded.diagnostics["fec_evidence"][
                    "initial_state"
                ],
                "tone_symbol_count": decoded.diagnostics["tone_evidence"][
                    "symbol_count"
                ],
                "track_measurement": {
                    key: decoded.diagnostics["tone_evidence"]["frequency_track"].get(
                        key
                    )
                    for key in (
                        "measurement_window_count",
                        "measurement_requested_samples",
                        "measurement_maximum_block_samples",
                    )
                },
                "comparison": selected_trial["comparison"],
                "traceback_trials": trials,
                "profile_top_cumulative": _profile_rows(profiler, limit=24),
            }
        )

    document = {
        "schema": "grampy-session11c-spikes.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases": results,
        "all_event_signatures_exact": all(
            item["comparison"]["event_signatures_exact"] for item in results
        ),
        "peak_rss_bytes": _peak_rss_bytes(),
    }
    _atomic_json(args.output, document)
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["all_event_signatures_exact"] else 1


def _profile_rows(profiler: cProfile.Profile, *, limit: int) -> list[dict]:
    stats = pstats.Stats(profiler)
    rows = []
    for (filename, line, function), values in sorted(
        stats.stats.items(), key=lambda item: item[1][3], reverse=True
    )[:limit]:
        primitive_calls, total_calls, total_time, cumulative_time, _ = values
        rows.append(
            {
                "function": f"{Path(filename).name}:{line}:{function}",
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "self_seconds": total_time,
                "cumulative_seconds": cumulative_time,
            }
        )
    return rows


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
