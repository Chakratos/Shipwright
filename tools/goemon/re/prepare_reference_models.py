#!/usr/bin/env python3
"""Fetch four published *static* N64 character reference meshes locally.

Source: The Models Resource, Mystical Ninja Starring Goemon playable
characters (Jingleboy's 2014 OBJ+PNG exports). These are original-looking
external model *references*, NOT the source-ROM animation or skeletons.

The downloader NEVER commits, uploads or writes asset bytes to GitHub.
Source ZIPs, .gomesh files and PNGs live outside the Shipwright checkout.
The model archive URLs are taken from each source page's download link.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import shutil
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from import_reference_models import CHARACTERS, load_reference_model

REFERENCE_URLS = {
    "Goemon": "https://models.spriters-resource.com/media/assets/288/291117.zip?updated=1755498095",
    "Ebisumaru": "https://models.spriters-resource.com/media/assets/288/291027.zip?updated=1755498073",
    "Sasuke": "https://models.spriters-resource.com/media/assets/288/291233.zip?updated=1755498125",
    "Yae": "https://models.spriters-resource.com/media/assets/288/291015.zip?updated=1755498070",
}
SOURCE_PAGES = {
    "Goemon": "https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291117/",
    "Ebisumaru": "https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291027/",
    "Sasuke": "https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291233/",
    "Yae": "https://models.spriters-resource.com/nintendo_64/mysticalninjastarringgoemon/asset/291015/",
}
MAX_ZIP_BYTES = 5 * 1024 * 1024
# Original model asset IDs and archive OBJ entry names from provider pages.
MODEL_ASSET_IDS = {
    "Goemon": ("291117", "goe/goe.obj"),
    "Ebisumaru": ("291027", "ebi/ebisumaru.obj"),
    "Sasuke": ("291233", "sas/sas.obj"),
    "Yae": ("291015", "yae/yae.obj"),
}

def discover_local_archive(character: str, downloads: Path) -> Path | None:
    if character not in MODEL_ASSET_IDS or not downloads.is_dir():
        return None
    _, signature = MODEL_ASSET_IDS[character]
    for path in sorted(downloads.glob("*.zip")):
        if path.stat().st_size > MAX_ZIP_BYTES:
            continue
        try:
            with ZipFile(path) as archive:
                entries = {name.replace(chr(92), "/").lower()
                           for name in archive.namelist()}
                if signature in entries and archive.testzip() is None:
                    return path
        except (OSError, BadZipFile):
            continue
    return None

def download_reference_archive(character: str, output: Path) -> str:
    if character not in REFERENCE_URLS:
        raise ValueError("unknown original character archive")
    req = Request(
        REFERENCE_URLS[character],
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GoemonLocalModelStudy/1",
            "Referer": SOURCE_PAGES[character],
            "Accept": "application/zip,application/octet-stream,*/*",
        }
    )
    with urlopen(req, timeout=35) as response:
        raw = response.read(MAX_ZIP_BYTES + 1)
    if len(raw) > MAX_ZIP_BYTES or len(raw) < 30 or raw[:2] != b"PK":
        raise ValueError("external model response is not the expected small ZIP")
    # Validate before populating the local cache, so a transient HTML or
    # partial network response never poisons subsequent offline attempts.
    with ZipFile(BytesIO(raw)) as archive:
        if archive.testzip() is not None:
            raise ValueError("corrupted N64 character reference ZIP")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()

def prepare_all_models(destination: Path, *, download_dir: Path | None = None,
                       allow_network: bool = True) -> dict:
    project = Path(__file__).resolve().parents[3]
    destination = destination.expanduser().resolve()
    if project == destination or project in destination.parents:
        raise ValueError("do not store external character assets inside Git checkout")
    source_dir = destination / "source-zips"
    summary = []
    for character in CHARACTERS:
        source = source_dir / f"{character}.zip"
        if not source.is_file() and download_dir is not None:
            local = discover_local_archive(character, download_dir)
            if local is not None:
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(local, source)
                print(f"LOCAL MODEL SOURCE: {character} from {local.name}")
        if source.is_file():
            archive_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        elif allow_network:
            archive_hash = download_reference_archive(character, source)
        else:
            raise ValueError(
                f"{character}: ZIP missing. Download from {SOURCE_PAGES[character]} "
                "into the selected Downloads directory; no network access attempted."
            )
        packed, report, textures = load_reference_model(source, character)
        target = destination / character
        target.mkdir(parents=True,exist_ok=True)
        (target / "model.gomesh").write_bytes(packed)
        (target / "manifest.json").write_text(
            json.dumps(report,indent=2)+"\n",encoding="utf-8")
        for name,raw in textures.items():
            (target / name).write_bytes(raw)
        summary.append({
            "character": character,
            "source_page": SOURCE_PAGES[character],
            "source_zip_sha256": archive_hash,
            "vertices": report["vertex_count"],
            "triangles": report["triangle_count"],
            "material_count": len(report["materials"]),
            "local_model_path": str(target),
        })
        print(f"LOCAL CHARACTER MESH: {character}, "
              f"{report['vertex_count']} vertices, "
              f"{report['triangle_count']} triangles, "
              f"{len(report['materials'])} materials")
    (destination / "local-reference-summary.json").write_text(
        json.dumps({
            "schema": "goemon-local-reference-models-v1",
            "note": "External static N64 rips; NOT yet ROM-validated skeletons or animation.",
            "characters": summary,
        },indent=2)+"\n",encoding="utf-8")
    return {"characters":summary}

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",required=True,type=Path)
    p.add_argument("--download-dir", type=Path,
                   help="optional browser Downloads directory, auto-match four original ZIPs")
    p.add_argument("--offline", action="store_true",
                   help="use cached/browser-downloaded ZIPs only; no network access")
    args=p.parse_args(argv)
    try:
        prepare_all_models(args.output_dir, download_dir=args.download_dir,
                           allow_network=not args.offline)
    except (OSError,ValueError,BadZipFile) as exc:
        print(f"MODEL REFERENCE IMPORT FAILED: {exc}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
