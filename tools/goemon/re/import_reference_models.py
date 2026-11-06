#!/usr/bin/env python3
"""Convert a local reference character OBJ ZIP to a deterministic Ship mesh.

The publicly documented Goemon/Ebisumaru/Sasuke/Yae N64 OBJ model exports
are optional static-geometry references, not animation/rig replacements.
Input ZIPs and output .bin/.png files are always LOCAL, outside the Git repo.

This bridge deliberately uses a tiny versioned binary format:
  "GOMESH01" + LE u32 vertex_count, face_count, material_count
  each vertex: LE f32 xyz, LE f32 UV, RGBA8 (24 bytes)
  each triangle: LE u32 index0,index1,index2,material_index (16 bytes)
A companion JSON holds the ordered material/texture filenames.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path, PurePosixPath
import struct
import sys
from zipfile import ZipFile

MAGIC = b"GOMESH01"
HEADER = struct.Struct("<8sIII")
VERTEX = struct.Struct("<fffffBBBB")
FACE = struct.Struct("<IIII")
CHARACTERS = ("Goemon", "Ebisumaru", "Sasuke", "Yae")
MAX_VERTICES = 300000
MAX_FACES = 200000

@dataclass(frozen=True)
class MeshVertex:
    x: float
    y: float
    z: float
    u: float
    v: float

@dataclass(frozen=True)
class ReferenceMesh:
    vertices: tuple[MeshVertex, ...]
    faces: tuple[tuple[int,int,int,int], ...]
    materials: tuple[str, ...]

def _obj_index(s: str, count: int) -> int:
    i = int(s)
    if i == 0:
        raise ValueError("OBJ vertex/UV index cannot be zero")
    index = i - 1 if i > 0 else count + i
    if not 0 <= index < count:
        raise ValueError("OBJ face index outside preceding vertex/UV records")
    return index

def parse_reference_obj(text: str) -> ReferenceMesh:
    positions: list[tuple[float,float,float]] = []
    uvs: list[tuple[float,float]] = []
    vertices: list[MeshVertex] = []
    faces: list[tuple[int,int,int,int]] = []
    material_names: list[str] = []
    material_index: dict[str,int] = {}
    dedup: dict[tuple[int,int | None],int] = {}
    current_material = "default"

    for lineno, source_line in enumerate(text.splitlines(), 1):
        line = source_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        tag = fields[0]
        if tag in ("v", "vt"):
            required = 3 if tag == "v" else 2
            if len(fields) < required + 1:
                raise ValueError(f"OBJ incomplete {tag} at line {lineno}")
            coords = tuple(float(x) for x in fields[1:required+1])
            if not all(math.isfinite(x) for x in coords):
                raise ValueError(f"OBJ nonfinite coordinates at line {lineno}")
            if tag == "v":
                positions.append(coords)
            else:
                uvs.append(coords)
        elif tag == "usemtl":
            if len(fields) != 2:
                raise ValueError(f"OBJ bad material name at line {lineno}")
            current_material = fields[1]
        elif tag == "f":
            if not 4 <= len(fields) <= 33:
                raise ValueError(f"OBJ face must have 3..32 corners at line {lineno}")
            if current_material not in material_index:
                material_index[current_material] = len(material_names)
                material_names.append(current_material)
            mid = material_index[current_material]
            indices: list[int] = []
            for token in fields[1:]:
                parts = token.split("/")
                if not parts[0] or len(parts) > 3:
                    raise ValueError(f"OBJ unsupported face token {token!r}")
                vi = _obj_index(parts[0], len(positions))
                ti = _obj_index(parts[1], len(uvs)) if len(parts) > 1 and parts[1] else None
                key = vi, ti
                if key not in dedup:
                    x, y, z = positions[vi]
                    u, v = uvs[ti] if ti is not None else (0.0, 0.0)
                    dedup[key] = len(vertices)
                    vertices.append(MeshVertex(x, y, z, u, v))
                indices.append(dedup[key])
            for n in range(1, len(indices) - 1):
                faces.append((indices[0], indices[n], indices[n+1], mid))
                if len(faces) > MAX_FACES:
                    raise ValueError("OBJ triangle budget exceeded")
            if len(vertices) > MAX_VERTICES:
                raise ValueError("OBJ vertex budget exceeded")
        # Object names, normals and export-tool metadata do not change
        # geometric vertices; preserve only material, positions and UV.
    if not faces:
        raise ValueError("original reference OBJ has no polygons")
    return ReferenceMesh(tuple(vertices), tuple(faces), tuple(material_names))

def pack_ship_mesh(mesh: ReferenceMesh) -> bytes:
    if not mesh.vertices or not mesh.faces:
        raise ValueError("refusing empty Ship mesh")
    if len(mesh.vertices) > MAX_VERTICES or len(mesh.faces) > MAX_FACES:
        raise ValueError("Ship mesh exceeds source validation budget")
    content = bytearray(HEADER.pack(
        MAGIC, len(mesh.vertices), len(mesh.faces), len(mesh.materials)
    ))
    for v in mesh.vertices:
        content.extend(VERTEX.pack(v.x,v.y,v.z,v.u,v.v,255,255,255,255))
    for a,b,c,material in mesh.faces:
        if min(a,b,c) < 0 or max(a,b,c) >= len(mesh.vertices):
            raise ValueError("Ship mesh invalid triangle index")
        if not 0 <= material < len(mesh.materials):
            raise ValueError("Ship mesh invalid material")
        content.extend(FACE.pack(a,b,c,material))
    return bytes(content)

def _zip_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not name or path.is_absolute() or ".." in path.parts or ":" in name:
        raise ValueError("unsafe original model ZIP path")
    return str(path)

def load_reference_model(zip_path: Path, character: str) -> tuple[bytes, dict, dict[str,bytes]]:
    if character not in CHARACTERS:
        raise ValueError("unknown original playable character")
    with ZipFile(zip_path) as archive:
        names = {_zip_name(name): name for name in archive.namelist() if not name.endswith("/")}
        if len(names) != len([x for x in archive.namelist() if not x.endswith("/")]):
            raise ValueError("ambiguous ZIP paths")
        models = [name for name in names if name.lower().endswith(".obj")]
        mtls = [name for name in names if name.lower().endswith(".mtl")]
        if len(models) != 1 or len(mtls) != 1:
            raise ValueError("expected one original OBJ and MTL per character archive")
        obj = archive.read(names[models[0]]).decode("utf-8-sig")
        mtl = archive.read(names[mtls[0]]).decode("utf-8-sig")
        mesh = parse_reference_obj(obj)
        # Material-to-texture mapping from OBJ's companion Wavefront MTL.
        materials: dict[str,str | None] = {}
        current: str | None = None
        for raw in mtl.splitlines():
            parts = raw.strip().split()
            if len(parts) >= 2 and parts[0] == "newmtl":
                current = " ".join(parts[1:])
                materials[current] = None
            elif len(parts) >= 2 and parts[0] == "map_Kd" and current:
                materials[current] = parts[-1]
        textures: dict[str,bytes] = {}
        manifest_materials = []
        for index, material in enumerate(mesh.materials):
            source = materials.get(material)
            output_name = None
            if source:
                rel = _zip_name(source)
                full = str(PurePosixPath(models[0]).parent / rel)
                # Some old N64 rips store texture paths relative to ZIP root.
                matches = [p for p in (full, rel) if p in names]
                if not matches:
                    raise ValueError(f"missing original material texture {source}")
                data = archive.read(names[matches[0]])
                if len(data) < 24 or data[:8] != bytes.fromhex("89504E470D0A1A0A"):
                    raise ValueError("model texture is not PNG")
                width, height = struct.unpack_from(">II", data, 16)
                if not 1 <= width <= 4096 or not 1 <= height <= 4096:
                    raise ValueError("PNG image dimensions outside limits")
                output_name = f"texture_{index:03d}.png"
                textures[output_name] = data
            manifest_materials.append({
                "name": material, "original_texture": source,
                "local_texture": output_name,
            })
    packed = pack_ship_mesh(mesh)
    report = {
        "schema": "goemon-ship-reference-mesh-v1",
        "character": character,
        "provenance": "external extracted N64 OBJ, NOT source-verified against local ROM",
        "static_geometry_only": True,
        "original_animation_and_skeleton": False,
        "mesh_file": "model.gomesh",
        "vertex_count": len(mesh.vertices),
        "triangle_count": len(mesh.faces),
        "materials": manifest_materials,
        "note": "For original-appearance renderer integration, not faithful NG5E rig/animation.",
    }
    return packed, report, textures

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--character", choices=CHARACTERS, required=True)
    p.add_argument("--zip", type=Path, required=True, help="local original model OBJ ZIP")
    p.add_argument("--output-dir", type=Path, required=True,
                   help="local folder OUTSIDE the Shipwright checkout")
    args = p.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    destination = args.output_dir.expanduser().resolve()
    try:
        if destination == root or root in destination.parents:
            raise ValueError("original game graphics must not be placed in Git checkout")
        packed, manifest, textures = load_reference_model(args.zip, args.character)
        folder = destination / args.character
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "model.gomesh").write_bytes(packed)
        (folder / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        for name,data in textures.items():
            (folder / name).write_bytes(data)
        print(f"{args.character}: {manifest['vertex_count']} vertices, "
              f"{manifest['triangle_count']} triangles; local mesh: {folder}")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
