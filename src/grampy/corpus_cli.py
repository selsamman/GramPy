from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .corpus import build_inventory, promote, read_json, verify_corpus


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="mfsk-corpus")
    commands = result.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser("inventory")
    inventory.add_argument("--intake", type=Path, required=True)
    inventory.add_argument("--output", type=Path, required=True)
    inventory.add_argument("--metadata-only", action="store_true")

    promotion = commands.add_parser("promote")
    promotion.add_argument("--intake", type=Path, required=True)
    promotion.add_argument("--corpus", type=Path, required=True)
    promotion.add_argument("--selection", type=Path, required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--corpus", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "inventory":
        inventory = build_inventory(args.intake, measure_iq=not args.metadata_only)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"captures={inventory['capture_count']} "
            f"complete={inventory['complete_capture_count']} "
            f"bytes={inventory['total_data_bytes']} output={args.output}"
        )
        return 0
    if args.command == "promote":
        manifest = promote(
            intake_root=args.intake,
            corpus_root=args.corpus,
            selection=read_json(args.selection),
        )
        print(
            f"sources={manifest['storage']['source_count']} "
            f"cases={manifest['storage']['case_count']} "
            f"bytes={manifest['storage']['source_bytes']}"
        )
        return 0
    errors = verify_corpus(args.corpus)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print(f"verified corpus={args.corpus}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
