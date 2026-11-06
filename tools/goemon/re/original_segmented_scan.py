#!/usr/bin/env python3
"""Find REAL Goemon character rendering records in the ORIGINAL decompressed ROM.

Authoritative overlay segments from klorfmorf/mnsg config/usa/splat.yaml:
  character file roots 288/292/296/300 -> N64 0x09000000 (asset_9)
  character file +3  291/295/299/303 -> N64 0x07000000 (asset_7)
The previous experimental scan ONLY accepted segment 0x08 pointers, causing
false negatives. This scanner resolves 0x09 and 0x07 *in their individual
character file banks*, not invented universal segment-8 offsets.

The scan returns ONLY integer offsets/statistics, no copyrighted geometry,
image or ROM bytes. Candidate != confirmed rig; no speculative decoding.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import struct
from typing import Mapping

from character_assets import read_file_table, character_graphics_ids

CHARACTER_ROOTS = (288, 292, 296, 300)
SOURCE_SEGMENTS = {0: 9, 3: 7}
N64_G_VTX = 0x04
N64_G_TRI1 = 0xBF
N64_G_TRI2 = 0xB1
N64_G_DL = 0x06
N64_G_ENDDL = 0xB8
LIMB_SIZE = 24

@dataclass(frozen=True)
class SegmentPointer:
    segment: int
    offset: int

def dereference_segmented(
    ptr: int, banks: Mapping[int, bytes], length: int = 1
) -> tuple[int, bytes] | None:
    if not isinstance(ptr, int) or not 0 <= ptr <= 0xFFFFFFFF:
        return None
    seg, offset = ptr >> 24, ptr & 0xFFFFFF
    bank = banks.get(seg)
    if (bank is None or offset > len(bank) or
            length < 1 or len(bank) - offset < length):
        return None
    return offset, bank

def n64_vtx_dma(
    w0: int, w1: int, banks: Mapping[int, bytes]
) -> tuple[int, int, int] | None:
    """F3DEX libultra gSPVertex: n, v0, data pointer."""
    if (w0 >> 24) != N64_G_VTX:
        return None
    n = (w0 >> 10) & 63
    encoded_slot = (w0 >> 16) & 255
    if not 1 <= n <= 32 or encoded_slot & 1 or (encoded_slot // 2) + n > 32:
        return None
    if (w0 & 0x3FF) != n * 16 - 1:
        return None
    resolved = dereference_segmented(w1, banks, n * 16)
    if resolved is None or resolved[0] % 8:
        return None
    return n, encoded_slot // 2, w1 >> 24

def validate_skeleton(
    pointer: int, banks: Mapping[int, bytes]
) -> tuple[int, int, int] | None:
    resolved = dereference_segmented(pointer, banks, LIMB_SIZE)
    if resolved is None:
        return None
    offset, bank = resolved
    if offset % 4: return None
    display, child, sibling, *transform = struct.unpack_from(">Ibb9h", bank, offset)
    if display:
        # Original renderer can mark a skeletal node with high-bit sentinel;
        # this is a potential reference, NOT a guaranteed valid Gfx DL.
        if (dereference_segmented(display & 0x0FFFFFFF, banks) is None and
                dereference_segmented(display, banks) is None):
            return None
    for displacement in (child, sibling):
        if displacement:
            next_node = offset + displacement * LIMB_SIZE
            if not 0 <= next_node <= len(bank) - LIMB_SIZE:
                return None
    if all(v == 0 for v in transform):
        return None
    return offset, child, sibling

def find_rig_header_candidates(
    root_data: bytes, banks: Mapping[int, bytes], max_hits: int = 24
) -> dict:
    """Search original 0x09 root object for AnimatedSkeleton flags and pointers.

    The semantics match Goemon64Recomp patches/types.h (flags, anim ptr,
    skeleton[]), and patches/anime.c func_80016C44_17844.
    """
    candidates: list[dict] = []
    by_segment: Counter[int] = Counter()
    count = 0
    for at in range(0, len(root_data) - 11, 4):
        flags, animation, first_limb = struct.unpack_from(">III", root_data, at)
        limbs = (flags >> 8) & 0x7FFF
        if not 1 <= limbs <= 128: continue
        # Zero and wildcard animation pointers can be valid, but a random
        # out-of-bank pointer must never pass as an actual rig candidate.
        if animation and dereference_segmented(animation, banks) is None:
            continue
        limb = validate_skeleton(first_limb, banks)
        if limb is None: continue
        count += 1
        by_segment[first_limb >> 24] += 1
        if len(candidates) < max_hits:
            candidates.append({
                "header_offset": at,
                "limb_count_from_flags": limbs,
                "skeleton_segment": first_limb >> 24,
                "first_limb_offset": limb[0],
                "child_offset": limb[1],
                "sibling_offset": limb[2],
                "animation_segment": animation >> 24,
            })
    return {
        "candidate_count": count,
        "first_candidates": candidates,
        "candidate_skeleton_segments": {
            f"0x{k:02X}": v for k, v in sorted(by_segment.items())
        },
        "note": "Structural candidates only; object root/pointer linkage still needed",
    }

def scan_segmented_graphics(
    data: bytes, banks: Mapping[int, bytes], max_hits: int = 24
) -> dict:
    """Count the real F3DEX commands whose DMA addresses resolve in the
    attached 0x09/0x07 resources; do not assign ownership heuristically."""
    opcodes: Counter[int] = Counter()
    triangle_commands = 0
    vtx_count = 0
    display_list_targets = 0
    first_vtx: list[dict] = []
    for at in range(0, len(data) - 7, 8):
        w0, w1 = struct.unpack_from(">II", data, at)
        opcode = w0 >> 24
        opcodes[opcode] += 1
        valid_dma = n64_vtx_dma(w0, w1, banks)
        if valid_dma:
            vtx_count += 1
            if len(first_vtx) < max_hits:
                first_vtx.append({
                    "command_offset": at,
                    "vertices": valid_dma[0],
                    "first_cache_slot": valid_dma[1],
                    "source_segment": valid_dma[2],
                    "vertex_data_offset": w1 & 0xFFFFFF,
                })
        if opcode in (N64_G_TRI1, N64_G_TRI2):
            triangle_commands += 1
        elif opcode == N64_G_DL and dereference_segmented(w1, banks, 8):
            display_list_targets += 1
    return {
        "valid_segmented_f3dex_vtx_dmas": vtx_count,
        "raw_f3dex_triangle_command_candidates": triangle_commands,
        "resolved_display_list_targets": display_list_targets,
        "first_valid_vertex_dmas": first_vtx,
        "source_segment_scope": ["0x07", "0x09"],
        "note": "Counted commands are not proof of renderable mesh ownership",
    }

def scan_original_character_group(rom: bytes, character_slot: int) -> dict:
    if not 0 <= character_slot <= 3:
        raise ValueError("character slot must be 0..3")
    table = read_file_table(rom)
    roots = character_graphics_ids(rom, table)
    if tuple(roots) != CHARACTER_ROOTS:
        raise ValueError("original character file ids do not match verified US source")
    root = roots[character_slot]
    files = {i: rom[table[root + i].start:table[root + i].end] for i in range(4)}
    banks = {9: files[0], 7: files[3]}
    # Character +1/+2 PIC/other resources were observed as file-loaded
    # separate data with no stable 0x08 segment-base mapping. Do not
    # invent one or treat 0x08 as the file's own address.
    graphics = {
        str(index): {
            "file_id": root + index,
            "byte_length": len(files[index]),
            "declared_segment": f"0x{SOURCE_SEGMENTS[index]:02X}"
                if index in SOURCE_SEGMENTS else None,
            **scan_segmented_graphics(files[index], banks),
        }
        for index in range(4)
    }
    rig = find_rig_header_candidates(files[0], banks)
    return {
        "character_slot": character_slot,
        "source_graphics_file_ids": [root, root + 1, root + 2, root + 3],
        "segmented_resources": {"0x09": root, "0x07": root + 3},
        "files": graphics,
        "rig_headers_in_root_file": rig,
        "provenance": "mnsg/config/usa/splat.yaml + Goemon64Recomp/patches/types.h",
        "copyrighted_data_exported": False,
    }
