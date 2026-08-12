from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

from .pipeline import DecodeConfig, run_reference_pipeline, write_manifest_atomic
from .sigmf import InputError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mfsk-iq-decode",
        description="Decode MFSK text and pictures directly from SigMF IQ.",
    )
    parser.add_argument("--in-meta", required=True, type=Path)
    parser.add_argument("--in-data", required=True, type=Path)
    parser.add_argument("--out-manifest", required=True, type=Path)
    parser.add_argument("--start-sample", type=int)
    parser.add_argument("--stop-sample", type=int)
    parser.add_argument("--block-samples", type=int, default=262_144)
    parser.add_argument(
        "--mode", choices=("auto", "MFSK32", "MFSK64"), default="MFSK32"
    )
    parser.add_argument("--center-hz", type=float)
    parser.add_argument(
        "--orientation", choices=("normal", "reverse", "unknown"), default="unknown"
    )
    parser.add_argument(
        "--trace-level",
        choices=("none", "summary", "events", "full"),
        default="none",
    )
    parser.add_argument(
        "--picture-component-estimator",
        choices=("fft_peak", "phase_difference", "bounded_correlation"),
        default="bounded_correlation",
    )
    parser.add_argument(
        "--picture-component-window",
        choices=("center_crop", "full", "full_hann"),
        default="full_hann",
    )
    parser.add_argument(
        "--picture-filter-profile",
        choices=("current_wide", "response_matched"),
        default="response_matched",
    )
    parser.add_argument(
        "--picture-boundary-estimator",
        choices=("unified_grid",),
        default="unified_grid",
    )
    parser.add_argument(
        "--persistent-tone-policy",
        choices=("measure", "suppress"),
        default="measure",
    )
    parser.add_argument(
        "--pipeline-organization",
        choices=("supported_hybrid", "p11d", "independent_window_oracle"),
        default="supported_hybrid",
    )
    parser.add_argument("--picture-range-workers", type=int, default=1)
    parser.add_argument("--picture-range-components", type=int, default=16_384)
    parser.add_argument("--picture-max-in-flight-ranges", type=int, default=1)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = DecodeConfig(
            block_samples=args.block_samples,
            orientation=args.orientation,
            trace_level=args.trace_level,
            mode=args.mode,
            center_hz=args.center_hz,
            picture_component_estimator=args.picture_component_estimator,
            picture_component_window=args.picture_component_window,
            picture_filter_profile=args.picture_filter_profile,
            picture_boundary_estimator=args.picture_boundary_estimator,
            persistent_tone_policy=args.persistent_tone_policy,
            pipeline_organization=args.pipeline_organization,
            picture_range_workers=args.picture_range_workers,
            picture_range_components=args.picture_range_components,
            picture_max_in_flight_ranges=args.picture_max_in_flight_ranges,
        )
        manifest = run_reference_pipeline(
            meta_path=args.in_meta,
            data_path=args.in_data,
            start_sample=args.start_sample,
            stop_sample=args.stop_sample,
            config=config,
            artifact_dir=args.out_manifest.parent
            / f"{args.out_manifest.stem}.artifacts",
            artifact_path_prefix=f"{args.out_manifest.stem}.artifacts",
        )
        write_manifest_atomic(args.out_manifest, manifest)
    except (InputError, ValueError) as error:
        _write_terminal_failure(args.out_manifest, args, error, 64)
        print(f"mfsk-iq-decode: {error}", file=sys.stderr)
        return 64
    except OSError as error:
        _write_terminal_failure(args.out_manifest, args, error, 74)
        print(f"mfsk-iq-decode: {error}", file=sys.stderr)
        return 74
    return 0


def _write_terminal_failure(
    path: Path, args: argparse.Namespace, error: Exception, exit_status: int
) -> None:
    """Atomically preserve terminal operational evidence when decode cannot start."""
    document = {
        "schema": "grampy-decode-terminal.v1",
        "status": "failed",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "metadata_path": str(args.in_meta),
            "data_path": str(args.in_data),
            "requested_interval": {
                "start": args.start_sample,
                "stop": args.stop_sample,
            },
        },
        "configuration": {
            "block_samples": args.block_samples,
            "mode": args.mode,
            "center_hz": args.center_hz,
            "orientation": args.orientation,
            "trace_level": args.trace_level,
            "picture_component_estimator": args.picture_component_estimator,
            "picture_component_window": args.picture_component_window,
            "picture_filter_profile": args.picture_filter_profile,
            "picture_boundary_estimator": args.picture_boundary_estimator,
            "persistent_tone_policy": args.persistent_tone_policy,
            "pipeline_organization": args.pipeline_organization,
            "picture_range_workers": args.picture_range_workers,
            "picture_range_components": args.picture_range_components,
            "picture_max_in_flight_ranges": args.picture_max_in_flight_ranges,
        },
        "terminal_failure": {
            "kind": type(error).__name__,
            "message": str(error),
            "exit_status": exit_status,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
