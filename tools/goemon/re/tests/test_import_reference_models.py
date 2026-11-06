"""No actual game meshes in tests: synthetic OBJ/MTL/PNG ZIP only."""
from __future__ import annotations
from io import BytesIO
import json
import math
from pathlib import Path
import struct
import sys
import unittest
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from import_reference_models import (
    FACE, HEADER, VERTEX, MAGIC, load_reference_model,
    parse_reference_obj, pack_ship_mesh,
)

OBJ = """# synthetic geometry
mtllib test.mtl
o synthetic
v 0 0 0
v 2 0 0
v 2 2 0
v 0 2 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
usemtl skin
f 1/1 2/2 3/3 4/4
"""
MTL = "newmtl skin\nmap_Kd demo.png\n"
PNG = bytes.fromhex("89504e470d0a1a0a") + b"\x00"*8 + struct.pack(">II",1,1) + b"\x00"*8

def make_zip(path: Path, *, obj=OBJ, mtl=MTL, image=PNG):
    with ZipFile(path, "w") as z:
        z.writestr("Goe/goe.obj",obj)
        z.writestr("Goe/goe.mtl",mtl)
        z.writestr("Goe/demo.png",image)

class ReferenceMeshImportTests(unittest.TestCase):
    def test_fan_triangulation_and_deterministic_indexed_mesh(self):
        mesh = parse_reference_obj(OBJ)
        self.assertEqual(len(mesh.vertices),4)
        self.assertEqual(len(mesh.faces),2)
        self.assertEqual(mesh.faces[0],(0,1,2,0))
        self.assertEqual(mesh.faces[1],(0,2,3,0))
        raw = pack_ship_mesh(mesh)
        self.assertEqual(raw,pack_ship_mesh(mesh))
        self.assertEqual(HEADER.unpack_from(raw),(MAGIC,4,2,1))
        self.assertEqual(len(raw),HEADER.size+4*VERTEX.size+2*FACE.size)
        self.assertEqual(VERTEX.unpack_from(raw,HEADER.size)[:3],(0,0,0))
        self.assertEqual(FACE.unpack_from(raw,HEADER.size+4*VERTEX.size),
                         (0,1,2,0))
        self.assertEqual(mesh.vertices[2].u,1.0)

    def test_negative_indices_are_supported_without_guessing(self):
        src = OBJ.replace("f 1/1 2/2 3/3 4/4","f -4/-4 -3/-3 -2/-2 -1/-1")
        self.assertEqual(parse_reference_obj(src),parse_reference_obj(OBJ))

    def test_material_and_png_are_kept_as_local_assets(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory)/"source.zip"
            make_zip(path)
            packed, report, textures = load_reference_model(path,"Goemon")
            self.assertEqual(report["vertex_count"],4)
            self.assertEqual(report["triangle_count"],2)
            self.assertTrue(report["static_geometry_only"])
            self.assertFalse(report["original_animation_and_skeleton"])
            self.assertEqual(report["materials"][0]["local_texture"],
                             "texture_000.png")
            self.assertEqual(textures["texture_000.png"],PNG)
            self.assertEqual(HEADER.unpack_from(packed),(MAGIC,4,2,1))
            self.assertEqual(packed,load_reference_model(path,"Goemon")[0])
            self.assertNotIn("ROM", report["provenance"].split(" " )[:2])

    def test_unknown_character_and_missing_texture_fail(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory)/"source.zip"
            make_zip(path)
            with self.assertRaisesRegex(ValueError,"unknown"):
                load_reference_model(path,"Link")
            make_zip(path,mtl="newmtl skin\nmap_Kd missing.png\n")
            with self.assertRaisesRegex(ValueError,"missing original"):
                load_reference_model(path,"Goemon")

    def test_zip_path_traversal_is_refused(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            path = Path(directory)/"source.zip"
            with ZipFile(path,"w") as z:
                z.writestr("../goe.obj",OBJ)
                z.writestr("goe.mtl",MTL)
            with self.assertRaisesRegex(ValueError,"unsafe"):
                load_reference_model(path,"Goemon")

    def test_reject_invalid_faces_and_nonfinite_geometry(self):
        with self.assertRaisesRegex(ValueError,"index outside"):
            parse_reference_obj(OBJ.replace("1/1 2/2 3/3", "1/1 2/2 999/3"))
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            parse_reference_obj(OBJ.replace("v 2 2 0", "v nan 2 0"))
        with self.assertRaisesRegex(ValueError,"no polygons"):
            parse_reference_obj("v 0 0 0\n")

if __name__=="__main__":
    unittest.main()
