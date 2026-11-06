#!/usr/bin/env python3
"""Trace source-original N64 F3DEX display lists from *actual Skeleton Gfx roots*.

Unlike scanning every gSPVertex in the ROM and guessing the owner, this
follows the original segmented display-list pointer stored in a Skeleton
limb, then recursively interprets real G_DL calls and G_ENDDL returns.

Source: original MNSG F3DEX microcode, Goemon64Recomp patches/anime.c.
Only valid N64 Gfx addresses in source-verified segments 0x07/0x09 are
followed. Dynamic/unresolved pointers are reported, never substituted
with invented graphics. No original assets uploaded.
"""
from __future__ import annotations

from collections import Counter
import struct
from typing import Mapping

from original_segmented_scan import (
    N64_G_VTX, N64_G_TRI1, N64_G_TRI2, N64_G_ENDDL,
    N64_G_DL, n64_vtx_dma
)

MAX_COMMANDS = 65536
MAX_STACK = 32
MAX_VISITS = 4


def trace_original_display_list(
    ptr: int, banks: Mapping[int, bytes], *,
    command_budget: int = 8192, stack_budget: int = MAX_STACK,
) -> dict:
    if not 1 <= command_budget <= MAX_COMMANDS:
        raise ValueError("invalid source original DL command budget")
    if not 1 <= stack_budget <= MAX_STACK:
        raise ValueError("invalid original N64 DL stack limit")

    initial = ptr
    stack: list[int] = []
    visited = Counter()
    source_vertex_commands: list[dict] = []
    gfx_calls = []
    unknown = []
    opcodes = Counter()
    complete = False
    reason = "command_budget"
    triangles = 0
    for _ in range(command_budget):
        segment = ptr >> 24
        offset = ptr & 0xFFFFFF
        bank = banks.get(segment)
        if bank is None or offset % 8 != 0 or offset + 8 > len(bank):
            reason = "unresolved_or_unaligned_segmented_gfx"
            unknown.append(f"0x{ptr:08X}")
            break
        visited[ptr] += 1
        if visited[ptr] > MAX_VISITS:
            reason = "display_list_cycle"
            break
        w0, w1 = struct.unpack_from(">II",bank,offset)
        opcode = w0 >> 24
        opcodes[opcode] += 1
        if opcode == N64_G_VTX:
            valid = n64_vtx_dma(w0,w1,banks)
            if valid is not None:
                source_vertex_commands.append({
                    "gfx_segment":segment,
                    "command_offset":offset,
                    "gfx_pointer":f"0x{ptr:08X}",
                    "source_vertex_segment":valid[2],
                    "source_vertex_offset":w1&0xFFFFFF,
                    "vertex_count":valid[0],
                })
        elif opcode in (N64_G_TRI1, N64_G_TRI2):
            triangles += (2 if opcode==N64_G_TRI2 else 1)
        elif opcode == N64_G_DL:
            target=w1
            gfx_calls.append({
                "at":f"0x{ptr:08X}",
                "target":f"0x{target:08X}",
                "branch":(w0&0x00010000)!=0
            })
            if (w0&0x00010000)==0:
                if len(stack)>=stack_budget:
                    reason="display_list_call_stack_exceeded"
                    break
                stack.append(ptr+8)
            ptr=target
            continue
        elif opcode == N64_G_ENDDL:
            if stack:
                ptr=stack.pop()
                continue
            complete=True
            reason="enddl"
            break
        ptr += 8
    else:
        reason="command_budget_exceeded"
    return {
        "original_root_gfx_pointer":f"0x{initial:08X}",
        "complete":complete,
        "reason":reason,
        "commands_executed":sum(opcodes.values()),
        "triangle_opcode_candidates":triangles,
        "source_gspvertex_commands":source_vertex_commands,
        "gdl_calls":gfx_calls,
        "unresolved_targets":unknown,
        "opcode_counts":{f"0x{k:02X}":v for k,v in sorted(opcodes.items())},
        "graphics_sources_verified_by_ROM":True,
    }


def link_original_skeleton_gfx_roots(
    pose_doc: dict, banks: Mapping[int,bytes],
    source_mesh_manifest: dict,
) -> dict:
    if pose_doc.get("format")!="ng5e-original-rom-skeletal-poses-v1":
        raise ValueError("not source-ROM original Skeleton pose catalog")
    starts={}
    for part in source_mesh_manifest["per_display_list_objects"]:
        at=int(part["display_list_offset"])
        if at in starts:
            raise ValueError("duplicate original Gfx run start")
        starts[at]=part["local_obj_file"]

    distinct={
        bone["gfx"]
        for pose in pose_doc["original_source_poses"]
        for bone in pose["limbs"]
        if bone["gfx"]
    }
    outcomes=[]
    for ptr in sorted(distinct):
        if ptr & 0x80000000:
            outcomes.append({
                "original_root_gfx":f"0x{ptr:08X}",
                "status":"special_indirect_original_skeleton",
            })
            continue
        trace=trace_original_display_list(ptr,banks)
        matches=[]
        for vertex in trace["source_gspvertex_commands"]:
            if vertex["gfx_segment"]==9:
                off=vertex["command_offset"]
                if off in starts:
                    matches.append({
                        "original_run_start":off,
                        "model_part":starts[off],
                        "source_vertex_segment":vertex["source_vertex_segment"],
                    })
        outcomes.append({
            "original_root_gfx":f"0x{ptr:08X}",
            "status":"complete" if trace["complete"] else trace["reason"],
            "valid_gspvertex_commands":len(trace["source_gspvertex_commands"]),
            "matched_source_parts":matches,
            "gdl_calls":len(trace["gdl_calls"]),
            "candidate_triangles":trace["triangle_opcode_candidates"],
        })
    return {
        "character":pose_doc["character"],
        "source_rom_skeleton_graphics_roots":len(distinct),
        "fully_terminated_source_display_lists":sum(
            x["status"]=="complete" for x in outcomes),
        "roots_with_confirmed_mesh_parts":sum(
            bool(x.get("matched_source_parts")) for x in outcomes),
        "matched_unique_mesh_parts":len({
            item["model_part"] for result in outcomes
            for item in result.get("matched_source_parts",[])
        }),
        "sources":outcomes,
        "original_animation_timeline_decoded":False
    }
