from __future__ import annotations

import argparse
from importlib.resources import files
import json
from pathlib import Path
import sys

from .fixtures import (
    FixtureEvidenceError,
    default_fixture_root,
    inventory,
    load_evidence,
    summarize,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mfsk-fixture-inventory",
        description="Verify controlled fldigi-derived MFSK fixture availability and hashes.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        help="fixture evidence JSON; defaults to GramPy's packaged evidence",
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=default_fixture_root(),
        help="artifact root (default: GRAM_PY_MFSK_FIXTURES or .local/fldigi-fixtures)",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="return nonzero when any pinned artifact is unavailable",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        evidence_path = args.evidence
        if evidence_path is None:
            packaged = files("grampy").joinpath("data", "mfsk_fixture_evidence.json")
            evidence = json.loads(packaged.read_text(encoding="utf-8"))
            if not isinstance(evidence, dict):
                raise FixtureEvidenceError("packaged fixture evidence must be an object")
        else:
            evidence = load_evidence(evidence_path)
        if evidence.get("schema") != "grampy-fixture-evidence.v1":
            raise FixtureEvidenceError("fixture evidence must use schema grampy-fixture-evidence.v1")
        checks = inventory(evidence, args.fixture_root)
    except (FixtureEvidenceError, OSError) as error:
        print(f"mfsk-fixture-inventory: {error}", file=sys.stderr)
        return 2

    counts = summarize(checks)
    result = {
        "schema": "grampy-fixture-inventory.v1",
        "evidence": str(args.evidence) if args.evidence else "package:grampy/data/mfsk_fixture_evidence.json",
        "fixture_root": str(args.fixture_root),
        "status": (
            "hash-mismatch"
            if counts["hash-mismatch"]
            else "incomplete"
            if counts["missing"]
            else "verified"
        ),
        "summary": counts,
        "fixtures": [check.to_dict() for check in checks],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if counts["hash-mismatch"]:
        return 1
    if args.require_all and counts["missing"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
