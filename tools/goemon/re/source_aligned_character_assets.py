#!/usr/bin/env python3
"""Cross-validate original NG5E file-table IDs against the decomp splat.yaml.

CRITICAL: klorfmorf/mnsg/config/usa/splat.yaml names its files ONE HIGHER
than read_file_table() of the decompressed ROM. This is an independently
checkable exact ROM offset relationship, not a heuristic based on sizes.

Previously our character extractor incorrectly interpreted actual file 291
as source 'file_291' (0x07). In fact:
    runtime ID 290 -> splat file_291 -> N64 segment 0x07
    runtime ID 291 -> splat file_292 -> N64 segment 0x09
and Yae:
    runtime ID 302 -> splat file_303 -> N64 segment 0x07
    runtime ID 303 -> splat file_304 -> N64 segment 0x08

Source: klorfmorf/mnsg/config/usa/splat.yaml, main at 2026-11-06.
File offsets are validated exactly before any original graphics decoding.
No game assets or ROM data are uploaded or printed by this module.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import struct
from character_assets import character_graphics_ids, read_file_table
from original_segmented_scan import scan_segmented_graphics, find_rig_header_candidates

# (decomp splat file ID, uncompressed absolute ROM start, N64 virtual segment)
# Direct source transcription of splat.yaml's file_289 through file_305.
SOURCE_SPLAT_GROUP_FILES = (
    (289, 0xE2AE80, 0),
    (290, 0xE39E80, 0),
    (291, 0xE3C1C0, 7),
    (292, 0xE6ABA0, 9),
    (293, 0xE72890, 0),
    (294, 0xE79890, 0),
    (295, 0xE7C030, 7),
    (296, 0xEABC20, 9),
    (297, 0xEB41A0, 0),
    (298, 0xEC11A0, 0),
    (299, 0xEC3880, 7),
    (300, 0xEFA790, 9),
    (301, 0xF04C60, 0),
    (302, 0xF11C60, 0),
    (303, 0xF14610, 7),
    (304, 0xF54EA0, 8),
    (305, 0xF55070, 8),
)
CHARACTER_NAMES = ("Goemon","Ebisumaru","Sasuke","Yae")

@dataclass(frozen=True)
class SourceAlignedFile:
    runtime_file_id: int
    splat_file_id: int
    source_start: int
    size: int
    source_segment: int

def source_align_character_files(rom: bytes) -> tuple[tuple[SourceAlignedFile, ...], ...]:
    table = read_file_table(rom)
    roots = character_graphics_ids(rom, table)
    if tuple(roots) != (288, 292, 296, 300):
        raise ValueError("not verified NG5E character file roots")
    source = {id: (offset, segment) for id, offset, segment in
              SOURCE_SPLAT_GROUP_FILES}
    groups = []
    for root in roots:
        current = []
        for real_file in range(root, root+4):
            splat_file_id = real_file+1
            expected_start, segment = source[splat_file_id]
            entry = table[real_file]
            if entry.start != expected_start:
                raise ValueError(
                    "splat.yaml file index mismatch: runtime "
                    f"{real_file} / source file_{splat_file_id}, "
                    f"ROM 0x{entry.start:X} != source 0x{expected_start:X}")
            # The next splat entry names the end of this one. It must
            # agree with the game's own table length EXACTLY.
            expected_end = source[splat_file_id+1][0]
            if entry.end != expected_end:
                raise ValueError(
                    f"source file_{splat_file_id} end mismatch: "
                    f"ROM 0x{entry.end:X} != 0x{expected_end:X}")
            current.append(SourceAlignedFile(
                real_file, splat_file_id, entry.start, entry.size, segment))
        groups.append(tuple(current))
    return tuple(groups)

def analyze_source_aligned_rom(rom: bytes) -> dict:
    table = read_file_table(rom)
    groups = source_align_character_files(rom)
    result = []
    for slot, (files0, files1, files2, files3) in enumerate(groups):
        root = groups[slot][0].runtime_file_id
        raw = {
            i: rom[table[root+i].start:table[root+i].end] for i in range(4)
        }
        banks = {files2.source_segment: raw[2],
                 files3.source_segment: raw[3]}
        if set(banks) != ({7, 9} if slot < 3 else {7,8}):
            raise ValueError("inconsistent splat.yaml source segments")
        scans = {}
        for i, file in enumerate(groups[slot]):
            report = scan_segmented_graphics(raw[i], banks)
            scans[str(file.runtime_file_id)] = {
                "source_file": file.splat_file_id,
                "splat_segment": f"0x{file.source_segment:02X}",
                "bytes": file.size,
                "valid_vertex_dmas": report["valid_segmented_f3dex_vtx_dmas"],
                "vertex_source_segments":
                    report["raw_vtx_source_segments"],
                "triangle_opcode_candidates":
                    report["raw_f3dex_triangle_command_candidates"],
                "resolved_dl_targets":
                    report["resolved_display_list_targets"],
                "valid_vertex_command_samples":
                    report["first_valid_vertex_dmas"][:5]
            }
        rigs = {}
        for i, file in enumerate(groups[slot]):
            report = find_rig_header_candidates(raw[i], banks, max_hits=5)
            rigs[str(file.runtime_file_id)] = {
                "count": report["candidate_count"],
                "examples": report["first_candidates"],
            }
        result.append({
            "slot":slot, "character_name":CHARACTER_NAMES[slot],
            "splat_file_id_offset":1,
            "confirmed_segment_banks": {
                f"0x{k:02X}": root+(2 if k==7 else 3)
                for k in sorted(banks)
            },
            "files": scans,
            "structural_rig_candidates_unverified": rigs,
        })
    return {
        "source": "splat.yaml source file labels correlated with uncompressed NG5E ROM table by exact bytes",
        "verified_index_offset": 1,
        "source_aligned_character_groups": result,
        "prior_decoded_geometry_validity": "UNVERIFIED: previous extractor used the wrong source segment bank",
        "assets_uploaded": False
    }
