from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from grampy.corpus_setup import CorpusSetupError, setup_corpus


class SetupCorpusTests(unittest.TestCase):
    def make_archive(
        self, directory: Path, *, version: str = "test-1", unsafe_name: str | None = None,
        appledouble_root_metadata: bool = False,
    ) -> Path:
        archive = directory / "corpus.tar"
        with tarfile.open(archive, "w") as tar:
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

    def make_manifest(self, directory: Path, archive: Path, *, version: str = "test-1") -> Path:
        manifest = directory / "corpus.json"
        manifest.write_text(
            json.dumps(
                {
                    "version": version,
                    "url": archive.as_uri(),
                    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_installs_and_skips_matching_version(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            manifest = self.make_manifest(directory, archive)
            root = directory / "samples" / "received-corpus"
            self.assertTrue(setup_corpus(manifest, root))
            self.assertEqual(json.loads((root / "version.json").read_text())["version"], "test-1")
            self.assertFalse(setup_corpus(manifest, root))

    def test_ignores_optional_appledouble_root_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory, appledouble_root_metadata=True)
            manifest = self.make_manifest(directory, archive)
            root = directory / "samples" / "received-corpus"
            self.assertTrue(setup_corpus(manifest, root))
            self.assertTrue((root / "README.md").is_file())
            self.assertFalse((root.parent / "._received-corpus").exists())

    def test_script_installs_from_a_local_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            manifest = self.make_manifest(directory, archive)
            root = directory / "samples" / "received-corpus"
            project = Path(__file__).resolve().parents[1]
            result = subprocess.run(
                [project / "tools" / "setup-corpus", "--manifest", manifest, "--corpus-root", root],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "installed corpus")
            self.assertTrue((root / "README.md").is_file())

    def test_checksum_failure_preserves_existing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            manifest = self.make_manifest(directory, archive)
            data = json.loads(manifest.read_text())
            data["sha256"] = "0" * 64
            manifest.write_text(json.dumps(data), encoding="utf-8")
            root = directory / "samples" / "received-corpus"
            root.mkdir(parents=True)
            (root / "version.json").write_text(json.dumps({"version": "old"}), encoding="utf-8")
            with self.assertRaisesRegex(CorpusSetupError, "SHA-256 mismatch"):
                setup_corpus(manifest, root)
            self.assertEqual(json.loads((root / "version.json").read_text())["version"], "old")

    def test_unsafe_archive_path_is_rejected_without_replacing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory, unsafe_name="received-corpus/../../escaped")
            manifest = self.make_manifest(directory, archive)
            root = directory / "samples" / "received-corpus"
            root.mkdir(parents=True)
            (root / "version.json").write_text(json.dumps({"version": "old"}), encoding="utf-8")
            with self.assertRaisesRegex(CorpusSetupError, "unsafe path"):
                setup_corpus(manifest, root)
            self.assertEqual(json.loads((root / "version.json").read_text())["version"], "old")

    def test_wrong_extracted_version_is_rejected_without_replacing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory, version="different")
            manifest = self.make_manifest(directory, archive, version="required")
            root = directory / "samples" / "received-corpus"
            root.mkdir(parents=True)
            (root / "version.json").write_text(json.dumps({"version": "old"}), encoding="utf-8")
            with self.assertRaisesRegex(CorpusSetupError, "version does not match"):
                setup_corpus(manifest, root)
            self.assertEqual(json.loads((root / "version.json").read_text())["version"], "old")

    def test_symlinked_corpus_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            manifest = self.make_manifest(directory, archive)
            actual = directory / "actual-corpus"
            actual.mkdir()
            (actual / "version.json").write_text(json.dumps({"version": "test-1"}), encoding="utf-8")
            root = directory / "samples" / "received-corpus"
            root.parent.mkdir()
            root.symlink_to(actual, target_is_directory=True)
            with self.assertRaisesRegex(CorpusSetupError, "symlinked corpus root"):
                setup_corpus(manifest, root)

    def test_script_rejects_symlinked_corpus_root(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            archive = self.make_archive(directory)
            manifest = self.make_manifest(directory, archive)
            actual = directory / "actual-corpus"
            actual.mkdir()
            (actual / "version.json").write_text(
                json.dumps({"version": "test-1"}), encoding="utf-8"
            )
            root = directory / "samples" / "received-corpus"
            root.parent.mkdir()
            root.symlink_to(actual, target_is_directory=True)
            project = Path(__file__).resolve().parents[1]
            result = subprocess.run(
                [project / "tools" / "setup-corpus", "--manifest", manifest,
                 "--corpus-root", root],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("symlinked corpus root", result.stderr)


if __name__ == "__main__":
    unittest.main()
