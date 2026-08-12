from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from grampy.fixtures import FixtureEvidenceError, inventory, load_evidence


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "decoder" / "data" / "mfsk_fixture_evidence.json"


class MfskFixtureInventoryTests(unittest.TestCase):
    def test_checked_in_evidence_has_complete_controlled_fixture_matrix(self) -> None:
        evidence = load_evidence(EVIDENCE)
        fixtures = {fixture["id"]: fixture for fixture in evidence["fixtures"]}
        self.assertEqual(
            set(fixtures),
            {
                "mfsk32-text-printable",
                "mfsk64-text-printable",
                "mfsk64-gray-8x4-p8",
                "mfsk64-primary-color-8x4-p8",
            },
        )
        for fixture in fixtures.values():
            self.assertIn("capability", fixture)
            self.assertEqual(
                set(fixture["artifacts"]),
                {"wav", "sigmf_data", "sigmf_meta"},
            )

    def test_inventory_distinguishes_verified_missing_and_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture_dir = root / "case"
            fixture_dir.mkdir()
            wav = b"wav"
            data = b"data"
            (fixture_dir / "fixture.wav").write_bytes(wav)
            (fixture_dir / "fixture.sigmf-data").write_bytes(data)
            evidence = sample_evidence(wav, data, b"meta")

            check = inventory(evidence, root)[0]
            self.assertEqual(check.status, "missing")
            (fixture_dir / "fixture.sigmf-meta").write_bytes(b"wrong")
            check = inventory(evidence, root)[0]
            self.assertEqual(check.status, "hash-mismatch")
            (fixture_dir / "fixture.sigmf-meta").write_bytes(b"meta")
            check = inventory(evidence, root)[0]
            self.assertEqual(check.status, "verified")

    def test_cli_missing_is_available_by_default_and_strict_on_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence_path = root / "evidence.json"
            evidence_path.write_text(
                json.dumps(sample_evidence(b"wav", b"data", b"meta")),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                "-m",
                "grampy.fixture_cli",
                "--evidence",
                str(evidence_path),
                "--fixture-root",
                str(root / "absent"),
            ]
            environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            optional = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(optional.returncode, 0, optional.stderr)
            self.assertEqual(json.loads(optional.stdout)["status"], "incomplete")
            required = subprocess.run(
                [*command, "--require-all"],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(required.returncode, 1)

    def test_rejects_artifact_path_escape(self) -> None:
        evidence = sample_evidence(b"wav", b"data", b"meta")
        evidence["fixtures"][0]["artifact_directory"] = "../outside"
        with self.assertRaises(FixtureEvidenceError):
            inventory(evidence, Path("/tmp/fixtures"))


class MfskControlledCorpusTests(unittest.TestCase):
    def test_available_pinned_artifacts_match_all_hashes(self) -> None:
        fixture_root = Path(
            os.environ.get(
                "GRAM_PY_MFSK_FIXTURES",
                ROOT / ".local" / "fldigi-fixtures",
            )
        )
        checks = inventory(load_evidence(EVIDENCE), fixture_root)
        mismatches = [
            check.fixture_id
            for check in checks
            if check.status == "hash-mismatch"
        ]
        self.assertEqual(mismatches, [])
        if any(check.status == "missing" for check in checks):
            self.skipTest(
                "controlled MFSK corpus unavailable; set GRAM_PY_MFSK_FIXTURES"
            )
        self.assertTrue(all(check.status == "verified" for check in checks))


def sample_evidence(wav: bytes, data: bytes, meta: bytes) -> dict:
    return {
        "schema": "grampy-fixture-evidence.v1",
        "fixtures": [
            {
                "id": "fixture",
                "mode": "MFSK32",
                "kind": "text",
                "capability": "test",
                "artifact_directory": "case",
                "artifacts": {
                    "wav": "fixture.wav",
                    "sigmf_data": "fixture.sigmf-data",
                    "sigmf_meta": "fixture.sigmf-meta",
                },
                "wav_sha256": hashlib.sha256(wav).hexdigest(),
                "sigmf_data_sha256": hashlib.sha256(data).hexdigest(),
                "sigmf_meta_sha256": hashlib.sha256(meta).hexdigest(),
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
