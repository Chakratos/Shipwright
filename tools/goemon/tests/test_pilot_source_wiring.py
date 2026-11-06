"""Check cross-language pilot wiring without an expensive Ship build.

These are source-boundary tests, not runtime camera or player validation.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
PLAYER = ROOT / "soh/src/overlays/actors/ovl_player_actor/z_player.c"
ACTOR = ROOT / "soh/soh/Enhancements/Goemon/OriginalPrototypeActor.cpp"
MENU = ROOT / "soh/soh/SohGui/SohMenuDevTools.cpp"
CAMERA = ROOT / "soh/soh/Enhancements/Goemon/OriginalPilotCamera.hpp"

class PilotSourceWiringTests(unittest.TestCase):
    def test_player_filters_local_input_only(self):
        source = PLAYER.read_text(encoding="utf-8")
        self.assertIn("Goemon_PrototypeFilterLinkInput(play, this, &input);", source)
        self.assertEqual(
            source.count("Goemon_PrototypeFilterLinkInput(play, this, &input);"), 1)
        hook = source.index("Goemon_PrototypeFilterLinkInput(play, this, &input);")
        player_update = source.index("void Player_Update(Actor* thisx, PlayState* play)")
        vanilla = source.index("Player_UpdateCommon(this, play, &input);", player_update)
        self.assertTrue(player_update < hook < vanilla)
        self.assertIn("input = play->state.input[0];", source[player_update:hook])
        self.assertNotIn("memset(&play->state.input[0]", source[player_update:vanilla])

    def test_c_linkage_and_no_direct_link_teleport(self):
        source = ACTOR.read_text(encoding="utf-8")
        self.assertIn('extern "C" void Goemon_PrototypeFilterLinkInput(', source)
        self.assertIn("if (input == nullptr || !PilotReady(play, link)) return;", source)
        self.assertIn("*input = {};", source)
        self.assertIn("COND_HOOK(OnPlayDrawBegin, true, FollowPrototypeCamera);", source)
        self.assertNotIn("link->actor.world.pos =", source)
        self.assertIn("sPilotCamera.Render(", source)
        self.assertIn("sPilotCamera.Restore(", source)

    def test_actor_logs_pilot_and_link_without_repositioning_link(self):
        source = ACTOR.read_text(encoding="utf-8")
        self.assertIn("pilot_enabled,link_x,link_y,link_z", source)
        self.assertIn("static_cast<int>(PilotReady(play, link))", source)
        self.assertIn("link->actor.world.pos.x << ','", source)
        self.assertIn("link->actor.world.pos.y << ','", source)
        self.assertIn("link->actor.world.pos.z << ','", source)
        self.assertNotIn("link->actor.world.pos =", source)

    def test_menu_is_opt_in_not_a_default_replacement(self):
        source = MENU.read_text(encoding="utf-8")
        self.assertEqual(source.count('CVAR_SETTING("Goemon.PrototypePilot")'), 1)
        block = re.search(
            r'AddWidget\(path, "Pilot Goemon Actor \(Freeze Link Input\)"'
            r'.*?\.Options\(CheckboxOptions\(\)\.DefaultValue\(false\)',
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(block)
        header = CAMERA.read_text(encoding="utf-8")
        self.assertIn("struct PilotCameraHistory", header)
        self.assertIn("struct PilotInputGate", header)

if __name__ == "__main__":
    unittest.main()
