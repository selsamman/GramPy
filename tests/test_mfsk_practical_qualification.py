"""Contracts for the maintained practical qualification, without Pi execution.

These checks protect case coverage and the receive harness. Actual decode
quality requires the separate corpus/receiver acceptance run.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs/encoder/data/mfsk_encoder_pi_matrix_v3.json"
RECEIVER = ROOT / "experiments/mfsk-wav-encoder/session9_broadcast_receive.py"


class PracticalQualificationContractTests(unittest.TestCase):
    def test_matrix_covers_modes_picture_speeds_and_mixed_composition(self) -> None:
        matrix = json.loads(MATRIX.read_text())
        self.assertEqual(matrix["schema"], "grampy-mfsk-practical-qualification.v3")
        self.assertEqual(matrix["sample_rate_hz"], 48000)
        cases = matrix["cases"]
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        combinations = {(case["mode"], case["color"], case["speed"]) for case in cases}
        required = {("MFSK64", color, speed)
                    for color in ("grayscale", "color") for speed in (2, 4, 8)}
        required.update(("MFSK32", "grayscale", speed) for speed in (2, 4, 8))
        self.assertTrue(required <= combinations)
        self.assertTrue(any(case.get("mixed") for case in cases))
        for case in cases:
            source = matrix["sources"][case["source"]]
            self.assertTrue(all(size > 0 for size in source["output_size"]))
            # Frozen v3 scopes GramPy picture requirements to MFSK64. The
            # later accepted MFSK32 overlay is a separate evidence record.
            if case["mode"] == "MFSK64":
                self.assertTrue(case["grampy_picture_required"])

    def test_matrix_preserves_scoped_numerical_and_visual_acceptance(self) -> None:
        gate = json.loads(MATRIX.read_text())["picture_gate"]
        self.assertEqual(gate["raw_mae_255_max"], 25)
        self.assertEqual(gate["aligned_mae_255_max"], 20)
        self.assertEqual(gate["absolute_channel_bias_255_max"], 15)
        self.assertEqual(gate["alignment_max_offset_components"], 12)
        self.assertEqual(gate["alignment_max_changes"], 12)
        for requirement in (
            "requires_exact_dimensions_and_picture_count",
            "requires_all_caller_text_and_announcements_in_order",
            "requires_automatic_mode_and_carrier_acquisition",
            "requires_pm_visual_review",
        ):
            self.assertTrue(gate[requirement])


class PracticalReceiverContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        spec = importlib.util.spec_from_file_location("practical_receiver", RECEIVER)
        cls.receiver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.receiver)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.bundle = root / "bundle"
        self.output = root / "output"
        self.bundle.mkdir()
        self.output.mkdir()
        self.binary = root / "fldigi"
        self.adapter = root / "adapter"
        self.binary.write_bytes(b"receiver identity")
        self.adapter.write_bytes(b"adapter identity")
        self.cases = []
        for index, mode in enumerate(("MFSK32", "MFSK64")):
            wav = self.bundle / f"{mode}.wav"
            wav.write_bytes(f"retained input {mode}".encode())
            self.cases.append({
                "id": mode, "duration_seconds": index + 1,
                "frame_count": (index + 1) * 48000,
                "wav": {"path": wav.name, "sha256": hashlib.sha256(wav.read_bytes()).hexdigest()},
            })
        (self.bundle / "prepared.json").write_text(json.dumps({"cases": self.cases}))

    def test_receiver_uses_whole_input_with_continuous_rxid_and_no_manual_modes(self) -> None:
        # Replace only this module's subprocess reference; platform.platform()
        # may itself use the real stdlib subprocess module to identify the host.
        with mock.patch.object(self.receiver, "subprocess", wraps=self.receiver.subprocess) as processes:
            processes.check_output.return_value = "fldigi 4.2.13\n"
            receive = processes.run
            receive.return_value = SimpleNamespace(returncode=0)
            self.receiver.main(self.bundle, self.output, self.adapter, self.binary)

        self.assertEqual(receive.call_count, len(self.cases))
        for case, call in zip(self.cases, receive.call_args_list):
            command = call.args[0]
            self.assertEqual(command[0], str(self.adapter))
            for option, value in (("--input", str(self.bundle / case["wav"]["path"])),
                                  ("--mode", "BPSK31"), ("--rxid", "on"), ("--afc", "off"),
                                  ("--audio-backend", "alsa-loopback"),
                                  ("--alsa-capture-plugin", "plug")):
                self.assertEqual(command[command.index(option) + 1], value)
            self.assertNotIn("--start-sec", command)
            self.assertNotIn("--stop-sec", command)
            settings = ET.parse(self.output / case["id"] / "config/fldigi_def.xml").getroot()
            for key, value in (("RECEIVERSID", "1"), ("RSIDNOTIFYONLY", "0"),
                               ("RSIDAUTODISABLE", "0"), ("DISABLERSIDFREQCHANGE", "0"),
                               ("AFC_BY_MODE", "0")):
                self.assertEqual(settings.findtext(key), value)
        runs = json.loads((self.output / "runs.json").read_text())
        for case, run in zip(self.cases, runs):
            self.assertEqual(run["id"], case["id"])
            self.assertEqual(run["input_interval"], {"start_frame": 0, "end_frame": case["frame_count"]})
            self.assertEqual(run["manual_mode_changes"], 0)
            self.assertEqual(run["input_sha256"], case["wav"]["sha256"])

    def test_changed_input_is_rejected_before_receiver_execution(self) -> None:
        (self.bundle / self.cases[0]["wav"]["path"]).write_bytes(b"changed input")
        with mock.patch.object(self.receiver, "subprocess", wraps=self.receiver.subprocess) as processes:
            processes.check_output.return_value = "fldigi 4.2.13\n"
            receive = processes.run
            with self.assertRaisesRegex(ValueError, "WAV transfer hash mismatch"):
                self.receiver.main(self.bundle, self.output, self.adapter, self.binary)
        receive.assert_not_called()


if __name__ == "__main__":
    unittest.main()
