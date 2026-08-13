"""Fetch and install a received-IQ test corpus safely."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen


class CorpusSetupError(RuntimeError):
    """A corpus archive could not be installed safely."""


ENCRYPTION_DIGEST = "sha256"
ENCRYPTION_ITERATIONS = 200_000


def corpus_version(corpus_root: Path) -> str | None:
    """Return a non-empty corpus version, or None when it is absent or invalid."""
    try:
        value = json.loads((corpus_root / "version.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = value.get("version") if isinstance(value, dict) else None
    return version if isinstance(version, str) and version else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    try:
        with urlopen(url) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except OSError as error:
        raise CorpusSetupError(f"download failed for {url}: {error}") from error


def decrypt_archive(source: Path, destination: Path, password: str) -> None:
    """Decrypt an OpenSSL-encrypted archive without exposing its password in argv."""
    if not password:
        raise CorpusSetupError("encrypted corpus requires a non-empty password")
    try:
        result = subprocess.run(
            [
                "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2",
                "-iter", str(ENCRYPTION_ITERATIONS), "-md", ENCRYPTION_DIGEST,
                "-pass", "stdin", "-in", str(source), "-out", str(destination),
            ],
            input=password + "\n",
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise CorpusSetupError("openssl is required to install the encrypted corpus") from error
    if result.returncode != 0:
        destination.unlink(missing_ok=True)
        detail = result.stderr.strip() or "decryption failed"
        raise CorpusSetupError(f"cannot decrypt corpus archive (wrong password?): {detail}")


def _safe_archive_member(member: tarfile.TarInfo) -> PurePosixPath:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts or path == PurePosixPath("."):
        raise CorpusSetupError(f"archive contains unsafe path: {member.name!r}")
    if not (member.isfile() or member.isdir()):
        raise CorpusSetupError(f"archive contains unsupported entry: {member.name!r}")
    return path


def _is_appledouble_root_metadata(member: tarfile.TarInfo, expected_root: str) -> bool:
    """Return whether member is the optional Finder metadata sibling of the root."""
    return member.isfile() and member.name == f"._{expected_root}"


def _decompress_zstd(archive: Path, tar_path: Path) -> None:
    try:
        with tar_path.open("wb") as output:
            subprocess.run(
                ["zstd", "--decompress", "--stdout", str(archive)],
                check=True,
                stdout=output,
                stderr=subprocess.PIPE,
                text=True,
            )
    except FileNotFoundError as error:
        raise CorpusSetupError("zstd is required to install the .tar.zst corpus archive") from error
    except subprocess.CalledProcessError as error:
        raise CorpusSetupError(f"cannot decompress corpus archive: {error.stderr.strip()}") from error


def _open_archive(archive: Path, workspace: Path) -> tarfile.TarFile:
    try:
        return tarfile.open(archive, "r:*")
    except tarfile.ReadError:
        tar_path = workspace / "corpus.tar"
        _decompress_zstd(archive, tar_path)
        try:
            return tarfile.open(tar_path, "r:")
        except tarfile.ReadError as error:
            raise CorpusSetupError("downloaded corpus is not a valid tar archive") from error


def extract_archive(archive: Path, destination: Path, expected_root: str) -> Path:
    """Validate and extract an archive, returning its required top-level root."""
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".corpus-extract-") as name:
        workspace = Path(name)
        with _open_archive(archive, workspace) as tar:
            members = tar.getmembers()
            paths = [_safe_archive_member(member) for member in members]
            install_members = [
                member
                for member in members
                if not _is_appledouble_root_metadata(member, expected_root)
            ]
            install_paths = [
                path
                for member, path in zip(members, paths)
                if not _is_appledouble_root_metadata(member, expected_root)
            ]
            roots = {path.parts[0] for path in install_paths if path.parts}
            if roots != {expected_root}:
                raise CorpusSetupError(
                    f"archive must contain exactly the {expected_root!r} root, found {sorted(roots)!r}"
                )
            # Python 3.11 does not provide tarfile's extraction filters. The
            # member validation permits only regular files/directories beneath
            # the one expected root; newer Python versions additionally apply
            # the standard data filter.
            for member in install_members:
                if sys.version_info >= (3, 12):
                    tar.extract(member, path=workspace, filter="data")
                else:
                    tar.extract(member, path=workspace)
        extracted = workspace / expected_root
        if not extracted.is_dir():
            raise CorpusSetupError(f"archive does not contain directory {expected_root!r}")
        # Move it out before TemporaryDirectory cleans up the workspace.
        staging = Path(tempfile.mkdtemp(dir=destination.parent, prefix=".corpus-ready-"))
        staging.rmdir()
        extracted.replace(staging)
        return staging


def replace_corpus(staging: Path, corpus_root: Path) -> None:
    """Replace the installed corpus using same-filesystem atomic renames."""
    backup = Path(
        tempfile.mkdtemp(dir=corpus_root.parent, prefix=".received-corpus-old-")
    )
    backup.rmdir()
    moved_old = False
    try:
        if corpus_root.exists() or corpus_root.is_symlink():
            if corpus_root.is_symlink():
                raise CorpusSetupError(f"refusing to replace symlinked corpus root: {corpus_root}")
            corpus_root.replace(backup)
            moved_old = True
        staging.replace(corpus_root)
    except OSError as error:
        if moved_old and not corpus_root.exists() and backup.exists():
            backup.replace(corpus_root)
        raise CorpusSetupError(f"cannot replace installed corpus: {error}") from error
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    if moved_old:
        shutil.rmtree(backup)


def fetch_corpus(
    url: str, expected_sha256: str, corpus_root: Path, password: str | None = None
) -> None:
    """Fetch, verify, and install the explicitly requested corpus archive."""
    expected_sha256 = expected_sha256.lower()
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise CorpusSetupError("expected SHA-256 must be 64 hexadecimal characters")
    if corpus_root.is_symlink():
        raise CorpusSetupError(f"refusing to use symlinked corpus root: {corpus_root}")
    corpus_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=corpus_root.parent, prefix=".corpus-download-") as name:
        archive = Path(name) / "received-corpus.archive"
        download(url, archive)
        actual = sha256_file(archive)
        if actual != expected_sha256:
            raise CorpusSetupError(
                f"downloaded corpus SHA-256 mismatch: expected {expected_sha256}, got {actual}"
            )
        install_archive = archive
        if password is not None:
            install_archive = Path(name) / "received-corpus.tar.zst"
            decrypt_archive(archive, install_archive, password)
        staging = extract_archive(install_archive, corpus_root, corpus_root.name)
        if corpus_version(staging) is None:
            shutil.rmtree(staging)
            raise CorpusSetupError("extracted corpus has no valid version.json")
        replace_corpus(staging, corpus_root)


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        prog="tools/fetch-corpus", description="fetch and install a received-IQ test corpus"
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument(
        "--encrypted", action="store_true", help="prompt for the archive password"
    )
    parser.add_argument(
        "--corpus-root", type=Path, default=root / "tests" / "samples" / "received-corpus"
    )
    args = parser.parse_args(argv)
    try:
        password = getpass.getpass("Corpus password: ") if args.encrypted else None
        # Do not resolve corpus_root: resolving a symlink would hide precisely
        # the Dropbox-style installation this tool must reject.
        fetch_corpus(args.url, args.sha256, args.corpus_root.absolute(), password)
    except (CorpusSetupError, EOFError) as error:
        parser.exit(1, f"fetch-corpus: {error}\n")
    print("installed corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
