#!/usr/bin/env python3
"""Verify a LOCAL original NTSC-U NG5E ROM against known original data.

Runs only on the user's machine; never copies ROM data to GitHub or log output.
Synthetic test fixtures are not accepted as authenticity evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ORIGINAL_SHA256 = "1603be37427a33548857fc3d2e8867ede71121c353fb631b79b44f1d94845d80"
DECOMPRESSED_SHA256 = "e40bee20508c2e29e651dca4e47504e40f908f0a2186e34a582784bf5a64be4c"
EXPECTED_GRAPHICS = ((288, 61440), (292, 28672), (296, 53248), (300, 53248))
DEFAULT_ROM = Path(r"C:\actions-runner-goemon\roms\Goemon.z64")
ROM_DIRECTORIES = (
    DEFAULT_ROM.parent,
    Path(r"C:\Users\Chakratos\source\repos\OOT_Goemon"),
)


def locate_rom() -> Path:
    override = os.environ.get("GOEMON_ROM_PATH")
    if override:
        return Path(override)
    for directory in ROM_DIRECTORIES:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.z64")):
            if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ORIGINAL_SHA256:
                return path
    return DEFAULT_ROM


def check_rom(path: Path, *, graphics_scan: bool = False,
              segmented_scan: bool = False, recover_geometry: bool = False,
              source_aligned: bool = False, offline_rigs: bool = False) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "re"))
    from decompress_rom import decompress_us_rom
    from character_assets import make_manifest, read_file_table
    from character_id_binding import source_proven_character_graphics

    raw = path.read_bytes()
    if len(raw) != 16 * 1024 * 1024:
        raise ValueError("expected original 16 MiB NG5E .z64")
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("source ROM SHA-256 differs from verified original")
    if raw[:4] != bytes.fromhex("80371240") or raw[0x3B:0x3F] != b"NG5E":
        raise ValueError("incorrect original N64 ROM header")

    decoded = decompress_us_rom(raw)
    if hashlib.sha256(decoded).hexdigest() != DECOMPRESSED_SHA256:
        raise ValueError("decompressed ROM SHA-256 differs from real baseline")

    manifest, character_entries = make_manifest(decoded)
    source_roots = source_proven_character_graphics(decoded)
    if source_roots != (288, 292, 296, 300):
        raise ValueError("original MIPS character ID -> graphics root mapping differs")
    if manifest["file_table_count"] != 1311:
        raise ValueError("actual ROM file table entry count differs from 1311")
    graphics = manifest["character_graphics"]
    if tuple((g["graphics_file_id"], g["size"]) for g in graphics) != EXPECTED_GRAPHICS:
        raise ValueError("actual character graphics entries differ from original")
    if not all(g["adjacent_resource_candidates"][1]["signature"] == "PIC0000"
               for g in graphics):
        raise ValueError("character graphics signatures differ from original")

    print("REAL NG5E ROM: PASS")
    print("Verified original and decompressed SHA-256, real 1311-entry file table, "
          "and four original character graphics sets.")
    print("No ROM or extracted asset bytes were uploaded or printed.")

    if offline_rigs:
        from offline_original_rigs import scan_offline_original_rom
        report = scan_offline_original_rom(decoded)
        print("GOEMON_ROM_ONLY_RIGS " + json.dumps(report, separators=(",", ":")))
        print("GOEMON_ROM_ONLY_RIGS COMPLETE: original ROM-only linked Skeleton structs, no gameplay recording")

    if source_aligned:
        from source_aligned_character_assets import analyze_source_aligned_rom
        report = analyze_source_aligned_rom(decoded)
        print("GOEMON_SOURCE_ALIGNED " + json.dumps(report, separators=(",", ":")))
        print("GOEMON_SOURCE_ALIGNED COMPLETE: splat file labels aligned to ROM table, "
              "no manual in-game capture, no ROM bytes printed")

    if segmented_scan:
        from original_segmented_scan import scan_original_character_group
        for slot in range(4):
            report = scan_original_character_group(decoded, slot)
            print("GOEMON_SEGMENTED_SCAN " + json.dumps(
                report, separators=(",", ":")))
        print("GOEMON_SEGMENTED_SCAN COMPLETE: real NG5E ROM, 4 source-proven "
              "character pairs 0x09/0x07; pointer linkage still needs validation.")

    if recover_geometry:
        from original_segmented_geometry import (
            recover_character_from_rom, recovery_summary)
        for slot in range(4):
            found = recover_character_from_rom(decoded, slot)
            print("GOEMON_ORIGINAL_GEOMETRY " + json.dumps({
                "character_slot": slot,
                **recovery_summary(found)
            }, separators=(",", ":")))
        print("GOEMON_ORIGINAL_GEOMETRY COMPLETE: original ROM data only; "
              "no mesh files or copyrighted bytes uploaded.")

    if graphics_scan:
        from original_graphics_scan import scan_original_graphics_resource
        table = read_file_table(decoded)
        for slot, (_, root_entry) in enumerate(character_entries):
            for part in range(4):
                entry = table[root_entry.file_id + part]
                graphic = decoded[entry.start:entry.end]
                report = scan_original_graphics_resource(graphic)
                # Only metadata from the local ROM, never source bytes.
                print("GOEMON_GRAPHICS_SCAN " + json.dumps({
                    "character_id": slot,
                    "original_file_id": entry.file_id,
                    "group_part": part,
                    "starts_with_pic0000": graphic.startswith(
                        bytes.fromhex("504943303030301a")),
                    "character_name": manifest["character_graphics"][slot]["character_name"],
                    **report,
                }, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=locate_rom())
    parser.add_argument("--graphics-scan", action="store_true",
                        help="print metadata-only N64 graphics/rigger candidate counts")
    parser.add_argument("--offline-rigs", action="store_true",
                        help="decode Skeleton pointer graphs directly from ROM")
    parser.add_argument("--source-aligned", action="store_true",
                        help="cross-validate actual ROM file IDs against source splat segments")
    parser.add_argument("--segmented-scan", action="store_true",
                        help="inspect genuine per-character 0x09/0x07 banks from splat.yaml")
    parser.add_argument("--recover-geometry", action="store_true",
                        help="decode source-ROM F3DEX triangles; print metadata only")
    args = parser.parse_args(argv)
    if not args.rom.is_file():
        print(f"REAL NG5E ROM: NOT FOUND at {args.rom}. "
              "Install the user-provided ROM locally in the runner's roms directory.",
              file=sys.stderr)
        return 2
    try:
        check_rom(args.rom, graphics_scan=args.graphics_scan,
                  segmented_scan=args.segmented_scan,
                  recover_geometry=args.recover_geometry,
                  source_aligned=args.source_aligned,
                  offline_rigs=args.offline_rigs)
    except (OSError, ValueError) as exc:
        print(f"REAL NG5E ROM: FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
