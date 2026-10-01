from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import unittest

from grampy.text_encode import (
    MODE_PARAMETERS,
    StatefulTextToneEncoder,
    physical_tone_index,
    varicode_codeword,
)
from mfsk_encoder_evidence import (
    BINARY_LABEL_TO_TONE_INDEX,
    binary_labels,
    convolutional_encode,
    interleave_groups,
    physical_tone_indices,
)


ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_wire_vectors.json").read_text(
        encoding="utf-8"
    )
)
VARICODE = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_varicode.json").read_text(
        encoding="utf-8"
    )
)["encodings"]


class MfskTextToneEncoderTests(unittest.TestCase):
    def test_mode_parameters_match_frozen_wire_vectors(self) -> None:
        timing = VECTORS["mode_timing"]
        framing = VECTORS["transmission_framing"]
        for mode in ("MFSK32", "MFSK64"):
            with self.subTest(mode=mode):
                parameters = MODE_PARAMETERS[mode]
                self.assertEqual(parameters.internal_sample_rate_hz, 8000)
                self.assertEqual(
                    parameters.samples_per_symbol,
                    timing[mode]["samples_per_symbol"],
                )
                self.assertEqual(
                    parameters.symbols_per_second,
                    timing[mode]["symbols_per_second"],
                )
                self.assertEqual(parameters.tone_count, 16)
                self.assertEqual(parameters.bits_per_symbol, 4)
                self.assertEqual(
                    parameters.tone_spacing_hz,
                    timing[mode]["tone_spacing_hz"],
                )
                self.assertEqual(
                    parameters.tone_span_hz,
                    timing[mode]["tone_span_hz"],
                )
                self.assertEqual(parameters.interleaver_depth, 10)
                self.assertEqual(
                    parameters.preamble_input_bits,
                    framing[mode]["preamble_parameter_input_bits"],
                )

    def test_all_varicode_octets_match_the_frozen_table(self) -> None:
        for octet, expected in enumerate(VARICODE):
            with self.subTest(octet=octet):
                self.assertEqual(
                    "".join(map(str, varicode_codeword(octet))),
                    expected,
                )

    def test_every_convolutional_vector_matches_through_candidate_state(self) -> None:
        for vector in VECTORS["convolutional_code"]["vectors"]:
            with self.subTest(name=vector["name"]):
                encoder = StatefulTextToneEncoder("MFSK32")
                encoder.push_bits(map(int, vector["input_bits"]))
                checkpoint = encoder.checkpoint()
                coded = "".join(
                    str(bit)
                    for group in checkpoint.raw_group_history
                    for bit in group
                ) + "".join(map(str, checkpoint.pending_coded_bits))
                self.assertEqual(coded, vector["output_bits"])

    def test_short_text_vector_matches_every_intermediate_and_tone(self) -> None:
        vector = VECTORS["text_to_tones_from_reset"]
        encoder = StatefulTextToneEncoder("MFSK64")
        tones = encoder.push_bytes(bytes(vector["text_octets"]))
        checkpoint = encoder.checkpoint()
        self.assertEqual(list(tones), vector["normal_sideband_physical_tone_indices"])
        self.assertEqual(
            ["".join(map(str, group)) for group in checkpoint.raw_group_history],
            vector["complete_preinterleaver_groups"],
        )
        self.assertEqual(
            "".join(map(str, checkpoint.pending_coded_bits)),
            vector["residual_coded_bits"],
        )
        self.assertEqual(checkpoint.convolutional_state, int("1001100", 2))
        self.assertEqual(checkpoint.input_bit_count, len(vector["varicode_bits"]))
        self.assertEqual(checkpoint.input_octet_count, 3)
        self.assertEqual(checkpoint.group_count, 5)
        self.assertEqual(checkpoint.tone_count, 5)

    def test_all_binary_labels_map_to_exact_physical_tones(self) -> None:
        self.assertEqual(
            [physical_tone_index(label) for label in range(16)],
            list(BINARY_LABEL_TO_TONE_INDEX),
        )

    def test_all_octets_cover_steady_state_interleaving(self) -> None:
        data = bytes(range(256))
        bits = "".join(VARICODE[octet] for octet in data)
        coded = [int(bit) for bit in convolutional_encode(bits)]
        complete = len(coded) // 4
        groups = [coded[index * 4 : index * 4 + 4] for index in range(complete)]
        expected = physical_tone_indices(binary_labels(interleave_groups(groups)))

        encoder = StatefulTextToneEncoder("MFSK32")
        actual = encoder.push_bytes(data)
        self.assertEqual(list(actual), expected)
        checkpoint = encoder.checkpoint()
        self.assertEqual(
            checkpoint.pending_coded_bits,
            tuple(coded[complete * 4 :]),
        )
        self.assertEqual(len(checkpoint.raw_group_history), 30)

    def test_chunk_boundaries_do_not_change_tones_or_final_state(self) -> None:
        data = bytes(range(256))
        reference = StatefulTextToneEncoder("MFSK64")
        expected_tones = reference.push_bytes(data)
        expected_checkpoint = reference.checkpoint()

        for chunk_size in (1, 2, 3, 7, 16, 31, 64, 255, 256):
            with self.subTest(chunk_size=chunk_size):
                encoder = StatefulTextToneEncoder("MFSK64")
                tones: list[int] = []
                for start in range(0, len(data), chunk_size):
                    tones.extend(encoder.push_bytes(data[start : start + chunk_size]))
                    encoder = StatefulTextToneEncoder.restore(encoder.checkpoint())
                self.assertEqual(tuple(tones), expected_tones)
                self.assertEqual(encoder.checkpoint(), expected_checkpoint)

        for split in range(len(data) + 1):
            with self.subTest(split=split):
                encoder = StatefulTextToneEncoder("MFSK64")
                tones = encoder.push_bytes(data[:split]) + encoder.push_bytes(data[split:])
                self.assertEqual(tones, expected_tones)
                self.assertEqual(encoder.checkpoint(), expected_checkpoint)

    def test_modes_share_logical_tones_but_not_physical_parameters(self) -> None:
        data = b"mode-independent logical tones"
        encoder32 = StatefulTextToneEncoder("MFSK32")
        encoder64 = StatefulTextToneEncoder("MFSK64")
        self.assertEqual(encoder32.push_bytes(data), encoder64.push_bytes(data))
        self.assertNotEqual(
            encoder32.parameters.tone_spacing_hz,
            encoder64.parameters.tone_spacing_hz,
        )

    def test_partial_group_is_retained_and_completed_without_implicit_flush(self) -> None:
        encoder = StatefulTextToneEncoder("MFSK32")
        self.assertEqual(encoder.push_bits([1]), ())
        partial = encoder.checkpoint()
        self.assertEqual(partial.pending_coded_bits, (1, 1))
        self.assertEqual(partial.convolutional_state, 1)
        self.assertEqual(partial.group_count, 0)
        self.assertEqual(encoder.push_bytes(b""), ())
        self.assertEqual(encoder.checkpoint(), partial)

        self.assertEqual(encoder.push_bits([0]), (15,))
        complete = encoder.checkpoint()
        self.assertEqual(complete.raw_group_history, ((1, 1, 0, 1),))
        self.assertEqual(complete.pending_coded_bits, ())
        self.assertEqual(complete.group_count, 1)

    def test_checkpoint_restore_is_exact_across_a_partial_group(self) -> None:
        prefix = bytes(range(32))
        suffix = bytes(range(64))
        uninterrupted = StatefulTextToneEncoder("MFSK64")
        first_tones = uninterrupted.push_bytes(prefix)
        checkpoint = uninterrupted.checkpoint()
        if not checkpoint.pending_coded_bits:
            uninterrupted.push_bits([1])
            checkpoint = uninterrupted.checkpoint()
        self.assertEqual(len(checkpoint.raw_group_history), 30)
        self.assertEqual(len(checkpoint.pending_coded_bits), 2)
        expected_suffix = uninterrupted.push_bytes(suffix)
        expected_final = uninterrupted.checkpoint()

        restored = StatefulTextToneEncoder.restore(checkpoint)
        self.assertEqual(restored.push_bytes(suffix), expected_suffix)
        self.assertEqual(restored.checkpoint(), expected_final)
        self.assertTrue(first_tones)
        with self.assertRaises(FrozenInstanceError):
            checkpoint.group_count = 0  # type: ignore[misc]

    def test_malformed_checkpoints_are_rejected(self) -> None:
        encoder = StatefulTextToneEncoder("MFSK32")
        encoder.push_bytes(b"state")
        checkpoint = encoder.checkpoint()
        malformed = (
            replace(checkpoint, convolutional_state=128),
            replace(checkpoint, pending_coded_bits=(0,)),
            replace(checkpoint, raw_group_history=()),
            replace(checkpoint, tone_count=checkpoint.tone_count + 1),
            replace(checkpoint, input_bit_count=checkpoint.input_bit_count + 1),
        )
        for candidate in malformed:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    StatefulTextToneEncoder.restore(candidate)

    def test_input_validation_does_not_mutate_state(self) -> None:
        encoder = StatefulTextToneEncoder("MFSK32")
        checkpoint = encoder.checkpoint()
        with self.assertRaises(ValueError):
            encoder.push_bits([0, 2, 1])
        self.assertEqual(encoder.checkpoint(), checkpoint)
        with self.assertRaises(TypeError):
            encoder.push_bytes(bytearray(b"not-bytes"))  # type: ignore[arg-type]
        self.assertEqual(encoder.checkpoint(), checkpoint)
        with self.assertRaises(ValueError):
            StatefulTextToneEncoder("MFSK16")  # type: ignore[arg-type]

    def test_long_input_retains_fixed_interleaver_history(self) -> None:
        encoder = StatefulTextToneEncoder("MFSK32")
        encoder.push_bytes(bytes(range(256)) * 40)
        checkpoint = encoder.checkpoint()
        self.assertGreater(checkpoint.group_count, 30)
        self.assertEqual(len(checkpoint.raw_group_history), 30)


if __name__ == "__main__":
    unittest.main()
