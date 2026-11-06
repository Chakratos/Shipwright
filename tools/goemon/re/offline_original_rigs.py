#!/usr/bin/env python3
"""Reconstruct candidate ORIGINAL MNSG animated skeleton graphs OFFLINE from ROM.

Uses the verified splat.yaml +1 ROM index alignment. No game running,
no manual capture, no external OBJ, and NO invented animation frames.

Goemon64Recomp/patches/types.h: 24-byte Skeleton struct; anime.c:
func_80018CA0_198A0 follows signed child/sibling offsets relative to the
current Skeleton pointer and accesses display-list pointers separately.
func_80016C44_17844 (type 0x60000000) dereferences AnimatedSkeleton
at the current overlay base.

This is a structural pointer-graph analyzer, NOT proof of an active player
skeleton or decoded keyframe clip. Results are grounded to exact ROM offsets.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import struct
from typing import Mapping

from character_assets import read_file_table
from source_aligned_character_assets import (
    CHARACTER_NAMES, source_align_character_files
)

SKELETON = struct.Struct(">Ibb9h")
ANIMATED = struct.Struct(">III")
MAX_NODES = 128

@dataclass(frozen=True)
class SkeletalNode:
    pointer: int
    graphics_pointer: int
    child: int
    sibling: int
    scale: tuple[int,int,int]
    rotation: tuple[int,int,int]
    translation: tuple[int,int,int]


def read_skeletal_node(
    ptr: int, banks: Mapping[int, bytes]
) -> SkeletalNode:
    seg = ptr >> 24
    data = banks.get(seg)
    off = ptr & 0xFFFFFF
    if data is None or off % 4 or off < 0 or off + SKELETON.size > len(data):
        raise ValueError("skeleton limb outside original source segment")
    dlist, child, sibling, *transform = SKELETON.unpack_from(data, off)
    if dlist and not (dlist & 0x80000000):
        target = banks.get(dlist >> 24)
        # The source allows 0x08000000 as a special overlay-zero pointer.
        # If this cannot be resolved OFFLINE, reject the candidate instead
        # of accepting unrelated random binary as model geometry.
        if target is None or (dlist & 0xFFFFFF) >= len(target):
            raise ValueError("source skeleton has unresolved graphics pointer")
    return SkeletalNode(ptr, dlist, child, sibling,
                        tuple(transform[:3]), tuple(transform[3:6]),
                        tuple(transform[6:9]))


def traverse_original_skeleton(
    ptr: int, banks: Mapping[int, bytes], *,
    max_nodes: int = MAX_NODES
) -> dict:
    if max_nodes < 1 or max_nodes > MAX_NODES:
        raise ValueError("invalid skeleton traversal budget")
    visited: set[int] = set()
    stack: list[tuple[int, int | None, str]] = [(ptr, None, "root")]
    nodes: list[dict] = []
    while stack:
        current, parent, relation = stack.pop()
        if current in visited:
            raise ValueError("source skeleton contains a cycle/shared limb")
        if len(visited) >= max_nodes:
            raise ValueError("source skeleton exceeds limb budget")
        node = read_skeletal_node(current, banks)
        visited.add(current)
        nodes.append({
            "ptr": current,
            "parent": parent,
            "relation": relation,
            "gfx": node.graphics_pointer,
            "child": node.child,
            "sibling": node.sibling,
            "scale": node.scale,
            "rotation": node.rotation,
            "translation": node.translation,
        })
        # A sibling shares the current parent. Child is parented to
        # the current node. These 24-byte strides are source-proven.
        if node.sibling:
            stack.append((current + 24*node.sibling,
                          parent, "sibling"))
        if node.child:
            stack.append((current + 24*node.child,
                          current, "child"))
    return {
        "root_pointer": ptr,
        "limbs": len(nodes),
        "graphics_limb_count": sum(x["gfx"] != 0 for x in nodes),
        "graphics_segments": sorted({f"0x{x['gfx'] >> 24:02X}"
                                    for x in nodes if x["gfx"]}),
        "nodes": nodes,
    }


def candidate_animated_skeletons(
    banks: Mapping[int, bytes], *,
    min_limbs: int = 4,
    max_candidates: int = 24
) -> dict:
    """Enumerate AnimatedSkeleton headers, verify entire linked graphs.

    Reject partial/out-of-bank/cyclic linkages. A plausible pointer graph
    is NOT enough to assert it is the active character rig.
    """
    if not 2 <= min_limbs <= MAX_NODES:
        raise ValueError("invalid original skeleton minimum")
    count = 0
    good: list[dict] = []
    reasons = {}
    seen_roots: set[int] = set()
    for seg, data in sorted(banks.items()):
        for offset in range(0, len(data) - ANIMATED.size + 1, 4):
            flags, animation, bone_ptr = ANIMATED.unpack_from(data, offset)
            limb_count_hint = (flags >> 8) & 0x7FFF
            if not 1 <= limb_count_hint <= MAX_NODES:
                continue
            if (bone_ptr == 0 or bone_ptr in seen_roots or
                    (bone_ptr >> 24) not in banks):
                continue
            if animation != 0 and not (animation & 0x80000000):
                source = banks.get(animation >> 24)
                if source is None or (animation & 0xFFFFFF) >= len(source):
                    continue
            try:
                hierarchy = traverse_original_skeleton(bone_ptr, banks)
            except ValueError:
                continue
            if hierarchy["limbs"] < min_limbs:
                continue
            seen_roots.add(bone_ptr)
            count += 1
            if len(good) < max_candidates:
                good.append({
                    "header_segment": f"0x{seg:02X}",
                    "header_offset": offset,
                    "flags": f"0x{flags:08X}",
                    "animation_pointer": f"0x{animation:08X}",
                    "root_skeleton_pointer": f"0x{bone_ptr:08X}",
                    "limb_count_hint": limb_count_hint,
                    "actual_traversed_limbs": hierarchy["limbs"],
                    "graphics_limb_count": hierarchy["graphics_limb_count"],
                    "graphics_segments": hierarchy["graphics_segments"],
                    "first_nodes": hierarchy["nodes"][:3],
                })
    return {
        "structurally_valid_candidate_count":count,
        "first_valid_candidates":good,
        "min_limb_count":min_limbs,
        "runtime_player_identity_proven":False,
        "animation_sequence_decoded":False
    }


def scan_yae_shared_09_hypotheses(rom: bytes) -> list[dict]:
    """Check the remaining source 0x09 asset banks when Yae only lists 07/08.

    The user's known ROM confirms source splat file_303 (runtime 302)
    is a 264336-byte 0x07 bank, while runtime 303 is a 464-byte 0x08
    bank. An original 0x09 overlay may remain resident from the prior
    group; test exact source-listed 0x09 banks, without asserting which
    was actually resident in the active game scene.
    """
    table = read_file_table(rom)
    groups = source_align_character_files(rom)
    yae = groups[3]
    base = {}
    for file in yae[2:4]:
        entry = table[file.runtime_file_id]
        base[file.source_segment] = rom[entry.start:entry.end]
    outcomes = []
    for source_slot in range(3):
        from_source = groups[source_slot][3]
        if from_source.source_segment != 9:
            raise ValueError("source candidate not mapped at 0x09")
        entry = table[from_source.runtime_file_id]
        shared = rom[entry.start:entry.end]
        candidate_banks = {**base, 9:shared}
        candidates = candidate_animated_skeletons(
            candidate_banks, min_limbs=4, max_candidates=6
        )
        outcomes.append({
            "splat_file": from_source.splat_file_id,
            "actual_runtime_file": from_source.runtime_file_id,
            "hypothesis_not_runtime_confirmed": True,
            "valid_structural_graphs": candidates["structurally_valid_candidate_count"],
            "samples": candidates["first_valid_candidates"],
        })
    return outcomes


def scan_offline_original_rom(rom: bytes) -> dict:
    groups = source_align_character_files(rom)
    table = read_file_table(rom)
    result = []
    for slot, files in enumerate(groups):
        bank2, bank3 = files[2], files[3]
        banks = {
            bank2.source_segment: rom[
                table[bank2.runtime_file_id].start:table[bank2.runtime_file_id].end
            ],
            bank3.source_segment: rom[
                table[bank3.runtime_file_id].start:table[bank3.runtime_file_id].end
            ],
        }
        found = candidate_animated_skeletons(banks)
        result.append({
            "character_slot":slot,
            "name":CHARACTER_NAMES[slot],
            "source_banks": {
                f"0x{segment:02X}":file.runtime_file_id
                for segment, file in ((bank2.source_segment,bank2),
                                       (bank3.source_segment,bank3))
            },
            **found
        })
    return {
        "analysis": "ROM-only source-mapped N64 Skeleton graphs",
        "source": "klorfmorf/mnsg splat + Goemon64Recomp types.h/anime.c",
        "gameplay_capture_required":False,
        "source_rom_hash_verified_externally":True,
        "characters":result,
        "yae_candidate_shared_segment09": scan_yae_shared_09_hypotheses(rom),
        "limitations":[
            "Structural graph consistency is not proof of player animation ownership",
            "Original keyframe data and active action mapping not yet decoded",
            "No commercial asset bytes exported"
        ]
    }
