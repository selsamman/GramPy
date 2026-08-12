from __future__ import annotations

import unittest
from unittest import mock

import numpy as np

from grampy.picture_decode import (
    ComponentClock,
    PictureDecode,
    _component_frequencies,
    _fractional_component_frequencies,
    _isolate_picture_channel,
    parse_picture_headers,
)
from grampy.pipeline import (
    DecodeConfig,
    _refine_damaged_picture_headers,
    _suppress_accepted_picture_text,
)
from grampy.text_decode import MFSKTextDecode


class PictureComponentEstimatorExperimentTests(unittest.TestCase):
    RATE = 48_000.0
    CENTER = 1_500.0
    BANDWIDTH = 937.5

    @classmethod
    def _samples(cls, frequencies: np.ndarray) -> np.ndarray:
        phase = 2.0 * np.pi * np.cumsum(frequencies) / cls.RATE
        return np.exp(1j * phase).astype(np.complex64)

    def _estimate(
        self, values: np.ndarray, speed: int, estimator: str
    ) -> np.ndarray:
        samples_per_component = speed * 6
        frequencies = self.CENTER + self.BANDWIDTH * (
            values.astype(np.float64) - 128.0
        ) / 256.0
        samples = self._samples(np.repeat(frequencies, samples_per_component))
        measured, _ = _component_frequencies(
            samples,
            0,
            len(values),
            samples_per_component,
            self.RATE,
            center_hz=self.CENTER,
            bandwidth_hz=self.BANDWIDTH,
            estimator=estimator,
        )
        return 128.0 + 256.0 * (measured - self.CENTER) / self.BANDWIDTH

    def test_phase_difference_meets_p2_p4_p8_value_and_ramp_acceptance(self) -> None:
        patterns = (
            np.asarray([0, 1, 17, 64, 127, 128, 129, 192, 238, 254, 255]),
            np.arange(256),
            np.arange(255, -1, -1),
        )
        for speed in (2, 4, 8):
            for pattern in patterns:
                with self.subTest(speed=speed, direction=int(pattern[-1] - pattern[0])):
                    measured = self._estimate(pattern, speed, "phase_difference")
                    self.assertLessEqual(
                        float(np.median(np.abs(measured - pattern))),
                        speed / 8.0,
                    )
                    if pattern[-1] > pattern[0]:
                        self.assertGreater(measured[-1] - measured[0], 0.0)
                    else:
                        self.assertLess(measured[-1] - measured[0], 0.0)

    def test_phase_difference_is_stable_under_deterministic_ci16_quantization(self) -> None:
        values = np.arange(256)
        samples_per_component = 48
        frequencies = self.CENTER + self.BANDWIDTH * (
            values.astype(np.float64) - 128.0
        ) / 256.0
        cf32 = self._samples(np.repeat(frequencies, samples_per_component))
        scale = 30_000.0
        ci16 = (
            np.rint(cf32.real * scale).astype(np.int16).astype(np.float32) / scale
            + 1j
            * np.rint(cf32.imag * scale).astype(np.int16).astype(np.float32)
            / scale
        ).astype(np.complex64)
        estimates = []
        for samples in (cf32, ci16):
            measured, _ = _component_frequencies(
                samples,
                0,
                len(values),
                samples_per_component,
                self.RATE,
                center_hz=self.CENTER,
                bandwidth_hz=self.BANDWIDTH,
                estimator="phase_difference",
            )
            estimates.append(
                128.0 + 256.0 * (measured - self.CENTER) / self.BANDWIDTH
            )
        self.assertLessEqual(float(np.median(np.abs(estimates[1] - values))), 1.0)
        self.assertLessEqual(
            float(np.max(np.abs(estimates[1] - estimates[0]))), 0.01
        )

    def test_experiment_compares_all_predeclared_estimators(self) -> None:
        values = np.arange(256)
        errors = {}
        for estimator in ("fft_peak", "phase_difference", "bounded_correlation"):
            measured = self._estimate(values, 8, estimator)
            errors[estimator] = float(np.median(np.abs(measured - values)))
        self.assertLessEqual(errors["phase_difference"], 1.0)
        self.assertLess(errors["phase_difference"], errors["fft_peak"])
        self.assertLessEqual(errors["bounded_correlation"], 1.0)

    def test_unknown_estimator_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "unsupported picture component estimator"
        ):
            self._estimate(np.asarray([128]), 8, "unknown")

    def test_session10e_component_windows_preserve_clean_p8_ramp(self) -> None:
        values = np.arange(256)
        samples_per_component = 48
        frequencies = self.CENTER + self.BANDWIDTH * (
            values.astype(np.float64) - 128.0
        ) / 256.0
        samples = self._samples(np.repeat(frequencies, samples_per_component))
        for component_window in ("center_crop", "full", "full_hann"):
            with self.subTest(component_window=component_window):
                measured, _ = _component_frequencies(
                    samples,
                    0,
                    len(values),
                    samples_per_component,
                    self.RATE,
                    center_hz=self.CENTER,
                    bandwidth_hz=self.BANDWIDTH,
                    estimator="bounded_correlation",
                    component_window=component_window,
                )
                decoded = 128.0 + 256.0 * (
                    measured - self.CENTER
                ) / self.BANDWIDTH
                self.assertLessEqual(
                    float(np.median(np.abs(decoded - values))), 1.0
                )

    def test_session10e_unknown_component_window_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "unsupported picture component window"
        ):
            _component_frequencies(
                self._samples(np.repeat([self.CENTER], 48)),
                0,
                1,
                48,
                self.RATE,
                center_hz=self.CENTER,
                estimator="fft_peak",
                component_window="unknown",
            )

    def test_session10e_response_matched_filter_preserves_picture_endpoints(self) -> None:
        samples_per_component = 48
        values = np.repeat(np.asarray([0.0, 255.0, 0.0, 255.0]), 100)
        frequencies = self.CENTER + self.BANDWIDTH * (
            values - 128.0
        ) / 256.0
        samples = self._samples(np.repeat(frequencies, samples_per_component))
        filtered = _isolate_picture_channel(
            samples,
            self.RATE,
            self.CENTER,
            self.BANDWIDTH,
            profile="response_matched",
        )
        measured, _ = _component_frequencies(
            filtered,
            0,
            len(values),
            samples_per_component,
            self.RATE,
            center_hz=self.CENTER,
            bandwidth_hz=self.BANDWIDTH,
            estimator="bounded_correlation",
            component_window="full",
        )
        decoded = 128.0 + 256.0 * (
            measured - self.CENTER
        ) / self.BANDWIDTH
        valid = np.ones(len(values), dtype=bool)
        for boundary in (0, 100, 200, 300, 400):
            valid[max(0, boundary - 10) : min(len(values), boundary + 10)] = False
        self.assertLessEqual(
            float(np.percentile(np.abs(decoded[valid] - values[valid]), 95)),
            0.01,
        )

    def test_fractional_clock_batches_equal_width_component_runs(self) -> None:
        values = np.resize(np.arange(256, dtype=np.float64), 512)
        clock = ComponentClock(
            epoch_input_sample=0.0,
            samples_per_component=48.0,
            rate_error_ppm=1_000.0,
        )
        intervals = [clock.interval(index) for index in range(len(values))]
        frequencies = np.empty(intervals[-1][1], dtype=np.float64)
        for value, (start, stop) in zip(values, intervals):
            frequencies[start:stop] = self.CENTER + self.BANDWIDTH * (
                value - 128.0
            ) / 256.0
        samples = self._samples(frequencies)

        with mock.patch(
            "grampy.picture_decode._component_frequencies",
            wraps=_component_frequencies,
        ) as estimator:
            measured, _, measured_intervals = _fractional_component_frequencies(
                samples,
                len(values),
                self.RATE,
                component_clock=clock,
                center_hz=self.CENTER,
                bandwidth_hz=self.BANDWIDTH,
                estimator="bounded_correlation",
                component_window="full",
            )

        decoded = 128.0 + 256.0 * (measured - self.CENTER) / self.BANDWIDTH
        self.assertEqual(measured_intervals, intervals)
        self.assertEqual({stop - start for start, stop in intervals}, {48, 49})
        self.assertLess(estimator.call_count, len(values) // 4)
        self.assertLessEqual(float(np.median(np.abs(decoded - values))), 1.0)


class PictureCoordinatorTests(unittest.TestCase):
    @staticmethod
    def _event(index: int, octet: int, *, control_role: str | None = None) -> dict:
        return {
            "id": f"text-{index:04d}",
            "octet": octet,
            "control_role": control_role,
            "wire_interval": {
                "start": 10_000 + index * 100,
                "stop": 10_050 + index * 100,
            },
            "recognized_at_input_sample": 10_050 + index * 100,
            "confidence": {"value": 1.0},
            "damage_flags": [],
            "provenance": {},
        }

    def test_damaged_landmarks_trigger_exact_local_recovery(self) -> None:
        header = b"Pic:156x195C;"
        exact = [self._event(index, octet) for index, octet in enumerate(header)]
        decoded = MFSKTextDecode(
            mode_segment={},
            text_events=exact,
            text_summary={},
            diagnostics={},
            text_epochs=[],
        )

        class Recording:
            sample_rate = 48_000.0
            requested_start = 0
            requested_stop = 2_000_000

            @staticmethod
            def read_complex64(start: int, stop: int) -> np.ndarray:
                return np.zeros(stop - start, dtype=np.complex64)

        damaged_streams = (b"Pi:156x195C;", b"Pxc:156x195C;", bytes([4]))
        for stream in damaged_streams:
            events = [
                self._event(
                    index,
                    octet,
                    control_role="EOT" if octet == 4 else None,
                )
                for index, octet in enumerate(stream)
            ]
            if stream == bytes([4]):
                for index in range(1, 4):
                    damaged = self._event(index, ord("?"))
                    damaged["octet"] = None
                    damaged["damage_flags"] = ["invalid_varicode"]
                    events.append(damaged)
            with self.subTest(stream=stream), mock.patch(
                "grampy.pipeline.decode_mfsk_text", return_value=decoded
            ):
                refined, evidence = _refine_damaged_picture_headers(
                    Recording(), DecodeConfig(mode="MFSK64"), events
                )
            headers = [
                item["header_text"] for item in parse_picture_headers(refined)[0]
            ]
            self.assertEqual(headers, ["Pic:156x195C;"])
            self.assertTrue(any(item["status"] == "recovered" for item in evidence))

    def test_landmark_without_exact_local_header_does_not_create_picture(self) -> None:
        events = [self._event(0, 4, control_role="EOT")]
        for index in range(1, 4):
            damaged = self._event(index, ord("?"))
            damaged["octet"] = None
            damaged["damage_flags"] = ["invalid_varicode"]
            events.append(damaged)
        decoded = MFSKTextDecode(
            mode_segment={},
            text_events=[],
            text_summary={},
            diagnostics={},
            text_epochs=[],
        )

        class Recording:
            sample_rate = 48_000.0
            requested_start = 0
            requested_stop = 2_000_000

            @staticmethod
            def read_complex64(start: int, stop: int) -> np.ndarray:
                return np.zeros(stop - start, dtype=np.complex64)

        with mock.patch(
            "grampy.pipeline.decode_mfsk_text", return_value=decoded
        ):
            refined, evidence = _refine_damaged_picture_headers(
                Recording(), DecodeConfig(mode="MFSK64"), events
            )
        self.assertEqual(parse_picture_headers(refined)[0], [])
        self.assertEqual(evidence[0]["status"], "no_exact_header")

    def test_damaged_header_retries_at_half_symbol_alignment(self) -> None:
        events = [
            self._event(index, octet)
            for index, octet in enumerate(b"Pi:156x195C;")
        ]
        exact_events = [
            self._event(index, octet)
            for index, octet in enumerate(b"Pic:156x195C;")
        ]
        empty = MFSKTextDecode(
            mode_segment={}, text_events=[], text_summary={},
            diagnostics={}, text_epochs=[],
        )
        exact = MFSKTextDecode(
            mode_segment={}, text_events=exact_events, text_summary={},
            diagnostics={}, text_epochs=[],
        )

        class Recording:
            sample_rate = 48_000.0
            requested_start = 0
            requested_stop = 2_000_000

            @staticmethod
            def read_complex64(start: int, stop: int) -> np.ndarray:
                return np.zeros(stop - start, dtype=np.complex64)

        with mock.patch(
            "grampy.pipeline.decode_mfsk_text",
            side_effect=[empty, exact],
        ):
            refined, evidence = _refine_damaged_picture_headers(
                Recording(), DecodeConfig(mode="MFSK64"), events
            )
        headers = [
            item["header_text"] for item in parse_picture_headers(refined)[0]
        ]
        self.assertEqual(headers, ["Pic:156x195C;"])
        recovered = next(
            item for item in evidence if item["status"] == "recovered"
        )
        self.assertEqual(recovered["alignment_shift_input_samples"], -384)

    def test_suppresses_only_events_inside_accepted_picture_interval(self) -> None:
        def event(index: int, sample: int, octet: int = ord("x")) -> dict:
            return {
                "id": f"text-{index:04d}",
                "octet": octet,
                "control_role": None,
                "wire_interval": {"start": sample, "stop": sample + 10},
                "recognized_at_input_sample": sample,
            }

        events = [
            event(1, 90, ord("a")),
            event(2, 110),
            event(3, 190, ord("b")),
        ]
        text = MFSKTextDecode(
            mode_segment={},
            text_events=events,
            text_summary={"octets": [ord("a"), ord("x"), ord("b")], "text": "axb"},
            diagnostics={},
            text_epochs=[],
        )
        picture = {
            "prologue_interval": {"start": 100, "stop": 120},
            "return_to_text_reacquisition_interval": {"start": 180, "stop": 185},
            "end_alternatives": [{"input_sample": 180, "selected": True}],
        }
        decoded = PictureDecode([picture], [], [], {})
        _suppress_accepted_picture_text(text, decoded)
        self.assertEqual(
            [item["id"] for item in text.text_events],
            ["text-0001", "text-0003"],
        )
        self.assertEqual(text.text_summary["text"], "ab")
        self.assertEqual(picture["suppressed_text_event_ids"], ["text-0002"])


if __name__ == "__main__":
    unittest.main()
