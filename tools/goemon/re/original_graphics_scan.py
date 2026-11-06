#!/usr/bin/env python3
"""Locate plausible original F3DEX command streams in NG5E character assets.

Read-only and metadata-only. A valid DMA reference to in-file source vertex
bytes is a stronger signal than simply counting 0x04 bytes. Candidates are
NOT declared a reconstructed model until linked to an original rig pointer.
This is used to choose the next real decoder work without publishing ROM bytes.
"""
from __future__ import annotations

from collections import Counter
import struct

from original_f3dex_geometry import G_VTX, G_TRI1, G_TRI2, G_ENDDL, G_DL

def valid_f3dex_vertex_dma(data: bytes, at: int) -> tuple[int, int] | None:
    if at < 0 or at % 8 or at + 8 > len(data):
        return None
    w0, ptr = struct.unpack_from(">II", data, at)
    if w0 >> 24 != G_VTX:
        return None
    n = (w0 >> 10) & 63
    v0_encoded = (w0 >> 16) & 255
    if not 1 <= n <= 32 or (v0_encoded & 1):
        return None
    if v0_encoded // 2 + n > 32 or (w0 & 1023) != n * 16 - 1:
        return None
    if (ptr >> 24) != 8:
        return None
    source = ptr & 0xFFFFFF
    if source % 8 or source + n * 16 > len(data):
        return None
    return n, source

def scan_original_graphics_resource(data: bytes) -> dict:
    """Collect evidence, not asset bytes or guessed skeleton ownership."""
    dmas = []
    ends = []
    tri1 = 0
    tri2 = 0
    segment8_pointers = 0
    for i in range(0, len(data) - 7, 8):
        w0, w1 = struct.unpack_from(">II", data, i)
        opcode = w0 >> 24
        candidate = valid_f3dex_vertex_dma(data, i)
        if candidate is not None:
            dmas.append((i, candidate[0], candidate[1]))
        if opcode == G_ENDDL and w1 == 0:
            ends.append(i)
        elif opcode == G_TRI1:
            tri1 += 1
        elif opcode == G_TRI2:
            tri2 += 1
        if w1 >> 24 == 8 and (w1 & 0xFFFFFF) < len(data):
            segment8_pointers += 1

    # Conservative candidate AnimatedSkeleton: flags, Animation*,
    # Skeleton*; the latter has a verified pointer inside THIS file.
    rig_candidates = []
    for offset in range(0, len(data) - 11, 4):
        flags, animation, skel_ptr = struct.unpack_from(">III", data, offset)
        bones = (flags >> 8) & 0x7FFF
        if bones < 1 or bones > 128:
            continue
        if skel_ptr >> 24 != 8:
            continue
        root = skel_ptr & 0xFFFFFF
        if root % 4 or root + 24 > len(data):
            continue
        # A plausible original skeleton must reference its own limb
        # structure, and at least one child/sibling offset must be in-file.
        right, left = struct.unpack_from(">bb", data, root + 4)
        if ((right and not 0 <= root + right * 24 <= len(data) - 24) or
            (left and not 0 <= root + left * 24 <= len(data) - 24)):
            continue
        dlist_ptr = struct.unpack_from(">I", data, root)[0]
        if dlist_ptr and (dlist_ptr >> 24 != 8 or
                          (dlist_ptr & 0xFFFFFF) >= len(data)):
            continue
        rig_candidates.append(offset)
    return {
        "file_length": len(data),
        "valid_f3dex_vertex_dmas": len(dmas),
        "f3dex_tri1_opcode_candidates": tri1,
        "f3dex_tri2_opcode_candidates": tri2,
        "f3dex_enddl_opcode_candidates": len(ends),
        "in_file_segment8_second_words": segment8_pointers,
        "animated_skeleton_header_candidates": len(rig_candidates),
        "first_vtx_dma_offsets": [d[0] for d in dmas[:12]],
        "first_rig_header_offsets": rig_candidates[:12],
        "interpretation": (
            "F3DEX/rig structural candidates, NOT confirmed mesh, "
            "skeleton ownership, texture or character rendering"
        )
    }
