"""Static safety/wiring checks for original MNSG skeletal capture.

This is not a claim that an authentic animation has been recorded. Native
MIPS mod compilation is checked separately on the self-hosted Windows runner.
"""
from pathlib import Path
import unittest

PROJECT = Path(__file__).resolve().parents[3]
ROOT = PROJECT / "tools/goemon/diagnostic_mod"
C_SOURCE = ROOT / "src/goemon_skeletal_capture.c"
BUILD = ROOT / "build_windows.ps1"
MANIFEST = ROOT / "mod.toml"

class OriginalSkeletonCaptureTests(unittest.TestCase):
    def test_source_hooks_actual_original_game_functions(self):
        c = C_SOURCE.read_text(encoding="utf-8")
        for symbol in (
            "func_80016C44_17844",
            "func_80018CA0_198A0",
            "func_800192D0_19ED0",
            'RECOMP_HOOK_RETURN("func_80018CA0_198A0")',
            'RECOMP_HOOK_RETURN("func_800192D0_19ED0")',
            "D_801684B0_1690B0",
        ):
            self.assertIn(symbol, c)

    def test_capture_is_opt_in_with_bounded_frame_count(self):
        c = C_SOURCE.read_text("utf-8")
        manifest = MANIFEST.read_text("utf-8")
        self.assertIn('recomp_get_config_u32("capture_animation")', c)
        self.assertIn("GOEMON_ANIM_CAPTURE_MAX_FRAMES 1800", c)
        self.assertIn("GOEMON_ANIM_MAX_LIMBS_PER_FRAME 96", c)
        self.assertIn('id = "capture_animation"', manifest)
        self.assertIn('default = "Aus"', manifest)
        self.assertIn("pad->stick_raw_x", c)
        self.assertIn("pad->stick_raw_y", c)
        self.assertNotIn("GOEMON_ANIM_FAKE", c)

    def test_records_render_root_and_real_limb_matrices(self):
        c = C_SOURCE.read_text("utf-8")
        self.assertIn("GOEMON_ANIM_ROOT,", c)
        self.assertIn("GOEMON_ANIM_BONE,", c)
        self.assertIn("GOEMON_ANIM_MATRIX,", c)
        self.assertIn("GOEMON_ANIM_BEGIN,", c)
        self.assertIn("GOEMON_ANIM_END,", c)
        self.assertIn("g_anim_stack_depth", c)
        self.assertIn("g_anim_pending_bone", c)
        self.assertIn("m[15]", c)
        # No texture, vertex or ROM payload is ever printed.
        self.assertNotIn("GOEMON_VERTEX_BYTES", c)

    def test_windows_builder_compiles_and_links_both_instrumentation_files(self):
        script = BUILD.read_text("utf-8")
        self.assertIn("goemon_skeletal_capture.c", script)
        self.assertIn("build/src/goemon_skeletal_capture.o", script)
        self.assertIn("build/src/goemon_trace.o", script)
        self.assertIn("RecompModTool", script)
        self.assertIn("goemon_skeletal_capture.o", script)
        workflow = (PROJECT / ".github/workflows/goemon-selfhosted.yml").read_text("utf-8")
        self.assertIn("goemon_original_trace.nrm", workflow)
        self.assertIn("original-animation-capture", workflow)

if __name__ == "__main__":
    unittest.main()
