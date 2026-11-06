"""Verify true model-actor pilot integration without rebuilding Ship.

These tests verify source wiring and opt-in guarantees. Runtime movement,
camera, battle, and cutscene correctness still require in-game tests.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
PLAYER = ROOT / "soh/src/overlays/actors/ovl_player_actor/z_player.c"
ACTOR = ROOT / "soh/soh/Enhancements/Goemon/OriginalReferenceCharacterActor.cpp"
MENU = ROOT / "soh/soh/SohGui/SohMenuDevTools.cpp"
CORE = ROOT / "soh/soh/Enhancements/Goemon/OriginalPlayableCharacter.hpp"

class PlayableOriginalModelWiringTests(unittest.TestCase):
    def test_new_model_actor_drives_source_measured_original_motion(self):
        source = ACTOR.read_text("utf-8")
        self.assertIn('#include "OriginalPlayableCharacter.hpp"', source)
        self.assertIn("AdvanceOriginalLivePreview(", source)
        self.assertIn("MapShipInputForOriginalPlayable(", source)
        self.assertIn("ProbeConservativeZeldaTerrain(", source)
        self.assertIn("BgCheck_EntityLineTest1(", source)
        self.assertIn("BgCheck_EntityRaycastFloor3(", source)
        self.assertNotIn("DebugDisplay_AddObject", source)
        self.assertNotIn('CVAR_SETTING("Goemon.PrototypePilot")', source)
        self.assertIn("Link's original model", source)
        self.assertIn("sPilotRoom != play->roomCtx.curRoom.num", source)

    def test_source_motion_uses_same_position_as_hidden_native_link(self):
        source = ACTOR.read_text("utf-8")
        self.assertIn("link->actor.world.pos = actor->world.pos;", source)
        self.assertIn("link->actor.speedXZ = 0.0f;", source)
        self.assertIn("actor->world.pos = {\n        sOriginalMotion.controller.motion.groundX,", source)
        self.assertIn("CharacterPilotReady(play, link)", source)
        self.assertIn("if (!sPilotActive || sPilotRoom", source)
        self.assertIn('goemon_original_player_error.txt', source)
        self.assertIn("sPilotFaulted = true;", source)
        # Render/showcase path remains independent and explicitly opt-in.
        self.assertIn("55.0f;", source)
        self.assertIn("sPilotActive = false;", source)

    def test_only_the_filtered_vanilla_input_is_changed(self):
        code = PLAYER.read_text("utf-8")
        self.assertEqual(code.count(
            "Goemon_ReferenceFilterLinkInput(play, this, &input);"), 1)
        self.assertIn(
            "Goemon_PrototypeFilterLinkInput(play, this, &input);\n"
            "        Goemon_ReferenceFilterLinkInput(play, this, &input);\n"
            "        Player_UpdateCommon(this, play, &input);",
            code)
        self.assertIn("if (Goemon_ReferenceShouldHideLink(play, this))", code)
        source = ACTOR.read_text("utf-8")
        self.assertIn('extern "C" void Goemon_ReferenceFilterLinkInput(', source)
        self.assertIn('extern "C" int Goemon_ReferenceShouldHideLink(', source)
        self.assertIn("*input = {};", source)
        self.assertNotIn("play->state.input[0] = {}", source)

    def test_menu_requires_explicit_opt_in(self):
        source = MENU.read_text("utf-8")
        self.assertEqual(
            source.count('CVAR_SETTING("Goemon.ControlOriginalCharacter")'), 1)
        checkbox = re.search(
            r'AddWidget\(path, "Control Original Character \(ROM Motion\)"'
            r'.*?\.Options\(CheckboxOptions\(\)\.DefaultValue\(false\)',
            source, flags=re.DOTALL)
        self.assertIsNotNone(checkbox)
        gate = CORE.read_text("utf-8")
        self.assertIn("struct PlayableOriginalCharacterGate", gate)
        self.assertIn("gate.originalModelLoaded", gate)
        self.assertIn("gate.noLegacyPilotConflict", gate)
        self.assertIn("gate.faultFree", gate)
        self.assertIn("MapShipStickForOriginalPreview(-stickX,", gate)

if __name__ == "__main__":
    unittest.main()
