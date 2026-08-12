"""Public callable interface for direct MFSK IQ decoding."""

from __future__ import annotations

from pathlib import Path

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
    """Decode a SigMF IQ recording and return its manifest document."""
    return run_reference_pipeline(
        meta_path=meta_path,
        data_path=data_path,
        start_sample=start_sample,
        stop_sample=stop_sample,
        config=config or DecodeConfig(),
        artifact_dir=artifact_dir,
        artifact_path_prefix=artifact_path_prefix,
    )


__all__ = ["DecodeConfig", "decode_iq"]
