"""Synthetic round-trip tests for lossless GOPA0001 original-pose archives."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_pose_archive import (
    MAGIC, HEADER, FRAME, BONE, encode_pose_archive, inspect_pose_archive
)
from original_skeletal_poses import read_original_animation_log


def sample() -> dict:
    bone = ("GOEMON_ANIM_BONE,110,0,15,80123480,070024A8,"
            "1,0,100,100,100,10,20,30,40,50,60")
    bone2 = bone.replace(",110,0,15,", ",111,0,23,")
    matrix = ("GOEMON_ANIM_MATRIX,110,0,15,80123480,2.0,"
              "1,0,0,0,0,1,0,0,0,0,1,0,3.5,0,0,1")
    matrix2 = matrix.replace(",110,0,15,", ",111,0,23,").replace(",2.0,",",3.0,")
    return read_original_animation_log([bone,matrix,bone2,matrix2])


class OriginalAnimationArchiveTests(unittest.TestCase):
    def test_faithfully_roundtrips_original_bone_frames(self):
        data=sample()
        blob=encode_pose_archive(data)
        self.assertEqual(blob[:8],MAGIC)
        self.assertEqual(len(blob),HEADER.size+2*(FRAME.size+BONE.size))
        decoded=inspect_pose_archive(blob)
        self.assertEqual(decoded["frame_count"],2)
        self.assertEqual(decoded["original_bone_matrices"],2)
        first=decoded["frames"][0]
        self.assertEqual(first["original_game_frame"],110)
        self.assertEqual(first["character_id"],0)
        self.assertEqual(first["action_id"],15)
        self.assertEqual(first["limbs"][0]["gfx"],0x070024A8)
        self.assertEqual(first["limbs"][0]["matrix"][12],3.5)
        self.assertEqual(first["limbs"][0]["raw_transform"][:3],(100,100,100))
        self.assertEqual(decoded["frames"][1]["action_id"],23)

    def test_garbage_and_nonfinite_matrices_rejected(self):
        data=sample()
        with self.assertRaisesRegex(ValueError,"authentic"):
            encode_pose_archive({**data,"matrices_are_original_game_values":False})
        bad=bytearray(encode_pose_archive(data))
        bad[0]=0
        with self.assertRaisesRegex(ValueError,"magic"):
            inspect_pose_archive(bytes(bad))
        with self.assertRaisesRegex(ValueError,"truncated"):
            inspect_pose_archive(encode_pose_archive(data)[:-1])
        with self.assertRaisesRegex(ValueError,"length/count"):
            inspect_pose_archive(encode_pose_archive(data)+b"\0")
        first=sample()
        first["frames"][0]["limbs"][0]["matrix_global_D_801684B0"][0]=float("nan")
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            encode_pose_archive(first)

    def test_original_frames_not_reordered_or_interpolated(self):
        doc=sample()
        doc["frames"][0],doc["frames"][1]=doc["frames"][1],doc["frames"][0]
        with self.assertRaisesRegex(ValueError,"out of tick order"):
            encode_pose_archive(doc)
        doc=sample()
        doc["frames"][0]["limbs"].append(doc["frames"][0]["limbs"][0])
        with self.assertRaisesRegex(ValueError,"duplicated"):
            encode_pose_archive(doc)

    def test_raw_binary_size_and_field_order(self):
        blob=encode_pose_archive(sample())
        magic,nframes,nbones=HEADER.unpack_from(blob)
        self.assertEqual((magic,nframes,nbones),(MAGIC,2,2))
        tick,char,action,bone_count=FRAME.unpack_from(blob,HEADER.size)
        self.assertEqual((tick,char,action,bone_count),(110,0,15,1))
        orig,gfx,child,sibling,*tail=BONE.unpack_from(
            blob,HEADER.size+FRAME.size)
        self.assertEqual((orig,gfx,child,sibling),
                         (0x80123480,0x070024A8,1,0))
        self.assertEqual(tail[0:3],[100,100,100])
        self.assertEqual(tail[9+12],3.5)

if __name__=="__main__":
    unittest.main()
