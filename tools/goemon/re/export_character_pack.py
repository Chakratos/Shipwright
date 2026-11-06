#!/usr/bin/env python3
"""Package genuine four-character Goemon graphics *locally* from an owned ROM.

Includes the original 4 x 4 adjacent asset resources and every separately
framed PIC0000 image in the four +1 resource files. This stage is a LOSSLESS
resource packer, not a speculative texture/animation/geometry decoder.

The game ROM and extracted assets must never be added to the Git repository.
With no --output path, the program prints metadata only and writes nothing.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from character_assets import (
    character_graphics_ids, read_file_table, validate_decompressed_rom,
)
from decompress_rom import ensure_decompressed_rom
from character_id_binding import source_proven_character_graphics
from character_names import corroborated_character_names
from pic0000_catalog import MAGIC, catalog_chunks


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def make_archive(files: dict[str, bytes]) -> bytes:
    """Create deterministic ZIP with hashes independent of ZIP timestamps."""
    memory = BytesIO()
    with ZipFile(memory, "w") as archive:
        for name, content in sorted(files.items()):
            if name.startswith("/") or ".." in name.split("/") or "\\" in name:
                raise ValueError("invalid original character resource path")
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    return memory.getvalue()


def package_character_files(
    groups: list[list[tuple[int, bytes]]],
    *,
    original_rom_hash: str,
    decompressed_rom_hash: str,
) -> tuple[dict, dict[str, bytes]]:
    """Pack 4 groups of exactly 4 original files; synthetic-test friendly."""
    if len(groups) != 4 or any(len(group) != 4 for group in groups):
        raise ValueError("expected precisely four original character resource groups")
    names: set[str] = set()
    assets: dict[str, bytes] = {}
    characters = []
    names = corroborated_character_names(tuple(group[0][0] for group in groups))
    picture_total = 0
    for slot, group in enumerate(groups):
        ids = [file_id for file_id, _ in group]
        if ids != list(range(ids[0], ids[0] + 4)):
            raise ValueError("non-consecutive original character group")
        resource_records = []
        picture_records = []
        for sub, (file_id, payload) in enumerate(group):
            if not payload:
                raise ValueError(f"empty original character resource {file_id}")
            role = "picture-blocks" if sub == 1 else "unclassified-original-binary"
            name = f"resources/slot_{slot}/file_{file_id:04d}_part_{sub}.bin"
            if name in names:
                raise ValueError("duplicate original character resource")
            names.add(name)
            assets[name] = payload
            resource_records.append({
                "original_file_id": file_id,
                "group_part": sub,
                "role": role,
                "archive_path": name,
                "byte_length": len(payload),
                "sha256": sha256(payload),
            })
            if sub == 1:
                if not payload.startswith(MAGIC):
                    raise ValueError(f"original character +1 file {file_id} lacks PIC0000")
                pictures = catalog_chunks(payload)
                for pic in pictures:
                    start = pic.local_file_offset
                    finish = start + pic.allocated_bytes
                    name = (
                        f"pictures/slot_{slot}/file_{file_id:04d}"
                        f"_image_{pic.index:03d}.pic"
                    )
                    chunk = payload[start:finish]
                    if len(chunk) != pic.allocated_bytes:
                        raise ValueError("PIC picture boundaries exceeded original file")
                    assets[name] = chunk
                    picture_records.append({
                        **asdict(pic),
                        "archive_path": name,
                        "source_file_id": file_id,
                        "source_absolute_offset_in_group": start,
                    })
                    picture_total += 1
        characters.append({
            "character_slot": slot,
            "original_root_id": ids[0],
            "character_name": names[slot]["character_name"],
            "name_provenance": names[slot]["name_provenance"],
            "rom_proven_name_string": False,
            "source_files": resource_records,
            "picture_chunks": picture_records,
        })

    manifest = {
        "schema": "goemon64-original-character-pack-v1",
        "rom_sha256": original_rom_hash,
        "decompressed_rom_sha256": decompressed_rom_hash,
        "character_slots": 4,
        "resource_file_count": 16,
        "picture_block_count": picture_total,
        "characters": characters,
        "name_evidence": {str(k): v for k, v in names.items()},
        "limitations": (
            "Lossless original binary resource pack only. Character names are "
            "externally corroborated by published USA GameShark modifiers, "
            "not by in-ROM name strings. Texture codec, display-list parsing "
            "and animation decoding remain unknown; not ready to render."
        ),
    }
    assets["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    return manifest, assets


def from_rom(original: bytes) -> tuple[dict, dict[str, bytes]]:
    image = ensure_decompressed_rom(original)
    validate_decompressed_rom(image)
    table = read_file_table(image)
    roots = character_graphics_ids(image, table)
    proven_roots = source_proven_character_graphics(image)
    if roots != proven_roots:
        raise ValueError("original MIPS numeric character ID -> root file mapping inconsistent")
    groups = []
    for root in roots:
        if root + 3 >= len(table):
            raise ValueError(f"original character group {root} exceeds ROM table")
        parts = []
        for file_id in range(root, root + 4):
            entry = table[file_id]
            parts.append((file_id, image[entry.start:entry.end]))
        groups.append(parts)
    manifest, assets = package_character_files(
        groups, original_rom_hash=sha256(original),
        decompressed_rom_hash=sha256(image),
    )
    # Original ROM table IDs, not guessed character names.
    manifest["character_graphics_root_ids"] = list(roots)
    manifest["numeric_character_ids_source_proven"] = True
    manifest["proof_mips_function_ram"] = "0x801DC9C8"
    for character_id, character in enumerate(manifest["characters"]):
        character["original_numeric_character_id"] = character_id
    assets["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    return manifest, assets


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_us_rom", type=Path)
    parser.add_argument("--output", type=Path,
                        help="explicit local output path (*.zip), outside the Git checkout")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing local output ZIP")
    parser.add_argument("--manifest", type=Path,
                        help="optional metadata-only JSON file")
    args = parser.parse_args(argv)
    try:
        manifest, assets = from_rom(args.original_us_rom.read_bytes())
        text = json.dumps(manifest, indent=2) + "\n"
        if args.manifest:
            if args.manifest.exists() and not args.force:
                raise ValueError("manifest exists (use --force to replace)")
            args.manifest.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        if args.output:
            if args.output.suffix.lower() != ".zip":
                raise ValueError("output must have a .zip extension")
            if args.output.exists() and not args.force:
                raise ValueError("local output ZIP exists (use --force to replace)")
            args.output.write_bytes(make_archive(assets))
            print(f"Local original character pack: {args.output}")
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
