#!/usr/bin/env python3
"""Decode ORIGINAL segmented N64 skeletal-limb meshes from the actual limb Gfx root.

Unlike broad raw-ROM gSPVertex scanning, this starts at each source Skeleton's
graphics pointer and executes real F3DEX G_DL call/return, shared vertex cache,
G_VTX/G_TRI1/G_TRI2 and G_ENDDL. Results retain *limb-local coordinates*.
All decoded positions and triangle indices are from the user's verified ROM.

RDP/TMEM texture state is not yet decoded. Unsupported commands that modify
geometry fail closed; no "model" gets invented to fill gaps.
"""
from __future__ import annotations

from collections import Counter
import struct
from typing import Mapping

from original_f3dex_geometry import N64Mesh, N64Vertex
from original_segmented_geometry import N64_VERTEX_STRUCT, _triangle_slots
from original_segmented_scan import (
    N64_G_VTX, N64_G_TRI1, N64_G_TRI2, N64_G_ENDDL,
    N64_G_DL, n64_vtx_dma
)

MAX_COMMANDS=20000
MAX_FACES=30000
MAX_CALLS=32


def decode_original_limb_mesh(
    source_gfx_pointer: int,
    banks: Mapping[int,bytes],
    *, max_commands:int=MAX_COMMANDS
) -> N64Mesh:
    if source_gfx_pointer == 0:
        raise ValueError("empty original skeletal graphics pointer")
    if not 1 <= max_commands <= MAX_COMMANDS:
        raise ValueError("original F3DEX command budget invalid")
    if 9 not in banks or 7 not in banks:
        raise ValueError("source N64 limb needs real 0x07 and 0x09 banks")
    pc=source_gfx_pointer
    original_pc=pc
    cache:list[N64Vertex|None]=[None]*32
    faces=[]
    vertices=[]
    ignored=Counter()
    callstack:list[int]=[]
    count=0

    while count < max_commands:
        seg=pc>>24
        source=banks.get(seg)
        off=pc&0xFFFFFF
        if source is None or off%8 or off+8>len(source):
            raise ValueError(f"original N64 Gfx pointer unresolved 0x{pc:08X}")
        w0,w1=struct.unpack_from(">II",source,off)
        op=w0>>24
        count+=1
        next_pc=pc+8
        if op==N64_G_VTX:
            checked=n64_vtx_dma(w0,w1,banks)
            if checked is None:
                raise ValueError(f"invalid original gSPVertex at 0x{pc:08X}")
            n,v0,src_seg=checked
            src=banks[src_seg]
            pos=w1&0xFFFFFF
            for i in range(n):
                cache[v0+i]=N64Vertex(*N64_VERTEX_STRUCT.unpack_from(
                    src,pos+i*16))
        elif op in (N64_G_TRI1,N64_G_TRI2):
            words=(w1,) if op==N64_G_TRI1 else (w0,w1)
            for word in words:
                a,b,c=_triangle_slots(word)
                if any(cache[x] is None for x in (a,b,c)):
                    raise ValueError(f"original N64 triangle before vertex DMA at 0x{pc:08X}")
                index=len(vertices)
                vertices.extend((cache[a],cache[b],cache[c]))
                faces.append((index,index+1,index+2))
                if len(faces)>MAX_FACES:
                    raise ValueError("source original limb exceeds face count limit")
        elif op==N64_G_DL:
            branch=(w0>>16)&255
            if branch not in (0,1):
                raise ValueError("invalid F3DEX gSPDisplayList branch opcode")
            target=w1
            t_bank=banks.get(target>>24)
            t_off=target&0xFFFFFF
            if t_bank is None or t_off%8 or t_off+8>len(t_bank):
                raise ValueError(f"unresolved original N64 child display list 0x{target:08X}")
            if branch==0:
                if len(callstack)>=MAX_CALLS:
                    raise ValueError("original N64 DL stack exceeded")
                callstack.append(next_pc)
            pc=target
            continue
        elif op==N64_G_ENDDL:
            if w1:
                raise ValueError("invalid original gSPEndDisplayList parameters")
            if callstack:
                pc=callstack.pop()
                continue
            if not faces:
                raise ValueError("source original display list has no triangles")
            return N64Mesh(
                tuple(vertices),tuple(faces),original_pc,count,
                {f"0x{k:02X}":n for k,n in sorted(ignored.items())})
        elif op in (0x01,0xB2,0x05,0xDE,0xDF):
            raise ValueError(f"unsupported original geometry state opcode 0x{op:02X}")
        else:
            # RDP color/texture/lighting commands change APPEARANCE
            # but not the original vertex coordinates or triangle layout.
            ignored[op]+=1
        pc=next_pc
    raise ValueError("original N64 source display-list command limit exhausted")


def decode_all_character_skeletal_meshes(
    pose_catalog:dict,banks:Mapping[int,bytes]
) -> dict:
    if pose_catalog.get("format")!="ng5e-original-rom-skeletal-poses-v1":
        raise ValueError("expected authentic ROM-authored Skeleton catalog")
    unique=sorted({
        bone["gfx"]
        for record in pose_catalog["original_source_poses"]
        for bone in record["limbs"]
        if bone["gfx"]
    })
    meshes={}
    failure_reason=Counter()
    failures=[]
    for ptr in unique:
        try:
            decoded=decode_original_limb_mesh(ptr,banks)
            meshes[f"0x{ptr:08X}"]=decoded
        except ValueError as error:
            failure_reason[str(error).split(" at ")[0]]+=1
            failures.append({
                "original_display_list_pointer":f"0x{ptr:08X}",
                "reason":str(error),
            })
    return {
        "character":pose_catalog["character"],
        "source_original_limb_gfx_count":len(unique),
        "fully_decoded_limb_meshes":len(meshes),
        "decoded_source_triangles":sum(len(m.faces) for m in meshes.values()),
        "decode_failures":failures,
        "failure_reasons":dict(sorted(failure_reason.items())),
        "source_meshes":meshes,
        "textures_decoded":False,
        "animation_timing_verified":False,
    }
