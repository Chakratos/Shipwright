#!/usr/bin/env python3
"""Catalog the original Goemon PIC0000 image blocks in a user-owned US ROM.

The real NG5E file table contains 31 PIC0000 resource files with 1,810
16-byte-aligned image records. The four character-adjacent resource files
(289/293/297/301) together contain 45 records. The header gives the
format marker plus plausible width/height; the payload codec, texture
semantics and rendering are not yet proven. This script NEVER exports raw
images, copyrighted graphics, original ROM bytes or models.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import sys

from character_assets import (
    FILE_TABLE_ROM_OFFSET, character_graphics_ids, read_file_table,
    validate_decompressed_rom,
)
from decompress_rom import ensure_decompressed_rom

MAGIC = b"PIC0000\x1a"
HEADER_SIZE = 17
BLOCK_ALIGNMENT = 16
MAX_IMAGE_DIM = 4096
KNOWN_FORMAT_MARKERS = frozenset((4, 8, 15, 16))


@dataclass(frozen=True)
class PictureChunk:
    index: int
    local_file_offset: int
    allocated_bytes: int
    format_marker: int
    header_flags: int
    width: int
    height: int
    sha256: str


def catalog_chunks(data: bytes) -> list[PictureChunk]:
    if not data.startswith(MAGIC):
        raise ValueError("not an original PIC0000 resource")
    starts: list[int] = []
    index = 0
    while True:
        index = data.find(MAGIC, index)
        if index < 0:
            break
        if index % BLOCK_ALIGNMENT:
            raise ValueError(f"unaligned PIC0000 block at file offset {index:#x}")
        if index + HEADER_SIZE > len(data):
            raise ValueError("truncated PIC0000 image header")
        starts.append(index)
        index += len(MAGIC)
    if not starts:
        raise ValueError("missing PIC0000 image blocks")
    records: list[PictureChunk] = []
    for number, start in enumerate(starts):
        end = starts[number + 1] if number + 1 < len(starts) else len(data)
        if end <= start + HEADER_SIZE or (end - start) % BLOCK_ALIGNMENT:
            raise ValueError(f"malformed 16-byte image allocation at {start:#x}")
        header_flags = int.from_bytes(data[start + 8 : start + 12], "big")
        # Real NG5E uses both 0x00000000 and 0x00004000 in this
        # header field. Their semantics require original decoder RE.
        if header_flags not in (0, 0x4000):
            raise ValueError(f"unexpected PIC0000 header flags at {start:#x}")
        marker = data[start + 12]
        width = int.from_bytes(data[start + 13 : start + 15], "big")
        height = int.from_bytes(data[start + 15 : start + 17], "big")
        if (marker not in KNOWN_FORMAT_MARKERS
                or width < 1 or height < 1
                or width > MAX_IMAGE_DIM or height > MAX_IMAGE_DIM):
            raise ValueError(f"unrecognized PIC0000 header at {start:#x}")
        allocated = data[start:end]
        records.append(PictureChunk(
            index=number, local_file_offset=start, allocated_bytes=len(allocated),
            format_marker=marker, header_flags=header_flags,
            width=width, height=height,
            sha256=hashlib.sha256(allocated).hexdigest(),
        ))
    return records


def catalog_rom(data: bytes, *, all_pic_resources: bool = False) -> dict:
    image = ensure_decompressed_rom(data)
    validate_decompressed_rom(image)
    files = read_file_table(image)
    roots = character_graphics_ids(image, files)
    selected = set(root + 1 for root in roots)
    if all_pic_resources:
        selected.update(
            entry.file_id for entry in files
            if image[entry.start:entry.end].startswith(MAGIC)
        )
    images = []
    total = Counter()
    for index in sorted(selected):
        entry = files[index]
        raw = image[entry.start:entry.end]
        blocks = catalog_chunks(raw)
        total.update(chunk.format_marker for chunk in blocks)
        images.append({
            "file_id": index,
            "character_slot": (
                next((slot for slot, root in enumerate(roots)
                      if index == root + 1), None)
            ),
            "character_name": None,
            "file_rom_offset": entry.start,
            "file_bytes": entry.size,
            "picture_count": len(blocks),
            "picture_chunks": [asdict(chunk) for chunk in blocks],
        })
    return {
        "source": "original NG5E user-owned ROM",
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "decompressed_sha256": hashlib.sha256(image).hexdigest(),
        "source_file_table_offset": f"0x{FILE_TABLE_ROM_OFFSET:X}",
        "all_resources": all_pic_resources,
        "character_root_file_ids": list(roots),
        "file_count": len(images),
        "picture_count": sum(item["picture_count"] for item in images),
        "format_marker_counts": dict(sorted(total.items())),
        "resource_files": images,
        "limits": (
            "PIC0000 block boundary, format marker and likely image width/height "
            "only. Compression codec, textures, palettes, skeletons and "
            "Goemon/Ebisumaru/Sasuke/Yae name-to-slot mappings unverified."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_us_rom", type=Path, help="your own 16 MiB NG5E or decompressed ROM")
    parser.add_argument("--all", action="store_true", help="catalog every original PIC0000 file")
    parser.add_argument("--output", type=Path, help="metadata-only JSON destination")
    args = parser.parse_args(argv)
    try:
        data = catalog_rom(args.original_us_rom.read_bytes(), all_pic_resources=args.all)
        payload = json.dumps(data, indent=2) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
