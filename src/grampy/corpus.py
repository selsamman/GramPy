from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import shutil
from typing import Any, Iterable

import numpy as np


SCHEMA_VERSION = 1
BYTES_PER_CI16_SAMPLE = 4


@dataclass(frozen=True)
class CapturePaths:
    group: str
    stem: str
    data: Path
    meta: Path
    capture: Path
    log: Path


def discover_captures(intake_root: Path) -> list[CapturePaths]:
    captures: list[CapturePaths] = []
    for data in sorted(intake_root.glob("*/*.sigmf-data")):
        if data.parent.name == "output":
            continue
        stem = data.name.removesuffix(".sigmf-data")
        captures.append(
            CapturePaths(
                group=data.parent.name,
                stem=stem,
                data=data,
                meta=data.with_suffix(".sigmf-meta"),
                capture=data.with_suffix(".capture.json"),
                log=data.with_suffix(".log"),
            )
        )
    return captures


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def effective_metadata(paths: CapturePaths) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if paths.meta.is_file():
        result.update(read_json(paths.meta))
    if paths.capture.is_file():
        result.update(read_json(paths.capture))
    return result


def ci16_metrics(
    path: Path,
    *,
    sample_rate: int,
    block_seconds: int = 1,
) -> dict[str, Any]:
    byte_size = path.stat().st_size
    if byte_size == 0 or byte_size % BYTES_PER_CI16_SAMPLE:
        return {
            "status": "unavailable",
            "reason": "empty" if byte_size == 0 else "unaligned_byte_length",
        }

    block_samples = sample_rate * block_seconds
    values = np.memmap(path, dtype="<i2", mode="r").reshape(-1, 2)
    sample_count = int(values.shape[0])
    rms_blocks: list[float] = []
    zero_count = 0
    clipped_count = 0
    sum_i = 0.0
    sum_q = 0.0
    sum_power = 0.0

    for start in range(0, sample_count, block_samples):
        raw = np.asarray(values[start : start + block_samples], dtype=np.int32)
        power = raw[:, 0].astype(np.float64) ** 2 + raw[:, 1].astype(np.float64) ** 2
        sum_i += float(raw[:, 0].sum(dtype=np.int64))
        sum_q += float(raw[:, 1].sum(dtype=np.int64))
        block_power = float(power.sum())
        sum_power += block_power
        rms_blocks.append(math.sqrt(block_power / len(raw)))
        zero_count += int(np.count_nonzero((raw[:, 0] == 0) & (raw[:, 1] == 0)))
        clipped_count += int(
            np.count_nonzero((np.abs(raw[:, 0]) >= 32760) | (np.abs(raw[:, 1]) >= 32760))
        )

    rms = np.asarray(rms_blocks)
    median = float(np.median(rms))
    low_threshold = median * 0.25
    return {
        "status": "measured",
        "sample_rate_hz": sample_rate,
        "sample_count": sample_count,
        "duration_sec": sample_count / sample_rate,
        "complex_rms": math.sqrt(sum_power / sample_count),
        "dc_i": sum_i / sample_count,
        "dc_q": sum_q / sample_count,
        "zero_sample_fraction": zero_count / sample_count,
        "clipped_sample_fraction": clipped_count / sample_count,
        "block_seconds": block_seconds,
        "block_rms_min": float(rms.min()),
        "block_rms_p10": float(np.percentile(rms, 10)),
        "block_rms_median": median,
        "block_rms_p90": float(np.percentile(rms, 90)),
        "block_rms_max": float(rms.max()),
        "low_level_block_fraction": float(np.mean(rms < low_threshold)),
        "low_level_threshold": low_threshold,
    }


def inventory_capture(paths: CapturePaths, *, measure_iq: bool) -> dict[str, Any]:
    metadata = effective_metadata(paths)
    byte_size = paths.data.stat().st_size
    sample_rate = int(
        metadata.get("output_sample_rate_hz")
        or metadata.get("core:sample_rate")
        or metadata.get("global", {}).get("core:sample_rate", 48_000)
    )
    expected_bytes = metadata.get("expected_output_bytes")
    complete = (
        byte_size > 0
        and byte_size % BYTES_PER_CI16_SAMPLE == 0
        and (expected_bytes is None or byte_size == int(expected_bytes))
        and (metadata.get("exit_status") in (None, 0))
    )
    result: dict[str, Any] = {
        "intake_group": paths.group,
        "intake_stem": paths.stem,
        "data_bytes": byte_size,
        "data_sha256": sha256_file(paths.data) if byte_size else None,
        "metadata_present": paths.meta.is_file(),
        "capture_provenance_present": paths.capture.is_file(),
        "log_present": paths.log.is_file(),
        "complete": complete,
        "sample_rate_hz": sample_rate,
        "duration_sec": (
            byte_size / BYTES_PER_CI16_SAMPLE / sample_rate if byte_size else 0.0
        ),
        "station_group": paths.group,
        "frequency_hz": metadata.get("frequency_hz"),
        "start_utc": metadata.get("start_utc"),
        "capture_engine": metadata.get("capture_engine"),
        "receiver_profile_id": metadata.get("receiver_profile_id"),
        "receiver_family": metadata.get("receiver_family"),
    }
    if measure_iq:
        result["iq_metrics"] = ci16_metrics(paths.data, sample_rate=sample_rate)
    return result


def build_inventory(intake_root: Path, *, measure_iq: bool = True) -> dict[str, Any]:
    captures = [
        inventory_capture(paths, measure_iq=measure_iq)
        for paths in discover_captures(intake_root)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "radiogram-received-iq-intake-inventory",
        "capture_count": len(captures),
        "complete_capture_count": sum(item["complete"] for item in captures),
        "total_data_bytes": sum(item["data_bytes"] for item in captures),
        "captures": captures,
    }


def atomic_copy_verified(source: Path, destination: Path, expected_sha256: str) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        return destination.stat().st_size
    temporary = destination.with_name(f".{destination.name}.copying")
    if temporary.exists():
        temporary.unlink()
    shutil.copy2(source, temporary)
    actual = sha256_file(temporary)
    if actual != expected_sha256:
        temporary.unlink()
        raise ValueError(
            f"copy hash mismatch for {source}: expected {expected_sha256}, got {actual}"
        )
    temporary.replace(destination)
    return destination.stat().st_size


def _copy_small(source: Path, destination: Path) -> dict[str, Any]:
    digest = sha256_file(source)
    size = atomic_copy_verified(source, destination, digest)
    return {"path": destination.name, "bytes": size, "sha256": digest}


def promote(
    *,
    intake_root: Path,
    corpus_root: Path,
    selection: dict[str, Any],
) -> dict[str, Any]:
    available = {
        (item.group, item.stem): item for item in discover_captures(intake_root)
    }
    samples_root = intake_root.parent
    sources: list[dict[str, Any]] = []
    for requested in selection["sources"]:
        key = (requested["intake_group"], requested["intake_stem"])
        if key not in available:
            raise FileNotFoundError(f"selected intake capture not found: {key}")
        paths = available[key]
        measured_hash = sha256_file(paths.data)
        expected_hash = requested["data_sha256"]
        if measured_hash != expected_hash:
            raise ValueError(
                f"source hash mismatch for {paths.data}: "
                f"expected {expected_hash}, got {measured_hash}"
            )
        source_dir = corpus_root / "sources" / requested["id"]
        data_artifact = {
            "path": "capture.sigmf-data",
            "bytes": atomic_copy_verified(
                paths.data, source_dir / "capture.sigmf-data", expected_hash
            ),
            "sha256": expected_hash,
        }
        artifacts = {"data": data_artifact}
        for name, source in (
            ("metadata", paths.meta),
            ("capture_provenance", paths.capture),
            ("capture_log", paths.log),
        ):
            if source.is_file():
                artifacts[name] = _copy_small(source, source_dir / {
                    "metadata": "capture.sigmf-meta",
                    "capture_provenance": "capture.capture.json",
                    "capture_log": "capture.log",
                }[name])
        sources.append(
            {
                "id": requested["id"],
                "station": requested["station"],
                "start_utc": requested["start_utc"],
                "frequency_hz": requested["frequency_hz"],
                "partition": requested["partition"],
                "quality_role": requested["quality_role"],
                "selection_reason": requested["selection_reason"],
                "observed_iq_metrics": requested.get("observed_iq_metrics"),
                "evidence": requested.get("evidence", []),
                "artifacts": artifacts,
            }
        )

    for case in selection["cases"]:
        case_dir = corpus_root / "cases" / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "case.json").write_text(
            json.dumps(case, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    preserved_files: list[dict[str, Any]] = []
    for item in selection.get("preserved_files", []):
        source = samples_root / item["sample_root_source"]
        destination = corpus_root / item["destination"]
        artifact = _copy_small(source, destination)
        preserved_files.append(
            {
                "id": item["id"],
                "purpose": item["purpose"],
                "path": item["destination"],
                "bytes": artifact["bytes"],
                "sha256": artifact["sha256"],
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "radiogram-received-iq-corpus",
        "corpus_version": selection["corpus_version"],
        "policy": "docs/decoder/mfsk_received_corpus.md",
        "sources": sources,
        "cases": [
            {"id": item["id"], "path": f"cases/{item['id']}/case.json"}
            for item in selection["cases"]
        ],
        "preserved_files": preserved_files,
        "storage": {
            "source_bytes": sum(
                artifact["bytes"]
                for item in sources
                for artifact in item["artifacts"].values()
            ) + sum(item["bytes"] for item in preserved_files),
            "source_count": len(sources),
            "case_count": len(selection["cases"]),
        },
    }
    corpus_root.mkdir(parents=True, exist_ok=True)
    (corpus_root / "corpus.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def verify_corpus(corpus_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = corpus_root / "corpus.json"
    if not manifest_path.is_file():
        return [f"missing manifest: {manifest_path}"]
    manifest = read_json(manifest_path)
    for source in manifest.get("sources", []):
        source_dir = corpus_root / "sources" / source["id"]
        for artifact in source["artifacts"].values():
            path = source_dir / artifact["path"]
            if not path.is_file():
                errors.append(f"missing artifact: {path}")
                continue
            if path.stat().st_size != artifact["bytes"]:
                errors.append(f"size mismatch: {path}")
            elif sha256_file(path) != artifact["sha256"]:
                errors.append(f"hash mismatch: {path}")
    for case in manifest.get("cases", []):
        path = corpus_root / case["path"]
        if not path.is_file():
            errors.append(f"missing case: {path}")
    for artifact in manifest.get("preserved_files", []):
        path = corpus_root / artifact["path"]
        _verify_artifact(path, artifact, errors, "preserved file")
    for program_entry in manifest.get("programs", []):
        program_path = corpus_root / program_entry["path"]
        if not program_path.is_file():
            errors.append(f"missing program manifest: {program_path}")
            continue
        program = read_json(program_path)
        program_root = program_path.parent
        review_path = program_root / program["text_truth"]["review"]
        if not review_path.is_file():
            errors.append(f"missing text review: {review_path}")
        for picture in program.get("pictures", []):
            artifact = picture.get("artifact")
            if picture.get("pixel_truth_status") == "missing":
                if artifact is not None:
                    errors.append(
                        f"missing-truth picture has artifact: "
                        f"{program['id']} order {picture['order']}"
                    )
                continue
            if not artifact:
                errors.append(
                    f"available picture lacks artifact: "
                    f"{program['id']} order {picture['order']}"
                )
                continue
            _verify_artifact(
                program_root / artifact["path"], artifact, errors, "picture truth"
            )
        for transmission in program.get("transmissions", []):
            transmission_path = program_root / transmission["path"]
            if not transmission_path.is_file():
                errors.append(f"missing transmission manifest: {transmission_path}")
                continue
            record = read_json(transmission_path)
            for artifact in record.get("fldigi_reference", {}).get("artifacts", []):
                _verify_artifact(
                    corpus_root / artifact["path"],
                    artifact,
                    errors,
                    "fldigi reference",
                )
    for scorecard in manifest.get("scorecards", []):
        _verify_artifact(
            corpus_root / scorecard["path"],
            scorecard,
            errors,
            "scorecard",
        )
    return errors


def _verify_artifact(
    path: Path,
    artifact: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if not path.is_file():
        errors.append(f"missing {label}: {path}")
    elif path.stat().st_size != artifact["bytes"]:
        errors.append(f"size mismatch: {path}")
    elif sha256_file(path) != artifact["sha256"]:
        errors.append(f"hash mismatch: {path}")
