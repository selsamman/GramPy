"""Strict availability and integrity contract for maintained controlled inputs."""
from pathlib import Path
import hashlib
import os

from grampy.fixtures import inventory, load_evidence


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "tests/fixtures/mfsk/controlled-v1.json"


def fixture_root():
    override = os.environ.get("GRAM_PY_MFSK_FIXTURES")
    if override:
        return Path(override).expanduser()
    samples = Path(os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests/samples"))
    return samples / "controlled-mfsk-v1"


def preflight(root=None, evidence_path=EVIDENCE_PATH):
    evidence = load_evidence(evidence_path)
    root = fixture_root() if root is None else Path(root)
    checks = inventory(evidence, root)
    failures = [f"{check.fixture_id}: {check.status}" for check in checks
                if check.status != "verified"]
    if failures:
        raise AssertionError(
            "Required controlled fixtures are unavailable or changed: "
            + "; ".join(failures)
            + f". Install the versioned sidecar at {root}; see tests/README.md."
        )
    for fixture in evidence["fixtures"]:
        if "source_image" in fixture:
            image = ROOT / fixture["source_image"]
            actual = hashlib.sha256(image.read_bytes()).hexdigest()
            if actual != fixture["source_image_sha256"]:
                raise AssertionError(f"Controlled source image changed: {image}")
    return evidence


def require_fixture(fixture_id):
    evidence = preflight()
    fixture = next(item for item in evidence["fixtures"] if item["id"] == fixture_id)
    directory = fixture_root() / fixture["artifact_directory"]
    return (fixture, directory / fixture["artifacts"]["sigmf_meta"],
            directory / fixture["artifacts"]["sigmf_data"])
