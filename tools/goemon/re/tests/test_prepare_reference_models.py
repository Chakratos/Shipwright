"""Offline verification of local-only four-character model preparation.

No network access and no copyrighted N64 resources. Cache entries here
are synthetic OBJ/MTL/PNG fixtures, not original game art.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from import_reference_models import CHARACTERS, HEADER, MAGIC
from prepare_reference_models import (
    REFERENCE_URLS, SOURCE_PAGES,
    MODEL_ASSET_IDS, discover_local_archive,
    download_reference_archive, prepare_all_models,
)

OBJ = """o synthetic
v 0 0 0
v 1 0 0
v 0 1 0
vt 0 0
vt 1 0
vt 0 1
usemtl test
f 1/1 2/2 3/3
"""
MTL = "newmtl test\nmap_Kd original.png\n"
PNG = (
    bytes.fromhex("89504e470d0a1a0a")
    + b"\x00" * 8 + struct.pack(">II", 2, 2) + b"\x00" * 8
)

def synthetic_zip() -> bytes:
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        archive.writestr("model/example.obj", OBJ)
        archive.writestr("model/example.mtl", MTL)
        archive.writestr("model/original.png", PNG)
    return out.getvalue()

class PrepareReferenceModelsTests(unittest.TestCase):
    def test_all_four_cached_reference_meshes_stay_outside_git(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            source = path / "source-zips"
            source.mkdir()
            for character in CHARACTERS:
                (source / f"{character}.zip").write_bytes(synthetic_zip())
            # A cached import must never contact any external service.
            with patch("prepare_reference_models.download_reference_archive",
                       side_effect=AssertionError("unexpected network access")):
                result = prepare_all_models(path)
            self.assertEqual(
                [x["character"] for x in result["characters"]], list(CHARACTERS)
            )
            summary = json.loads(
                (path / "local-reference-summary.json").read_text("utf-8")
            )
            self.assertEqual(len(summary["characters"]), 4)
            for character in CHARACTERS:
                dest = path / character
                raw = (dest / "model.gomesh").read_bytes()
                self.assertEqual(HEADER.unpack_from(raw), (MAGIC, 3, 1, 1))
                self.assertEqual((dest / "texture_000.png").read_bytes(), PNG)
                report = json.loads((dest / "manifest.json").read_text("utf-8"))
                self.assertEqual(report["character"], character)
                self.assertTrue(report["static_geometry_only"])
                self.assertFalse(report["original_animation_and_skeleton"])

    def test_offline_browser_downloads_need_no_file_renames(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            downloads = root / "Downloads"
            downloads.mkdir()
            destination = root / "generated"
            for character in CHARACTERS:
                asset_id, internal_obj = MODEL_ASSET_IDS[character]
                source_dir = internal_obj.rsplit("/", 1)[0]
                archive_path = downloads / f"n64-{asset_id}-download.zip"
                with ZipFile(archive_path, "w") as archive:
                    archive.writestr(internal_obj, OBJ)
                    archive.writestr(f"{source_dir}/material.mtl", MTL)
                    archive.writestr(f"{source_dir}/original.png", PNG)
                self.assertEqual(
                    discover_local_archive(character, downloads), archive_path
                )
            with patch("prepare_reference_models.download_reference_archive",
                       side_effect=AssertionError("offline mode must never download")):
                result = prepare_all_models(
                    destination, download_dir=downloads, allow_network=False
                )
            self.assertEqual(len(result["characters"]), 4)
            for character in CHARACTERS:
                self.assertTrue((destination / character / "model.gomesh").is_file())
                self.assertTrue((destination / "source-zips" /
                                 f"{character}.zip").is_file())

    def test_offline_rejects_missing_zip_without_network(self):
        with TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Goemon: ZIP missing"):
                prepare_all_models(Path(temp) / "models", allow_network=False)
            self.assertIsNone(
                discover_local_archive("Yae", Path(temp) / "not-a-directory")
            )

    def test_fetch_uses_character_specific_zip_and_validates_archive(self):
        with TemporaryDirectory() as temp:
            dst = Path(temp) / "character.zip"
            sample = synthetic_zip()
            def fake_open(req, timeout):
                self.assertIn("291117.zip", req.full_url)
                self.assertEqual(timeout, 35)
                return BytesIO(sample)
            with patch("prepare_reference_models.urlopen", side_effect=fake_open):
                sha = download_reference_archive("Goemon", dst)
            self.assertEqual(len(sha), 64)
            self.assertEqual(dst.read_bytes(), sample)
            with self.assertRaisesRegex(ValueError, "unknown original"):
                download_reference_archive("Missing", dst)

    def test_refuses_asset_write_inside_git_checkout(self):
        root = Path(__file__).resolve().parents[3]
        with self.assertRaisesRegex(ValueError, "Git checkout"):
            prepare_all_models(root / "_no_model_assets_here")

    def test_all_sources_are_specific_and_have_valid_pages(self):
        self.assertEqual(tuple(REFERENCE_URLS), CHARACTERS)
        self.assertEqual(tuple(SOURCE_PAGES), CHARACTERS)
        self.assertEqual(len(set(REFERENCE_URLS.values())), 4)
        self.assertEqual(len(set(SOURCE_PAGES.values())), 4)
        self.assertTrue(all(url.startswith("https://") and ".zip?" in url
                            for url in REFERENCE_URLS.values()))

if __name__ == "__main__":
    unittest.main()
