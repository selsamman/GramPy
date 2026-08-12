from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

import numpy as np

from grampy.cli import build_parser
from grampy.picture_decode import (
    ComponentClock,
    PictureJob,
    PictureRangeCancelled,
    PictureRangeConfig,
    PictureRangeFailure,
    PictureSampleSource,
    _assemble_raster,
    _fractional_component_frequencies,
    _isolate_picture_channel,
    _picture_component_ranges,
    decode_picture_component_ranges,
)
from grampy.pipeline import (
    DecodeConfig,
    _decode_bounded_text,
    _p11d_compact_text_enabled,
    _p11d_picture_ranges_enabled,
)
from grampy.sigmf import SigmfRecording
from grampy.stateful_pipeline import (
    P11DTextEvidencePass,
    StatefulBoundedTextReceiver,
    adapt_stateful_text_events,
)
from grampy.tracking import ClockTrack, FrequencyTrack
from grampy.text_decode import plan_received_tracks_from_reader
from grampy.wire import StatefulPictureFlushEncoder, picture_flush_tones


RATE = 8_000.0
CENTER = 1_500.0
BAND = 937.5


def source_samples(count: int) -> np.ndarray:
    index = np.arange(count, dtype=np.float64)
    component = (index.astype(np.int64) // 8) % 256
    frequency = CENTER + (component - 127.5) * (BAND / 256.0)
    phase = np.cumsum(2.0 * np.pi * frequency / RATE)
    return np.exp(1j * phase).astype(np.complex64)


class Session11EPictureRangeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.data = root / "picture.sigmf-data"
        self.meta = root / "picture.sigmf-meta"
        self.samples = source_samples(8 * 4_097 + 2_048)
        pairs = np.column_stack((self.samples.real, self.samples.imag)).astype("<f4")
        pairs.tofile(self.data)
        self.meta.write_text(json.dumps({
            "global": {"core:datatype": "cf32_le", "core:sample_rate": RATE},
            "captures": [{"core:sample_start": 0}],
        }))
        self.recording = SigmfRecording.open(self.meta, self.data)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def job(self, *, components: int = 4_097) -> PictureJob:
        return PictureJob(
            id="picture-test",
            source_identity=str(self.data.resolve()),
            source_start=0,
            source_stop=len(self.samples),
            component_count=components,
            component_clock=ComponentClock(
                epoch_input_sample=257.25,
                samples_per_component=8.0,
                rate_error_ppm=73.0,
            ),
            sample_rate=RATE,
            center_hz=CENTER,
            bandwidth_hz=BAND,
            orientation="normal",
            component_estimator="bounded_correlation",
            component_window="full",
            filter_profile="response_matched",
        )

    def bounded_source(self, reader=None) -> PictureSampleSource:
        return PictureSampleSource(
            input_start=0,
            input_stop=len(self.samples),
            identity=str(self.data.resolve()),
            reader=reader or self.recording.read_complex64,
        )

    def test_one_and_multiple_workers_are_exact_to_whole_filter(self) -> None:
        job = self.job()
        whole = _isolate_picture_channel(
            self.recording.read_complex64(0, len(self.samples)),
            RATE, CENTER, BAND, profile="response_matched",
        )
        expected_frequency, expected_quality, expected_intervals = (
            _fractional_component_frequencies(
                whole,
                job.component_count,
                RATE,
                component_clock=job.component_clock,
                center_hz=CENTER,
                bandwidth_hz=BAND,
                estimator="bounded_correlation",
                component_window="full",
            )
        )
        results = []
        for workers, in_flight in ((1, 1), (2, 2), (4, 3)):
            result = decode_picture_component_ranges(
                job,
                self.bounded_source(),
                PictureRangeConfig(
                    workers=workers,
                    components_per_range=997,
                    max_in_flight_ranges=in_flight,
                ),
            )
            np.testing.assert_array_equal(result.frequencies, expected_frequency)
            np.testing.assert_array_equal(result.quality, expected_quality)
            self.assertEqual(result.component_intervals, tuple(expected_intervals))
            results.append(result)
        self.assertEqual(
            results[0].diagnostics["filtered_range_sha256"],
            results[1].diagnostics["filtered_range_sha256"],
        )
        self.assertEqual(
            results[0].diagnostics["filtered_range_sha256"],
            results[2].diagnostics["filtered_range_sha256"],
        )

    def test_ranges_cover_indices_once_and_preserve_color_order(self) -> None:
        ranges = _picture_component_ranges(self.job(components=25), 7)
        indices = [
            index
            for item in ranges
            for index in range(item.first_component, item.stop_component)
        ]
        self.assertEqual(indices, list(range(25)))
        values = np.arange(24, dtype=np.uint8)
        color = _assemble_raster(values, 4, 2, True)
        np.testing.assert_array_equal(color[0, :, 0], values[0:4])
        np.testing.assert_array_equal(color[0, :, 1], values[4:8])
        np.testing.assert_array_equal(color[0, :, 2], values[8:12])
        np.testing.assert_array_equal(color[1, :, 0], values[12:16])
        np.testing.assert_array_equal(color[1, :, 1], values[16:20])
        np.testing.assert_array_equal(color[1, :, 2], values[20:24])
        self.assertEqual(_assemble_raster(values[:8], 4, 2, False).shape, (2, 4))

    def test_first_and_last_recording_edges_and_component_speeds(self) -> None:
        whole = _isolate_picture_channel(
            self.recording.read_complex64(0, len(self.samples)),
            RATE, CENTER, BAND, profile="response_matched",
        )
        for samples_per_component in (2.0, 4.0, 8.0):
            count = int((len(self.samples) - 1) // samples_per_component)
            clock = ComponentClock(
                epoch_input_sample=0.0,
                samples_per_component=samples_per_component,
                rate_error_ppm=31.0,
            )
            while count and clock.interval(count - 1)[1] > len(self.samples):
                count -= 1
            template = self.job(components=count)
            job = PictureJob(
                **{
                    **template.__dict__,
                    "component_count": count,
                    "component_clock": clock,
                }
            )
            expected = _fractional_component_frequencies(
                whole, count, RATE, component_clock=clock,
                center_hz=CENTER, bandwidth_hz=BAND,
                estimator="bounded_correlation", component_window="full",
            )
            actual = decode_picture_component_ranges(
                job,
                self.bounded_source(),
                PictureRangeConfig(
                    workers=2, components_per_range=1001,
                    max_in_flight_ranges=2,
                ),
            )
            np.testing.assert_array_equal(actual.frequencies, expected[0])
            np.testing.assert_array_equal(actual.quality, expected[1])
            self.assertEqual(actual.component_intervals, tuple(expected[2]))

    def test_cancellation_and_worker_failure_are_explicit(self) -> None:
        with self.assertRaises(PictureRangeCancelled):
            decode_picture_component_ranges(
                self.job(), self.bounded_source(), PictureRangeConfig(),
                cancelled=lambda: True,
            )

        def broken_reader(start: int, stop: int) -> np.ndarray:
            raise OSError("controlled read failure")

        with self.assertRaisesRegex(PictureRangeFailure, "range 0"):
            decode_picture_component_ranges(
                self.job(),
                self.bounded_source(broken_reader),
                PictureRangeConfig(workers=2, max_in_flight_ranges=1),
            )

    def test_in_flight_depth_is_independent_of_worker_count(self) -> None:
        active = 0
        maximum = 0
        lock = threading.Lock()

        def measured_reader(start: int, stop: int) -> np.ndarray:
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                return self.recording.read_complex64(start, stop)
            finally:
                with lock:
                    active -= 1

        decode_picture_component_ranges(
            self.job(),
            self.bounded_source(measured_reader),
            PictureRangeConfig(
                workers=4, components_per_range=512, max_in_flight_ranges=2
            ),
        )
        self.assertLessEqual(maximum, 2)

    def test_configuration_exposes_three_separate_controls(self) -> None:
        config = DecodeConfig(
            picture_range_workers=2,
            picture_range_components=2048,
            picture_max_in_flight_ranges=3,
        ).to_dict()
        self.assertEqual(config["picture_range_workers"], 2)
        self.assertEqual(config["picture_range_components"], 2048)
        self.assertEqual(config["picture_max_in_flight_ranges"], 3)

    def test_large_picture_beyond_received_corpus_stays_range_bounded(self) -> None:
        component_count = 262_145
        samples = source_samples(component_count * 2 + 1_024)
        clock = ComponentClock(epoch_input_sample=0.0, samples_per_component=2.0)
        job = PictureJob(
            id="large-picture",
            source_identity="large-synthetic",
            source_start=0,
            source_stop=len(samples),
            component_count=component_count,
            component_clock=clock,
            sample_rate=RATE,
            center_hz=CENTER,
            bandwidth_hz=BAND,
            orientation="normal",
            component_estimator="bounded_correlation",
            component_window="full",
            filter_profile="response_matched",
        )
        source = PictureSampleSource(
            input_start=0,
            input_stop=len(samples),
            identity="large-synthetic",
            reader=lambda start, stop: samples[start:stop],
        )
        sequential = decode_picture_component_ranges(
            job, source,
            PictureRangeConfig(
                workers=1, components_per_range=32_768,
                max_in_flight_ranges=1,
            ),
        )
        parallel = decode_picture_component_ranges(
            job, source,
            PictureRangeConfig(
                workers=2, components_per_range=32_768,
                max_in_flight_ranges=2,
            ),
        )
        np.testing.assert_array_equal(sequential.frequencies, parallel.frequencies)
        np.testing.assert_array_equal(sequential.quality, parallel.quality)
        self.assertEqual(
            sequential.diagnostics["filtered_range_sha256"],
            parallel.diagnostics["filtered_range_sha256"],
        )
        self.assertLess(
            sequential.diagnostics["maximum_range_output_samples"],
            component_count * 2,
        )

    def test_text_epochs_close_only_at_explicit_semantic_boundaries(self) -> None:
        receiver = StatefulBoundedTextReceiver(
            orientation="normal", traceback_depth=384
        )
        with self.assertRaisesRegex(ValueError, "closure cause"):
            receiver.close_epoch("administrative_window")
        result = receiver.close_epoch(
            "picture", affected_interval=(100, 200), initial_state=None
        )
        self.assertEqual(receiver.epoch, 2)
        self.assertEqual(result.reset_events[0]["cause"], "picture")
        self.assertEqual(
            result.reset_events[0]["affected_interval"],
            {"start": 100, "stop": 200},
        )
        self.assertEqual(receiver.traceback_depth, 384)

    def test_text_observer_and_receiver_rollback_as_one_transaction(self) -> None:
        track = FrequencyTrack.fixed(center_hz=CENTER)
        clock = ClockTrack(epoch_input_sample=0.0, samples_per_symbol=128.0)
        coordinator = P11DTextEvidencePass(
            sample_rate=RATE,
            tone_spacing_hz=62.5,
            frequency_track=track,
            clock_track=clock,
            orientation="normal",
        )
        samples = source_samples(512)
        coordinator.push(samples[:200], input_start=0)
        before = coordinator.checkpoint()
        with self.assertRaisesRegex(ValueError, "contiguous"):
            coordinator.push(samples[200:300], input_start=201)
        after = coordinator.checkpoint()
        self.assertEqual(after["observer"], before["observer"])
        self.assertEqual(after["receiver"], before["receiver"])
        self.assertEqual(after["accounting"]["rollback_count"], 1)
        coordinator.push(samples[200:], input_start=200)
        restored = P11DTextEvidencePass.restore(
            coordinator.checkpoint(), frequency_track=track, clock_track=clock
        )
        self.assertEqual(restored.state_digest(), coordinator.state_digest())
        self.assertLess(restored.diagnostics()["maximum_retained_iq_samples"], 128)

    def test_picture_interval_advances_track_without_decoding_raster(self) -> None:
        track = FrequencyTrack.fixed(center_hz=CENTER)
        clock = ClockTrack(epoch_input_sample=0.0, samples_per_symbol=128.0)
        coordinator = P11DTextEvidencePass(
            sample_rate=RATE,
            tone_spacing_hz=62.5,
            frequency_track=track,
            clock_track=clock,
            orientation="normal",
        )
        samples = source_samples(768)
        coordinator.push(samples[:256], input_start=0)
        closure = coordinator.close_epoch(
            "picture", affected_interval=(256, 512), initial_state=None
        )
        coordinator.skip_picture_interval(input_start=256, input_stop=512)
        coordinator.push(samples[512:], input_start=512)
        self.assertEqual(coordinator.epoch, 2)
        self.assertEqual(closure.reset_events[0]["cause"], "picture")
        self.assertEqual(
            coordinator.checkpoint()["observer"]["expected_input_start"], 768
        )
        self.assertEqual(coordinator.diagnostics()["requested_samples"], 768)

    def test_compact_track_plan_uses_bounded_recording_reads(self) -> None:
        frequency, clock, diagnostics = plan_received_tracks_from_reader(
            self.recording.read_complex64,
            input_start=0,
            input_stop=len(self.samples),
            sample_rate=RATE,
            mode="MFSK64",
            center_hz=CENTER,
        )
        self.assertLessEqual(diagnostics["measurement_window_count"], 9)
        self.assertLessEqual(
            diagnostics["maximum_materialized_iq_samples"], int(8 * RATE)
        )
        self.assertTrue(frequency.anchors)
        self.assertGreater(clock.tracked_samples_per_symbol, 0)

    def test_compact_picture_flush_state_is_exact_to_full_prefix(self) -> None:
        bits = np.random.default_rng(1105).integers(0, 2, 2_003).tolist()
        encoder = StatefulPictureFlushEncoder()
        start = 0
        for stop in (1, 2, 59, 60, 61, 998, 1_999, len(bits)):
            encoder.push(bits[start:stop])
            encoder = StatefulPictureFlushEncoder.restore(encoder.checkpoint())
            for mode in ("MFSK32", "MFSK64"):
                self.assertEqual(
                    encoder.predict_flush(mode), picture_flush_tones(bits[:stop], mode)
                )
            start = stop
        encoded = json.dumps(encoder.checkpoint(), separators=(",", ":"))
        self.assertLess(len(encoded), 700)

    def test_public_adapter_preserves_frozen_nominal_coordinates(self) -> None:
        source = [{
            "octet": 65,
            "codeword": "101010",
            "confidence": {"value": 0.75},
            "damage_flags": [],
            "source_bit_interval": {"start": 68, "stop": 75},
            "recognized_at_bit": 76,
            "source_input_interval": {"start": 1200, "stop": 1800},
            "source_coordinate_status": "complete",
            "text_epoch": 1,
            "decision_available_at_input_sample": 2400,
        }]
        event = adapt_stateful_text_events(
            source,
            mode_segment_id="mode-test",
            clock_track=ClockTrack(
                epoch_input_sample=920.0,
                samples_per_symbol=1536.0,
                rate_error_ppm=100.0,
            ),
        )[0]
        self.assertEqual(event["wire_interval"], {
            "start": 920 + 4 * 1536,
            "stop": 920 + 38 * 1536,
        })
        self.assertEqual(event["recognized_at_input_sample"], 920 + 38 * 1536)
        self.assertEqual(
            event["provenance"]["decision_available_at_input_sample"], 2400
        )

    def test_long_resolved_fixed_mode_routes_to_compact_p11d(self) -> None:
        recording = mock.Mock(
            requested_start=0, requested_stop=20_000, sample_rate=8_000.0
        )
        acquisition = mock.Mock(mode_segments=({
            "id": "mode-rsid",
            "mode": "MFSK64",
            "orientation": "normal",
            "center_hz": CENTER,
            "interval": {"start": 1_000, "stop": 19_000},
        },))
        sentinel = object()
        with mock.patch(
            "grampy.pipeline._decode_p11d_bounded_text",
            return_value=sentinel,
        ) as compact:
            result = _decode_bounded_text(
                recording, acquisition, DecodeConfig(mode="MFSK64"),
                run_wall_start=0.0,
            )
        self.assertIs(result, sentinel)
        compact.assert_called_once()

    def test_supported_hybrid_routes_only_qualified_mfsk64_to_p11d(self) -> None:
        mfsk32 = DecodeConfig(mode="MFSK32")
        mfsk64 = DecodeConfig(mode="MFSK64")
        self.assertEqual(mfsk32.pipeline_organization, "supported_hybrid")
        self.assertEqual(
            mfsk32.to_dict()["pipeline_organization"], "supported_hybrid"
        )
        self.assertFalse(_p11d_compact_text_enabled(mfsk32))
        self.assertFalse(_p11d_picture_ranges_enabled(mfsk32))
        self.assertTrue(_p11d_compact_text_enabled(mfsk64))
        self.assertTrue(_p11d_picture_ranges_enabled(mfsk64))

        forced = DecodeConfig(mode="MFSK32", pipeline_organization="p11d")
        self.assertTrue(_p11d_compact_text_enabled(forced))
        self.assertTrue(_p11d_picture_ranges_enabled(forced))

        arguments = build_parser().parse_args([
            "--in-meta", "input.sigmf-meta",
            "--in-data", "input.sigmf-data",
            "--out-manifest", "output.json",
        ])
        self.assertEqual(arguments.pipeline_organization, "supported_hybrid")


if __name__ == "__main__":
    unittest.main()
