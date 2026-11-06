#!/usr/bin/env python3
"""Export decoded source-ROM Goemon meshes locally, organized by Gfx run.

No externally-ripped geometry is used: vertex bytes and triangle indices come
from the OWNED NG5E ROM via actual F3DEX gSPVertex/gSP1Triangle instructions.
No ROM, OBJ, textures or 3D files are uploaded or committed to GitHub.
The 0x07 display-list spans are not yet mapped to original skeleton limbs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

# real_rom_check.py is one directory above this source-only decoder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from character_names import CHARACTER_NAMES
from decompress_rom import decompress_us_rom
from original_f3dex_geometry import N64Mesh, mesh_to_obj
from original_segmented_geometry import (
    OriginalGeometryRecovery, recover_character_from_rom, recovery_summary,
)

def verify_owned_rom(data: bytes) -> None:
    if len(data) != 0x1000000 or data[:4] != bytes.fromhex("80371240"):
        raise ValueError("requires original big-endian 16 MiB NG5E ROM")
    if data[0x3B:0x3F] != b"NG5E":
        raise ValueError("requires US original NG5E ROM")
    # Same original hash used by real_rom_check.py. Fail closed before
    # generating any source-derived player data.
    from real_rom_check import ORIGINAL_SHA256
    if hashlib.sha256(data).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("ROM SHA-256 differs from user's original validated NG5E")

def write_original_character(
    recovery: OriginalGeometryRecovery, character: str, destination: Path
) -> dict:
    if character not in CHARACTER_NAMES:
        raise ValueError("unknown original character")
    if not destination.is_absolute():
        raise ValueError("output directory must be absolute and outside repo")
    if recovery.mesh is None:
        return {
            **recovery_summary(recovery), "character": character,
            "status": "not_yet_recovered", "source_obj": None,
            "per_display_list_objects": [],
        }

    target = destination / character
    target.mkdir(parents=True, exist_ok=True)
    # Complete lossless geometry-only combined OBJ.
    source = mesh_to_obj(recovery.mesh, name=character + "_source_rom")
    (target / "all_original_parts.obj").write_text(source, encoding="utf-8")
    cursor = 0
    per_part = []
    for index, run in enumerate(recovery.runs):
        first = cursor
        end = first + run.triangles * 3
        cursor = end
        raw_vertices = recovery.mesh.vertices[first:end]
        raw_faces = tuple((i, i+1, i+2)
                          for i in range(0, len(raw_vertices), 3))
        part = N64Mesh(
            raw_vertices, raw_faces, run.start,
            run.vertex_commands, {}
        )
        name = f"gfx_{index:03d}_at_0x{run.start:06x}.obj"
        (target / name).write_text(
            mesh_to_obj(part, name=f"{character}_original_gfx_{index:03d}"),
            encoding="utf-8"
        )
        per_part.append({
            "display_list_offset": run.start,
            "display_list_end": run.end,
            "triangles": run.triangles,
            "local_obj_file": name,
            "terminated_by_enddl": run.terminated_by_enddl,
        })
    if cursor != len(recovery.mesh.vertices):
        raise ValueError("source display-list run-to-mesh topology mismatch")
    manifest = {
        **recovery_summary(recovery),
        "character": character,
        "status": "raw_source_geometry_without_skeleton",
        "source_obj": "all_original_parts.obj",
        "per_display_list_objects": per_part,
        "provenance": "original ROM + Goemon64Recomp F3DEX + mnsg/splat.yaml",
        "texture_uv_semantics_established": False,
        "skeleton_limb_assignment_established": False,
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest

def export_owned_original_rom(rom: bytes, output_dir: Path) -> dict:
    verify_owned_rom(rom)
    from real_rom_check import DECOMPRESSED_SHA256
    decoded = decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest() != DECOMPRESSED_SHA256:
        raise ValueError("decompressed source ROM differs from verified baseline")
    project = Path(__file__).resolve().parents[3]
    target = output_dir.expanduser().resolve()
    if target == project or project in target.parents:
        raise ValueError("refuse copyrighted original meshes within Git checkout")
    target.mkdir(parents=True, exist_ok=True)
    characters = []
    for i, name in enumerate(CHARACTER_NAMES):
        recovered = recover_character_from_rom(decoded, i)
        summary = write_original_character(recovered, name, target)
        characters.append({
            "id": i, "name": name, "triangles": summary["triangles"],
            "runs": summary["geometry_runs"], "status": summary["status"],
        })
        print(f"GOEMON_ORIGINAL_ASSET_LOCAL {name}: "
              f"{summary['triangles']} source-ROM triangles, "
              f"{summary['geometry_runs']} separate Gfx runs")
    result = {
        "schema": "ng5e-source-rom-geometry-v1",
        "data_origin": "local hash-verified original NG5E ROM",
        "source_hash_sha256": hashlib.sha256(rom).hexdigest(),
        "characters": characters,
        "source_animation_extracted": False,
        "source_skeleton_extracted": False,
        "asset_upload_performed": False,
    }
    (target / "original_asset_manifest.json").write_text(
        json.dumps(result, indent=2)+"\n", encoding="utf-8")
    return result

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom", type=Path)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        from real_rom_check import locate_rom
        source = args.rom or locate_rom()
        out = export_owned_original_rom(source.read_bytes(), args.output_dir)
        if len(out["characters"]) != 4:
            raise ValueError("incomplete character export manifest")
        print("GOEMON_ORIGINAL_ASSET_LOCAL manifest written. No GitHub artifact.")
    except (OSError, ValueError) as err:
        print(f"GOEMON ORIGINAL ROM EXPORT FAILED: {err}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
