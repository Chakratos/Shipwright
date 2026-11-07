"""CI contract: automate authentic private ROM analysis without user interaction.

The Windows runner must:
- run MIPS animation codec/limb/Rig diagnostics independently;
- never upload ROM, graphics or extracted limb data to GitHub;
- never touch the separate Archipelago game installation;
- stage only in the isolated Goemon Test environment.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = ROOT / ".github/workflows/goemon-selfhosted.yml"


class OfflineOriginalAnimationBuildContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_original_rom_analyses_are_one_shot_explicit_and_independent(self):
        source=self.source
        for name in ("[goemon-rig-limbs]",
                     "[goemon-animation-codec]",
                     "[goemon-rig-package]"):
            self.assertIn(name,source)
        self.assertIn("always() && github.event_name == 'push'",source)
        self.assertIn("export_original_rig_limbs.py",source)
        self.assertIn("disasm_original_animation_mips.py",source)
        self.assertIn("archive_original_animation_streams.py",source)
        self.assertIn("package_original_rig.py",source)
        self.assertIn("goemon_original_trace.nrm",source)  # unrelated, opt-in
        self.assertNotIn("actions/upload-artifact",source)

    def test_source_assets_stage_locally_without_archipelago_overwrite(self):
        source=self.source
        self.assertIn("C:\\Users\\Chakratos\\Desktop\\SoH Goemon Test",source)
        self.assertIn("character-original",source)
        self.assertIn("original.goskel",source)
        self.assertIn("original.goanim",source)
        # The source-workflow must NEVER deploy original data to AP.
        self.assertNotIn("C:\\Users\\Chakratos\\Desktop\\SoH AP",source)
        self.assertIn("no fake animation enabled",source)

    def test_private_rom_files_stay_outside_the_checkout(self):
        source=self.source
        self.assertIn("C:\\actions-runner-goemon\\original-rom-rigs",source)
        self.assertIn("C:\\actions-runner-goemon\\original-animation-streams",source)
        self.assertIn("C:\\actions-runner-goemon\\original-rig-limbs",source)


if __name__ == "__main__":
    unittest.main()
