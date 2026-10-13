"""Load content-bearing received expectations only for selected external tests."""
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def heldout_text():
    binding = json.loads((ROOT / "tests/fixtures/received-expectations.json").read_text())
    samples = Path(os.environ.get("GRAMPY_TEST_SAMPLES", ROOT / "tests/samples"))
    path = samples / binding["path"]
    try:
        content = path.read_bytes()
    except OSError as error:
        raise AssertionError(f"Required received expectations unavailable: {path}") from error
    if len(content) != binding["bytes"] or hashlib.sha256(content).hexdigest() != binding["sha256"]:
        raise AssertionError(f"Required received expectations changed: {path}")
    expected = json.loads(content)
    if set(expected) != {"r2_mfsk32", "r2_mfsk64", "r3_mfsk32"} or not all(
        isinstance(value, str) and value for value in expected.values()
    ):
        raise AssertionError(f"Invalid received expectations: {path}")
    return expected
