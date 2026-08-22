"""Ensure the command-line adapter consumes GramPy's public API."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
