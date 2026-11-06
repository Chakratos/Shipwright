"""Validate local source-ROM geometry export. All vertices here are synthetic."""
from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_f3dex_geometry import N64Vertex, N64Mesh
from original_segmented_geometry import (
    OriginalGeometryRun, OriginalGeometryRecovery
)
from export_original_models import write_original_character

def synthetic():
    vertices = [
        N64Vertex(x, y, z, 0, 0, 0, 255, 200, 100, 255)
        for (x,y,z) in [
            (0,0,0),(1,0,0),(0,1,0),
            (5,0,0),(6,0,0),(5,1,0),
        ]
    ]
    mesh=N64Mesh(tuple(vertices),((0,1,2),(3,4,5)),0,2,{})
    runs=(
        OriginalGeometryRun(0x40,0x50,1,1,True,"enddl"),
        OriginalGeometryRun(0x80,0x90,1,1,True,"enddl"),
    )
    return OriginalGeometryRecovery(mesh,runs,0,291)

class OriginalModelExporterTests(unittest.TestCase):
    def test_original_parts_exported_to_separate_local_files(self):
        with TemporaryDirectory() as folder:
            dst=Path(folder).resolve()
            manifest=write_original_character(synthetic(),"Goemon",dst)
            self.assertEqual(manifest["triangles"],2)
            self.assertEqual(manifest["geometry_runs"],2)
            self.assertFalse(manifest["original_animation_recovered"])
            self.assertFalse(manifest["source_skeleton_extracted"] if
                             "source_skeleton_extracted" in manifest else False)
            self.assertEqual(manifest["source_obj"],"all_original_parts.obj")
            self.assertEqual(len(manifest["per_display_list_objects"]),2)
            name0=manifest["per_display_list_objects"][0]["local_obj_file"]
            name1=manifest["per_display_list_objects"][1]["local_obj_file"]
            self.assertNotEqual(name0,name1)
            self.assertIn("v 0 0 0", (dst/"Goemon"/name0).read_text())
            self.assertIn("v 5 0 0", (dst/"Goemon"/name1).read_text())
            self.assertEqual((dst/"Goemon"/"all_original_parts.obj")
                             .read_text().count("\nf "),2)
            saved=json.loads((dst/"Goemon"/"manifest.json").read_text())
            self.assertEqual(saved["file_id"],291)
            self.assertEqual(saved["per_display_list_objects"][1]["triangles"],1)

    def test_missing_yae_geometry_reports_explicit_unresolved_state(self):
        with TemporaryDirectory() as folder:
            unresolved=OriginalGeometryRecovery(None,(),0,303)
            report=write_original_character(unresolved,"Yae",Path(folder).resolve())
            self.assertEqual(report["status"],"not_yet_recovered")
            self.assertEqual(report["triangles"],0)
            self.assertFalse((Path(folder)/"Yae"/"all_original_parts.obj").exists())

    def test_rejects_unknown_characters_and_relative_destinations(self):
        src=synthetic()
        with self.assertRaisesRegex(ValueError,"unknown original"):
            write_original_character(src,"Mario",Path("/tmp"))
        with self.assertRaisesRegex(ValueError,"absolute"):
            write_original_character(src,"Goemon",Path("relative"))

if __name__ == "__main__":
    unittest.main()
