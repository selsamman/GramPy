from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .coordinates import SampleMap


DATATYPES = {
    "ci16_le": (np.dtype("<i2"), 4, 32768.0),
    "cf32_le": (np.dtype("<f4"), 8, 1.0),
}


class InputError(ValueError):
    pass


@dataclass(frozen=True)
class SigmfRecording:
    meta_path: Path
    data_path: Path
    metadata: dict[str, Any]
    datatype: str
    sample_rate: float
    sample_count: int
    bytes_per_sample: int
    requested_start: int
    requested_stop: int
    warnings: tuple[dict[str, str], ...]
    ancestry: tuple[dict[str, Any], ...]

    @classmethod
    def open(
        cls,
        meta_path: Path,
        data_path: Path,
        *,
        start_sample: int | None = None,
        stop_sample: int | None = None,
    ) -> SigmfRecording:
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise InputError(f"malformed SigMF metadata JSON: {error}") from error
        if not isinstance(metadata, dict):
            raise InputError("SigMF metadata root must be an object")
        global_fields = metadata.get("global")
        if not isinstance(global_fields, dict):
            raise InputError("SigMF metadata must contain a global object")

        datatype = global_fields.get("core:datatype")
        if datatype not in DATATYPES:
            raise InputError(f"unsupported SigMF datatype: {datatype!r}")
        sample_rate = global_fields.get("core:sample_rate")
        if (
            isinstance(sample_rate, bool)
            or not isinstance(sample_rate, (int, float))
            or not math.isfinite(sample_rate)
            or sample_rate <= 0
        ):
            raise InputError("core:sample_rate must be finite and positive")
        _, bytes_per_sample, _ = DATATYPES[datatype]
        size = data_path.stat().st_size
        if size % bytes_per_sample:
            raise InputError(
                f"input data size {size} is not aligned to {datatype} samples"
            )
        sample_count = size // bytes_per_sample

        captures = metadata.get("captures")
        if not isinstance(captures, list) or not captures:
            raise InputError("SigMF metadata must contain at least one capture")
        capture_starts: list[int] = []
        for capture in captures:
            if not isinstance(capture, dict):
                raise InputError("each capture must be an object")
            capture_start = capture.get("core:sample_start")
            if (
                isinstance(capture_start, bool)
                or not isinstance(capture_start, int)
                or not 0 <= capture_start <= sample_count
            ):
                raise InputError("each capture must have a valid core:sample_start")
            capture_starts.append(capture_start)

        start = 0 if start_sample is None else start_sample
        stop = sample_count if stop_sample is None else stop_sample
        if isinstance(start, bool) or isinstance(stop, bool):
            raise InputError("sample interval endpoints must be integers")
        if start < 0 or stop <= start or stop > sample_count:
            raise InputError(
                f"invalid interval [{start}, {stop}) for {sample_count} samples"
            )
        if not any(capture_start <= start for capture_start in capture_starts):
            raise InputError("no capture establishes the requested sample interval")

        warnings: list[dict[str, str]] = []
        first_capture = min(captures, key=lambda capture: capture["core:sample_start"])
        if "core:datetime" not in first_capture:
            warnings.append(_warning("absent-capture-time", "capture time is absent"))
        if "core:frequency" not in first_capture:
            warnings.append(_warning("absent-rf-frequency", "capture frequency is absent"))
        for capture in captures:
            frequency = capture.get("core:frequency")
            if frequency is not None and (
                isinstance(frequency, bool)
                or not isinstance(frequency, (int, float))
                or not math.isfinite(frequency)
            ):
                raise InputError("capture frequency must be finite when present")

        return cls(
            meta_path=meta_path,
            data_path=data_path,
            metadata=metadata,
            datatype=datatype,
            sample_rate=float(sample_rate),
            sample_count=sample_count,
            bytes_per_sample=bytes_per_sample,
            requested_start=start,
            requested_stop=stop,
            warnings=tuple(warnings),
            ancestry=tuple(_read_ancestry(metadata)),
        )

    @property
    def sample_map(self) -> SampleMap:
        return SampleMap.identity()

    def iter_complex64(self, block_samples: int) -> Iterator[tuple[int, np.ndarray]]:
        if block_samples <= 0:
            raise ValueError("block_samples must be positive")
        dtype, _, scale = DATATYPES[self.datatype]
        raw = np.memmap(self.data_path, mode="r", dtype=dtype)
        values_per_sample = 2
        start_value = self.requested_start * values_per_sample
        stop_value = self.requested_stop * values_per_sample
        for value_start in range(start_value, stop_value, block_samples * 2):
            value_stop = min(value_start + block_samples * 2, stop_value)
            pairs = np.asarray(raw[value_start:value_stop]).reshape(-1, 2)
            samples = (
                pairs[:, 0].astype(np.float32)
                + 1j * pairs[:, 1].astype(np.float32)
            ) / scale
            yield value_start // 2, samples.astype(np.complex64, copy=False)

    def read_complex64(self, start: int, stop: int) -> np.ndarray:
        """Materialize one bounded absolute input interval as complex64."""
        if start < self.requested_start or stop > self.requested_stop or stop <= start:
            raise ValueError(
                f"invalid bounded read [{start}, {stop}) within "
                f"[{self.requested_start}, {self.requested_stop})"
            )
        dtype, _, scale = DATATYPES[self.datatype]
        raw = np.memmap(self.data_path, mode="r", dtype=dtype)
        pairs = np.asarray(raw[start * 2 : stop * 2]).reshape(-1, 2)
        samples = (
            pairs[:, 0].astype(np.float32)
            + 1j * pairs[:, 1].astype(np.float32)
        ) / scale
        return samples.astype(np.complex64, copy=False)

    def hashes(self) -> dict[str, str]:
        return {
            "metadata_sha256": _sha256(self.meta_path),
            "data_sha256": _sha256(self.data_path),
        }


def inspect_samples(
    recording: SigmfRecording, block_samples: int
) -> dict[str, int | float]:
    clipping_count = 0
    nonfinite_count = 0
    peak_magnitude = 0.0
    for _, samples in recording.iter_complex64(block_samples):
        finite = np.isfinite(samples.real) & np.isfinite(samples.imag)
        nonfinite_count += int((~finite).sum())
        if finite.any():
            magnitudes = np.abs(samples[finite])
            peak_magnitude = max(peak_magnitude, float(magnitudes.max(initial=0.0)))
        if recording.datatype == "ci16_le":
            clipping_count += int(
                (
                    (np.abs(samples.real) >= 32767.0 / 32768.0)
                    | (np.abs(samples.imag) >= 32767.0 / 32768.0)
                ).sum()
            )
    return {
        "clipping_sample_count": clipping_count,
        "nonfinite_sample_count": nonfinite_count,
        "peak_magnitude": peak_magnitude,
    }


def _read_ancestry(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    ancestry: list[dict[str, Any]] = []
    for annotation in metadata.get("annotations", []):
        if not isinstance(annotation, dict):
            continue
        if "radiogram:trim_start_sample" in annotation:
            trim = annotation["radiogram:trim_start_sample"]
            if isinstance(trim, int) and not isinstance(trim, bool) and trim >= 0:
                ancestry.append(
                    {
                        "operation": "trim",
                        "parent_sample_offset": trim,
                        "parent": annotation.get("radiogram:source"),
                    }
                )
    return ancestry


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}
