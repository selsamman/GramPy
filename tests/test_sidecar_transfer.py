"""Whole-sidecar transport using independently authored synthetic payloads."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from grampy.corpus_package import CorpusPackageError, package_corpus
from grampy.corpus_setup import CorpusSetupError, fetch_corpus, replace_corpus
from grampy.sidecar import RELEASE_FILE, inventory_digest, read_release, verify


class SidecarTransferTests(unittest.TestCase):
    def test_default_output_and_automatic_snapshot_label_round_trip(self):
        from grampy import corpus_package
        for encrypted in (False, True):
            with self.subTest(encrypted=encrypted), tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                source, manifest = self.make_source(directory)
                inventory = directory / "inventory.json"
                inventory.write_text(json.dumps(manifest))
                args = ["--samples-root", str(source), "--manifest", str(inventory)]
                if encrypted:
                    args.append("--encrypt")
                with patch.object(corpus_package, "ROOT", directory), \
                     patch.object(corpus_package, "datetime") as clock, \
                     patch("getpass.getpass", return_value="independent-password"):
                    clock.now.return_value = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
                    self.assertEqual(corpus_package.main(args), 0)
                suffix = ".tar.zst.enc" if encrypted else ".tar.zst"
                archive = directory / ".local" / ("samples-20261016T120000Z" + suffix)
                target = directory / "restored"
                fetch_corpus(archive.as_uri(), hashlib.sha256(archive.read_bytes()).hexdigest(), target,
                             "independent-password" if encrypted else None, sidecar_inventory=manifest)
                self.assertEqual(read_release(target, manifest)["version"], "20261016T120000Z")
                self.assertEqual(verify(target, manifest, include_history=True), (5, []))

    def test_explicit_label_cannot_escape_default_output_and_existing_file_is_preserved(self):
        from grampy import corpus_package
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source, manifest = self.make_source(directory)
            inventory = directory / "inventory.json"
            inventory.write_text(json.dumps(manifest))
            args = ["--samples-root", str(source), "--manifest", str(inventory), "--version", "review/preview"]
            with patch.object(corpus_package, "ROOT", directory):
                self.assertEqual(corpus_package.main(args), 0)
                archive = directory / ".local/samples-review_preview.tar.zst"
                original = archive.read_bytes()
                with self.assertRaises(SystemExit) as error:
                    corpus_package.main(args)
                self.assertEqual(error.exception.code, 1)
                self.assertEqual(archive.read_bytes(), original)
            target = directory / "restored"
            fetch_corpus(archive.as_uri(), hashlib.sha256(original).hexdigest(), target,
                         sidecar_inventory=manifest)
            self.assertEqual(read_release(target, manifest)["version"], "review/preview")
            archive.unlink()
            archive.symlink_to(directory / "missing-target")
            with patch.object(corpus_package, "ROOT", directory):
                with self.assertRaises(SystemExit):
                    corpus_package.main(args)
            self.assertTrue(archive.is_symlink())
            self.assertFalse((directory / "missing-target").exists())

    def make_source(self, parent, *, history=True):
        source = parent / "source"
        payloads = {
            "received-corpus/version.json": b'{"version":"received-unchanged"}\n',
            "received-corpus/input.bin": b"INDEPENDENT RF STAND-IN",
            "controlled-mfsk-v1/input.bin": b"INDEPENDENT CONTROLLED STAND-IN",
            "regression-expectations/expected.txt": b"INDEPENDENT EXPECTATION",
            "archive/history.bin": b"INDEPENDENT HISTORY",
        }
        files = []
        for name, content in payloads.items():
            group = "archive" if name.startswith("archive/") else "required"
            files.append({"path": name, "bytes": len(content),
                          "sha256": hashlib.sha256(content).hexdigest(), "group": group})
            if group == "archive" and not history:
                continue
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return source, {"schema": "grampy-sidecar-inventory.v1", "version": "synthetic-v1", "files": files}

    def make_tar(self, source, manifest, output):
        (source / RELEASE_FILE).write_text(json.dumps({
            "schema": "grampy-sidecar-release.v1", "version": "test-release",
            "inventory_sha256": inventory_digest(manifest), "include_history": True,
        }))
        with tarfile.open(output, "w") as archive:
            archive.add(source, arcname="samples")
        return hashlib.sha256(output.read_bytes()).hexdigest()

    def test_whole_sidecar_round_trip_preserves_siblings_and_source_identities(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source, manifest = self.make_source(directory)
            received_version = (source / "received-corpus/version.json").read_bytes()
            (source / ".DS_Store").write_bytes(b"synthetic finder metadata")
            archive = directory / "samples.tar.zst"
            digest = package_corpus(source, archive, "complete-1", sidecar_inventory=manifest)
            self.assertEqual((source / "received-corpus/version.json").read_bytes(), received_version)
            self.assertFalse((source / RELEASE_FILE).exists())
            target = directory / "arbitrary-install-name"
            fetch_corpus(archive.as_uri(), digest, target, sidecar_inventory=manifest)
            self.assertEqual(verify(target, manifest, include_history=True), (5, []))
            self.assertEqual(read_release(target, manifest)["version"], "complete-1")
            self.assertFalse((target / ".DS_Store").exists())
            # Repacking an installed release must replace transport metadata in
            # the new archive without editing that installed source release.
            second_archive = directory / "second.tar.zst"
            second_digest = package_corpus(target, second_archive, "complete-2", sidecar_inventory=manifest)
            second_target = directory / "second-install"
            fetch_corpus(second_archive.as_uri(), second_digest, second_target, sidecar_inventory=manifest)
            self.assertEqual(read_release(second_target, manifest)["version"], "complete-2")
            self.assertEqual(read_release(target, manifest)["version"], "complete-1")

    def test_cli_defaults_transfer_entire_encrypted_sidecar(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source, manifest = self.make_source(directory)
            manifest_path = directory / "inventory.json"
            manifest_path.write_text(json.dumps(manifest))
            archive = directory / "samples.tar.zst.enc"
            # The public CLI mains exercise the full-sidecar defaults; only the
            # terminal password prompt is replaced for this noninteractive test.
            from grampy.corpus_package import main as package_main
            from grampy.corpus_setup import main as fetch_main
            with patch("getpass.getpass", return_value="independent-password"):
                self.assertEqual(package_main([
                    "--samples-root", str(source), "--manifest", str(manifest_path),
                    "--version", "encrypted-1", "--output", str(archive), "--encrypt",
                ]), 0)
                target = directory / "restored"
                self.assertEqual(fetch_main([
                    "--url", archive.as_uri(), "--sha256", hashlib.sha256(archive.read_bytes()).hexdigest(),
                    "--samples-root", str(target), "--manifest", str(manifest_path), "--encrypted",
                ]), 0)
            self.assertEqual(verify(target, manifest, include_history=True), (5, []))

    def test_required_only_install_works_without_optional_archive(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source, manifest = self.make_source(directory, history=False)
            archive = directory / "samples.tar.zst"
            digest = package_corpus(source, archive, "required-1", sidecar_inventory=manifest)
            target = directory / "restored"
            fetch_corpus(archive.as_uri(), digest, target, sidecar_inventory=manifest)
            self.assertFalse((target / "archive").exists())
            self.assertFalse(read_release(target, manifest)["include_history"])
            self.assertEqual(verify(target, manifest), (4, []))

    def test_packaging_rejects_unclassified_or_missing_inputs_without_modifying_source(self):
        for mutation in ("unknown", "missing"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                source, manifest = self.make_source(directory)
                received = (source / "received-corpus/version.json").read_bytes()
                if mutation == "unknown":
                    (source / "unclassified.bin").write_bytes(b"independent extra")
                else:
                    (source / "regression-expectations/expected.txt").unlink()
                output = directory / "samples.tar.zst"
                with self.assertRaisesRegex(CorpusPackageError, "inventory failed"):
                    package_corpus(source, output, "bad", sidecar_inventory=manifest)
                self.assertFalse(output.exists())
                self.assertEqual((source / "received-corpus/version.json").read_bytes(), received)
                self.assertFalse((source / RELEASE_FILE).exists())

    def test_valid_outer_checksum_does_not_allow_bad_internal_inputs_to_replace_install(self):
        for mutation in ("missing", "changed", "inventory"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as name:
                directory = Path(name)
                source, manifest = self.make_source(directory)
                if mutation == "missing":
                    (source / "controlled-mfsk-v1/input.bin").unlink()
                elif mutation == "changed":
                    (source / "regression-expectations/expected.txt").write_bytes(b"ALTERED")
                embedded = manifest if mutation != "inventory" else {**manifest, "version": "wrong"}
                output = directory / "bad.tar"
                digest = self.make_tar(source, embedded, output)
                target = directory / "existing"
                target.mkdir()
                marker = target / "keep.bin"
                marker.write_bytes(b"PRESERVE EVERY EXISTING DIRECTORY")
                with self.assertRaises(CorpusSetupError):
                    fetch_corpus(output.as_uri(), digest, target, sidecar_inventory=manifest)
                self.assertEqual(marker.read_bytes(), b"PRESERVE EVERY EXISTING DIRECTORY")
                self.assertEqual(list(directory.glob(".corpus-ready-*")), [])

    def test_received_only_archive_cannot_replace_whole_sidecar(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            source, manifest = self.make_source(directory)
            output = directory / "old.tar"
            with tarfile.open(output, "w") as tar:
                tar.add(source / "received-corpus", arcname="received-corpus")
            target = directory / "existing"
            target.mkdir()
            (target / "keep.bin").write_bytes(b"KEEP")
            with self.assertRaisesRegex(CorpusSetupError, "exactly the 'samples' root"):
                fetch_corpus(output.as_uri(), hashlib.sha256(output.read_bytes()).hexdigest(),
                             target, sidecar_inventory=manifest)
            self.assertEqual((target / "keep.bin").read_bytes(), b"KEEP")

    def test_failed_install_rename_restores_existing_sidecar(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            target = directory / "samples"
            staging = directory / "staging"
            target.mkdir()
            staging.mkdir()
            (target / "keep.bin").write_bytes(b"EXISTING DATA")
            (staging / "new.bin").write_bytes(b"NEW DATA")
            original = Path.replace

            def fail_install(path, destination):
                if path == staging:
                    raise OSError("synthetic installation failure")
                return original(path, destination)

            with patch.object(Path, "replace", fail_install):
                with self.assertRaisesRegex(CorpusSetupError, "synthetic installation failure"):
                    replace_corpus(staging, target)
            self.assertEqual((target / "keep.bin").read_bytes(), b"EXISTING DATA")
            self.assertFalse(staging.exists())
