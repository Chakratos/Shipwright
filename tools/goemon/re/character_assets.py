#!/usr/bin/env python3
"""Locate original character graphics files in a USER-PROVIDED decompressed MNSG ROM.

The table uses overlapping pairs of 32-bit offsets (4-byte stride), as\nGoemon64Recomp/src/game/rom_decompression.cpp increments its pointer by one\nuint32_t per file. The addresses are grounded in that source and
patches/variables.h. This is raw file extraction, not N64 model conversion.
Files are written only when --output-dir is explicitly provided.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys


FILE_TABLE_ROM_OFFSET = 0x57FD8
CHARACTER_GRAPHICS_IDS_ROM_OFFSET = 0x5BFF30
EXPECTED_CRC = (0x9CC11F4B, 0xABAA8538)
N64_Z64_MAGIC = bytes.fromhex("80371240")
MAX_FILES = 4096


@dataclass(frozen=True)
class FileEntry:
    file_id: int
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start


def validate_decompressed_rom(data: bytes, *, check_crc: bool = True) -> None:
    if data[:4] != N64_Z64_MAGIC:
        raise ValueError("expected big-endian N64 .z64 ROM")
    if len(data) < CHARACTER_GRAPHICS_IDS_ROM_OFFSET + 8:
        raise ValueError("ROM too small to contain original character-graphics file IDs")
    if check_crc and struct.unpack_from(">II", data, 0x10) != EXPECTED_CRC:
        raise ValueError(
            "expected Goemon64Recomp's decompressed US ROM (header CRC mismatch); "
            "run its ROM decompression step first"
        )


def read_file_table(data: bytes) -> list[FileEntry]:
    entries = []
    for file_id in range(MAX_FILES):
        address = FILE_TABLE_ROM_OFFSET + file_id * 4
        if address + 8 > len(data):
            raise ValueError("file table reaches past end of ROM")
        start, end = struct.unpack_from(">II", data, address)
        # Goemon64Recomp's decompressor terminates when either of two
        # overlapping adjacent offsets is zero (while start && end).
        if start == 0 or end == 0:
            break
        if start & 0x80000000 or end & 0x80000000:
            raise ValueError("compressed file-table flag remains: decompressed ROM required")
        if end < start or end > len(data) or start < FILE_TABLE_ROM_OFFSET + 8:
            raise ValueError(f"invalid file-table range for ID {file_id}: {start:#x}..{end:#x}")
        entries.append(FileEntry(file_id, start, end))
    else:
        raise ValueError("file table exceeds maximum permitted entry count")

    if not entries:
        raise ValueError("empty ROM file table")
    for a, b in zip(entries, entries[1:]):
        if b.start < a.end:
            raise ValueError(f"overlapping file-table entries: {a.file_id}, {b.file_id}")
    return entries


def character_graphics_ids(data: bytes, entries: list[FileEntry]) -> tuple[int, int, int, int]:
    ids = struct.unpack_from(">4H", data, CHARACTER_GRAPHICS_IDS_ROM_OFFSET)
    if len(set(ids)) != 4:
        raise ValueError(
            "character graphics ID table contains duplicates; values may be "
            "runtime-populated and must be verified in a Goemon player trace"
        )
    for index in ids:
        if index >= len(entries):
            raise ValueError(f"invalid character graphics file ID {index} (table length {len(entries)})")
    return ids


def make_manifest(data: bytes) -> tuple[dict, list[tuple[int, FileEntry]]]:
    validate_decompressed_rom(data)
    files = read_file_table(data)
    ids = character_graphics_ids(data, files)
    from character_names import CHARACTER_GRAPHICS_ROOTS, corroborated_character_names
    # Synthetic ROM fixtures and nonstandard graphics tables are not
    # automatically given character names. Only the corroborated NG5E
    # order has a defensible name assignment.
    names = (corroborated_character_names(ids)
             if tuple(ids) == CHARACTER_GRAPHICS_ROOTS else None)
    selected = []
    characters = []
    for slot, index in enumerate(ids):
        entry = files[index]
        raw = data[entry.start:entry.end]
        sha = hashlib.sha256(raw).hexdigest()
        characters.append({
            "slot": slot,
            "character_name": names[slot]["character_name"] if names else None,
            "name_provenance": names[slot]["name_provenance"] if names else None,
            "rom_proven_name_string": False,
            "graphics_file_id": index,
            "rom_start": entry.start,
            "rom_end": entry.end,
            "size": entry.size,
            "sha256": sha,
        })
        selected.append((slot, entry))
        # Four original character roots are separated by four consecutive
        # file-table indices. Inspect neighbors as candidates, not proven
        # model/texture/animation roles. Real ROM has PIC0000 at root+1.
        neighbors = []
        for neighbor_id in range(index, min(index + 4, len(files))):
            neighbor = files[neighbor_id]
            payload = data[neighbor.start:neighbor.end]
            neighbors.append({
                "file_id": neighbor_id,
                "relative_to_root": neighbor_id - index,
                "rom_start": neighbor.start,
                "rom_end": neighbor.end,
                "size": neighbor.size,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "signature": "PIC0000" if payload.startswith(b"PIC0000") else None,
                "format_role": None,  # Requires original renderer tracing.
            })
        characters[-1]["adjacent_resource_candidates"] = neighbors

    return {
        "source": "original decompressed US Mystical Ninja Starring Goemon ROM",
        "rom_sha256": hashlib.sha256(data).hexdigest(),
        "file_table_address": f"0x{FILE_TABLE_ROM_OFFSET:08X}",
        "character_ids_rom_address": f"0x{CHARACTER_GRAPHICS_IDS_ROM_OFFSET:08X}",
        "file_table_count": len(files),
        "character_graphics": characters,
        "name_source_urls": list(names[0]["name_source_urls"]) if names else [],
        "note": "Names are corroborated by published USA GameShark codes and original global-ID traces; no original ROM name strings. Adjacent resource roles unverified.",
    }, selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decompressed_z64", type=Path)
    parser.add_argument("--output-dir", type=Path, help="explicitly extract binary assets locally")
    parser.add_argument("--manifest", type=Path, help="optional JSON manifest path")
    args = parser.parse_args(argv)
    try:
        rom = args.decompressed_z64.read_bytes()
        manifest, selected = make_manifest(rom)
        if args.output_dir:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for slot, entry in selected:
                target = args.output_dir / f"character_slot_{slot}_file_{entry.file_id}.bin"
                target.write_bytes(rom[entry.start:entry.end])
        result = json.dumps(manifest, indent=2) + "\n"
        if args.manifest:
            args.manifest.write_text(result, encoding="utf-8")
        else:
            print(result, end="")
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
