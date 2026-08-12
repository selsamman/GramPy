from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np

from grampy.stateful_text import (
    PictureHeaderScanner,
    StatefulVaricodeParser,
)
from grampy.stateful_pipeline import StatefulBoundedTextReceiver
from grampy.text_decode import (
    FixedTrackToneObserver,
    StatefulToneObservation,
    _measure_received_tracks,
    _measure_received_tracks_from_reader,
    _observe_tracked_tones,
    plan_track_measurement_windows,
)
from grampy.tracking import (
    ClockTrack,
    FrequencyAnchor,
    FrequencyTrack,
)
from grampy.wire import (
    SoftDeinterleaver,
    StatefulSoftViterbiDecoder,
    _advance_viterbi_survivors,
    convolutional_encode,
    fldigi_gray_encode,
    fldigi_forward_interleave,
    soft_viterbi_decode,
)


class Session11CStateCarrySpikeTests(unittest.TestCase):
    def test_vectorized_viterbi_step_matches_scalar_tie_semantics(self) -> None:
        def scalar(path_metrics: np.ndarray, pair: np.ndarray):
            next_metrics = np.full(64, -np.inf)
            predecessors = np.zeros(64, dtype=np.uint8)
            input_bits = np.zeros(64, dtype=np.uint8)
            for state in range(64):
                if not np.isfinite(path_metrics[state]):
                    continue
                for bit in (0, 1):
                    encoder_state = ((state << 1) | bit) & 0x7F
                    coded = tuple(
                        (encoder_state & mask).bit_count() & 1
                        for mask in (0x6D, 0x4F)
                    )
                    branch = sum(
                        (1.0 if coded_bit else -1.0) * llr
                        for coded_bit, llr in zip(coded, pair)
                    )
                    next_state = encoder_state & 0x3F
                    candidate = path_metrics[state] + branch
                    if candidate > next_metrics[next_state]:
                        next_metrics[next_state] = candidate
                        predecessors[next_state] = state
                        input_bits[next_state] = bit
            next_metrics -= np.max(next_metrics)
            return next_metrics, predecessors, input_bits

        rng = np.random.default_rng(111)
        metrics = np.full(64, -np.inf)
        metrics[0] = 0.0
        pairs = [np.zeros(2), *rng.normal(size=(200, 2))]
        for pair in pairs:
            expected = scalar(metrics, pair)
            actual = _advance_viterbi_survivors(metrics, pair)
            np.testing.assert_array_equal(actual[0], expected[0])
            np.testing.assert_array_equal(actual[1], expected[1])
            np.testing.assert_array_equal(actual[2], expected[2])
            metrics = actual[0]

    def test_sustained_loss_is_chunk_equivalent_and_bounds_contamination(self) -> None:
        encodings = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "docs"
                / "decoder"
                / "data"
                / "mfsk_varicode.json"
            )
            .read_text(encoding="utf-8")
        )["encodings"]

        def transmission(text: bytes, start_symbol: int):
            bits = [int(bit) for octet in text for bit in encodings[octet]]
            groups = fldigi_forward_interleave(
                convolutional_encode([*bits, *([0] * 500)])
            )
            observations = []
            for offset, group in enumerate(groups):
                if len(group) != 4:
                    continue
                label = sum(bit << (3 - lane) for lane, bit in enumerate(group))
                tone = fldigi_gray_encode(label)
                metrics = np.full(16, -24.0)
                metrics[tone] = 0.0
                symbol = start_symbol + offset
                observations.append(
                    StatefulToneObservation(
                        symbol_index=symbol,
                        input_interval=(128 * symbol, 128 * (symbol + 1)),
                        log_metrics=tuple(metrics),
                        winner_runner_up_margin_nats=24.0,
                        noise_log_metric=-24.0,
                        erased=False,
                    )
                )
            return observations

        first = transmission(b"FIRST Pic:12x7Cp4; ", 0)
        loss_start_symbol = len(first)
        erased = [
            StatefulToneObservation(
                symbol_index=loss_start_symbol + index,
                input_interval=(
                    128 * (loss_start_symbol + index),
                    128 * (loss_start_symbol + index + 1),
                ),
                log_metrics=tuple([-np.log(16.0)] * 16),
                winner_runner_up_margin_nats=0.0,
                noise_log_metric=-np.log(16.0),
                erased=True,
            )
            for index in range(12)
        ]
        second_start = loss_start_symbol + len(erased)
        second = transmission(b"SECOND Pic:9x5; ", second_start)

        receiver = StatefulBoundedTextReceiver(orientation="normal")
        results = [receiver.push(first + erased[:5])]
        receiver = StatefulBoundedTextReceiver.restore(receiver.checkpoint())
        results.append(receiver.push(erased[5:]))
        receiver = StatefulBoundedTextReceiver.restore(receiver.checkpoint())
        results.append(receiver.push(second))
        results.append(receiver.finish_epoch())

        text_events = [event for result in results for event in result.text_events]
        headers = [header for result in results for header in result.picture_headers]
        resets = [event for result in results for event in result.reset_events]
        recovered = bytes(
            event["octet"] for event in text_events if event["octet"] is not None
        )

        self.assertIn(b"FIRST Pic:12x7Cp4;", recovered)
        self.assertIn(b"SECOND Pic:9x5;", recovered)
        self.assertEqual(
            [header["header_text"] for header in headers],
            ["Pic:12x7Cp4;", "Pic:9x5;"],
        )
        self.assertEqual(
            [event["cause"] for event in resets],
            ["sustained_signal_loss", "signal_recovered"],
        )
        self.assertEqual(receiver.epoch, 2)
        loss_start = erased[0].input_interval[0]
        loss_stop = erased[-1].input_interval[1]
        self.assertFalse(
            any(
                event["source_input_interval"] is not None
                and event["source_input_interval"]["start"] < loss_start
                and event["source_input_interval"]["stop"] > loss_stop
                for event in text_events
                if event["text_epoch"] == 2
            )
        )

    def test_track_measurement_uses_bounded_random_access(self) -> None:
        sample_rate = 8_000.0
        samples_per_symbol = 128
        samples = np.zeros(16_000, dtype=np.complex64)
        for symbol in range(len(samples) // samples_per_symbol):
            start = symbol * samples_per_symbol
            stop = start + samples_per_symbol
            tone_hz = 1_500.0 + ((5 * symbol) % 16 - 7.5) * 62.5
            samples[start:stop] = np.exp(
                2j
                * np.pi
                * tone_hz
                * np.arange(samples_per_symbol)
                / sample_rate
            )

        expected = _measure_received_tracks(
            samples,
            input_start=40_000,
            sample_rate=sample_rate,
            center_hz=1_500.0,
            samples_per_symbol=samples_per_symbol,
            tone_spacing_hz=62.5,
        )
        requests = []

        def reader(start: int, stop: int) -> np.ndarray:
            requests.append((start, stop))
            return samples[start:stop]

        actual = _measure_received_tracks_from_reader(
            reader,
            sample_count=len(samples),
            input_start=40_000,
            sample_rate=sample_rate,
            center_hz=1_500.0,
            samples_per_symbol=samples_per_symbol,
            tone_spacing_hz=62.5,
        )
        self.assertEqual(actual, expected)
        self.assertEqual(
            tuple(requests),
            plan_track_measurement_windows(
                sample_count=len(samples),
                sample_rate=sample_rate,
                samples_per_symbol=samples_per_symbol,
            ),
        )

        long_windows = plan_track_measurement_windows(
            sample_count=30 * 60 * 48_000,
            sample_rate=48_000.0,
            samples_per_symbol=768,
        )
        self.assertEqual(len(long_windows), 9)
        self.assertLessEqual(
            max(stop - start for start, stop in long_windows), 8 * 48_000
        )
        self.assertEqual(
            sum(stop - start for start, stop in long_windows), 72 * 48_000
        )
        self.assertEqual(long_windows[-1][1], 30 * 60 * 48_000)

    def test_fixed_track_iq_observer_is_sample_split_equivalent(self) -> None:
        sample_rate = 8_000.0
        clock = ClockTrack(
            epoch_input_sample=37.0,
            samples_per_symbol=128.0,
            rate_error_ppm=275.0,
        )
        frequency = FrequencyTrack(
            (
                FrequencyAnchor(0, 1_490.0, 0.2, "controlled"),
                FrequencyAnchor(8_000, 1_506.0, 0.2, "controlled"),
            )
        )
        tone_spacing = 62.5
        samples = np.zeros(8_000, dtype=np.complex64)
        generated_stop = 0
        for symbol in range(50):
            start, stop = clock.interval(symbol)
            if stop > len(samples):
                break
            tone = (7 * symbol + 3) % 16
            center = frequency.center_at((start + stop) // 2)
            tone_hz = center + (tone - 7.5) * tone_spacing
            time_axis = np.arange(stop - start) / sample_rate
            samples[start:stop] = np.exp(2j * np.pi * tone_hz * time_axis)
            generated_stop = stop

        expected = _observe_tracked_tones(
            samples,
            input_start=0,
            input_stop=generated_stop,
            sample_rate=sample_rate,
            frequency_track=frequency,
            clock_track=clock,
            tone_spacing_hz=tone_spacing,
        )
        observer = FixedTrackToneObserver(
            sample_rate=sample_rate,
            frequency_track=frequency,
            clock_track=clock,
            tone_spacing_hz=tone_spacing,
        )
        observations = []
        cursor = 0
        chunk_sizes = (1, 36, 91, 127, 2, 255, 64, 513, 17, 389)
        chunk_index = 0
        while cursor < generated_stop:
            stop = min(
                generated_stop,
                cursor + chunk_sizes[chunk_index % len(chunk_sizes)],
            )
            observations.extend(observer.push(samples[cursor:stop], input_start=cursor))
            if chunk_index in {1, 4, 8, 17}:
                observer = FixedTrackToneObserver.restore(
                    observer.checkpoint(),
                    sample_rate=sample_rate,
                    frequency_track=frequency,
                    clock_track=clock,
                    tone_spacing_hz=tone_spacing,
                )
            cursor = stop
            chunk_index += 1

        actual_metrics = np.asarray(
            [observation.log_metrics for observation in observations]
        )
        np.testing.assert_allclose(
            actual_metrics, expected["log_metrics"], rtol=0.0, atol=1e-12
        )
        self.assertEqual(
            [observation.input_interval for observation in observations],
            expected["intervals"],
        )
        np.testing.assert_array_equal(
            [observation.erased for observation in observations],
            expected["erased"],
        )
        self.assertLess(
            observer.maximum_retained_samples,
            int(np.ceil(clock.tracked_samples_per_symbol)),
        )

    def test_varicode_source_coordinates_survive_checkpoint(self) -> None:
        bits = tuple(map(int, "1010011100101"))
        intervals = [(10_000 + 17 * i, 10_000 + 17 * (i + 1)) for i in range(13)]
        whole = StatefulVaricodeParser().push(
            bits, [0.8] * len(bits), source_intervals=intervals
        )

        split = StatefulVaricodeParser()
        first = split.push(
            bits[:5], [0.8] * 5, source_intervals=intervals[:5]
        )
        restored = StatefulVaricodeParser()
        restored.restore(split.checkpoint())
        second = restored.push(
            bits[5:], [0.8] * 8, source_intervals=intervals[5:]
        )

        self.assertEqual(first + second, whole)
        self.assertTrue(
            all(event.source_input_interval is not None for event in whole)
        )
        for event in whole:
            start, stop = event.source_input_interval
            self.assertLess(start, stop)

    def test_header_checkpoint_is_transactional_and_coordinate_aware(self) -> None:
        def event(index: int, octet: int | None) -> dict:
            return {
                "id": f"text-{index:03d}",
                "octet": octet,
                "confidence": {"value": 0.9},
                "damage_flags": [],
                "source_input_interval": {
                    "start": 50_000 + 120 * index,
                    "stop": 50_000 + 120 * (index + 1),
                },
            }

        token = b"Pic:12x7Cp4;"
        scanner = PictureHeaderScanner()
        accepted, rejected = scanner.push(
            [event(index, value) for index, value in enumerate(token[:7])]
        )
        self.assertEqual((accepted, rejected), ([], 0))
        checkpoint = scanner.checkpoint()

        # Work after the checkpoint can be discarded together with its state.
        scanner.push([event(7, ord("Z"))])
        scanner = PictureHeaderScanner.restore(checkpoint)
        accepted, rejected = scanner.push(
            [event(index, value) for index, value in enumerate(token[7:], 7)]
        )

        self.assertEqual(rejected, 0)
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]["header_text"], token.decode("ascii"))
        self.assertEqual(
            accepted[0]["source_input_interval"],
            {"start": 50_000, "stop": 50_000 + 120 * len(token)},
        )
        self.assertEqual(scanner.push([]), ([], 0))

        discontinuous = PictureHeaderScanner()
        broken = [event(index, value) for index, value in enumerate(token)]
        broken.insert(5, event(99, None))
        self.assertEqual(discontinuous.push(broken), ([], 0))

    def test_viterbi_checkpoint_is_chunk_and_batch_equivalent(self) -> None:
        bits = tuple(np.random.default_rng(11).integers(0, 2, 400).tolist())
        llrs = np.asarray(
            [18.0 if bit else -18.0 for bit in convolutional_encode(bits)]
        )
        expected = soft_viterbi_decode(llrs).bits

        uninterrupted = StatefulSoftViterbiDecoder(traceback_depth=48)
        uninterrupted_events = list(uninterrupted.push(llrs))
        uninterrupted_events.extend(uninterrupted.finish())

        restored = StatefulSoftViterbiDecoder(traceback_depth=48)
        actual = []
        split_steps = [1, 2, 47, 48, 49, 117, 233, 399, 400]
        start_step = 0
        for stop_step in split_steps:
            actual.extend(restored.push(llrs[2 * start_step : 2 * stop_step]))
            checkpoint = restored.checkpoint()
            digest = restored.state_digest()
            restored = StatefulSoftViterbiDecoder.restore(checkpoint)
            self.assertEqual(restored.state_digest(), digest)
            start_step = stop_step
        actual.extend(restored.finish())

        self.assertEqual(tuple(event.bit for event in actual), expected)
        self.assertEqual(actual, uninterrupted_events)
        self.assertEqual(
            [event.decoded_bit_index for event in actual], list(range(len(bits)))
        )

    def test_checkpoint_rollback_contains_a_damaged_chunk(self) -> None:
        bits = tuple(np.random.default_rng(19).integers(0, 2, 240).tolist())
        llrs = np.asarray(
            [14.0 if bit else -14.0 for bit in convolutional_encode(bits)]
        )
        decoder = StatefulSoftViterbiDecoder(traceback_depth=48)
        accepted = list(decoder.push(llrs[:160]))
        checkpoint = decoder.checkpoint()

        damaged = llrs[160:200].copy()
        damaged[::2] *= -1
        discarded = decoder.push(damaged)
        self.assertTrue(discarded)

        decoder = StatefulSoftViterbiDecoder.restore(checkpoint)
        accepted.extend(decoder.push(llrs[160:]))
        accepted.extend(decoder.finish())

        self.assertEqual(tuple(event.bit for event in accepted), bits)
        self.assertEqual(decoder.committed_count, len(bits))

    def test_checkpoint_working_set_stays_bounded_by_traceback(self) -> None:
        bits = tuple(np.random.default_rng(23).integers(0, 2, 5_000).tolist())
        llrs = [9.0 if bit else -9.0 for bit in convolutional_encode(bits)]
        decoder = StatefulSoftViterbiDecoder(traceback_depth=48)
        decoder.push(llrs)
        checkpoint = decoder.checkpoint()

        self.assertEqual(decoder.uncommitted_count, 48)
        self.assertEqual(len(checkpoint["predecessors"]), 48)
        encoded = json.dumps(
            checkpoint, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
        self.assertLess(len(encoded), 10_000)

    def test_deinterleaver_fec_and_varicode_restore_mid_header(self) -> None:
        encodings = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "docs"
                / "decoder"
                / "data"
                / "mfsk_varicode.json"
            )
            .read_text(encoding="utf-8")
        )["encodings"]
        message = b"Pic:12x7Cp4; "
        decoded_bits = [
            int(bit) for octet in message for bit in encodings[octet]
        ]
        # Continue the real encoder/interleaver path long enough to drain the
        # receiver's 30-group deinterleaver history.
        transmitted = fldigi_forward_interleave(
            convolutional_encode([*decoded_bits, *([0] * 60)])
        )
        transmitted = [group for group in transmitted if len(group) == 4]

        deinterleaver = SoftDeinterleaver()
        viterbi = StatefulSoftViterbiDecoder(traceback_depth=48)
        parser = StatefulVaricodeParser()
        events = []
        for index, group in enumerate(transmitted):
            deinterleaved = deinterleaver.push(
                [16.0 if bit else -16.0 for bit in group]
            )
            committed = viterbi.push(deinterleaved)
            events.extend(
                parser.push(
                    [event.bit for event in committed],
                    [1.0] * len(committed),
                )
            )
            if index == 53:
                deinterleaver = SoftDeinterleaver.restore(
                    deinterleaver.checkpoint()
                )
                viterbi = StatefulSoftViterbiDecoder.restore(
                    viterbi.checkpoint()
                )
                parser_checkpoint = parser.checkpoint()
                parser = StatefulVaricodeParser()
                parser.restore(parser_checkpoint)

        tail = viterbi.finish()
        events.extend(
            parser.push([event.bit for event in tail], [1.0] * len(tail))
        )
        recovered = bytes(
            event.octet for event in events if event.octet is not None
        )

        self.assertIn(b"Pic:12x7Cp4;", recovered)


if __name__ == "__main__":
    unittest.main()
