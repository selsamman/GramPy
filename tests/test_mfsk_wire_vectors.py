from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "docs" / "decoder" / "data" / "mfsk_wire_vectors.json"
EVIDENCE = ROOT / "docs" / "decoder" / "data" / "mfsk_fixture_evidence.json"
VARICODE = ROOT / "docs" / "decoder" / "data" / "mfsk_varicode.json"


class MfskWireVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vectors = json.loads(VECTORS.read_text(encoding="utf-8"))

    def test_convolutional_vectors_match_explicit_contract(self) -> None:
        section = self.vectors["convolutional_code"]
        masks = [int(value, 16) for value in section["generator_masks_hex"]]
        for vector in section["vectors"]:
            state = section["initial_state"]
            output = []
            for character in vector["input_bits"]:
                state = ((state << 1) | int(character)) & 0x7F
                output.extend(
                    str((state & mask).bit_count() & 1)
                    for mask in masks
                )
            self.assertEqual(
                "".join(output),
                vector["output_bits"],
                vector["name"],
            )

    def test_fldigi_interleaver_vectors_match_closed_form_rule(self) -> None:
        section = self.vectors["interleaver"]
        for vector in section["fldigi_numbered_group_vectors"]:
            group = vector["input_group"]
            expected = [
                f"{group}:0",
                f"{group - 10}:1" if group >= 10 else 0,
                f"{group - 20}:2" if group >= 20 else 0,
                f"{group - 30}:3" if group >= 30 else 0,
            ]
            self.assertEqual(vector["output"], expected)

    def test_lettered_interleaver_example_distinguishes_orientations(self) -> None:
        example = self.vectors["interleaver"]["lettered_orientation_example"]
        groups = {
            int(group): values
            for group, values in example["input_groups"].items()
        }
        self.assertEqual(
            example["output_at_group_30"]["fldigi_transmit_orientation"],
            [groups[30][0], groups[20][1], groups[10][2], groups[0][3]],
        )
        self.assertEqual(
            example["output_at_group_30"]["published_forward_orientation"],
            [groups[0][0], groups[10][1], groups[20][2], groups[30][3]],
        )

    def test_mode_timing_is_internally_consistent(self) -> None:
        timing = self.vectors["mode_timing"]
        rate = timing["internal_sample_rate_hz"]
        for mode in ("MFSK32", "MFSK64"):
            values = timing[mode]
            baud = rate / values["samples_per_symbol"]
            self.assertEqual(values["symbols_per_second"], baud)
            self.assertEqual(values["tone_spacing_hz"], baud)
            self.assertEqual(values["tone_span_hz"], 15 * baud)

    def test_transmission_framing_counts_match_mode_parameters(self) -> None:
        framing = self.vectors["transmission_framing"]
        self.assertEqual(framing["start_characters"], [13, 2, 13])
        self.assertEqual(framing["end_characters"], [13, 4, 13])
        for mode in ("MFSK32", "MFSK64"):
            values = framing[mode]
            preamble = values["preamble_parameter_input_bits"]
            self.assertEqual(
                values["fldigi_4_2_12_transmitted_leading_zero_input_bits"],
                preamble // 3,
            )
            self.assertEqual(
                values["fldigi_4_2_06_transmitted_leading_zero_input_bits"],
                0,
            )
            self.assertEqual(
                values["common_flush_input_bits"],
                {"leading_one_bits": 1, "following_zero_bits": preamble},
            )

    def test_text_to_tones_vector_composes_independent_contracts(self) -> None:
        vector = self.vectors["text_to_tones_from_reset"]
        varicode = json.loads(VARICODE.read_text(encoding="utf-8"))["encodings"]
        bits = "".join(varicode[octet] for octet in vector["text_octets"])
        self.assertEqual(bits, vector["varicode_bits"])

        masks = [
            int(value, 16)
            for value in self.vectors["convolutional_code"]["generator_masks_hex"]
        ]
        state = 0
        coded: list[int] = []
        for character in bits:
            state = ((state << 1) | int(character)) & 0x7F
            coded.extend((state & mask).bit_count() & 1 for mask in masks)
        self.assertEqual("".join(map(str, coded)), vector["convolutional_bits"])

        complete = len(coded) // 4
        groups = [coded[index * 4 : index * 4 + 4] for index in range(complete)]
        self.assertEqual(
            ["".join(map(str, group)) for group in groups],
            vector["complete_preinterleaver_groups"],
        )
        self.assertEqual(
            "".join(map(str, coded[complete * 4 :])),
            vector["residual_coded_bits"],
        )

        interleaved = []
        for group_index, group in enumerate(groups):
            interleaved.append([
                group[0],
                groups[group_index - 10][1] if group_index >= 10 else 0,
                groups[group_index - 20][2] if group_index >= 20 else 0,
                groups[group_index - 30][3] if group_index >= 30 else 0,
            ])
        self.assertEqual(
            ["".join(map(str, group)) for group in interleaved],
            vector["interleaved_groups"],
        )
        labels = [
            sum(bit << (3 - index) for index, bit in enumerate(group))
            for group in interleaved
        ]
        self.assertEqual(labels, vector["packed_binary_labels"])

        def fldigi_gray_encode(value: int) -> int:
            encoded = value
            for shift in range(1, 8):
                encoded ^= value >> shift
            return encoded

        self.assertEqual(
            [fldigi_gray_encode(label) for label in labels],
            vector["normal_sideband_physical_tone_indices"],
        )

    def test_fixture_evidence_is_well_formed_and_independently_received(self) -> None:
        evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(
            evidence["schema"],
            "grampy-fixture-evidence.v1",
        )
        self.assertEqual(len(evidence["fixtures"]), 4)
        for fixture in evidence["fixtures"]:
            for field in ("wav_sha256", "sigmf_data_sha256", "sigmf_meta_sha256"):
                digest = fixture[field]
                self.assertEqual(len(digest), 64)
                self.assertTrue(all(character in "0123456789abcdef" for character in digest))
            if fixture["kind"] == "text":
                self.assertEqual(fixture["decoded_text"], fixture["input_text"])
            else:
                self.assertTrue(fixture["receiver_produced_image"])

    def test_complete_varicode_table_has_required_structure(self) -> None:
        document = json.loads(VARICODE.read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], "grampy-varicode.v1")
        encodings = document["encodings"]
        self.assertEqual(len(encodings), 256)
        self.assertEqual(len(set(encodings)), 256)
        for encoding in encodings:
            self.assertTrue(encoding.startswith("1"))
            self.assertTrue(encoding.endswith("00"))
            self.assertNotIn("00", encoding.rstrip("0"))
        self.assertEqual(encodings[32], "100")
        self.assertEqual(encodings[101], "1000")
        self.assertEqual(encodings[116], "1100")
        self.assertEqual(encodings[2], "11101101000")
        self.assertEqual(encodings[4], "11101110000")


if __name__ == "__main__":
    unittest.main()
