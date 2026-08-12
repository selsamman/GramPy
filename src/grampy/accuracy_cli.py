from __future__ import annotations

import argparse
from collections.abc import Iterable
import hashlib
import json
from pathlib import Path
import sys

from .accuracy import (
    align_component_streams,
    extract_framed_payload,
    load_png_raster,
    load_png_wire_components,
    normalize_presentation_text,
    score_mode_sequence,
    score_raw_rasters,
    score_text,
)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="mfsk-accuracy")
    commands = result.add_subparsers(dest="command", required=True)

    text = commands.add_parser("text", help="score decoded text against truth")
    text.add_argument("--truth", required=True, type=Path)
    text.add_argument("--decoded", required=True, type=Path)
    text.add_argument("--decoded-framing", choices=("stx-eot", "none"), default="stx-eot")
    text.add_argument("--output", required=True, type=Path)

    picture = commands.add_parser(
        "picture", help="align and score a decoded PNG against pixel truth"
    )
    picture.add_argument("--truth", required=True, type=Path)
    picture.add_argument("--decoded", required=True, type=Path)
    picture.add_argument("--output", required=True, type=Path)
    picture.add_argument("--max-offset-components", type=int, default=24)
    picture.add_argument("--change-penalty", type=float, default=25.0)
    picture.add_argument("--offset-penalty", type=float, default=0.0005)

    program = commands.add_parser(
        "program-fldigi",
        help="produce a draft FLDIGI scorecard for one corpus transmission",
    )
    program.add_argument("--corpus", required=True, type=Path)
    program.add_argument("--program", required=True)
    program.add_argument("--transmission", required=True)
    program.add_argument(
        "--reference-id",
        default="fldigi-4.2.06",
        help="immutable reference directory (default: fldigi-4.2.06)",
    )
    program.add_argument(
        "--decoder-version",
        help="decoder version recorded in the scorecard (default: transmission record)",
    )
    program.add_argument("--output", required=True, type=Path)
    program.add_argument("--max-offset-components", type=int, default=24)
    program.add_argument("--change-penalty", type=float, default=25.0)
    program.add_argument("--offset-penalty", type=float, default=0.0005)
    program.add_argument(
        "--score-status",
        choices=("draft_metric_calibration", "frozen_session9a_baseline"),
        default="draft_metric_calibration",
    )

    direct = commands.add_parser(
        "program-direct",
        help="produce a draft scorecard from fixed MFSK32/MFSK64 manifests",
    )
    direct.add_argument("--corpus", required=True, type=Path)
    direct.add_argument("--program", required=True)
    direct.add_argument("--transmission", required=True)
    direct.add_argument("--mfsk32-manifest", required=True, type=Path)
    direct.add_argument("--mfsk64-manifest", required=True, type=Path)
    direct.add_argument("--output", required=True, type=Path)
    direct.add_argument("--max-offset-components", type=int, default=24)
    direct.add_argument("--change-penalty", type=float, default=25.0)
    direct.add_argument("--offset-penalty", type=float, default=0.0005)
    direct.add_argument(
        "--score-status",
        choices=("draft_metric_calibration", "frozen_session9a_baseline"),
        default="draft_metric_calibration",
    )

    summary = commands.add_parser(
        "baseline-summary",
        help="publish compact reproducibility records from full scorecards",
    )
    summary.add_argument("--score", required=True, action="append", type=Path)
    summary.add_argument("--source-revision", required=True)
    summary.add_argument("--output", required=True, type=Path)

    gate = commands.add_parser(
        "planning-gate",
        help="compute the versioned direct-versus-fldigi planning gate",
    )
    gate.add_argument("--baseline", required=True, type=Path)
    gate.add_argument("--policy", required=True, type=Path)
    gate.add_argument("--output", required=True, type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "text":
            reference = normalize_presentation_text(
                args.truth.read_text(encoding="utf-8")
            )
            decoded_raw = args.decoded.read_text(encoding="utf-8")
            if args.decoded_framing == "stx-eot":
                framed = extract_framed_payload(decoded_raw)
                decoded_raw = framed.text
                framing = framed.diagnostics()
            else:
                framing = None
            score = score_text(
                reference, normalize_presentation_text(decoded_raw)
            )
            score["framing_diagnostics"] = framing
        elif args.command == "picture":
            reference, reference_image = load_png_wire_components(str(args.truth))
            decoded, decoded_image = load_png_wire_components(str(args.decoded))
            score = align_component_streams(
                reference,
                decoded,
                max_offset=args.max_offset_components,
                change_penalty=args.change_penalty,
                offset_penalty=args.offset_penalty,
            )
            score["truth_image"] = reference_image
            score["decoded_image"] = decoded_image
            score["geometry_matches"] = reference_image == decoded_image
            reference_raster, _ = load_png_raster(str(args.truth))
            decoded_raster, _ = load_png_raster(str(args.decoded))
            score["raw_raster"] = score_raw_rasters(
                reference_raster, decoded_raster
            )
        elif args.command == "program-fldigi":
            score = _score_fldigi_program(args)
        elif args.command == "program-direct":
            score = _score_direct_program(args)
        elif args.command == "baseline-summary":
            score = _summarize_baseline(args)
        else:
            score = _compute_planning_gate(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(score, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"mfsk-accuracy: {error}", file=sys.stderr)
        return 1
    print(f"wrote {args.output}")
    return 0


def _score_fldigi_program(args: argparse.Namespace) -> dict[str, object]:
    program_root = args.corpus / "programs" / args.program
    program = json.loads((program_root / "program.json").read_text())
    transmission_path = (
        program_root / "transmissions" / f"{args.transmission}.json"
    )
    transmission = json.loads(transmission_path.read_text())
    reference_root = (
        args.corpus / "references" / args.transmission / args.reference_id
    )
    review = json.loads(
        (program_root / program["text_truth"]["review"]).read_text()
    )
    if review.get("status") == "approved" and review.get("truth_path"):
        text_truth_path = program_root / review["truth_path"]
        text_truth_status = "reviewed_truth"
    else:
        text_truth_path = program_root / review["published_draft"]["path"]
        text_truth_status = "draft_pending_pm_review"
    decoded_text = reference_root / "decoded.txt"
    framed = extract_framed_payload(decoded_text.read_text(encoding="utf-8"))
    text_result = score_text(
        normalize_presentation_text(text_truth_path.read_text(encoding="utf-8")),
        normalize_presentation_text(framed.text),
    )
    text_result["framing_diagnostics"] = framed.diagnostics()
    text_result["truth_status"] = text_truth_status

    decoded_images = sorted(
        (reference_root / "images").glob("[0-9][0-9][0-9]-*.png")
    )
    decoded_geometry = {}
    for path in decoded_images:
        _, geometry = load_png_wire_components(str(path))
        decoded_geometry[path] = geometry
    unmatched = set(decoded_images)
    matched_images = {}
    for expected in program["pictures"]:
        candidates = [
            path
            for path in decoded_images
            if path in unmatched
            and decoded_geometry[path]["width"] == expected["width"]
            and decoded_geometry[path]["height"] == expected["height"]
        ]
        if candidates:
            selected = candidates[0]
            matched_images[expected["order"]] = selected
            unmatched.remove(selected)
    pictures: list[dict[str, object]] = []
    scored_mae: list[float] = []
    for expected in program["pictures"]:
        order = expected["order"]
        item: dict[str, object] = {
            "order": order,
            "stable_id": expected["stable_id"],
            "expected_header": expected["expected_header"],
        }
        decoded_path = matched_images.get(order)
        if decoded_path is None:
            item["event_status"] = "missed"
            item["pixel_score"] = {
                "status": "not_scored_picture_missing",
                "reason": "decoder emitted no picture at this order",
            }
            pictures.append(item)
            continue
        geometry = decoded_geometry[decoded_path]
        item["event_status"] = "detected"
        item["decoded_artifact"] = str(decoded_path.relative_to(args.corpus))
        item["geometry_matches"] = (
            geometry["width"] == expected["width"]
            and geometry["height"] == expected["height"]
        )
        truth_artifact = expected.get("artifact")
        if expected["pixel_truth_status"] == "missing":
            item["pixel_score"] = {
                "status": "not_scored_missing_truth",
                "reason": expected["reason"],
            }
        elif not truth_artifact:
            item["pixel_score"] = {
                "status": "error_truth_artifact_missing",
                "reason": "available truth has no artifact record",
            }
        else:
            truth_path = program_root / truth_artifact["path"]
            if not truth_path.is_file():
                item["pixel_score"] = {
                    "status": "error_truth_artifact_missing",
                    "reason": str(truth_path),
                }
            else:
                aligned = _score_picture_pixels(
                    truth_path, decoded_path, expected, args
                )
                aligned["status"] = "scored"
                item["pixel_score"] = aligned
                scored_mae.append(aligned["aligned_mean_absolute_error_255"])
        pictures.append(item)
    extra_artifacts = [
        str(path.relative_to(args.corpus)) for path in decoded_images if path in unmatched
    ]
    return {
        "schema": "grampy-program-scorecard.v1",
        "status": args.score_status,
        "program_id": args.program,
        "transmission_id": args.transmission,
        "decoder": transmission["fldigi_reference"]["decoder"],
        "decoder_version": (
            args.decoder_version or transmission["fldigi_reference"]["version"]
        ),
        "decoder_reference_id": args.reference_id,
        "truth": _truth_summary(program),
        "transmission_observability": {
            "benchmark_role": transmission["benchmark_role"],
            "classification": "compatibility_reference_output",
            "receiver_family": _receiver_family(args.corpus, args.transmission),
        },
        "damage": {"status": "not_available_from_preserved_fldigi_artifacts"},
        "transitions": {
            "status": "not_available_from_preserved_fldigi_artifacts"
        },
        "operations": {
            "status": "not_available_from_preserved_fldigi_artifacts"
        },
        "text": text_result,
        "pictures": pictures,
        "picture_summary": {
            "expected": len(program["pictures"]),
            "detected": sum(p["event_status"] == "detected" for p in pictures),
            "missed": sum(p["event_status"] == "missed" for p in pictures),
            "extra": len(extra_artifacts),
            "extra_artifacts": extra_artifacts,
            "pixel_scored": len(scored_mae),
            "pixel_not_scored": len(program["pictures"]) - len(scored_mae),
            "mean_aligned_mae_255_over_scored_pictures": (
                sum(scored_mae) / len(scored_mae) if scored_mae else None
            ),
            **_aggregate_raw_raster_metrics(pictures),
        },
        "alignment_parameters": {
            "max_offset_components": args.max_offset_components,
            "change_penalty": args.change_penalty,
            "offset_penalty": args.offset_penalty,
        },
    }


def _score_direct_program(args: argparse.Namespace) -> dict[str, object]:
    manifests = [
        json.loads(args.mfsk32_manifest.read_text()),
        json.loads(args.mfsk64_manifest.read_text()),
    ]
    expected_modes = ("MFSK32", "MFSK64")
    for path, manifest, expected_mode in zip(
        (args.mfsk32_manifest, args.mfsk64_manifest),
        manifests,
        expected_modes,
        strict=True,
    ):
        actual_mode = manifest["decoder"]["configuration"]["mode"]
        if actual_mode != expected_mode:
            raise ValueError(
                f"{path}: expected {expected_mode} manifest, found {actual_mode}"
            )

    program_root = args.corpus / "programs" / args.program
    program = json.loads((program_root / "program.json").read_text())
    review = json.loads(
        (program_root / program["text_truth"]["review"]).read_text()
    )
    if review.get("status") != "approved" or not review.get("truth_path"):
        raise ValueError(f"program {args.program}: text truth is not approved")
    truth_text = normalize_presentation_text(
        (program_root / review["truth_path"]).read_text(encoding="utf-8")
    )
    acquisition_views = [
        [
            hypothesis
            for hypothesis in manifest["mode_hypotheses"]
            if hypothesis.get("status") == "accepted"
        ]
        for manifest in manifests
    ]
    acquisition_signatures = [
        [
            (
                hypothesis["mode"],
                hypothesis["event_interval"]["start"],
                hypothesis["event_interval"]["stop"],
            )
            for hypothesis in view
        ]
        for view in acquisition_views
    ]
    if acquisition_signatures[0] != acquisition_signatures[1]:
        raise ValueError("fixed-mode manifests disagree on automatic acquisition")
    detected_modes = [
        {
            "mode": hypothesis["mode"],
            "event_interval": hypothesis["event_interval"],
            "interval_uncertainty_samples": hypothesis[
                "interval_uncertainty_samples"
            ],
            "center_hz": hypothesis["evidence"]["center_hz"],
            "center_uncertainty_hz": hypothesis["evidence"][
                "center_uncertainty_hz"
            ],
            "rsid_code": hypothesis["evidence"]["rsid_code"],
            "code_distance": hypothesis["evidence"]["code_distance"],
            "confidence": hypothesis["confidence"],
        }
        for hypothesis in acquisition_views[0]
    ]
    mode_truth = program["mode_sequence_truth"]
    acquisition_result = score_mode_sequence(
        [event["mode"] for event in mode_truth["events"]],
        detected_modes,
    )
    acquisition_result["truth_status"] = mode_truth["status"]
    acquisition_result["truth_basis"] = mode_truth["basis"]

    picture_payload_intervals = []
    for manifest in manifests:
        for picture in manifest["pictures"]:
            selected_end = next(
                (
                    alternative["input_sample"]
                    for alternative in picture.get("end_alternatives", [])
                    if alternative.get("selected")
                ),
                None,
            )
            if selected_end is not None:
                picture_payload_intervals.append(
                    (picture["prologue_interval"]["start"], selected_end)
                )
    candidate_text_events = [
        event
        for manifest in manifests
        for event in manifest["text_events"]
        if event.get("octet") is not None
    ]
    text_events = sorted(
        (
            event
            for event in candidate_text_events
            if not any(
                start <= event["recognized_at_input_sample"] < stop
                for start, stop in picture_payload_intervals
            )
        ),
        key=lambda event: (
            event["recognized_at_input_sample"],
            event["id"],
        ),
    )
    decoded_octets = bytes(event["octet"] for event in text_events)
    decoded_text = decoded_octets.decode("latin-1")
    framed = extract_framed_payload(decoded_text)
    text_result = score_text(
        truth_text, normalize_presentation_text(framed.text)
    )
    text_result["framing_diagnostics"] = framed.diagnostics()
    text_result["truth_status"] = "reviewed_truth"
    text_result["composition"] = {
        "policy": "chronological_fixed_mode_event_merge",
        "status": "two_pass_diagnostic",
        "event_count": len(text_events),
        "picture_payload_events_excluded": (
            len(candidate_text_events) - len(text_events)
        ),
    }

    decoded_pictures: list[tuple[Path, dict[str, object]]] = []
    for manifest_path, manifest in zip(
        (args.mfsk32_manifest, args.mfsk64_manifest), manifests, strict=True
    ):
        artifact_by_id = {
            artifact["id"]: manifest_path.parent / artifact["path"]
            for artifact in manifest["artifacts"]
        }
        for picture in manifest["pictures"]:
            raster_id = picture.get("raster_artifact")
            if not raster_id or raster_id not in artifact_by_id:
                continue
            raster_path = artifact_by_id[raster_id]
            decoded_pictures.append((raster_path, picture))
    decoded_pictures.sort(
        key=lambda item: item[1]["first_raster_input_sample"]
    )

    pictures: list[dict[str, object]] = []
    scored_mae: list[float] = []
    decoded_index = 0
    for expected in program["pictures"]:
        item: dict[str, object] = {
            "order": expected["order"],
            "stable_id": expected["stable_id"],
            "expected_header": expected["expected_header"],
        }
        selected = None
        for index in range(decoded_index, len(decoded_pictures)):
            path, picture = decoded_pictures[index]
            if (
                picture["width"] == expected["width"]
                and picture["height"] == expected["height"]
                and picture["color"] == expected["color"]
            ):
                selected = (path, picture)
                decoded_index = index + 1
                break
        if selected is None:
            item["event_status"] = "missed"
            item["pixel_score"] = {
                "status": "not_scored_picture_missing",
                "reason": "decoder emitted no matching picture at this order",
            }
            pictures.append(item)
            continue

        decoded_path, picture = selected
        item["event_status"] = "detected"
        item["decoded_artifact"] = str(decoded_path)
        item["geometry_matches"] = True
        item["completion_status"] = (
            "complete" if picture["complete"] else "partial"
        )
        truth_artifact = expected.get("artifact")
        if expected["pixel_truth_status"] == "missing":
            item["pixel_score"] = {
                "status": "not_scored_missing_truth",
                "reason": expected["reason"],
            }
        elif not truth_artifact:
            item["pixel_score"] = {
                "status": "error_truth_artifact_missing",
                "reason": "available truth has no artifact record",
            }
        else:
            truth_path = program_root / truth_artifact["path"]
            aligned = _score_picture_pixels(
                truth_path, decoded_path, expected, args
            )
            aligned["status"] = "scored"
            item["pixel_score"] = aligned
            scored_mae.append(aligned["aligned_mean_absolute_error_255"])
        item["damage"] = _picture_damage(picture)
        item["transition"] = _picture_transition(
            picture, manifests[0]["input"]["sample_rate_hz"]
        )
        item["decoded_header"] = picture["header_text"]
        item["decoded_geometry"] = {
            "width": picture["width"],
            "height": picture["height"],
            "color": picture["color"],
            "samples_per_component": picture["samples_per_component"],
        }
        pictures.append(item)

    damage_summary = _aggregate_damage(pictures)
    transition_summary = _aggregate_transitions(pictures)
    return {
        "schema": "grampy-program-scorecard.v1",
        "status": args.score_status,
        "program_id": args.program,
        "transmission_id": args.transmission,
        "decoder": "radiogram-direct-iq",
        "decoder_version": manifests[0]["decoder"]["version"],
        "truth": _truth_summary(program),
        "transmission_observability": {
            "benchmark_role": json.loads(
                (
                    program_root
                    / "transmissions"
                    / f"{args.transmission}.json"
                ).read_text()
            )["benchmark_role"],
            "classification": "received_iq",
            "receiver_family": _receiver_family(args.corpus, args.transmission),
        },
        "execution_composition": {
            "status": "two_pass_diagnostic",
            "payload_manifests": {
                "MFSK32": str(args.mfsk32_manifest),
                "MFSK64": str(args.mfsk64_manifest),
            },
        },
        "acquisition": acquisition_result,
        "damage": damage_summary,
        "transitions": transition_summary,
        "operations": _direct_operations(
            manifests,
            (args.mfsk32_manifest, args.mfsk64_manifest),
        ),
        "text": text_result,
        "pictures": pictures,
        "picture_summary": {
            "expected": len(program["pictures"]),
            "detected": sum(p["event_status"] == "detected" for p in pictures),
            "missed": sum(p["event_status"] == "missed" for p in pictures),
            "pixel_scored": len(scored_mae),
            "pixel_not_scored": len(program["pictures"]) - len(scored_mae),
            "mean_aligned_mae_255_over_scored_pictures": (
                sum(scored_mae) / len(scored_mae) if scored_mae else None
            ),
            **_aggregate_raw_raster_metrics(pictures),
        },
        "alignment_parameters": {
            "max_offset_components": args.max_offset_components,
            "change_penalty": args.change_penalty,
            "offset_penalty": args.offset_penalty,
        },
    }


def _score_picture_pixels(
    truth_path: Path,
    decoded_path: Path,
    expected: dict[str, object],
    args: argparse.Namespace,
) -> dict[str, object]:
    truth, _ = load_png_wire_components(
        str(truth_path), expected_color=expected["color"]
    )
    decoded, _ = load_png_wire_components(
        str(decoded_path), expected_color=expected["color"]
    )
    aligned = align_component_streams(
        truth,
        decoded,
        max_offset=args.max_offset_components,
        change_penalty=args.change_penalty,
        offset_penalty=args.offset_penalty,
    )
    truth_raster, _ = load_png_raster(
        str(truth_path), expected_color=expected["color"]
    )
    decoded_raster, _ = load_png_raster(
        str(decoded_path), expected_color=expected["color"]
    )
    aligned["raw_raster"] = score_raw_rasters(truth_raster, decoded_raster)
    return aligned


def _truth_summary(program: dict[str, object]) -> dict[str, object]:
    pictures = program["pictures"]
    strengths: dict[str, int] = {}
    transmitter_input: dict[str, int] = {}
    for picture in pictures:
        strength = picture["pixel_truth_status"]
        strengths[strength] = strengths.get(strength, 0) + 1
        provenance = picture.get("exact_transmitter_input", "unknown")
        transmitter_input[provenance] = transmitter_input.get(provenance, 0) + 1
    return {
        "text": {
            "status": program["text_truth"]["status"],
            "artifact": program["text_truth"]["artifact"],
        },
        "pictures": {
            "expected": len(pictures),
            "pixel_truth_strength_counts": strengths,
            "transmitter_input_provenance_counts": transmitter_input,
        },
        "mode_sequence": program["mode_sequence_truth"],
    }


def _receiver_family(corpus: Path, transmission_id: str) -> str:
    capture_path = corpus / "sources" / transmission_id / "capture.capture.json"
    if not capture_path.is_file():
        return "unavailable"
    capture = json.loads(capture_path.read_text())
    profile = str(capture.get("capture_profile", ""))
    driver = str(capture.get("access_driver", ""))
    if profile.startswith("rtl_"):
        return "RTL-SDR"
    if driver == "libairspyhf" or profile.startswith("airspyhf_"):
        return "Airspy HF+"
    return "unavailable"


def _picture_damage(picture: dict[str, object]) -> dict[str, object]:
    damage = picture["damage_summary"]
    count = damage["component_count"]
    return {
        **damage,
        "clipped_fraction": damage["clipped_count"] / count if count else None,
        "unstable_frequency_fraction": (
            damage["unstable_frequency_count"] / count if count else None
        ),
    }


def _picture_transition(
    picture: dict[str, object], sample_rate_hz: float
) -> dict[str, object]:
    selected_end = next(
        (
            alternative["input_sample"]
            for alternative in picture.get("end_alternatives", [])
            if alternative.get("selected")
        ),
        None,
    )
    first_text = picture.get("first_trustworthy_resumed_text_input_sample")
    latency = (
        first_text - selected_end
        if first_text is not None and selected_end is not None
        else None
    )
    evidence = picture.get("reacquisition_evidence")
    return {
        "status": evidence.get("status") if evidence else "not_available",
        "picture_end_input_sample": selected_end,
        "first_trustworthy_resumed_text_input_sample": first_text,
        "recovery_latency_input_samples": latency,
        "recovery_latency_seconds": (
            latency / sample_rate_hz if latency is not None else None
        ),
        "reacquisition_interval": picture.get(
            "return_to_text_reacquisition_interval"
        ),
    }


def _aggregate_damage(pictures: list[dict[str, object]]) -> dict[str, object]:
    available = [item["damage"] for item in pictures if "damage" in item]
    component_count = sum(item["component_count"] for item in available)
    clipped = sum(item["clipped_count"] for item in available)
    unstable = sum(item["unstable_frequency_count"] for item in available)
    return {
        "status": "reported" if available else "not_available",
        "picture_count": len(available),
        "component_count": component_count,
        "clipped_count": clipped,
        "clipped_fraction": clipped / component_count if component_count else None,
        "unstable_frequency_count": unstable,
        "unstable_frequency_fraction": (
            unstable / component_count if component_count else None
        ),
        "threshold_calibrated": all(
            item["threshold_calibrated"] for item in available
        )
        if available
        else None,
    }


def _aggregate_raw_raster_metrics(
    pictures: list[dict[str, object]],
) -> dict[str, object]:
    scored = [
        item["pixel_score"]["raw_raster"]
        for item in pictures
        if item.get("pixel_score", {}).get("status") == "scored"
    ]
    whole = [item["whole_raster"] for item in scored]
    channel_names = sorted(
        {name for item in scored for name in item["channels"]}
    )

    def average(field: str, values: list[dict[str, object]]) -> float | None:
        present = [item[field] for item in values if item[field] is not None]
        return sum(present) / len(present) if present else None

    fields = (
        "mean_absolute_error_255",
        "root_mean_square_error_255",
        "signed_bias_255",
        "exact_component_fraction",
        "psnr_db",
    )
    return {
        "mean_raw_whole_raster": {
            field: average(field, whole) for field in fields
        }
        if whole
        else None,
        "mean_raw_channels": {
            name: {
                field: average(
                    field,
                    [
                        item["channels"][name]
                        for item in scored
                        if name in item["channels"]
                    ],
                )
                for field in fields
            }
            for name in channel_names
        },
        **_aggregate_alignment_offset_metrics(pictures),
    }


def _aggregate_alignment_offset_metrics(
    pictures: list[dict[str, object]],
) -> dict[str, float | int | None]:
    scored = [
        item["pixel_score"]
        for item in pictures
        if item.get("pixel_score", {}).get("status") == "scored"
    ]
    maximum_offsets = [
        abs(score["maximum_absolute_offset_components"])
        for score in scored
        if score.get("maximum_absolute_offset_components") is not None
    ]
    dominant_offsets = []
    for score in scored:
        runs = score.get("offset_path_rle", [])
        if not runs:
            continue
        dominant = max(
            runs,
            key=lambda run: run["stop_component"] - run["start_component"],
        )
        dominant_offsets.append(abs(dominant["offset"]))
    return {
        "maximum_absolute_alignment_offset_components": (
            max(maximum_offsets) if maximum_offsets else None
        ),
        "mean_absolute_dominant_alignment_offset_components": (
            sum(dominant_offsets) / len(dominant_offsets)
            if dominant_offsets
            else None
        ),
        "maximum_absolute_dominant_alignment_offset_components": (
            max(dominant_offsets) if dominant_offsets else None
        ),
    }


def _aggregate_transitions(pictures: list[dict[str, object]]) -> dict[str, object]:
    available = [item["transition"] for item in pictures if "transition" in item]
    acquired = [item for item in available if item["status"] == "acquired"]
    latencies = [
        item["recovery_latency_seconds"]
        for item in acquired
        if item["recovery_latency_seconds"] is not None
    ]
    return {
        "status": "reported" if available else "not_available",
        "picture_count": len(available),
        "return_to_text_acquired": len(acquired),
        "return_to_text_not_acquired": len(available) - len(acquired),
        "mean_recovery_latency_seconds": (
            sum(latencies) / len(latencies) if latencies else None
        ),
        "maximum_recovery_latency_seconds": max(latencies) if latencies else None,
    }


def _direct_operations(
    manifests: list[dict[str, object]], paths: tuple[Path, Path]
) -> dict[str, object]:
    passes = {}
    for path, manifest in zip(paths, manifests, strict=True):
        mode = manifest["decoder"]["configuration"]["mode"]
        timing = manifest["timing"]
        diagnostics = manifest["diagnostics"]
        passes[mode] = {
            "manifest": str(path),
            "wall_seconds": timing["wall_seconds"],
            "cpu_seconds": timing["cpu_seconds"],
            "peak_rss_bytes": timing["peak_rss_bytes"],
            "bytes_read": diagnostics["bytes_read"],
            "bytes_written": diagnostics["bytes_written"],
            "peak_temporary_storage_bytes": diagnostics[
                "peak_temporary_storage_bytes"
            ],
            "incremental_time_to_result_seconds": diagnostics[
                "incremental_time_to_result_seconds"
            ],
            "stage_wall_seconds": diagnostics["stage_wall_seconds"],
        }
    return {
        "status": "measured",
        "composition": "two_pass_diagnostic",
        "passes": passes,
        "combined": {
            "wall_seconds_serial": sum(
                item["wall_seconds"] for item in passes.values()
            ),
            "cpu_seconds": sum(item["cpu_seconds"] for item in passes.values()),
            "peak_rss_bytes": max(item["peak_rss_bytes"] for item in passes.values()),
            "bytes_read": sum(item["bytes_read"] for item in passes.values()),
            "bytes_written": sum(item["bytes_written"] for item in passes.values()),
            "peak_temporary_storage_bytes": max(
                item["peak_temporary_storage_bytes"] for item in passes.values()
            ),
        },
    }


def _summarize_baseline(args: argparse.Namespace) -> dict[str, object]:
    records = []
    for path in args.score:
        content = path.read_bytes()
        score = json.loads(content)
        text = score["text"]
        pictures = score["picture_summary"]
        acquisition = score.get("acquisition")
        raw_raster = pictures.get("mean_raw_whole_raster")
        alignment_offsets = _summary_alignment_offset_metrics(score)
        records.append(
            {
                "program_id": score["program_id"],
                "transmission_id": score["transmission_id"],
                "decoder": score["decoder"],
                "decoder_version": score["decoder_version"],
                "scorecard_sha256": hashlib.sha256(content).hexdigest(),
                "scorecard_schema": score["schema"],
                "scorecard_status": score["status"],
                "execution_composition": (
                    score.get("execution_composition", {}).get("status")
                    if score.get("execution_composition")
                    else None
                ),
                "truth": score.get("truth"),
                "transmission_observability": score.get(
                    "transmission_observability"
                ),
                "receiver_family": score.get("transmission_observability", {}).get(
                    "receiver_family"
                ),
                "acquisition": (
                    {
                        "truth_scope": acquisition["truth_scope"],
                        "coordinate_truth_status": acquisition[
                            "coordinate_truth_status"
                        ],
                        "expected": acquisition["expected_count"],
                        "detected": acquisition["detected_count"],
                        "missed": acquisition["missed_count"],
                        "false": acquisition["false_count"],
                        "precision": acquisition["precision"],
                        "recall": acquisition["recall"],
                        "exact": acquisition["exact"],
                    }
                    if acquisition
                    else {"status": "not_scored"}
                ),
                "text": {
                    "reference_characters": text["reference_characters"],
                    "decoded_characters": text["decoded_characters"],
                    "substitutions": text["substitutions"],
                    "deletions": text["deletions"],
                    "insertions": text["insertions"],
                    "character_error_rate": text["character_error_rate"],
                    "reference_coverage": text["reference_coverage"],
                },
                "pictures": {
                    "expected": pictures["expected"],
                    "detected": pictures["detected"],
                    "missed": pictures["missed"],
                    "pixel_scored": pictures["pixel_scored"],
                    "pixel_not_scored": pictures["pixel_not_scored"],
                    "mean_aligned_mae_255_over_scored_pictures": pictures[
                        "mean_aligned_mae_255_over_scored_pictures"
                    ],
                    "mean_raw_whole_raster": pictures.get(
                        "mean_raw_whole_raster"
                    ),
                    "mean_raw_channels": pictures.get("mean_raw_channels"),
                    "mean_raw_mae_255_over_scored_pictures": (
                        raw_raster.get("mean_absolute_error_255")
                        if raw_raster
                        else None
                    ),
                    **alignment_offsets,
                },
                "damage": score.get("damage"),
                "transitions": score.get("transitions"),
                "operations": (
                    {
                        "status": score["operations"]["status"],
                        "composition": score["operations"].get("composition"),
                        "combined": score["operations"].get("combined"),
                    }
                    if score.get("operations")
                    else {"status": "not_available"}
                ),
                "alignment_parameters": score["alignment_parameters"],
            }
        )
    records.sort(
        key=lambda item: (
            item["program_id"],
            item["transmission_id"],
            item["decoder"],
        )
    )
    program_summaries = _program_summaries(records)
    return {
        "schema": "grampy-compact-baseline.v1",
        "source_revision": args.source_revision,
        "status": (
            "frozen_session9a_baseline"
            if all(
                record["scorecard_status"] == "frozen_session9a_baseline"
                for record in records
            )
            else "contains_unfrozen_scorecards"
        ),
        "scorecard_count": len(records),
        "records": records,
        "program_summaries": program_summaries,
        "decoder_summaries": _decoder_summaries(program_summaries),
    }


def _compute_planning_gate(args: argparse.Namespace) -> dict[str, object]:
    baseline_bytes = args.baseline.read_bytes()
    policy_bytes = args.policy.read_bytes()
    baseline = json.loads(baseline_bytes)
    policy = json.loads(policy_bytes)
    if policy.get("schema") != "grampy-fldigi-gate-policy.v1":
        raise ValueError("unsupported fldigi gate policy schema")
    if baseline.get("schema") not in {
        "grampy-baseline-publication.v1",
        "grampy-compact-baseline.v1",
    }:
        raise ValueError("unsupported baseline publication schema")

    weights = policy["weights"]
    expected_metrics = {"text_accuracy", "picture_event_recall", "pixel_fidelity"}
    if set(weights) != expected_metrics or any(
        value < 0 for value in weights.values()
    ):
        raise ValueError("gate weights must be nonnegative values for all three metrics")
    weight_total = sum(weights.values())
    if abs(weight_total - 1.0) > 1e-9:
        raise ValueError("gate weights must sum to 1")

    identities = policy["identities"]
    records = baseline["records"]
    direct_records = _select_gate_records(records, identities["direct_decoder"])
    fldigi_records = _select_gate_records(records, identities["fldigi"])
    direct_by_case = {
        (record["program_id"], record["transmission_id"]): record
        for record in direct_records
    }
    fldigi_by_case = {
        (record["program_id"], record["transmission_id"]): record
        for record in fldigi_records
    }
    expected_cases = set(direct_by_case) | set(fldigi_by_case)
    missing_pairs = [
        {"program_id": program, "transmission_id": transmission}
        for program, transmission in sorted(expected_cases)
        if (program, transmission) not in direct_by_case
        or (program, transmission) not in fldigi_by_case
    ]

    case_results = []
    for case in sorted(set(direct_by_case) & set(fldigi_by_case)):
        direct = direct_by_case[case]
        fldigi = fldigi_by_case[case]
        direct_metrics = _gate_metrics(direct)
        fldigi_metrics = _gate_metrics(fldigi)
        advantages = {
            name: direct_metrics[name] - fldigi_metrics[name]
            for name in expected_metrics
        }
        violations = []
        for name, limit in policy["catastrophic_regression_limits"].items():
            if advantages[name] < -limit:
                violations.append(
                    {"metric": name, "advantage": advantages[name], "limit": limit}
                )
        case_results.append(
            {
                "program_id": case[0],
                "transmission_id": case[1],
                "receiver_family": direct.get("receiver_family"),
                "direct": direct_metrics,
                "fldigi": fldigi_metrics,
                "advantages": advantages,
                "weighted_advantage": sum(
                    weights[name] * advantages[name] for name in expected_metrics
                ),
                "catastrophic_regressions": violations,
            }
        )

    program_results = []
    for program_id in sorted({item["program_id"] for item in case_results}):
        items = [item for item in case_results if item["program_id"] == program_id]
        program_results.append(
            {
                "program_id": program_id,
                "transmission_count": len(items),
                "aggregation": "unweighted_transmission_mean",
                "weighted_advantage": sum(item["weighted_advantage"] for item in items)
                / len(items),
            }
        )
    aggregate = (
        sum(item["weighted_advantage"] for item in program_results)
        / len(program_results)
        if program_results
        else None
    )
    violations = [
        {
            "program_id": item["program_id"],
            "transmission_id": item["transmission_id"],
            **violation,
        }
        for item in case_results
        for violation in item["catastrophic_regressions"]
    ]
    threshold = policy["pass_threshold"]
    computable = bool(program_results) and not missing_pairs
    passed = computable and aggregate >= threshold and not violations
    return {
        "schema": "grampy-fldigi-gate-result.v1",
        "policy_id": policy["policy_id"],
        "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(),
        "baseline_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
        "corpus_revision": policy["corpus_revision"],
        "identities": identities,
        "aggregation": (
            "unweighted transmission mean within program, "
            "then unweighted program mean"
        ),
        "weights": weights,
        "pass_threshold": threshold,
        "computable": computable,
        "passed": passed,
        "aggregate_weighted_advantage": aggregate,
        "missing_pairs": missing_pairs,
        "catastrophic_regressions": violations,
        "programs": program_results,
        "cases": case_results,
        "receiver_subsets": _receiver_subset_results(case_results),
    }


def _select_gate_records(
    records: list[dict[str, object]], identity: dict[str, str]
) -> list[dict[str, object]]:
    return [
        record
        for record in records
        if record["decoder"] == identity["name"]
        and record["decoder_version"] == identity["version"]
    ]


def _gate_metrics(record: dict[str, object]) -> dict[str, float]:
    text = record["text"]
    pictures = record["pictures"]
    cer = text.get("cer", text.get("character_error_rate"))
    detected = pictures["detected"]
    expected = pictures["expected"]
    mae = pictures.get(
        "aligned_mae_255",
        pictures.get("mean_aligned_mae_255_over_scored_pictures"),
    )
    if cer is None or mae is None or not expected:
        raise ValueError("gate record lacks scoreable text or picture metrics")
    return {
        "text_accuracy": max(0.0, min(1.0, 1.0 - float(cer))),
        "picture_event_recall": float(detected) / float(expected),
        "pixel_fidelity": max(0.0, min(1.0, 1.0 - float(mae) / 255.0)),
    }


def _receiver_subset_results(
    case_results: list[dict[str, object]],
) -> list[dict[str, object]]:
    families = sorted(
        {item["receiver_family"] for item in case_results if item["receiver_family"]}
    )
    results = []
    for family in families:
        items = [
            item for item in case_results if item["receiver_family"] == family
        ]
        results.append(
            {
                "receiver_family": family,
                "case_count": len(items),
                "mean_weighted_advantage": sum(
                    item["weighted_advantage"] for item in items
                )
                / len(items),
            }
        )
    return results


def _program_summaries(
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for record in records:
        key = (
            record["decoder"],
            record["decoder_version"],
            record["program_id"],
        )
        groups.setdefault(key, []).append(record)
    summaries = []
    for (decoder, version, program_id), items in sorted(groups.items()):
        text_cer = [item["text"]["character_error_rate"] for item in items]
        picture_recall = [
            item["pictures"]["detected"] / item["pictures"]["expected"]
            for item in items
        ]
        image_mae = [
            item["pictures"]["mean_aligned_mae_255_over_scored_pictures"]
            for item in items
            if item["pictures"]["mean_aligned_mae_255_over_scored_pictures"]
            is not None
        ]
        raw_image_mae = [
            item["pictures"]["mean_raw_mae_255_over_scored_pictures"]
            for item in items
            if item["pictures"]["mean_raw_mae_255_over_scored_pictures"]
            is not None
        ]
        maximum_offsets = [
            item["pictures"]["maximum_absolute_alignment_offset_components"]
            for item in items
            if item["pictures"][
                "maximum_absolute_alignment_offset_components"
            ]
            is not None
        ]
        dominant_offsets = [
            item["pictures"][
                "maximum_absolute_dominant_alignment_offset_components"
            ]
            for item in items
            if item["pictures"][
                "maximum_absolute_dominant_alignment_offset_components"
            ]
            is not None
        ]
        summaries.append(
            {
                "decoder": decoder,
                "decoder_version": version,
                "program_id": program_id,
                "aggregation": "unweighted_transmission_mean_with_range",
                "transmission_count": len(items),
                "text_character_error_rate": _mean_range(text_cer),
                "picture_event_recall": _mean_range(picture_recall),
                "aligned_image_mae_255": _mean_range(image_mae),
                "raw_image_mae_255": _mean_range(raw_image_mae),
                "maximum_absolute_alignment_offset_components": (
                    max(maximum_offsets) if maximum_offsets else None
                ),
                "maximum_absolute_dominant_alignment_offset_components": (
                    max(dominant_offsets) if dominant_offsets else None
                ),
            }
        )
    return summaries


def _decoder_summaries(
    program_summaries: list[dict[str, object]],
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for summary in program_summaries:
        groups.setdefault(
            (summary["decoder"], summary["decoder_version"]), []
        ).append(summary)
    results = []
    for (decoder, version), items in sorted(groups.items()):
        results.append(
            {
                "decoder": decoder,
                "decoder_version": version,
                "aggregation": "unweighted_program_mean",
                "program_count": len(items),
                "text_character_error_rate": sum(
                    item["text_character_error_rate"]["mean"] for item in items
                )
                / len(items),
                "picture_event_recall": sum(
                    item["picture_event_recall"]["mean"] for item in items
                )
                / len(items),
                "aligned_image_mae_255": sum(
                    item["aligned_image_mae_255"]["mean"] for item in items
                )
                / len(items),
                "raw_image_mae_255": _mean_of_present_program_means(
                    items, "raw_image_mae_255"
                ),
                "maximum_absolute_alignment_offset_components": _max_present(
                    item["maximum_absolute_alignment_offset_components"]
                    for item in items
                ),
                "maximum_absolute_dominant_alignment_offset_components": _max_present(
                    item[
                        "maximum_absolute_dominant_alignment_offset_components"
                    ]
                    for item in items
                ),
            }
        )
    return results


def _summary_alignment_offset_metrics(
    score: dict[str, object],
) -> dict[str, float | int | None]:
    summary = score["picture_summary"]
    keys = (
        "maximum_absolute_alignment_offset_components",
        "mean_absolute_dominant_alignment_offset_components",
        "maximum_absolute_dominant_alignment_offset_components",
    )
    if all(key in summary for key in keys):
        return {key: summary[key] for key in keys}
    return _aggregate_alignment_offset_metrics(score.get("pictures", []))


def _mean_of_present_program_means(
    items: list[dict[str, object]], key: str
) -> float | None:
    values = [
        item[key]["mean"]
        for item in items
        if item.get(key) and item[key].get("mean") is not None
    ]
    return sum(values) / len(values) if values else None


def _max_present(
    values: Iterable[float | int | None],
) -> float | int | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _mean_range(values: list[float]) -> dict[str, float | None]:
    return {
        "mean": sum(values) / len(values) if values else None,
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


if __name__ == "__main__":
    raise SystemExit(main())
