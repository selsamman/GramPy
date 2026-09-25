"""Supported callable interface for direct MFSK IQ decoding.

``decode_iq_products`` returns compact broadcast and quality documents;
``decode_iq`` retains the original diagnostic-manifest contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .pipeline import DecodeConfig, run_reference_pipeline


def decode_iq(
    *,
    meta_path: Path,
    data_path: Path,
    config: DecodeConfig | None = None,
    start_sample: int | None = None,
    stop_sample: int | None = None,
    artifact_dir: Path | None = None,
    artifact_path_prefix: str | None = None,
) -> dict[str, object]:
    """Decode a SigMF IQ recording and return a validated manifest document.

    ``meta_path`` and ``data_path`` identify the matching SigMF metadata and
    IQ-data files. ``start_sample`` and ``stop_sample`` optionally select a
    half-open input interval. Large picture artifacts are written only when
    ``artifact_dir`` is supplied; ``artifact_path_prefix`` is recorded in
    resulting artifact paths. This function does not write the manifest.

    Invalid input or configuration raises ``ValueError``; filesystem failures
    raise ``OSError``. Non-terminal decode failures are represented by a
    partial manifest and warnings.
    """
    return run_reference_pipeline(
        meta_path=meta_path,
        data_path=data_path,
        start_sample=start_sample,
        stop_sample=stop_sample,
        config=config or DecodeConfig(),
        artifact_dir=artifact_dir,
        artifact_path_prefix=artifact_path_prefix,
    )


@dataclass(frozen=True)
class DecodeProducts:
    text_manifest: dict[str, Any]
    quality_manifest: dict[str, Any]
    diagnostic_manifest: dict[str, Any] | None = None


def decode_iq_products(
    *,
    meta_path: Path,
    data_path: Path,
    config: DecodeConfig | None = None,
    start_sample: int | None = None,
    stop_sample: int | None = None,
    artifact_dir: Path | None = None,
    artifact_path_prefix: str | None = None,
    artifact_root: Path | None = None,
    include_diagnostic_manifest: bool = False,
) -> DecodeProducts:
    """Decode once and return aligned text and quality products.

    ``artifact_root`` resolves paths recorded in picture artifacts for the
    confidence estimator. Supply it when artifact paths use a custom prefix.
    """
    if artifact_root is None:
        if artifact_dir is None:
            artifact_root = meta_path.parent
        elif artifact_path_prefix is None:
            artifact_root = artifact_dir
        else:
            prefix = Path(artifact_path_prefix)
            if prefix.is_absolute() or ".." in prefix.parts or prefix.parts == ():
                raise ValueError("artifact_path_prefix must be a relative path")
            if tuple(artifact_dir.parts[-len(prefix.parts):]) != prefix.parts:
                raise ValueError("supply artifact_root for a custom artifact path prefix")
            artifact_root = artifact_dir.parents[len(prefix.parts) - 1]
    result = run_reference_pipeline(
        meta_path=meta_path,
        data_path=data_path,
        start_sample=start_sample,
        stop_sample=stop_sample,
        config=config or DecodeConfig(),
        artifact_dir=artifact_dir,
        artifact_path_prefix=artifact_path_prefix,
        _products=True,
        _include_diagnostic_manifest=include_diagnostic_manifest,
        _artifact_root=artifact_root,
    )
    return DecodeProducts(**result)


__all__ = ["DecodeConfig", "DecodeProducts", "decode_iq", "decode_iq_products"]
