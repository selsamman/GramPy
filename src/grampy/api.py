"""Supported callable interface for direct MFSK IQ decoding.

Import :class:`DecodeConfig` and :func:`decode_iq` from this module. The
returned dictionary conforms to ``grampy-decode-manifest.v1``; see
``docs/decoder/api.md`` for the consumer contract.
"""

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


__all__ = ["DecodeConfig", "decode_iq"]
