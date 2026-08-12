from __future__ import annotations

import unittest

import numpy as np

from grampy.picture_decode import (
    decode_pictures,
    _fit_known_flush_grid,
    _fit_unified_boundary_grid,
    _locate_protocol_change,
    _protocol_boundary_prediction,
    _protocol_header_to_prologue_symbols,
    parse_picture_headers,
)
from grampy.pipeline import DecodeConfig
from grampy.text_decode import (
    _annotate_picture_flush_tones,
    _fit_transition_crossover_clock,
)
from grampy.tracking import ClockTrack, FrequencyTrack
from grampy.wire import fldigi_forward_interleave, picture_flush_tones


def header_events(payload: bytes, *, decoded_bit_stop: int) -> list[dict]:
    events = []
    for index, octet in enumerate(payload):
        event = {
            "id": f"text-{index:04d}",
            "octet": octet,
            "wire_interval": {"start": index * 10, "stop": index * 10 + 10},
            "recognized_at_input_sample": 100_000 if index == len(payload) - 1 else 0,
            "confidence": {"value": 1.0},
            "damage_flags": [],
            "provenance": {},
        }
        if index == len(payload) - 1:
            event["provenance"]["decoded_bit_interval"] = {
                "start": decoded_bit_stop - 9,
                "stop": decoded_bit_stop,
            }
        events.append(event)
    return events


class ProtocolPictureBoundaryTests(unittest.TestCase):
    def test_forward_interleaver_uses_fldigi_lane_delays(self) -> None:
        groups = [
            tuple((index >> lane) & 1 for lane in range(4))
            for index in range(31)
        ]
        interleaved = fldigi_forward_interleave(
            [bit for group in groups for bit in group]
        )
        self.assertEqual(
            interleaved[30],
            (groups[30][0], groups[20][1], groups[10][2], groups[0][3]),
        )

    def test_flush_tone_vector_accounts_for_coded_bit_accumulator(self) -> None:
        odd = picture_flush_tones([1, 0, 1, 1, 0], "MFSK64")
        even = picture_flush_tones([1, 0, 1, 1, 0, 1], "MFSK64")
        self.assertEqual(len(odd), 91)
        self.assertEqual(len(even), 90)
        self.assertEqual(
            odd[:24],
            [
                15, 0, 15, 15, 0, 0, 0, 0,
                7, 0, 0, 7, 0, 0, 0, 0,
                0, 0, 0, 0, 0, 0, 3, 3,
            ],
        )

    def test_group_phase_offsets_account_for_recognition_lane(self) -> None:
        self.assertEqual(_protocol_header_to_prologue_symbols("MFSK32", 100), 24)
        self.assertEqual(_protocol_header_to_prologue_symbols("MFSK32", 101), 23)
        self.assertEqual(_protocol_header_to_prologue_symbols("MFSK64", 100), 60)
        self.assertEqual(_protocol_header_to_prologue_symbols("MFSK64", 101), 60)

    def test_header_parser_retains_final_decoded_bit_phase(self) -> None:
        descriptors, rejected = parse_picture_headers(
            header_events(b"Pic:180x132C;", decoded_bit_stop=11_508)
        )
        self.assertEqual(rejected, 0)
        self.assertEqual(descriptors[0]["header_decoded_bit_stop"], 11_508)

    def test_header_event_carries_compact_flush_reconstruction(self) -> None:
        events = header_events(b"Pic:180x132C;", decoded_bit_stop=200)
        _annotate_picture_flush_tones(events, (0,) * 200, "MFSK32")
        descriptors, rejected = parse_picture_headers(events)
        self.assertEqual(rejected, 0)
        self.assertEqual(len(descriptors[0]["picture_flush_tones"]), 54)

    def test_prediction_is_explicitly_non_operative_and_uncertain(self) -> None:
        prediction = _protocol_boundary_prediction(
            mode="MFSK32",
            sample_rate=48_000.0,
            header_completed_at=21_276_806,
            header_decoded_bit_stop=11_508,
            prologue_count=2_112,
        )
        assert prediction is not None
        self.assertEqual(prediction["recognition_to_prologue_symbols"], 24)
        self.assertEqual(
            prediction["predicted_first_raster_input_sample"], 21_315_782
        )
        self.assertFalse(prediction["operative"])
        self.assertFalse(prediction["uncertainty_calibrated"])

    def test_experimental_change_score_recovers_synthetic_boundary(self) -> None:
        sample_rate = 48_000.0
        component_samples = 48
        predicted = 5_000
        expected = 1_000.0
        actual = predicted + 123
        component_frequencies = np.resize(
            np.asarray([1_200.0, 1_550.0, 1_350.0, 1_700.0]), 64
        )
        frequencies = np.full(
            actual + len(component_frequencies) * component_samples + 1_000,
            expected,
            dtype=np.float64,
        )
        frequencies[
            actual : actual + len(component_frequencies) * component_samples
        ] = np.repeat(component_frequencies, component_samples)
        phase = 2.0 * np.pi * np.cumsum(frequencies) / sample_rate
        samples = np.exp(1j * phase).astype(np.complex64)

        selected, _, _, alternatives = _locate_protocol_change(
            samples,
            predicted_raster=predicted,
            sample_rate=sample_rate,
            mode="MFSK64",
            prologue_count=2_112,
            expected_frequency=expected,
            center_hz=1_400.0,
            bandwidth_hz=937.5,
            component_samples=component_samples,
            component_count=len(component_frequencies),
        )

        self.assertEqual(selected, actual)
        self.assertTrue(alternatives[0]["selected"])
        self.assertTrue(
            all(
                abs(
                    left["first_raster_input_sample"]
                    - right["first_raster_input_sample"]
                )
                >= component_samples
                for left, right in zip(alternatives, alternatives[1:])
            )
        )

    def test_unified_boundary_estimator_is_the_only_supported_policy(self) -> None:
        current = DecodeConfig()
        self.assertEqual(current.picture_boundary_estimator, "unified_grid")
        self.assertEqual(
            current.to_dict()["picture_boundary_estimator"], "unified_grid"
        )
        with self.assertRaisesRegex(
            ValueError, "unsupported picture boundary estimator"
        ):
            DecodeConfig(picture_boundary_estimator="protocol_change")

    def test_known_flush_crossovers_recover_constructed_grid(self) -> None:
        sample_rate = 8_000.0
        symbol_samples = 256
        prologue_samples = 352
        center_hz = 1_500.0
        decoded_bits = tuple((index * 7 + 1) % 2 for index in range(200))
        tones = picture_flush_tones(decoded_bits, "MFSK32")
        actual_prologue = 50_000
        frequencies = np.full(80_000, center_hz - 468.75 / 2.0)
        flush_start = actual_prologue - len(tones) * symbol_samples
        for index, tone in enumerate(tones):
            start = flush_start + index * symbol_samples
            frequencies[start : start + symbol_samples] = (
                center_hz + (tone - 7.5) * 31.25
            )
        phase = 2.0 * np.pi * np.cumsum(frequencies) / sample_rate
        samples = np.exp(1j * phase).astype(np.complex64)

        fitted = _fit_known_flush_grid(
            samples,
            input_start=0,
            sample_rate=sample_rate,
            mode="MFSK32",
            orientation="normal",
            center_hz=center_hz,
            header_decoded_bit_stop=len(decoded_bits),
            decoded_bits=decoded_bits,
            known_flush_tones=tones,
            nominal_prologue_start=actual_prologue - 100,
            prologue_count=prologue_samples,
        )

        self.assertEqual(fitted["status"], "estimated")
        self.assertAlmostEqual(
            fitted["predicted_prologue_start_input_sample_fractional"],
            actual_prologue - 0.5,
            delta=0.75,
        )
        self.assertAlmostEqual(
            fitted["predicted_first_raster_input_sample_fractional"],
            actual_prologue + prologue_samples - 0.5,
            delta=0.75,
        )

    def test_global_crossover_clock_recovers_constructed_symbol_grid(self) -> None:
        sample_rate = 8_000.0
        symbol_samples = 128
        epoch = 1_000
        tones = np.resize(np.asarray([0, 15, 3, 12, 7, 8]), 180)
        frequencies = np.full(epoch + len(tones) * symbol_samples + 1_000, 1_500.0)
        for index, tone in enumerate(tones):
            start = epoch + index * symbol_samples
            frequencies[start : start + symbol_samples] = (
                1_500.0 + (tone - 7.5) * 62.5
            )
        phase = 2.0 * np.pi * np.cumsum(frequencies) / sample_rate
        samples = np.exp(1j * phase).astype(np.complex64)
        log_metrics = np.full((len(tones), 16), -20.0)
        log_metrics[np.arange(len(tones)), tones] = 0.0
        provisional = ClockTrack(
            epoch_input_sample=epoch + 30,
            samples_per_symbol=symbol_samples,
        )
        intervals = [provisional.interval(index) for index in range(len(tones))]

        fitted, evidence, _ = _fit_transition_crossover_clock(
            samples,
            input_start=0,
            sample_rate=sample_rate,
            frequency_track=FrequencyTrack.fixed(
                center_hz=1_500.0, input_sample=0
            ),
            provisional_clock=provisional,
            tone_spacing_hz=62.5,
            log_metrics=log_metrics,
            intervals=intervals,
            erased=np.zeros(len(tones), dtype=bool),
        )

        assert fitted is not None
        self.assertEqual(evidence["status"], "estimated")
        self.assertEqual(
            evidence["tone_sequence_source"],
            "adjacent_high_margin_tracked_winners",
        )
        self.assertAlmostEqual(fitted.epoch_input_sample, epoch - 0.5, delta=0.75)
        self.assertAlmostEqual(
            fitted.tracked_samples_per_symbol, symbol_samples, delta=0.01
        )

    def test_unified_grid_uses_local_flush_to_correct_global_phase(self) -> None:
        sample_rate = 8_000.0
        symbol_samples = 256.0
        prologue_samples = 352
        center_hz = 1_500.0
        decoded_bits = tuple((index * 7 + 1) % 2 for index in range(200))
        tones = picture_flush_tones(decoded_bits, "MFSK32")
        actual_prologue = 50_000.0
        frequencies = np.full(80_000, center_hz - 468.75 / 2.0)
        flush_start = int(actual_prologue - len(tones) * symbol_samples)
        for index, tone in enumerate(tones):
            start = flush_start + index * int(symbol_samples)
            frequencies[start : start + int(symbol_samples)] = (
                center_hz + (tone - 7.5) * 31.25
            )
        phase = 2.0 * np.pi * np.cumsum(frequencies) / sample_rate
        samples = np.exp(1j * phase).astype(np.complex64)
        flush = _fit_known_flush_grid(
            samples,
            input_start=0,
            sample_rate=sample_rate,
            mode="MFSK32",
            orientation="normal",
            center_hz=center_hz,
            header_decoded_bit_stop=len(decoded_bits),
            decoded_bits=decoded_bits,
            known_flush_tones=tones,
            nominal_prologue_start=actual_prologue - 100.0,
            prologue_count=prologue_samples,
        )
        prologue_symbol = 100
        global_prologue = actual_prologue + 40.0
        global_clock = ClockTrack(
            epoch_input_sample=(
                global_prologue - prologue_symbol * symbol_samples
            ),
            samples_per_symbol=symbol_samples,
        )

        unified = _fit_unified_boundary_grid(
            mode="MFSK32",
            sample_rate=sample_rate,
            prologue_count=prologue_samples,
            protocol_prediction={"prologue_symbol_index": prologue_symbol},
            symbol_clock=global_clock,
            symbol_clock_covariance=((400.0, 0.0), (0.0, 1e-4)),
            transition_clock_evidence={"observations": []},
            flush_grid_prediction=flush,
        )

        self.assertEqual(unified["status"], "estimated")
        self.assertEqual(
            unified["conditional_evidence"],
            "global_text_and_local_header_flush",
        )
        self.assertAlmostEqual(
            unified["predicted_prologue_start_input_sample_fractional"],
            actual_prologue - 0.5,
            delta=1.0,
        )
        self.assertGreater(
            abs(unified["global_prior"]["posterior_innovation"][0]), 30.0
        )
        self.assertTrue(
            all(
                "unified_residual_input_samples" in observation
                for observation in unified["header_flush_observations"]
                if observation.get("crossover_input_sample") is not None
            )
        )

    def test_unified_grid_increases_variance_when_flush_is_missing(self) -> None:
        symbol_samples = 768.0
        prologue_symbol = 120
        clock = ClockTrack(
            epoch_input_sample=1_000.0,
            samples_per_symbol=symbol_samples,
        )
        covariance = ((4.0, 0.0), (0.0, 1e-4))

        unified = _fit_unified_boundary_grid(
            mode="MFSK64",
            sample_rate=48_000.0,
            prologue_count=2_112,
            protocol_prediction={"prologue_symbol_index": prologue_symbol},
            symbol_clock=clock,
            symbol_clock_covariance=covariance,
            transition_clock_evidence={"observations": []},
            flush_grid_prediction=None,
        )

        self.assertEqual(unified["status"], "estimated")
        self.assertEqual(unified["conditional_evidence"], "global_text_only")
        self.assertAlmostEqual(
            unified["predicted_prologue_start_input_sample_fractional"],
            1_000.0 + prologue_symbol * symbol_samples,
        )
        self.assertGreater(unified["raster_uncertainty_input_samples"], 2.0)

    def test_unified_grid_robustly_uses_partial_damaged_flush(self) -> None:
        symbol_samples = 256.0
        actual_prologue = 50_000.0
        prologue_symbol = 100
        clock = ClockTrack(
            epoch_input_sample=(
                actual_prologue + 20.0
                - prologue_symbol * symbol_samples
            ),
            samples_per_symbol=symbol_samples,
        )
        covariance = ((400.0, 0.0), (0.0, 1e-4))

        def fit(relative_symbols: tuple[int, ...]) -> dict:
            observations = [
                {
                    "relative_symbol": float(relative_symbol),
                    "crossover_input_sample": (
                        actual_prologue
                        + relative_symbol * symbol_samples
                        + (1_000.0 if relative_symbol == -8 else 0.0)
                    ),
                    "base_weight": 1.0,
                    "status": "measured",
                }
                for relative_symbol in relative_symbols
            ]
            observations.append(
                {
                    "relative_symbol": -9.0,
                    "status": "rejected_no_crossover",
                    "retained": False,
                }
            )
            return _fit_unified_boundary_grid(
                mode="MFSK32",
                sample_rate=8_000.0,
                prologue_count=352,
                protocol_prediction={
                    "prologue_symbol_index": prologue_symbol
                },
                symbol_clock=clock,
                symbol_clock_covariance=covariance,
                transition_clock_evidence={"observations": []},
                flush_grid_prediction={
                    "observations": observations,
                    "residual_sigma_input_samples": 0.25,
                },
            )

        complete = fit(tuple(range(-8, 0)))
        partial = fit((-8, -4, -1))

        self.assertAlmostEqual(
            complete["predicted_prologue_start_input_sample_fractional"],
            actual_prologue,
            delta=1.0,
        )
        measured = [
            observation
            for observation in complete["header_flush_observations"]
            if observation.get("crossover_input_sample") is not None
        ]
        self.assertLess(
            measured[0]["unified_robust_weight"],
            measured[1]["unified_robust_weight"] / 100.0,
        )
        self.assertTrue(
            any(
                observation.get("status") == "rejected_no_crossover"
                for observation in complete["header_flush_observations"]
            )
        )
        self.assertGreater(
            partial["parameter_covariance"][0][0],
            complete["parameter_covariance"][0][0],
        )

    def test_global_grid_selects_semantic_start_before_leading_zeros(self) -> None:
        sample_rate = 48_000.0
        symbol_samples = 768.0
        epoch = 1_000.0
        recognized_symbol = 50
        decoded_bit_stop = 100
        prologue_symbol = recognized_symbol + 60
        prologue_start = epoch + prologue_symbol * symbol_samples
        raster_start = prologue_start + 2_112
        values = np.asarray([0, 0, 0, 255, 32, 96, 160, 224], dtype=np.uint8)
        component_samples = 48
        center_hz = 1_500.0
        bandwidth_hz = 937.5
        decoded_bits = tuple((index * 7 + 1) % 2 for index in range(decoded_bit_stop))
        flush_tones = picture_flush_tones(decoded_bits, "MFSK64")
        sample_count = int(raster_start) + len(values) * component_samples + 4_000
        frequencies = np.full(sample_count, center_hz, dtype=np.float64)
        flush_start = int(prologue_start) - len(flush_tones) * int(symbol_samples)
        for index, tone in enumerate(flush_tones):
            start = flush_start + index * int(symbol_samples)
            frequencies[start : start + int(symbol_samples)] = (
                center_hz + (tone - 7.5) * 62.5
            )
        frequencies[int(prologue_start) : int(raster_start)] = (
            center_hz - bandwidth_hz / 2.0
        )
        for index, value in enumerate(values):
            start = int(raster_start) + index * component_samples
            frequencies[start : start + component_samples] = (
                center_hz
                + bandwidth_hz * (float(value) - 128.0) / 256.0
            )
        phase = 2.0 * np.pi * np.cumsum(frequencies) / sample_rate
        samples = np.exp(1j * phase).astype(np.complex64)

        events = header_events(b"Pic:8x1;", decoded_bit_stop=decoded_bit_stop)
        final = events[-1]
        final["recognized_at_input_sample"] = int(
            epoch + recognized_symbol * symbol_samples
        )
        final["provenance"]["recognized_symbol"] = recognized_symbol
        final["provenance"]["picture_flush_tones"] = flush_tones
        final["provenance"]["transition_crossover_clock"] = {
            "status": "estimated",
            "epoch_input_sample": epoch,
            "nominal_symbol_samples": symbol_samples,
            "estimated_rate_error_ppm": 0.0,
            "phase_uncertainty_input_samples": 0.25,
            "parameter_covariance": [[0.04, 0.0], [0.0, 1e-8]],
            "residual_sigma_input_samples": 0.25,
            "operative": False,
        }

        unified_decoded = decode_pictures(
            samples,
            input_start=0,
            sample_rate=sample_rate,
            mode="MFSK64",
            orientation="normal",
            center_hz=center_hz,
            text_events=events,
            component_estimator="bounded_correlation",
            component_window="full",
            boundary_estimator="unified_grid",
        )
        unified_picture = unified_decoded.pictures[0]
        self.assertAlmostEqual(
            unified_picture["first_raster_input_sample_fractional"],
            raster_start - 0.5,
            delta=0.75,
        )
        self.assertEqual(
            unified_decoded.transitions[0]["alignment"]["kind"],
            "unified_global_text_local_header_flush_grid",
        )
        self.assertNotIn(
            "agreement_gate",
            unified_picture["protocol_boundary_prediction"],
        )
        self.assertEqual(
            unified_picture["protocol_boundary_prediction"]
            ["unified_grid_estimate"]["conditional_evidence"],
            "global_text_and_local_header_flush",
        )
        self.assertEqual(
            unified_picture["protocol_boundary_prediction"]["status"],
            "qualified_unified_global_text_local_header_flush_grid",
        )
        self.assertEqual(
            unified_picture["component_clock"]["rate_error_ppm"], 0.0
        )
        actual = unified_decoded.artifacts[0]["values"]
        self.assertLessEqual(
            max(
                abs(int(left) - int(right))
                for left, right in zip(actual, values)
            ),
            2,
        )


if __name__ == "__main__":
    unittest.main()
