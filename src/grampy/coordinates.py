from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math


@dataclass(frozen=True)
class SampleMap:
    """An affine map from a block's output coordinate to input samples.

    ``input_sample = input_origin + output_sample * input_per_output``.
    Fractions keep rational resampling maps exact. Uncertainty is expressed in
    input samples and is deliberately separate from serialization rounding.
    """

    input_origin: Fraction = Fraction(0)
    input_per_output: Fraction = Fraction(1)
    uncertainty_input_samples: float = 0.0
    rounding: str = "nearest_ties_to_even"

    def __post_init__(self) -> None:
        if self.input_per_output <= 0:
            raise ValueError("input_per_output must be positive")
        if (
            not math.isfinite(self.uncertainty_input_samples)
            or self.uncertainty_input_samples < 0
        ):
            raise ValueError("uncertainty_input_samples must be finite and non-negative")
        if self.rounding != "nearest_ties_to_even":
            raise ValueError(f"unsupported rounding rule: {self.rounding}")

    @classmethod
    def identity(cls) -> SampleMap:
        return cls()

    @classmethod
    def trim(cls, start_input_sample: int) -> SampleMap:
        return cls(input_origin=Fraction(start_input_sample))

    @classmethod
    def resampled(
        cls,
        *,
        input_origin: Fraction | int = 0,
        input_rate: int,
        output_rate: int,
        uncertainty_input_samples: float = 0.0,
    ) -> SampleMap:
        if input_rate <= 0 or output_rate <= 0:
            raise ValueError("sample rates must be positive")
        return cls(
            input_origin=Fraction(input_origin),
            input_per_output=Fraction(input_rate, output_rate),
            uncertainty_input_samples=uncertainty_input_samples,
        )

    def input_estimate(self, output_sample: Fraction | int) -> Fraction:
        return self.input_origin + Fraction(output_sample) * self.input_per_output

    def serialize_point(self, output_sample: Fraction | int) -> dict[str, object]:
        estimate = self.input_estimate(output_sample)
        return {
            "input_sample": round(estimate),
            "input_sample_unrounded": _fraction_json(estimate),
            "uncertainty_input_samples": self.uncertainty_input_samples,
        }

    def output_estimate(self, input_sample: Fraction | int) -> Fraction:
        return (Fraction(input_sample) - self.input_origin) / self.input_per_output

    def compose(self, upstream: SampleMap) -> SampleMap:
        """Map this block through an upstream output-to-input map."""
        return SampleMap(
            input_origin=upstream.input_estimate(self.input_origin),
            input_per_output=self.input_per_output * upstream.input_per_output,
            uncertainty_input_samples=(
                self.uncertainty_input_samples
                * float(upstream.input_per_output)
                + upstream.uncertainty_input_samples
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": "affine",
            "input_origin": _fraction_json(self.input_origin),
            "input_per_output": _fraction_json(self.input_per_output),
            "rounding": self.rounding,
            "uncertainty_input_samples": self.uncertainty_input_samples,
        }


def _fraction_json(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}

