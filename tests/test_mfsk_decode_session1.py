from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

import jsonschema
import numpy as np

from grampy.coordinates import SampleMap
from grampy.pipeline import DecodeConfig, run_reference_pipeline
from grampy.resources import load_json
from grampy.sigmf import InputError, SigmfRecording
from grampy.wire import (
    SoftDeinterleaver,
    convolutional_encode,
    fldigi_gray_encode,
    tone_metrics_to_llrs,
)


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "mfsk-iq-decode"
VECTORS = json.loads(
    (ROOT / "docs" / "decoder" / "data" / "mfsk_wire_vectors.json").read_text(encoding="utf-8")
)


class CoordinateTests(unittest.TestCase):
    def test_rational_resampling_round_trip_and_ties_to_even(self) -> None:
        mapping = SampleMap.resampled(
            input_origin=Fraction(3, 2), input_rate=48_000, output_rate=8_000
        )
        estimate = mapping.input_estimate(17)
        self.assertEqual(estimate, Fraction(207, 2))
        self.assertEqual(mapping.output_estimate(estimate), 17)
        self.assertEqual(mapping.serialize_point(0)["input_sample"], 2)
        self.assertEqual(mapping.serialize_point(1)["input_sample"], 8)

    def test_composition_retains_exact_ratio_and_uncertainty(self) -> None:
        local = SampleMap.resampled(
            input_origin=2,
            input_rate=2,
            output_rate=3,
            uncertainty_input_samples=0.25,
        )
        upstream = SampleMap(
            input_origin=Fraction(10),
            input_per_output=Fraction(3, 2),
            uncertainty_input_samples=0.5,
        )
        composed = local.compose(upstream)
        self.assertEqual(composed.input_origin, 13)
        self.assertEqual(composed.input_per_output, 1)
        self.assertEqual(composed.uncertainty_input_samples, 0.875)


class WirePrimitiveTests(unittest.TestCase):
    def test_convolutional_encoder_matches_all_fixed_vectors(self) -> None:
        for vector in VECTORS["convolutional_code"]["vectors"]:
            actual = convolutional_encode(map(int, vector["input_bits"]))
            self.assertEqual("".join(map(str, actual)), vector["output_bits"])

    def test_gray_mapping_matches_composed_fixed_vector(self) -> None:
        labels = VECTORS["text_to_tones_from_reset"]["packed_binary_labels"]
        self.assertEqual(
            [fldigi_gray_encode(label) for label in labels],
            VECTORS["text_to_tones_from_reset"][
                "normal_sideband_physical_tone_indices"
            ],
        )

    def test_tone_metrics_produce_transmitted_lane_llrs(self) -> None:
        for physical_tone in range(16):
            metrics = np.full(16, -1000.0)
            metrics[physical_tone] = 0.0
            llrs = tone_metrics_to_llrs(metrics)
            label = next(
                value
                for value in range(16)
                if fldigi_gray_encode(value) == physical_tone
            )
            expected = [
                1 if label & (1 << (3 - lane)) else -1 for lane in range(4)
            ]
            self.assertEqual(list(np.sign(llrs).astype(int)), expected)
        self.assertTrue(np.allclose(tone_metrics_to_llrs([0.0] * 16), 0.0))

    def test_soft_deinterleaver_recovers_groups_after_fixed_delay(self) -> None:
        source = [
            tuple(float(group * 4 + lane + 1) for lane in range(4))
            for group in range(65)
        ]
        transmitted = [
            (
                source[t][0],
                source[t - 10][1] if t >= 10 else 0.0,
                source[t - 20][2] if t >= 20 else 0.0,
                source[t - 30][3] if t >= 30 else 0.0,
            )
            for t in range(len(source))
        ]
        decoder = SoftDeinterleaver()
        recovered = [decoder.push(group) for group in transmitted]
        for t in range(30, len(source)):
            self.assertEqual(recovered[t], source[t - 30])


class SigmfHarnessTests(unittest.TestCase):
    def test_cli_emits_schema_valid_atomic_manifest_without_intermediates(self) -> None:
        with Fixture("ci16_le", 32) as fixture:
            output = fixture.root / "result.json"
            completed = subprocess.run(
                [
                    str(TOOL),
                    "--in-meta",
                    str(fixture.meta),
                    "--in-data",
                    str(fixture.data),
                    "--out-manifest",
                    str(output),
                    "--start-sample",
                    "4",
                    "--stop-sample",
                    "20",
                    "--block-samples",
                    "5",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = json.loads(output.read_text(encoding="utf-8"))
            schema = load_json("schemas", "mfsk-decode-manifest-v1.json")
            jsonschema.Draft202012Validator(schema).validate(manifest)
            self.assertEqual(manifest["status"], "partial")
            self.assertEqual(
                manifest["input"]["requested_interval"], {"start": 4, "stop": 20}
            )
            self.assertEqual(
                manifest["diagnostics"]["persistent_intermediate_files"], 0
            )
            self.assertEqual(
                manifest["diagnostics"]["bytes_written"], output.stat().st_size
            )
            stage_timings = manifest["diagnostics"]["stage_wall_seconds"]
            self.assertEqual(
                set(stage_timings),
                {
                    "ingest_open_validate",
                    "input_hashing",
                "sample_inspection",
                "acquisition_segmentation",
                "sample_materialization",
                    "text_acquisition_evidence_fec_framing",
                    "picture_transition_raster_artifacts",
                    "manifest_assembly_validation",
                },
            )
            self.assertTrue(
                all(value >= 0.0 for value in stage_timings.values())
            )
            self.assertEqual(
                sorted(path.name for path in fixture.root.iterdir()),
                ["input.sigmf-data", "input.sigmf-meta", "result.json"],
            )

    def test_cf32_nonfinite_and_ci16_clipping_are_reported(self) -> None:
        with Fixture("cf32_le", 4, cf32_nonfinite=True) as fixture:
            manifest = run_reference_pipeline(
                meta_path=fixture.meta,
                data_path=fixture.data,
                start_sample=None,
                stop_sample=None,
                config=DecodeConfig(block_samples=2),
            )
            self.assertEqual(
                manifest["input"]["sample_summary"]["nonfinite_sample_count"], 1
            )
        with Fixture("ci16_le", 4, clipped=True) as fixture:
            manifest = run_reference_pipeline(
                meta_path=fixture.meta,
                data_path=fixture.data,
                start_sample=None,
                stop_sample=None,
                config=DecodeConfig(block_samples=2),
            )
            self.assertGreater(
                manifest["input"]["sample_summary"]["clipping_sample_count"], 0
            )

    def test_malformed_and_misaligned_inputs_are_rejected(self) -> None:
        with Fixture("ci16_le", 4) as fixture:
            fixture.meta.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(InputError, "malformed"):
                SigmfRecording.open(fixture.meta, fixture.data)
        with Fixture("ci16_le", 4) as fixture:
            with fixture.data.open("ab") as output:
                output.write(b"x")
            with self.assertRaisesRegex(InputError, "not aligned"):
                SigmfRecording.open(fixture.meta, fixture.data)

    def test_capture_must_establish_requested_interval(self) -> None:
        with Fixture("ci16_le", 4) as fixture:
            metadata = json.loads(fixture.meta.read_text(encoding="utf-8"))
            metadata["captures"][0]["core:sample_start"] = 2
            fixture.meta.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(InputError, "requested sample interval"):
                SigmfRecording.open(fixture.meta, fixture.data)

    def test_trim_ancestry_is_explicit_and_input_coordinates_stay_identity(self) -> None:
        with Fixture("ci16_le", 4, trim_offset=1200) as fixture:
            recording = SigmfRecording.open(fixture.meta, fixture.data)
            self.assertEqual(recording.sample_map, SampleMap.identity())
            self.assertEqual(recording.ancestry[0]["parent_sample_offset"], 1200)


class Fixture:
    def __init__(
        self,
        datatype: str,
        sample_count: int,
        *,
        clipped: bool = False,
        cf32_nonfinite: bool = False,
        trim_offset: int | None = None,
    ) -> None:
        self.datatype = datatype
        self.sample_count = sample_count
        self.clipped = clipped
        self.cf32_nonfinite = cf32_nonfinite
        self.trim_offset = trim_offset

    def __enter__(self) -> Fixture:
        self.tmp = tempfile.TemporaryDirectory(prefix="mfsk-session1-")
        self.root = Path(self.tmp.name)
        self.meta = self.root / "input.sigmf-meta"
        self.data = self.root / "input.sigmf-data"
        metadata = {
            "global": {
                "core:datatype": self.datatype,
                "core:sample_rate": 48_000,
                "core:version": "1.0.0",
            },
            "captures": [
                {
                    "core:sample_start": 0,
                    "core:frequency": 15_770_000,
                    "core:datetime": "2026-07-26T12:00:00Z",
                }
            ],
            "annotations": [],
        }
        if self.trim_offset is not None:
            metadata["annotations"].append(
                {
                    "core:sample_start": 0,
                    "radiogram:operation": "trim",
                    "radiogram:trim_start_sample": self.trim_offset,
                    "radiogram:source": "parent.sigmf-data",
                }
            )
        self.meta.write_text(json.dumps(metadata), encoding="utf-8")
        if self.datatype == "ci16_le":
            values = [(32767 if self.clipped and index == 0 else index, -index)
                      for index in range(self.sample_count)]
            self.data.write_bytes(
                b"".join(struct.pack("<hh", real, imag) for real, imag in values)
            )
        else:
            values = [
                (float("nan") if self.cf32_nonfinite and index == 0 else index / 8, 0.0)
                for index in range(self.sample_count)
            ]
            self.data.write_bytes(
                b"".join(struct.pack("<ff", real, imag) for real, imag in values)
            )
        return self

    def __exit__(self, *args: object) -> None:
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
