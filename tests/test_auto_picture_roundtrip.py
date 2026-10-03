from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

import numpy as np
from PIL import Image
from scipy.signal import hilbert

from grampy.api import (DecodeConfig, EncodeConfig, ImagePart, MfskSegment,
                        TextPart, decode_iq_products, encode_mfsk_wav)


class AutomaticPictureRoundtripTests(unittest.TestCase):
    def test_mixed_picture_modes_keep_order_files_and_resumed_text(self) -> None:
        """Real complete WAV, including two separated MFSK32 picture segments."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            y, x = np.mgrid[:120, :160]
            gray_a = ((x + y) // 2).astype(np.uint8)
            gray_b = (240 - (x + y) // 2).astype(np.uint8)
            rgb = np.stack((x, 30 + y, 230 - x), axis=2).astype(np.uint8)
            truths = (gray_a, rgb, gray_b)
            sources = []
            for index, truth in enumerate(truths):
                path = root / f"source-{index}.png"
                Image.fromarray(truth).save(path)
                sources.append(path)
            modes = ("MFSK32", "MFSK64", "MFSK32")
            parts = [MfskSegment((
                TextPart(f"PICTURE {index} BEGIN\n".encode()),
                ImagePart(path, color="color" if mode == "MFSK64" else "grayscale",
                          samples_per_pixel=4 if index < 2 else 2),
                TextPart(f"\nPICTURE {index} END".encode()),
            ), mode=mode, carrier_hz=carrier)
                for index, (mode, path, carrier) in enumerate(zip(modes, sources, (1400, 1600, 1500)))]
            wav_path = root / "broadcast.wav"
            encode_mfsk_wav(parts=parts, output_path=wav_path, config=EncodeConfig())
            with wave.open(str(wav_path)) as wav:
                sample_rate = wav.getframerate()
                pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768
            data, meta = root / "broadcast.sigmf-data", root / "broadcast.sigmf-meta"
            hilbert(pcm).astype("<c8").tofile(data)
            meta.write_text(json.dumps({
                "global": {"core:datatype": "cf32_le", "core:sample_rate": sample_rate},
                "captures": [{"core:sample_start": 0}], "annotations": [],
            }))
            products = decode_iq_products(meta_path=meta, data_path=data, config=DecodeConfig(),
                artifact_dir=root / "artifacts", artifact_path_prefix="artifacts",
                include_diagnostic_manifest=True)
            manifest = products.diagnostic_manifest
            pictures = manifest["pictures"]
            self.assertEqual([picture["mode"] for picture in pictures], list(modes))
            self.assertTrue(all(picture["complete"] for picture in pictures))
            self.assertEqual(len({picture["id"] for picture in pictures}), 3)
            artifacts = {item["id"]: item for item in manifest["artifacts"]}
            self.assertEqual(len(artifacts), len(manifest["artifacts"]))
            self.assertEqual(len({item["path"] for item in artifacts.values()}), len(artifacts))
            for picture, truth in zip(pictures, truths):
                artifact = artifacts[picture["raster_artifact"]]
                path = root / artifact["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact["sha256"])
                observed = np.asarray(Image.open(path))
                self.assertEqual(observed.shape, truth.shape)
                self.assertLess(np.mean(np.abs(observed.astype(float) - truth)), 25,
                                f"{picture['mode']} {picture['id']}")
            text = manifest["text_summary"]["text"]
            cursor = 0
            for index in range(3):
                for marker in (f"PICTURE {index} BEGIN", f"PICTURE {index} END"):
                    location = text.find(marker, cursor)
                    self.assertGreaterEqual(location, 0, marker)
                    cursor = location + len(marker)
            epochs = {epoch["id"]: epoch for epoch in manifest["text_epochs"]}
            self.assertEqual(len(epochs), len(manifest["text_epochs"]))
            for picture in pictures:
                if picture["following_text_epoch"] is not None:
                    self.assertEqual(epochs[picture["following_text_epoch"]]["picture"], picture["id"])
            self.assertEqual([segment["mode"] for segment in products.text_manifest["mode_segments"]], list(modes))
            for segment in products.text_manifest["mode_segments"]:
                items = [item for item in segment["items"] if item["kind"] == "picture"]
                self.assertEqual(len(items), 1)
                self.assertIsNotNone(items[0]["artifact"])


if __name__ == "__main__":
    unittest.main()
