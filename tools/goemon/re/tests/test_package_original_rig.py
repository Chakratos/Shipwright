"""Original NG5E 3D source rig binary exact round-trip (synthetic input only)."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_f3dex_geometry import N64Mesh,N64Vertex
from package_original_rig import (
    MAGIC,HEADER,MESH_HEADER,POSE_HEADER,LIMB,
    create_original_rig_package,inspect_original_rig_package
)


def fixture():
    vertices=tuple(
        N64Vertex(x,y,z,0,s,t,255,180,80,255)
        for x,y,z,s,t in (
            (3,4,5,0,0),(13,14,15,32,0),(23,24,25,0,32)))
    meshes={
        "0x09000020":N64Mesh(vertices,((0,1,2),),0x09000020,5,{})
    }
    catalog={
        "format":"ng5e-original-rom-skeletal-poses-v1",
        "original_source_poses":[
            {
                "source_header_segment":"0x07",
                "source_header_offset":0x63C,
                "original_animated_skeleton_flags":"0x80000111",
                "limbs":[
                    {"ptr":0x070005C4,"parent":None,"gfx":0,
                     "scale":(256,256,256),"rotation":(0,0,0),
                     "translation":(0,0,0)},
                    {"ptr":0x070005DC,"parent":0x070005C4,"gfx":0x09000020,
                     "scale":(256,256,256),"rotation":(0,128,0),
                     "translation":(15,5,4)}
                ]
            },
            {
                "source_header_segment":"0x07",
                "source_header_offset":0xCB8,
                "original_animated_skeleton_flags":"0x80000119",
                "limbs":[
                    {"ptr":0x07000C40,"parent":None,"gfx":0,
                     "scale":(256,256,256),"rotation":(0,0,0),
                     "translation":(0,0,0)},
                    {"ptr":0x07000C58,"parent":0x07000C40,"gfx":0x09000020,
                     "scale":(256,256,256),"rotation":(0,256,0),
                     "translation":(15,5,4)}
                ]
            },
        ]
    }
    return catalog,meshes


class OriginalSourceRigPackageTests(unittest.TestCase):
    def test_actual_source_fields_roundtrip_through_n64_mesh_and_pose_bytes(self):
        poses,meshes=fixture()
        binary=create_original_rig_package(0,poses,meshes)
        self.assertEqual(binary[:8],MAGIC)
        self.assertEqual(HEADER.unpack_from(binary),(MAGIC,0,1,2))
        self.assertEqual(MESH_HEADER.unpack_from(binary,HEADER.size),
                         (0x09000020,1))
        self.assertEqual(POSE_HEADER.unpack_from(
            binary,HEADER.size+MESH_HEADER.size+48),
            (0x0700063C,0x80000111,2))
        info=inspect_original_rig_package(binary)
        self.assertEqual(info["character_id"],0)
        self.assertEqual(info["rig_pose_count"],2)
        self.assertEqual(info["decoded_original_mesh_roots"],1)
        self.assertEqual(info["source_triangle_count"],1)
        self.assertEqual(info["first_original_pose_limb_count"],2)
        self.assertEqual(info["first_original_limb_raw_transform"][:3],
                         (256,256,256))
        self.assertFalse(info["original_action_timing_extracted"])

    def test_original_mesh_payload_is_untampered_big_endian_n64_vtx(self):
        p,m=fixture()
        encoded=create_original_rig_package(0,p,m)
        at=HEADER.size+MESH_HEADER.size
        self.assertEqual(encoded[at:at+6],
                         struct.pack(">hhh",3,4,5))
        self.assertEqual(encoded[at+16:at+22],
                         struct.pack(">hhh",13,14,15))

    def test_archive_rejects_wrong_magic_truncation_and_duplicate_meshes(self):
        p,m=fixture()
        encoded=create_original_rig_package(0,p,m)
        broken=bytearray(encoded);broken[0]=0
        with self.assertRaisesRegex(ValueError,"header"):
            inspect_original_rig_package(bytes(broken))
        with self.assertRaisesRegex(ValueError,"truncated"):
            inspect_original_rig_package(encoded[:-6])
        with self.assertRaisesRegex(ValueError,"trailing"):
            inspect_original_rig_package(encoded+b"\0")
        p["original_source_poses"][0]["limbs"][1]["parent"]=0x07000111
        with self.assertRaisesRegex(ValueError,"hierarchy"):
            create_original_rig_package(0,p,m)

    def test_no_fake_source_pose_or_player_clip_accepted(self):
        p,m=fixture()
        p["format"]="manual-created-fake"
        with self.assertRaisesRegex(ValueError,"ROM-authored"):
            create_original_rig_package(0,p,m)
        p,m=fixture()
        p["original_source_poses"][0]["source_header_segment"]="0x08"
        with self.assertRaisesRegex(ValueError,"unverified"):
            create_original_rig_package(0,p,m)


if __name__=="__main__":
    unittest.main()
