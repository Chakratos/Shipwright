"""Automated continuity checks for the GitHub-only Goemon agent handoff."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[3]
STATE = ROOT / "docs/goemon/agent_state.json"

class GitHubOnlyAgentHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = json.loads(STATE.read_text(encoding="utf-8"))

    def test_root_agent_instructions_and_canonical_documents(self):
        data = self.state
        self.assertEqual(data["schema"], "goemon-agent-handoff-v1")
        self.assertEqual(data["branch"], "feature/goemon-original-controller")
        self.assertEqual(data["repository"], "Chakratos/Shipwright")
        for document in data["authoritative_documents"]:
            file = ROOT / document
            with self.subTest(document=document):
                self.assertTrue(file.is_file(), document)
                self.assertGreater(len(file.read_text(encoding="utf-8")), 400)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("AGENTS.md", readme)
        self.assertIn("docs/goemon/START_HERE.md", readme)

    def test_active_gate_consistency_and_forbidden_false_claims(self):
        data = self.state
        gates = data["gates"]
        self.assertEqual(set(gates), {"G1", "G2", "G3", "G4", "G5"})
        self.assertIn(data["active_gate"], gates)
        self.assertEqual(gates[data["active_gate"]], "open")
        self.assertEqual(data["active_gate"], "G1")  # change when actually met
        v = data["verified"]
        self.assertTrue(v["original_rom_cpu_evaluator_executes"])
        self.assertFalse(v["numerically_changing_original_player_pose_verified"])
        self.assertFalse(v["original_timed_character_animations_play_in_ship"])
        self.assertFalse(v["all_four_characters_playable_in_oot"])
        self.assertFalse(v["randomizer_integrated"])
        self.assertEqual(data["critical_negative_evidence"]["source_descriptors_evaluated"], 371)
        self.assertEqual(data["critical_negative_evidence"]["numerically_changing_descriptors"], 0)
        self.assertTrue(data["archipelago_test_install_must_remain_untouched"])

    def test_restart_workflow_points_to_real_code_and_evidence(self):
        text = (ROOT / "docs/goemon/NEXT_TASKS.md").read_text(encoding="utf-8")
        status = (ROOT / "docs/goemon/CURRENT_STATE.md").read_text(encoding="utf-8")
        for source in (
            "tools/goemon/re/probe_original_mips_execution.py",
            "tools/goemon/re/original_mips_vm.py",
            "tools/goemon/re/sweep_original_mips_descriptors.py",
            "soh/soh/Enhancements/Goemon/OriginalReferenceCharacterActor.cpp",
            ".github/workflows/goemon-selfhosted.yml"
        ):
            with self.subTest(source=source):
                self.assertTrue((ROOT / source).is_file(), source)
                self.assertIn(source, text + status)
        self.assertIn("42474422364", status)
        self.assertIn("G1", text)
        self.assertIn("signed-zero", text.lower())
        self.assertGreaterEqual(len(self.state["next_task"]), 70)

if __name__ == "__main__":
    unittest.main()
