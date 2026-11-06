#!/usr/bin/env python3
"""Decode original F3DEX/RSP triangle geometry from a verified NG5E asset.

Uses N64 big-endian Gfx (8 bytes) and Vtx (16 bytes). The F3DEX opcodes
and index packing follow libultra/include/PR/gbi.h as pinned by the
Mystical Ninja decompilation project (not speculative DirectX geometry).

This deliberately extracts *only geometry*: texture/palette state, the
original limb transform/animation matrices and lighting remain separate.
Unsupported commands that would change vertex geometry fail closed.
A source-owned ROM or local original character file is required. Never
commit output meshes or original character assets to this repository.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import struct

# Goemon64Recomp's pinned N64 gbi.h, F3DEX_GBI, not F3DEX2:
G_VTX = 0x04
G_DL = 0x06
G_TRI1 = 0xBF
G_TRI2 = 0xB1
G_ENDDL = 0xB8
G_MTX = 0x01
G_MODIFYVTX = 0xB2
MAX_VERTEX_CACHE = 32

@dataclass(frozen=True)
class N64Vertex:
    x: int
    y: int
    z: int
    flags: int
    s: int
    t: int
    c0: int
    c1: int
    c2: int
    alpha: int

@dataclass(frozen=True)
class N64Mesh:
    vertices: tuple[N64Vertex, ...]
    faces: tuple[tuple[int, int, int], ...]
    source_display_list_offset: int
    commands: int
    ignored_opcodes: dict[str, int]

class UnsupportedGeometryCommand(ValueError):
    pass

def _file_offset(pointer: int, length: int, overlay_base: int) -> int:
    """Resolve ONLY known original segment-8 or recorded KSEG0 addresses."""
    if not (0 <= pointer <= 0xFFFFFFFF):
        raise ValueError("out-of-range N64 pointer")
    if pointer >> 24 == 8:
        offset = pointer & 0xFFFFFF
    elif pointer & 0x80000000 and overlay_base:
        offset = pointer - overlay_base
    else:
        raise ValueError(f"unsupported original N64 graphics pointer 0x{pointer:08X}")
    if not 0 <= offset < length:
        raise ValueError(f"N64 graphics pointer outside original resource: 0x{pointer:08X}")
    return offset

def _load_vertex(data: bytes, offset: int) -> N64Vertex:
    if offset < 0 or offset + 16 > len(data):
        raise ValueError("original N64 vertex extends outside file")
    return N64Vertex(*struct.unpack_from(">hhhHhhBBBB", data, offset))

def _decode_triangle_indices(word: int) -> tuple[int, int, int]:
    raw = ((word >> 16) & 255, (word >> 8) & 255, word & 255)
    if any(x & 1 or x >= 64 for x in raw):
        raise ValueError("invalid F3DEX triangle vertex cache index")
    return raw[0] // 2, raw[1] // 2, raw[2] // 2

def decode_f3dex(
    data: bytes, display_list_pointer: int, *,
    overlay_base: int = 0, max_commands: int = 65536,
    max_depth: int = 32,
) -> N64Mesh:
    """Read G_VTX, G_TRI1/G_TRI2, G_DL, G_ENDDL with shared vertex cache.

    Ignore RDP texture/material commands but reject transform and vertex
    modification commands that would make raw positions inaccurate.
    Each emitted face owns immutable copies of its three source vertices.
    """
    if max_commands < 1 or max_depth < 1:
        raise ValueError("invalid N64 command/depth budget")
    pc = _file_offset(display_list_pointer, len(data), overlay_base)
    if pc % 8:
        raise ValueError("N64 display-list pointer must be eight-byte aligned")
    first_pc = pc
    return_stack: list[int] = []
    active = set()
    cache: list[N64Vertex | None] = [None] * MAX_VERTEX_CACHE
    vertices: list[N64Vertex] = []
    faces: list[tuple[int, int, int]] = []
    ignored: Counter[int] = Counter()
    count = 0
    # Remember the current call chain to reject recursive display lists.
    active.add(pc)
    while True:
        if count >= max_commands:
            raise ValueError("N64 display-list command budget exceeded")
        if pc < 0 or pc + 8 > len(data):
            raise ValueError("unterminated or out-of-bounds original display list")
        w0, w1 = struct.unpack_from(">II", data, pc)
        count += 1
        command = w0 >> 24
        following = pc + 8

        if command == G_VTX:
            n = (w0 >> 10) & 63
            encoded_v0 = (w0 >> 16) & 255
            if not n or n > MAX_VERTEX_CACHE or encoded_v0 & 1:
                raise ValueError("invalid F3DEX vertex command count/index")
            v0 = encoded_v0 // 2
            if v0 + n > MAX_VERTEX_CACHE or (w0 & 1023) != n * 16 - 1:
                raise ValueError("invalid F3DEX vertex DMA length/cache bounds")
            source = _file_offset(w1, len(data), overlay_base)
            if source % 8 or source + n * 16 > len(data):
                raise ValueError("misaligned or truncated original vertex DMA")
            for i in range(n):
                cache[v0 + i] = _load_vertex(data, source + i * 16)
        elif command in (G_TRI1, G_TRI2):
            words = [w1] if command == G_TRI1 else [w0, w1]
            for word in words:
                indices = _decode_triangle_indices(word)
                if any(cache[x] is None for x in indices):
                    raise ValueError("F3DEX face references unloaded original vertices")
                next_idx = len(vertices)
                vertices.extend(cache[x] for x in indices)
                faces.append((next_idx, next_idx + 1, next_idx + 2))
        elif command == G_DL:
            target = _file_offset(w1, len(data), overlay_base)
            if target % 8:
                raise ValueError("unaligned original display-list jump")
            branch = (w0 >> 16) & 255
            if branch not in (0, 1):
                raise ValueError("unsupported original display-list branch mode")
            if branch == 0:
                if len(return_stack) >= max_depth:
                    raise ValueError("N64 display-list nesting limit exceeded")
                return_stack.append(following)
                active.add(target)
            pc = target
            if branch == 1:
                active.add(target)
            continue
        elif command == G_ENDDL:
            if return_stack:
                pc = return_stack.pop()
                continue
            break
        elif command in (G_MTX, G_MODIFYVTX):
            raise UnsupportedGeometryCommand(
                f"original display list changes vertex geometry (opcode 0x{command:02X})"
            )
        elif command in (0x01, 0x05, 0xDE, 0xDF):
            # These are F3DEX2 meanings; do not silently interpret them.
            raise UnsupportedGeometryCommand(
                f"possible F3DEX2 microcode command 0x{command:02X}"
            )
        else:
            ignored[command] += 1
        pc = following
    if not faces:
        raise ValueError("no F3DEX triangles in original display list")
    return N64Mesh(
        tuple(vertices), tuple(faces), first_pc, count,
        {f"0x{k:02X}": v for k, v in sorted(ignored.items())},
    )

def mesh_to_obj(mesh: N64Mesh, *, name: str = "Goemon_original") -> str:
    """Geometry-only Wavefront OBJ: original raw limb coordinates, no textures."""
    if not mesh.faces:
        raise ValueError("cannot export empty original N64 geometry")
    if any(max(face) >= len(mesh.vertices) or min(face) < 0 for face in mesh.faces):
        raise ValueError("invalid reconstructed original triangle indices")
    safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in name)
    lines = [
        "# Geometry from original N64 F3DEX commands",
        "# Raw limb-local positions. Original N64 matrices, material and UV scale NOT applied.",
        f"o {safe_name}",
    ]
    for v in mesh.vertices:
        lines.append(f"v {v.x} {v.y} {v.z}")
    for a, b, c in mesh.faces:
        lines.append(f"f {a + 1} {b + 1} {c + 1}")
    return "\n".join(lines) + "\n"
