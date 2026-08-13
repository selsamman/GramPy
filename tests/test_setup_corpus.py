from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from grampy.corpus_package import CorpusPackageError, package_corpus
from grampy.corpus_setup import CorpusSetupError, fetch_corpus


class CorpusTransferTests(unittest.TestCase):
    def make_archive(
        self,
        directory: Path,
        *,
        version: str | None = "test-1",
        unsafe_name: str | None = None,
        appledouble_root_metadata: bool = False,
    ) -> Path:
        archive = directory / "corpus.tar"
        with tarfile.open(archive, "w") as tar:
            if version is not None:
                version_json = json.dumps({"version": version}).encode()
                info = tarfile.TarInfo("received-corpus/version.json")
                info.size = len(version_json)
                tar.addfile(info, io.BytesIO(version_json))
            payload = b"corpus payload\n"
            info = tarfile.TarInfo("received-corpus/README.md")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
            if appledouble_root_metadata:
                info = tarfile.TarInfo("._received-corpus")
                info.size = 4
                tar.addfile(info, io.BytesIO(b"meta"))
            if unsafe_name:
                info = tarfile.TarInfo(unsafe_name)
                info.size = 1
                tar.addfile(info, io.BytesIO(b"x"))
        return archive

    @staticmethod
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def make_existing_corpus(root: Path) -> None:
        root.mkdir(parents=True)
        (root / "version.json").write_text(
            json.dumps({"version": "old"}), encoding="utf-8"
        )
        (root / "old-marker").write_text("preserve on failure", encoding="utf-8")

    def test_fetch_installs_requested_archive_without_version_synchronization(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            root = directory / "samples" / "received-corpus"

            fetch_corpus(archive.as_uri(), self.digest(archive), root)
            (root / "local-marker").write_text("replace me", encoding="utf-8")
            fetch_corpus(archive.as_uri(), self.digest(archive), root)

            self.assertFalse((root / "local-marker").exists())
            self.assertEqual(
                json.loads((root / "version.json").read_text())["version"], "test-1"
            )

    def test_package_and_fetch_encrypted_corpus_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source = directory / "source"
            source.mkdir()
            (source / "payload.txt").write_text("corpus payload", encoding="utf-8")
            archive = directory / "corpus.tar.zst.enc"

            digest = package_corpus(source, archive, "private-1", "test-password")
            root = directory / "installed" / "received-corpus"
            fetch_corpus(archive.as_uri(), digest, root, "test-password")

            self.assertEqual((root / "payload.txt").read_text(), "corpus payload")
            self.assertEqual(
                json.loads((root / "version.json").read_text())["version"], "private-1"
            )

    def test_package_without_encryption_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source = directory / "source"
            source.mkdir()
            (source / "payload.txt").write_text("corpus payload", encoding="utf-8")
            (source / "version.json").write_text(
                json.dumps({"version": "old", "created": "2026-08-11"}), encoding="utf-8"
            )
            archive = directory / "corpus.tar.zst"

            digest = package_corpus(source, archive, "public-1")
            root = directory / "installed" / "received-corpus"
            fetch_corpus(archive.as_uri(), digest, root)

            self.assertEqual((root / "payload.txt").read_text(), "corpus payload")
            version_data = json.loads((source / "version.json").read_text())
            self.assertEqual(version_data["version"], "public-1")
            self.assertEqual(version_data["created"], "2026-08-11")

    def test_package_refuses_to_overwrite_archive(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source = directory / "source"
            source.mkdir()
            output = directory / "existing.tar.zst"
            output.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(CorpusPackageError, "already exists"):
                package_corpus(source, output, "test-1")
            self.assertEqual(output.read_text(), "keep")

    def test_wrong_password_preserves_existing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source = directory / "source"
            source.mkdir()
            archive = directory / "corpus.tar.zst.enc"
            digest = package_corpus(source, archive, "test-1", "correct-password")
            root = directory / "samples" / "received-corpus"
            self.make_existing_corpus(root)

            with self.assertRaisesRegex(CorpusSetupError, "wrong password"):
                fetch_corpus(archive.as_uri(), digest, root, "wrong-password")
            self.assertTrue((root / "old-marker").is_file())

    def test_checksum_failure_preserves_existing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            root = directory / "samples" / "received-corpus"
            self.make_existing_corpus(root)

            with self.assertRaisesRegex(CorpusSetupError, "SHA-256 mismatch"):
                fetch_corpus(archive.as_uri(), "0" * 64, root)
            self.assertTrue((root / "old-marker").is_file())

    def test_invalid_checksum_is_rejected_before_download(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "samples" / "received-corpus"
            with self.assertRaisesRegex(CorpusSetupError, "64 hexadecimal"):
                fetch_corpus("file:///does-not-exist", "invalid", root)
            self.assertFalse(root.exists())

    def test_curl_failure_is_reported_without_leaving_a_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name) / "samples" / "received-corpus"
            with patch(
                "grampy.corpus_setup.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    args=["curl"], returncode=22, stdout="", stderr="HTTP 404"
                ),
            ):
                with self.assertRaisesRegex(CorpusSetupError, "HTTP 404"):
                    fetch_corpus("https://example.invalid/missing", "0" * 64, root)
            self.assertFalse(root.exists())

    def test_unsafe_archive_path_preserves_existing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(
                directory, unsafe_name="received-corpus/../../escaped"
            )
            root = directory / "samples" / "received-corpus"
            self.make_existing_corpus(root)

            with self.assertRaisesRegex(CorpusSetupError, "unsafe path"):
                fetch_corpus(archive.as_uri(), self.digest(archive), root)
            self.assertTrue((root / "old-marker").is_file())

    def test_missing_version_file_preserves_existing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory, version=None)
            root = directory / "samples" / "received-corpus"
            self.make_existing_corpus(root)

            with self.assertRaisesRegex(CorpusSetupError, "no valid version.json"):
                fetch_corpus(archive.as_uri(), self.digest(archive), root)
            self.assertTrue((root / "old-marker").is_file())

    def test_ignores_optional_appledouble_root_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory, appledouble_root_metadata=True)
            root = directory / "samples" / "received-corpus"

            fetch_corpus(archive.as_uri(), self.digest(archive), root)
            self.assertTrue((root / "README.md").is_file())
            self.assertFalse((root.parent / "._received-corpus").exists())

    def test_symlinked_corpus_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            actual = directory / "actual-corpus"
            actual.mkdir()
            root = directory / "samples" / "received-corpus"
            root.parent.mkdir()
            root.symlink_to(actual, target_is_directory=True)

            with self.assertRaisesRegex(CorpusSetupError, "symlinked corpus root"):
                fetch_corpus(archive.as_uri(), self.digest(archive), root)

    def test_fetch_script_installs_explicit_archive(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            root = directory / "samples" / "received-corpus"
            project = Path(__file__).resolve().parents[1]
            result = subprocess.run(
                [
                    project / "tools" / "fetch-corpus",
                    "--url", archive.as_uri(),
                    "--sha256", self.digest(archive),
                    "--corpus-root", root,
                ],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "installed corpus")


if __name__ == "__main__":
    unittest.main()
