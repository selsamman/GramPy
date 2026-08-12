from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any


EVIDENCE_SCHEMA = "grampy-fixture-evidence.v1"
ARTIFACT_HASH_FIELDS = {
    "wav": "wav_sha256",
    "sigmf_data": "sigmf_data_sha256",
    "sigmf_meta": "sigmf_meta_sha256",
}


class FixtureEvidenceError(ValueError):
    """The checked-in fixture evidence is malformed or contradictory."""


@dataclass(frozen=True)
class ArtifactCheck:
    kind: str
    path: Path
    expected_sha256: str
    actual_sha256: str | None

    @property
    def status(self) -> str:
        if self.actual_sha256 is None:
            return "missing"
        if self.actual_sha256 != self.expected_sha256:
            return "hash-mismatch"
        return "verified"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "path": str(self.path),
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "status": self.status,
        }


@dataclass(frozen=True)
class FixtureCheck:
    fixture_id: str
    mode: str
    kind: str
    capability: str
    artifacts: tuple[ArtifactCheck, ...]

    @property
    def status(self) -> str:
        statuses = {artifact.status for artifact in self.artifacts}
        if "hash-mismatch" in statuses:
            return "hash-mismatch"
        if "missing" in statuses:
            return "missing"
        return "verified"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.fixture_id,
            "mode": self.mode,
            "kind": self.kind,
            "capability": self.capability,
            "status": self.status,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


def default_fixture_root() -> Path:
    configured = os.environ.get("GRAM_PY_MFSK_FIXTURES")
    if configured:
        return Path(configured).expanduser()
    return Path(".local") / "fldigi-fixtures"


def load_evidence(path: Path) -> dict[str, Any]:
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise FixtureEvidenceError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(evidence, dict) or evidence.get("schema") != EVIDENCE_SCHEMA:
        raise FixtureEvidenceError(
            f"{path} must use evidence schema {EVIDENCE_SCHEMA}"
        )
    fixtures = evidence.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise FixtureEvidenceError(f"{path} must contain a non-empty fixtures list")
    return evidence


def inventory(evidence: dict[str, Any], fixture_root: Path) -> list[FixtureCheck]:
    results: list[FixtureCheck] = []
    seen: set[str] = set()
    for fixture in evidence["fixtures"]:
        if not isinstance(fixture, dict):
            raise FixtureEvidenceError("each fixture entry must be an object")
        fixture_id = required_string(fixture, "id")
        if fixture_id in seen:
            raise FixtureEvidenceError(f"duplicate fixture id: {fixture_id}")
        seen.add(fixture_id)
        relative_directory = safe_relative_path(
            required_string(fixture, "artifact_directory"),
            f"{fixture_id}.artifact_directory",
        )
        artifact_names = fixture.get("artifacts")
        if not isinstance(artifact_names, dict):
            raise FixtureEvidenceError(f"{fixture_id}.artifacts must be an object")

        checks: list[ArtifactCheck] = []
        for kind, hash_field in ARTIFACT_HASH_FIELDS.items():
            artifact_name = safe_relative_path(
                required_string(artifact_names, kind),
                f"{fixture_id}.artifacts.{kind}",
            )
            expected_hash = required_sha256(fixture, hash_field, fixture_id)
            path = fixture_root / relative_directory / artifact_name
            actual_hash = sha256_file(path) if path.is_file() else None
            checks.append(
                ArtifactCheck(kind, path, expected_hash, actual_hash)
            )
        results.append(
            FixtureCheck(
                fixture_id=fixture_id,
                mode=required_string(fixture, "mode"),
                kind=required_string(fixture, "kind"),
                capability=required_string(fixture, "capability"),
                artifacts=tuple(checks),
            )
        )
    return results


def summarize(checks: list[FixtureCheck]) -> dict[str, int]:
    return {
        status: sum(check.status == status for check in checks)
        for status in ("verified", "missing", "hash-mismatch")
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise FixtureEvidenceError(f"{key} must be a non-empty string")
    return value


def required_sha256(mapping: dict[str, Any], key: str, fixture_id: str) -> str:
    value = required_string(mapping, key)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise FixtureEvidenceError(f"{fixture_id}.{key} must be a lowercase SHA-256")
    return value


def safe_relative_path(value: str, field: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise FixtureEvidenceError(f"{field} must be a safe relative path")
    return path
