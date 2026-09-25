"""Ensure the command-line adapter consumes GramPy's public API."""

from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from grampy.api import DecodeProducts
from grampy.cli import main


class CliPublicApiTests(unittest.TestCase):
    def test_cli_decodes_through_public_api_then_writes_result(self) -> None:
        manifest = {"schema": "grampy-decode-manifest.v1"}
        with (
            patch("grampy.cli.decode_iq", return_value=manifest) as decode_iq,
            patch("grampy.cli.write_manifest_atomic") as write_manifest,
        ):
            status = main([
                "--in-meta", "capture.sigmf-meta",
                "--in-data", "capture.sigmf-data",
                "--out-manifest", "results/decode.json",
                "--mode", "MFSK64",
            ])

        self.assertEqual(status, 0)
        kwargs = decode_iq.call_args.kwargs
        self.assertEqual(kwargs["meta_path"], Path("capture.sigmf-meta"))
        self.assertEqual(kwargs["data_path"], Path("capture.sigmf-data"))
        self.assertEqual(kwargs["config"].mode, "MFSK64")
        self.assertEqual(kwargs["artifact_dir"], Path("results/decode.artifacts"))
        self.assertEqual(kwargs["artifact_path_prefix"], "decode.artifacts")
        write_manifest.assert_called_once_with(Path("results/decode.json"), manifest)

    def test_compact_outputs_use_one_product_decode(self) -> None:
        products = DecodeProducts(
            text_manifest={"schema": "grampy-text-manifest.v1"},
            quality_manifest={"schema": "grampy-quality-manifest.v1"},
        )
        with (
            patch("grampy.cli.decode_iq_products", return_value=products) as decode,
            patch("grampy.cli.decode_iq") as legacy_decode,
            patch("grampy.cli.write_manifest_atomic") as write,
        ):
            status = main([
                "--in-meta", "capture.sigmf-meta",
                "--in-data", "capture.sigmf-data",
                "--out-text-manifest", "results/text.manifest.json",
                "--out-quality-manifest", "results/quality.manifest.json",
            ])
        self.assertEqual(status, 0)
        legacy_decode.assert_not_called()
        self.assertEqual(decode.call_count, 1)
        self.assertFalse(decode.call_args.kwargs["include_diagnostic_manifest"])
        self.assertEqual(decode.call_args.kwargs["artifact_root"], Path("results"))
        self.assertEqual(write.call_count, 2)
        write.assert_any_call(Path("results/text.manifest.json"), products.text_manifest)
        write.assert_any_call(Path("results/quality.manifest.json"), products.quality_manifest)

    def test_diagnostic_alongside_products_still_decodes_once(self) -> None:
        products = DecodeProducts({"text": 1}, {"quality": 2}, {"diagnostic": 3})
        with (
            patch("grampy.cli.decode_iq_products", return_value=products) as decode,
            patch("grampy.cli.write_manifest_atomic") as write,
        ):
            status = main([
                "--in-meta", "capture.sigmf-meta",
                "--in-data", "capture.sigmf-data",
                "--out-text-manifest", "results/text.manifest.json",
                "--out-quality-manifest", "results/quality.manifest.json",
                "--out-manifest", "results/decode.manifest.json",
            ])
        self.assertEqual(status, 0)
        self.assertEqual(decode.call_count, 1)
        self.assertTrue(decode.call_args.kwargs["include_diagnostic_manifest"])
        self.assertEqual(write.call_count, 3)

    def test_compact_terminal_failure_is_published_to_both_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            text_path = Path(directory) / "text.json"
            quality_path = Path(directory) / "quality.json"
            status = main([
                "--in-meta", str(Path(directory) / "missing.sigmf-meta"),
                "--in-data", str(Path(directory) / "missing.sigmf-data"),
                "--out-text-manifest", str(text_path),
                "--out-quality-manifest", str(quality_path),
            ])
            self.assertNotEqual(status, 0)
            for path in (text_path, quality_path):
                document = json.loads(path.read_text())
                self.assertEqual(document["schema"], "grampy-decode-terminal.v1")
                self.assertEqual(document["status"], "failed")


if __name__ == "__main__":
    unittest.main()
