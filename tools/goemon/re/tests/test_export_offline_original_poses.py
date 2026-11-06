"""Ensure offline original skeletal pose records preserve all source fields."""
import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_offline_original_poses import inspect_source_pose_bank

class OfflineSourcePoseCatalogTests(unittest.TestCase):
    @staticmethod
    def bank_fixture():
        root=bytearray(0x900)
        gfx=bytes(0x300)
        for index in range(6):
            offset=0x100+24*index
            struct.pack_into(">Ibb9h",root,offset,
                             0x09000080 + index*8,
                             1 if index<5 else 0,0,
                             256,256,256, 0,index*30,0, 11,22,33)
        struct.pack_into(">III",root,0x50,0x8000010A,
                         0x07000600,0x07000100)
        return {7:bytes(root),9:gfx}

    def test_original_rom_raw_pose_is_exported_without_generated_animation(self):
        source=inspect_source_pose_bank(self.bank_fixture(),character="Goemon")
        self.assertEqual(source["structurally_valid_poses"],1)
        self.assertEqual(source["distinct_raw_transform_poses"],1)
        record=source["original_source_poses"][0]
        self.assertEqual(record["source_limb_count"],6)
        self.assertEqual(record["source_graphic_parts"],6)
        self.assertEqual(record["original_low_byte_parameter"],10)
        self.assertEqual(record["original_animation_pointer"],"0x07000600")
        self.assertEqual(record["limbs"][0]["scale"],(256,256,256))
        self.assertEqual(record["limbs"][5]["rotation"],(0,150,0))
        self.assertIsNone(record["animation_frame_index"])
        self.assertIsNone(record["original_action_id"])
        self.assertIsNone(record["animation_clip_owner"])
        self.assertFalse(record["animation_timeline_decoded"])
        self.assertEqual(source["actual_animation_frames_recovered"],0)
        self.assertFalse(source["gameplay_capture_required"])
        self.assertNotIn("synthetic_animation_frames", source)
        json.dumps(source)

    def test_invalid_limb_count_or_wrong_bank_not_claimed_as_pose(self):
        source=inspect_source_pose_bank({7:bytes(0x1000),9:bytes(0x100)},
                                        character="Goemon")
        self.assertEqual(source["structurally_valid_poses"],0)
        self.assertEqual(source["original_source_poses"],[])
        source=inspect_source_pose_bank({7:self.bank_fixture()[7],9:bytes(0x30)},
                                        character="Goemon")
        self.assertEqual(source["structurally_valid_poses"],0)

if __name__=="__main__":
    unittest.main()
