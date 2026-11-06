"""One-click desktop workflow for original animated Goemon model capture.

No auto-play, no fabricated capture, no uploads. The actual game must
run in the user's desktop session and record its authentic matrices.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "tools/goemon/diagnostic_mod"
WORKFLOW = ROOT / ".github/workflows/goemon-selfhosted.yml"

class OriginalAnimationLauncherTests(unittest.TestCase):
    def test_runner_stages_user_accessible_animation_capture_launcher(self):
        workflow=WORKFLOW.read_text("utf-8")
        self.assertIn("Goemon_Originalanimation_aufnehmen.cmd", workflow)
        self.assertIn("original-animation-capture",workflow)
        self.assertIn("Keine Original-ROM-", workflow)

    def test_launcher_runs_local_installer_not_background_scheduled_task(self):
        script=(MOD/"Goemon_Originalanimation_aufnehmen.cmd").read_text("utf-8")
        self.assertIn("install_and_record_windows.ps1",script)
        self.assertIn("powershell.exe",script)
        self.assertNotIn("schtasks",script)
        self.assertNotIn("upload",script)

    def test_original_game_capture_requires_real_play(self):
        script=(MOD/"install_and_record_windows.ps1").read_text("utf-8")
        self.assertIn("goemon_original_trace.nrm",script)
        self.assertIn("Original-Skelettanimationen aufnehmen",script)
        self.assertIn("capture_windows.ps1",script)
        self.assertIn("Goemon64Recompiled.exe",script)
        self.assertIn("bewegen",script)

if __name__=="__main__":
    unittest.main()
