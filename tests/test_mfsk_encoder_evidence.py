from __future__ import annotations

from pathlib import Path
import unittest

from mfsk_encoder_evidence import (
    EvidenceMismatch,
    FIXTURE_EVIDENCE_SHA256,
    BINARY_LABEL_TO_TONE_INDEX,
    MODE_PARAMETERS,
    PRIMARY_RGB_PPM_SHA256,
    VARICODE_SHA256,
    WIRE_VECTORS_SHA256,
    binary_labels,
    color_row_plane_values,
    convolutional_encode,
    count_symbols,
    grayscale_values,
    interleave_groups,
    load_json,
    physical_tone_indices,
    picture_control_token,
    pixel_frequencies,
    prologue_output_frames,
    raster_output_frames,
    read_ppm,
    require_close,
    require_exact,
    sha256,
)


ROOT = Path(__file__).resolve().parents[1]
WIRE_VECTORS = ROOT / "docs" / "decoder" / "data" / "mfsk_wire_vectors.json"
VARICODE = ROOT / "docs" / "decoder" / "data" / "mfsk_varicode.json"
FIXTURE_EVIDENCE = (
    ROOT / "docs" / "decoder" / "data" / "mfsk_fixture_evidence.json"
)
PACKAGED_DATA = ROOT / "src" / "grampy" / "data"
PRIMARY_RGB_PPM = ROOT / "tests" / "fixtures" / "mfsk" / "primary-color-8x4.ppm"


class OfflineEncoderOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vectors = load_json(WIRE_VECTORS)
        cls.varicode = load_json(VARICODE)["encodings"]

    def test_oracle_inputs_have_frozen_identity_and_match_packaged_copies(self) -> None:
        for path, expected in (
            (WIRE_VECTORS, WIRE_VECTORS_SHA256),
            (VARICODE, VARICODE_SHA256),
            (FIXTURE_EVIDENCE, FIXTURE_EVIDENCE_SHA256),
            (PRIMARY_RGB_PPM, PRIMARY_RGB_PPM_SHA256),
        ):
            self.assertEqual(sha256(path), expected, path)
        for filename in (
            "mfsk_wire_vectors.json",
            "mfsk_varicode.json",
            "mfsk_fixture_evidence.json",
        ):
            self.assertEqual(
                (WIRE_VECTORS.parent / filename).read_bytes(),
                (PACKAGED_DATA / filename).read_bytes(),
            )

    def test_all_varicode_octets_are_exact_and_uniquely_terminated(self) -> None:
        self.assertEqual(load_json(VARICODE)["schema"], "grampy-varicode.v1")
        self.assertEqual(len(self.varicode), 256)
        self.assertEqual(len(set(self.varicode)), 256)
        for octet, codeword in enumerate(self.varicode):
            with self.subTest(octet=octet):
                self.assertTrue(codeword.startswith("1"))
                self.assertTrue(codeword.endswith("00"))
                self.assertNotIn("00", codeword.rstrip("0"))
        self.assertEqual(
            [self.varicode[index] for index in (0, 2, 4, 13, 32, 101, 116, 255)],
            [
                "11101011100",
                "11101101000",
                "11101110000",
                "10101100",
                "100",
                "1000",
                "1100",
                "11101011000",
            ],
        )

    def test_every_fec_vector_matches_the_independent_equations(self) -> None:
        for vector in self.vectors["convolutional_code"]["vectors"]:
            self.assertEqual(
                convolutional_encode(vector["input_bits"]),
                vector["output_bits"],
                vector["name"],
            )

    def test_interleaver_and_text_to_tone_vectors_are_exact(self) -> None:
        vector = self.vectors["text_to_tones_from_reset"]
        bits = "".join(self.varicode[octet] for octet in vector["text_octets"])
        self.assertEqual(bits, vector["varicode_bits"])
        coded = convolutional_encode(bits)
        self.assertEqual(coded, vector["convolutional_bits"])
        groups = [
            [int(bit) for bit in coded[offset : offset + 4]]
            for offset in range(0, len(coded) - len(coded) % 4, 4)
        ]
        interleaved = interleave_groups(groups)
        self.assertEqual(
            ["".join(map(str, group)) for group in interleaved],
            vector["interleaved_groups"],
        )
        labels = binary_labels(interleaved)
        self.assertEqual(labels, vector["packed_binary_labels"])
        self.assertEqual(
            physical_tone_indices(labels),
            vector["normal_sideband_physical_tone_indices"],
        )
        self.assertEqual(
            physical_tone_indices(range(16)),
            list(BINARY_LABEL_TO_TONE_INDEX),
        )
        independently_calculated = []
        for label in range(16):
            tone = label
            for shift in range(1, 4):
                tone ^= label >> shift
            independently_calculated.append(tone)
        self.assertEqual(list(BINARY_LABEL_TO_TONE_INDEX), independently_calculated)

    def test_mode_and_framing_counts_are_exact(self) -> None:
        timing = self.vectors["mode_timing"]
        framing = self.vectors["transmission_framing"]
        start_character_bits = sum(
            len(self.varicode[octet]) for octet in framing["start_characters"]
        )
        end_character_bits = sum(
            len(self.varicode[octet]) for octet in framing["end_characters"]
        )
        self.assertEqual(start_character_bits, 27)
        self.assertEqual(end_character_bits, 27)
        for mode, expected in MODE_PARAMETERS.items():
            with self.subTest(mode=mode):
                actual = timing[mode]
                self.assertEqual(actual["symbols_per_second"], expected["symbols_per_second"])
                self.assertEqual(actual["tone_spacing_hz"], expected["tone_spacing_hz"])
                self.assertEqual(actual["tone_span_hz"], expected["tone_span_hz"])
                self.assertEqual(
                    framing[mode]["fldigi_4_2_12_transmitted_leading_zero_input_bits"],
                    expected["leading_zero_input_bits"],
                )
                flush_bits = 1 + expected["preamble_input_bits"]
                self.assertEqual(
                    count_symbols(flush_bits),
                    count_symbols(
                        108 if mode == "MFSK32" else 181
                    ),
                )
        self.assertEqual(count_symbols(108).complete_symbols, 54)
        self.assertEqual(count_symbols(108).residual_coded_bits, 0)
        self.assertEqual(count_symbols(181).complete_symbols, 90)
        self.assertEqual(count_symbols(181).residual_coded_bits, 2)
        self.assertEqual(count_symbols(181, pending_coded_bits=2).complete_symbols, 91)
        self.assertEqual(count_symbols(181, pending_coded_bits=2).residual_coded_bits, 0)
        self.assertEqual(count_symbols(35 + start_character_bits), count_symbols(62))
        self.assertEqual(count_symbols(62).complete_symbols, 31)
        self.assertEqual(count_symbols(62).residual_coded_bits, 0)
        self.assertEqual(count_symbols(60 + start_character_bits).complete_symbols, 43)
        self.assertEqual(count_symbols(60 + start_character_bits).residual_coded_bits, 2)
        self.assertEqual(count_symbols(end_character_bits + 108).complete_symbols, 67)
        self.assertEqual(count_symbols(end_character_bits + 108).residual_coded_bits, 2)
        self.assertEqual(count_symbols(end_character_bits + 181).complete_symbols, 104)
        self.assertEqual(count_symbols(end_character_bits + 181).residual_coded_bits, 0)

    def test_picture_headers_prologue_raster_order_and_frequencies_are_exact(self) -> None:
        expected_tokens = {
            (False, 8): b"Pic:8x4;",
            (False, 4): b"Pic:8x4p4;",
            (False, 2): b"Pic:8x4p2;",
            (True, 8): b"Pic:8x4C;",
            (True, 4): b"Pic:8x4Cp4;",
            (True, 2): b"Pic:8x4Cp2;",
        }
        for (color, speed), expected in expected_tokens.items():
            self.assertEqual(
                picture_control_token(8, 4, color=color, samples_per_pixel=speed),
                expected,
            )
        self.assertEqual(prologue_output_frames(48000), 2112)
        width, height, pixels = read_ppm(PRIMARY_RGB_PPM)
        self.assertEqual((width, height), (8, 4))
        gray = grayscale_values(pixels)
        color = color_row_plane_values(width, height, pixels)
        self.assertEqual(len(gray), 32)
        self.assertEqual(len(color), 96)
        self.assertEqual(color[:8], tuple(pixel[0] for pixel in pixels[:8]))
        self.assertEqual(color[8:16], tuple(pixel[1] for pixel in pixels[:8]))
        self.assertEqual(color[16:24], tuple(pixel[2] for pixel in pixels[:8]))
        for mode in ("MFSK32", "MFSK64"):
            frequencies = pixel_frequencies((0, 128, 255), mode=mode, carrier_hz=1500)
            bandwidth = MODE_PARAMETERS[mode]["tone_span_hz"]
            self.assertEqual(
                frequencies,
                (
                    1500 - bandwidth / 2,
                    1500.0,
                    1500 + bandwidth * 127 / 256,
                ),
            )
        self.assertEqual(
            pixel_frequencies((0, 128, 255), mode="MFSK64", carrier_hz=1500),
            tuple(
                self.vectors["picture_mapping_mfsk64_hz_at_1500_center"][str(value)]
                for value in (0, 128, 255)
            ),
        )
        for speed, gray_frames, color_frames in (
            (8, 1536, 4608),
            (4, 768, 2304),
            (2, 384, 1152),
        ):
            self.assertEqual(
                raster_output_frames(
                    width,
                    height,
                    color=False,
                    samples_per_pixel=speed,
                    sample_rate_hz=48000,
                ),
                gray_frames,
            )
            self.assertEqual(
                raster_output_frames(
                    width,
                    height,
                    color=True,
                    samples_per_pixel=speed,
                    sample_rate_hz=48000,
                ),
                color_frames,
            )

    def test_oracle_rejects_deliberate_tone_timing_and_rgb_order_defects(self) -> None:
        expected_tones = self.vectors["text_to_tones_from_reset"][
            "normal_sideband_physical_tone_indices"
        ]
        mutated_tones = list(expected_tones)
        mutated_tones[2] = (mutated_tones[2] + 1) % 16
        with self.assertRaisesRegex(EvidenceMismatch, "tone indices"):
            require_exact("tone indices", mutated_tones, expected_tones)

        with self.assertRaisesRegex(EvidenceMismatch, "prologue frames"):
            require_exact("prologue frames", 2111, prologue_output_frames(48000))
        with self.assertRaisesRegex(EvidenceMismatch, "pixel duration"):
            require_close("pixel duration", 47 / 48000, 8 / 8000)

        width, height, pixels = read_ppm(PRIMARY_RGB_PPM)
        expected_rgb = color_row_plane_values(width, height, pixels)
        pixel_interleaved = tuple(component for pixel in pixels for component in pixel)
        with self.assertRaisesRegex(EvidenceMismatch, "RGB raster order"):
            require_exact("RGB raster order", pixel_interleaved, expected_rgb)


if __name__ == "__main__":
    unittest.main()
