"""Byte-accurate original animation archive, raw channel tags, no invented frames."""
import struct
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from archive_original_animation_streams import (
    MAGIC,HEADER,CLIP,LIMB,extract_original_candidate_animation,
    create_original_animation_archive,inspect_original_animation_archive
)


def fixture():
    b=bytes((x*19+7)%256 for x in range(512))
    pose={
        "candidate_number":0,
        "source_header_segment":"0x07",
        "source_header_offset":0x140,
        "original_animated_skeleton_flags":"0x80000111",
        "original_animation_pointer":"0x07000000",
        "original_skeleton_root":"0x07000100",
        "limbs":[
            {"ptr":0x07000100,"parent":None,"gfx":0,
             "scale":(-20224,-20224,-20224),
             "rotation":(-20480,-20480,-20480),
             "translation":(-20480,-20480,-20480)},
            {"ptr":0x07000118,"parent":0x07000100,"gfx":0x09000020,
             "scale":(-20224,-20224,-20224),
             "rotation":(80,103,126),
             "translation":(149,172,195)}
        ]
    }
    return b,{"format":"ng5e-original-rom-skeletal-poses-v1",
              "original_source_poses":[pose]}


class OriginalAnimationArchiveTests(unittest.TestCase):
    def test_raw_animation_payload_exactly_matches_original_rom_segment(self):
        image,doc=fixture()
        payload,nodes=extract_original_candidate_animation(
            doc["original_source_poses"][0],image)
        self.assertEqual(payload,image[:0x100])
        self.assertEqual(len(nodes),2)
        self.assertEqual(nodes[0][3][0],-20224)
        self.assertEqual(nodes[1][3][4],103)

        archive=create_original_animation_archive(0,doc,image)
        self.assertEqual(archive[:8],MAGIC)
        self.assertEqual(HEADER.unpack_from(archive),(MAGIC,0,1))
        header=CLIP.unpack_from(archive,HEADER.size)
        self.assertEqual(header,(
            0x07000140,0x80000111,0x07000000,0x07000100,256,2
        ))
        self.assertEqual(archive[HEADER.size+CLIP.size:
                                 HEADER.size+CLIP.size+256],payload)
        summary=inspect_original_animation_archive(archive)
        self.assertEqual(summary["source_animation_descriptor_count"],1)
        self.assertEqual(summary["raw_compressed_animation_bytes"],256)
        self.assertEqual(summary["encoded_channel_markers"]["0xB000"],6)
        self.assertEqual(summary["encoded_channel_markers"]["0xB100"],6)
        self.assertFalse(summary["original_decoder_fully_ported"])
        self.assertFalse(summary["real_action_timing_known"])
        self.assertEqual(len(archive),HEADER.size+CLIP.size+256+2*LIMB.size)

    def test_corrupt_source_or_hierarchy_rejected(self):
        image,doc=fixture()
        payload=create_original_animation_archive(0,doc,image)
        with self.assertRaisesRegex(ValueError,"truncated"):
            inspect_original_animation_archive(payload[:-4])
        with self.assertRaisesRegex(ValueError,"trailing"):
            inspect_original_animation_archive(payload+b"\0")
        doc["original_source_poses"][0]["limbs"][1]["parent"]=0x07000220
        with self.assertRaisesRegex(ValueError,"parent"):
            create_original_animation_archive(0,doc,image)

    def test_out_of_bounds_original_animation_payload_rejected(self):
        image,doc=fixture()
        doc["original_source_poses"][0]["original_animation_pointer"]="0x07000400"
        with self.assertRaisesRegex(ValueError,"stream location"):
            create_original_animation_archive(0,doc,image)

    def test_rejects_unverified_source_data(self):
        image,doc=fixture()
        doc["format"]="not-original-rom"
        with self.assertRaisesRegex(ValueError,"wrong original"):
            create_original_animation_archive(0,doc,image)


if __name__=="__main__":
    unittest.main()
