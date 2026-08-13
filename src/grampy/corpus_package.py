"""Build a received-IQ corpus archive, with optional password protection."""

from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

from grampy.corpus_setup import (
    ENCRYPTION_DIGEST,
    ENCRYPTION_ITERATIONS,
    sha256_file,
)


class CorpusPackageError(RuntimeError):
    """The corpus could not be packaged safely."""


def _check_corpus_entries(corpus_root: Path) -> None:
    for entry in corpus_root.rglob("*"):
        if entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            raise CorpusPackageError(f"unsupported corpus entry: {entry}")


def _run(command: list[str], *, failure: str, input_text: str | None = None) -> None:
    try:
        result = subprocess.run(
            command, input=input_text, check=False, capture_output=True, text=True
        )
    except FileNotFoundError as error:
        raise CorpusPackageError(f"required command is not installed: {command[0]}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise CorpusPackageError(f"{failure}: {detail}")


def _compress_corpus(corpus_root: Path, destination: Path) -> None:
    """Stream a tar archive into zstd without making a full uncompressed copy."""
    try:
        with destination.open("wb") as output:
            process = subprocess.Popen(
                ["zstd", "--quiet", "--stdout"],
                stdin=subprocess.PIPE,
                stdout=output,
                stderr=subprocess.PIPE,
            )
    except FileNotFoundError as error:
        raise CorpusPackageError("required command is not installed: zstd") from error
    assert process.stdin is not None
    assert process.stderr is not None
    try:
        with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
            archive.add(corpus_root, arcname="received-corpus", recursive=True)
        process.stdin.close()
        detail = process.stderr.read().decode(errors="replace").strip()
        process.stderr.close()
        returncode = process.wait()
    except BaseException:
        process.kill()
        process.wait()
        process.stderr.close()
        destination.unlink(missing_ok=True)
        raise
    if returncode != 0:
        destination.unlink(missing_ok=True)
        raise CorpusPackageError(f"cannot compress corpus archive: {detail}")


def package_corpus(
    corpus_root: Path,
    output: Path,
    version: str,
    password: str | None = None,
) -> str:
    if not corpus_root.is_dir() or corpus_root.is_symlink():
        raise CorpusPackageError(f"corpus root is missing or symlinked: {corpus_root}")
    if not version.strip():
        raise CorpusPackageError("version must not be empty")
    if password is not None and not password:
        raise CorpusPackageError("encryption requires a non-empty password")
    if output.exists():
        raise CorpusPackageError(f"output archive already exists: {output}")
    try:
        output.resolve().relative_to(corpus_root.resolve())
    except ValueError:
        pass
    else:
        raise CorpusPackageError("output archive must be outside the corpus root")
    _check_corpus_entries(corpus_root)
    output.parent.mkdir(parents=True, exist_ok=True)

    version_path = corpus_root / "version.json"
    version_data: dict[str, object] = {}
    if version_path.exists():
        try:
            existing = json.loads(version_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CorpusPackageError(f"cannot read existing {version_path}: {error}") from error
        if not isinstance(existing, dict):
            raise CorpusPackageError(f"existing {version_path} must contain a JSON object")
        version_data.update(existing)
    version_data["version"] = version
    temporary_version = corpus_root / f".version.json.{os.getpid()}.tmp"
    try:
        temporary_version.write_text(
            json.dumps(version_data, indent=2) + "\n", encoding="utf-8"
        )
        temporary_version.replace(version_path)
    finally:
        temporary_version.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".corpus-package-") as name:
        workspace = Path(name)
        compressed_path = workspace / "received-corpus.tar.zst"
        _compress_corpus(corpus_root, compressed_path)
        if password is None:
            compressed_path.replace(output)
        else:
            encrypted_path = workspace / "received-corpus.tar.zst.enc"
            _run(
                [
                    "openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2",
                    "-iter", str(ENCRYPTION_ITERATIONS), "-md", ENCRYPTION_DIGEST,
                    "-pass", "stdin", "-in", str(compressed_path),
                    "-out", str(encrypted_path),
                ],
                input_text=password + "\n",
                failure="cannot encrypt corpus archive",
            )
            encrypted_path.replace(output)
    return sha256_file(output)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(prog="tools/package-corpus", description=__doc__)
    parser.add_argument(
        "--corpus-root", type=Path,
        default=root / "tests" / "samples" / "received-corpus",
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--encrypt", action="store_true", help="prompt for a password")
    args = parser.parse_args(argv)
    try:
        password = None
        if args.encrypt:
            password = getpass.getpass("Corpus password: ")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                raise CorpusPackageError("passwords do not match")
        digest = package_corpus(
            args.corpus_root.absolute(), args.output.absolute(), args.version, password
        )
    except (CorpusPackageError, EOFError) as error:
        parser.exit(1, f"package-corpus: {error}\n")
    print(f"wrote corpus archive: {args.output}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
