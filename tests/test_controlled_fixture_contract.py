"""Required-data behavior is tested without relying on installed sidecars."""
import hashlib
from contextlib import redirect_stderr, redirect_stdout
import io
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests.controlled_fixtures import preflight
from tests.suites import data_test


class RequiredFixtureContractTests(unittest.TestCase):
    def test_preflight_rejects_missing_and_changed_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contents = {kind: kind.encode() for kind in ("wav", "sigmf_data", "sigmf_meta")}
            fixture = {"id": "required", "mode": "MFSK32", "kind": "text",
                       "capability": "strict preflight", "artifact_directory": "input",
                       "artifacts": {kind: kind for kind in contents}}
            fixture.update({kind + "_sha256": hashlib.sha256(data).hexdigest()
                            for kind, data in contents.items()})
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps({"schema": "grampy-fixture-evidence.v1", "fixtures": [fixture]}))
            with self.assertRaisesRegex(AssertionError, "required: missing"):
                preflight(root, evidence)
            directory = root / "input"
            directory.mkdir()
            for kind, data in contents.items():
                (directory / kind).write_bytes(data)
            self.assertEqual(preflight(root, evidence)["fixtures"][0]["id"], "required")
            (directory / "sigmf_data").write_bytes(b"changed")
            with self.assertRaisesRegex(AssertionError, "required: hash-mismatch"):
                preflight(root, evidence)

    def test_selected_data_suite_fails_instead_of_accepting_skips(self):
        path = Path(__file__).resolve().parents[1] / "tools/test-suite"
        loader = importlib.machinery.SourceFileLoader("suite_runner", str(path))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        runner = importlib.util.module_from_spec(spec)
        loader.exec_module(runner)

        class MissingData(unittest.TestCase):
            @data_test("received")
            def test_unavailable(self):
                self.skipTest("required input unavailable")

        output = io.StringIO()
        with (
            redirect_stdout(output), redirect_stderr(output),
            mock.patch.object(runner.sys, "argv", [str(path), "--suite", "received"]),
            mock.patch.object(runner.unittest.defaultTestLoader, "discover",
                              return_value=unittest.TestSuite([MissingData("test_unavailable")])),
        ):
            self.assertEqual(runner.main(), 1)
        self.assertIn("Incomplete validation", output.getvalue())
