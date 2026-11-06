#!/usr/bin/env python3
"""Recover source-ROM character geometry from ORIGINAL segment 7 Gfx streams.

Goemon / Ebisumaru / Sasuke F3DEX commands live in file root+3 at 0x07,
with gSPVertex DMA pointing back into the root graphics file mapped at 0x09.
These mappings were verified against mnsg/config/usa/splat.yaml and the
user's unmodified original NG5E ROM by original_segmented_scan.py.

This decoder recovers geometry-only contiguous source display-list RUNS
from actual gSPVertex command boundaries. Ownership, original skeleton
joints, animations and material/texture state are NOT guessed. No source
ROM/asset bytes are ever printed or uploaded. Explicit file outputs local.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import struct
import sys

from character_assets import read_file_table, character_graphics_ids
from original_f3dex_geometry import N64Mesh, N64Vertex, mesh_to_obj
from original_segmented_scan import (
    CHARACTER_ROOTS, N64_G_VTX, N64_G_TRI1, N64_G_TRI2, N64_G_ENDDL,
    N64_G_DL, n64_vtx_dma,
)

N64_VERTEX_STRUCT = struct.Struct(">hhhHhhBBBB")
TRI_INDEX_SCALE = 2
MAX_COMMANDS_PER_RUN = 65536
MAX_TOTAL_FACES = 150000
MAX_RUNS = 2000

@dataclass(frozen=True)
class OriginalGeometryRun:
    start: int
    end: int
    vertex_commands: int
    triangles: int
    terminated_by_enddl: bool
    stop_reason: str

@dataclass(frozen=True)
class OriginalGeometryRecovery:
    mesh: N64Mesh | None
    runs: tuple[OriginalGeometryRun, ...]
    skipped_invalid_faces: int
    source_file_id: int

def _triangle_slots(word: int) -> tuple[int, int, int]:
    raw = ((word >> 16) & 255, (word >> 8) & 255, word & 255)
    if any(n >= 64 or n & 1 for n in raw):
        raise ValueError("invalid F3DEX original triangle cache references")
    return (raw[0] // TRI_INDEX_SCALE,
            raw[1] // TRI_INDEX_SCALE,
            raw[2] // TRI_INDEX_SCALE)

def decode_original_segmented_geometry(
    geometry_file: bytes, vertex_file: bytes, *, source_file_id: int = 291,
    source_banks: dict[int, bytes] | None = None,
) -> OriginalGeometryRecovery:
    """Read only vertex-backed, in-file commands and valid triangles.

    Any actual F3DEX run begins with source instructions loading vertices.
    We recover independent gSPVertex -> triangle -> gSPEndDisplayList
    regions without falsely claiming recovered skeletal ownership.
    """
    banks = (dict(source_banks) if source_banks is not None
             else {7: geometry_file, 9: vertex_file})
    if len(banks) < 2 or 7 not in banks or 9 not in banks:
        raise ValueError("source ROM F3DEX recovery requires mapped 0x07 and 0x09 banks")
    # Only verified source-mapped gSPVertex commands identify potential
    # display-list streams. We do NOT start parsing arbitrary data as Gfx.
    starts = []
    for off in range(0, len(geometry_file) - 7, 8):
        w0, w1 = struct.unpack_from(">II", geometry_file, off)
        if n64_vtx_dma(w0, w1, banks):
            starts.append(off)

    visited: set[int] = set()
    output_vertices: list[N64Vertex] = []
    output_faces: list[tuple[int, int, int]] = []
    runs: list[OriginalGeometryRun] = []
    errors = 0

    for first in starts:
        if first in visited:
            continue
        if len(runs) >= MAX_RUNS:
            raise ValueError("too many original character display-list runs")
        cache: list[N64Vertex | None] = [None] * 32
        count_vtx = 0
        faces_before = len(output_faces)
        terminated = False
        reason = "end_of_data"
        offset = first
        for _ in range(MAX_COMMANDS_PER_RUN):
            if offset + 8 > len(geometry_file):
                reason = "end_of_data"
                break
            w0, w1 = struct.unpack_from(">II", geometry_file, offset)
            opcode = w0 >> 24
            if opcode == N64_G_VTX:
                source = n64_vtx_dma(w0, w1, banks)
                if source is None:
                    reason = "invalid_vertex_dma"
                    break
                n, v0, seg = source
                raw = banks[seg]
                pointer = w1 & 0xFFFFFF
                for i in range(n):
                    cache[v0 + i] = N64Vertex(*N64_VERTEX_STRUCT.unpack_from(
                        raw, pointer + i * N64_VERTEX_STRUCT.size))
                visited.add(offset)
                count_vtx += 1
            elif opcode in (N64_G_TRI1, N64_G_TRI2):
                words = [w1] if opcode == N64_G_TRI1 else [w0, w1]
                valid = True
                pending: list[tuple[N64Vertex, N64Vertex, N64Vertex]] = []
                for word in words:
                    try:
                        a, b, c = _triangle_slots(word)
                    except ValueError:
                        valid = False
                        break
                    if cache[a] is None or cache[b] is None or cache[c] is None:
                        valid = False
                        break
                    pending.append((cache[a], cache[b], cache[c]))
                if valid:
                    for tri in pending:
                        idx = len(output_vertices)
                        output_vertices.extend(tri)
                        output_faces.append((idx, idx + 1, idx + 2))
                        if len(output_faces) > MAX_TOTAL_FACES:
                            raise ValueError("original character triangle budget exceeded")
                else:
                    errors += 1
                    reason = "triangle_without_loaded_vertices"
                    break
            elif opcode == N64_G_ENDDL:
                if w1 == 0:
                    terminated = True
                    reason = "enddl"
                else:
                    reason = "invalid_enddl"
                break
            elif opcode == N64_G_DL:
                # A genuine call to a dynamic display-list segment cannot
                # be followed blindly without a runtime overlay map.
                reason = "unresolved_display_list_call"
                break
            elif opcode in (0x01, 0xB2, 0x05, 0xDE, 0xDF):
                # Matrix/ModifyVtx or different microcode: static geometry
                # must not be silently corrupted by guessed transforms.
                reason = "unsupported_geometry_command"
                break
            # Other RDP/graphics-state commands don't change vertex positions.
            offset += 8
        else:
            reason = "command_budget_exceeded"

        gained = len(output_faces) - faces_before
        if gained:
            runs.append(OriginalGeometryRun(
                first, offset, count_vtx, gained, terminated, reason))
        # No geometry in a run is not evidence of a model.
    mesh = N64Mesh(
        tuple(output_vertices), tuple(output_faces), 0,
        sum(x.vertex_commands for x in runs), {}
    ) if output_faces else None
    return OriginalGeometryRecovery(mesh, tuple(runs), errors, source_file_id)

def recover_character_from_rom(rom: bytes, character: int) -> OriginalGeometryRecovery:
    if character < 0 or character >= 4:
        raise ValueError("character must be 0..3")
    files = read_file_table(rom)
    roots = character_graphics_ids(rom, files)
    if tuple(roots) != CHARACTER_ROOTS:
        raise ValueError("ROM character mappings differ from verified original")
    root = roots[character]
    model = files[root]
    gfx = files[root + 3]
    return decode_original_segmented_geometry(
        rom[gfx.start:gfx.end], rom[model.start:model.end],
        source_file_id=gfx.file_id,
    )

def recover_source_aligned_character_from_rom(
    rom: bytes, character: int
) -> OriginalGeometryRecovery:
    """Use source-verified splat.yaml 0x07/0x09 banks, NOT the old root
    assumption. The game loads genuine F3DEX commands in runtime root+3;
    their 0x09 vertex pointers address this SAME bank, rather than root+0.
    """
    from source_aligned_character_assets import source_align_character_files
    if not 0 <= character < 4:
        raise ValueError("character outside original four")
    aligned = source_align_character_files(rom)[character]
    if aligned[2].source_segment != 7 or aligned[3].source_segment != 9:
        raise ValueError("character has no verified source 0x07 and 0x09 graphics bank")
    entries = read_file_table(rom)
    image07 = entries[aligned[2].runtime_file_id]
    image09 = entries[aligned[3].runtime_file_id]
    raw07 = rom[image07.start:image07.end]
    raw09 = rom[image09.start:image09.end]
    return decode_original_segmented_geometry(
        raw09, raw09, source_file_id=image09.file_id,
        source_banks={7:raw07, 9:raw09},
    )

def recovery_summary(recovery: OriginalGeometryRecovery) -> dict:
    return {
        "file_id": recovery.source_file_id,
        "source": "genuine decompressed NG5E ROM + source-backed 0x07/0x09 mapping",
        "triangles": len(recovery.mesh.faces) if recovery.mesh else 0,
        "vertex_instances": len(recovery.mesh.vertices) if recovery.mesh else 0,
        "geometry_runs": len(recovery.runs),
        "terminated_runs": sum(r.terminated_by_enddl for r in recovery.runs),
        "invalid_triangulation_commands": recovery.skipped_invalid_faces,
        "run_samples": [
            {"start_offset": run.start, "end_offset": run.end,
             "triangles": run.triangles,
             "vertex_commands": run.vertex_commands,
             "stop_reason": run.stop_reason}
            for run in recovery.runs[:8]
        ],
        "skeletal_hierarchy_recovered": False,
        "original_animation_recovered": False,
        "note": "Real F3DEX source geometry, NOT yet verified limb attribution",
    }

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("decompressed_rom", type=Path)
    p.add_argument("--character", type=int, choices=range(4), required=True)
    p.add_argument("--output-obj", type=Path,
                   help="write real original mesh OBJ LOCALLY only, never to GitHub")
    p.add_argument("--output-json", type=Path)
    args = p.parse_args(argv)
    try:
        from character_assets import validate_decompressed_rom
        data = args.decompressed_rom.read_bytes()
        validate_decompressed_rom(data)
        recovery = recover_character_from_rom(data, args.character)
        if args.output_obj is not None:
            if recovery.mesh is None:
                raise ValueError("no verified source triangles recovered from character")
            args.output_obj.parent.mkdir(parents=True, exist_ok=True)
            args.output_obj.write_text(
                mesh_to_obj(recovery.mesh, name=f"Goemon_original_{args.character}"),
                encoding="utf-8")
        report = json.dumps(recovery_summary(recovery), indent=2) + "\n"
        if args.output_json:
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(report, encoding="utf-8")
        else:
            print(report, end="")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
