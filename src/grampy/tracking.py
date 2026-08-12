from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class FrequencyAnchor:
    input_sample: int
    center_hz: float
    uncertainty_hz: float
    source: str


@dataclass(frozen=True)
class FrequencyTrack:
    """Piecewise-linear carrier-center evidence in input-sample coordinates."""

    anchors: tuple[FrequencyAnchor, ...]
    breakpoints: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.anchors:
            raise ValueError("frequency track requires at least one anchor")
        positions = [anchor.input_sample for anchor in self.anchors]
        if positions != sorted(positions) or len(positions) != len(set(positions)):
            raise ValueError("frequency track anchors must be strictly increasing")
        if any(
            not np.isfinite(anchor.center_hz)
            or not np.isfinite(anchor.uncertainty_hz)
            or anchor.uncertainty_hz < 0
            for anchor in self.anchors
        ):
            raise ValueError("frequency track anchors must be finite")
        if list(self.breakpoints) != sorted(set(self.breakpoints)):
            raise ValueError("frequency track breakpoints must be strictly increasing")

    @classmethod
    def fixed(
        cls,
        *,
        center_hz: float,
        input_sample: int = 0,
        uncertainty_hz: float = 0.0,
        source: str = "fixed",
    ) -> FrequencyTrack:
        return cls(
            (
                FrequencyAnchor(
                    input_sample=input_sample,
                    center_hz=center_hz,
                    uncertainty_hz=uncertainty_hz,
                    source=source,
                ),
            )
        )

    def center_at(
        self, input_sample: int | np.ndarray
    ) -> float | np.ndarray:
        positions = np.asarray(
            [anchor.input_sample for anchor in self.anchors], dtype=np.float64
        )
        centers = np.asarray(
            [anchor.center_hz for anchor in self.anchors], dtype=np.float64
        )
        values = np.asarray(input_sample, dtype=np.float64)
        result = np.interp(values, positions, centers)
        return float(result) if values.ndim == 0 else result

    def to_dict(self) -> dict:
        return {
            "kind": "piecewise_linear",
            "breakpoints": list(self.breakpoints),
            "anchors": [
                {
                    "input_sample": anchor.input_sample,
                    "center_hz": anchor.center_hz,
                    "uncertainty_hz": anchor.uncertainty_hz,
                    "source": anchor.source,
                }
                for anchor in self.anchors
            ],
        }


@dataclass(frozen=True)
class ClockAnchor:
    input_sample: int
    symbol_index: float
    uncertainty_samples: float
    source: str


@dataclass(frozen=True)
class ClockTrack:
    """Affine symbol clock in input-sample coordinates."""

    epoch_input_sample: float
    samples_per_symbol: float
    rate_error_ppm: float = 0.0
    uncertainty_samples: float = 0.0
    anchors: tuple[ClockAnchor, ...] = ()

    def __post_init__(self) -> None:
        values = (
            self.epoch_input_sample,
            self.samples_per_symbol,
            self.rate_error_ppm,
            self.uncertainty_samples,
        )
        if not all(np.isfinite(value) for value in values):
            raise ValueError("clock track values must be finite")
        if self.samples_per_symbol <= 0 or self.uncertainty_samples < 0:
            raise ValueError("clock track scale must be positive")

    @property
    def tracked_samples_per_symbol(self) -> float:
        return self.samples_per_symbol * (1.0 + self.rate_error_ppm * 1e-6)

    def interval(self, symbol_index: int) -> tuple[int, int]:
        scale = self.tracked_samples_per_symbol
        start = int(round(self.epoch_input_sample + symbol_index * scale))
        stop = int(round(self.epoch_input_sample + (symbol_index + 1) * scale))
        return start, max(start + 1, stop)

    def to_dict(self) -> dict:
        return {
            "kind": "affine_symbol_clock",
            "epoch_input_sample": self.epoch_input_sample,
            "nominal_symbol_samples": self.samples_per_symbol,
            "tracked_symbol_samples": self.tracked_samples_per_symbol,
            "estimated_rate_error_ppm": self.rate_error_ppm,
            "phase_uncertainty_input_samples": self.uncertainty_samples,
            "anchors": [
                {
                    "input_sample": anchor.input_sample,
                    "symbol_index": anchor.symbol_index,
                    "uncertainty_samples": anchor.uncertainty_samples,
                    "source": anchor.source,
                }
                for anchor in self.anchors
            ],
        }
