"""Full local animation-only capture pipeline, no genuine assets or ROM bytes."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
import zipfile

PROJECT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(PROJECT/"tools/goemon/diagnostic_mod"))
sys.path.insert(0,str(PROJECT/"tools/goemon/reference_probe"))
from reprocess_log import reprocess
from original_pose_archive import inspect_pose_archive


class AnimationCaptureReprocessingTests(unittest.TestCase):
    def test_original_skeleton_capture_without_old_physics_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/"run-20261106-235900"
            folder.mkdir()
            matrix="1,0,0,0,0,1,0,0,0,0,1,0,3,2,1,1"
            contents=[
                "GOEMON_ANIM_BEGIN,1,100,source=func_800192D0_19ED0",
                "GOEMON_ANIM_BONE,100,0,15,80123480,070024A8,1,0,100,100,100,10,20,30,40,50,60",
                f"GOEMON_ANIM_MATRIX,100,0,15,80123480,2.5,{matrix}",
                "GOEMON_ANIM_BONE,101,0,23,80123480,070024A8,1,0,100,100,100,11,21,31,40,50,60",
                f"GOEMON_ANIM_MATRIX,101,0,23,80123480,3.5,{matrix}",
                "GOEMON_ANIM_END,102,limit",
            ]
            (folder/"stdout.log").write_text("\n".join(contents)+"\n",encoding="utf-8")
            archive=reprocess(folder)
            self.assertTrue(archive.exists())
            self.assertFalse((folder/"ERROR.txt").exists())
            summary=json.loads((folder/"capture_summary.json").read_text("utf-8"))
            self.assertEqual(summary["reference_samples"],0)
            self.assertEqual(summary["original_skeletal_matrix_events"],2)
            self.assertEqual(summary["original_skeletal_bone_events"],2)
            self.assertEqual(summary["parsers"]["original_skeletal_poses"]["status"],"ok")
            self.assertEqual(summary["parsers"]["original_pose_archive"]["status"],"ok")
            path=folder/"original_skeletal_poses.gopa"
            self.assertTrue(path.is_file())
            data=inspect_pose_archive(path.read_bytes())
            self.assertEqual(data["frame_count"],2)
            self.assertEqual(data["original_bone_matrices"],2)
            with zipfile.ZipFile(archive) as z:
                self.assertIn("original_skeletal_poses.gopa",z.namelist())
                self.assertIn("goemon_runtime.log",z.namelist())

if __name__=="__main__":
    unittest.main()
