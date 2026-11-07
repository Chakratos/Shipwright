"""Strict synthetic pairing of real-CPU sample schema and GOSKEL01 layout."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from package_original_mips_samples import (
    HEADER,LIMB,MATRIX,build_original_isolated_mips_binary,
    inspect_original_isolated_mips_binary,
)
from test_verify_original_rig_animation_pair import pair

def fixture():
    rig,_=pair(slot=3)
    s0=[0]*16
    s1=[0]*16
    for n in (0,5,10,15):s0[n]=s1[n]=0x3F800000
    s1[12]=0x41200000
    raw0=[-20224]*3+[-20480]*6
    raw1=[256]*3+[0]*6
    meta={
        "format":"goemon-owner-rom-original-mips-isolated-bone-matrices-v2",
        "original_mtxf_output_pointer_global":"D_80168530",
        "output_stack_separate_from_current_mtxf":True,
        "previous_alias_based_matrix_samples_invalidated":True,
        "character":"Yae","character_slot":3,
        "source_original_skeleton_header":"0x07000140",
        "original_animated_skeleton_flags":"0x80000111",
        "controlled_animation_progress_values":[0.0,1.0],
        "source_game_action_verified":False,
        "source_tick_mapping_verified":False,
        "parent_world_composition_verified":False,
        "engine_matrix_memory_layout_verified":False,
        "limbs":[{
            "source_limb_pointer":"0x07000100","raw_original_gfx_pointer":"0x0F000120",
            "source_parent_pointer":None,"source_raw_srt_channels":raw0,
            "samples":[
                {"original_animation_progress":0.0,"matrix_ieee754_u32":s0},
                {"original_animation_progress":1.0,"matrix_ieee754_u32":s0}
            ]
        },{
            "source_limb_pointer":"0x07000118","raw_original_gfx_pointer":"0x29000020",
            "source_parent_pointer":"0x07000100","source_raw_srt_channels":raw1,
            "samples":[
                {"original_animation_progress":0.0,"matrix_ieee754_u32":s0},
                {"original_animation_progress":1.0,"matrix_ieee754_u32":s1}
            ]
        }]
    }
    return rig,meta

class NativeSourceMipsPackageTests(unittest.TestCase):
    def test_exact_original_source_matrix_and_tagged_yae_gfx(self):
        rig,meta=fixture()
        encoded=build_original_isolated_mips_binary(rig,meta)
        self.assertEqual(len(encoded),HEADER.size+2*(LIMB.size+2*MATRIX.size))
        report=inspect_original_isolated_mips_binary(encoded)
        self.assertEqual(report["character"],"Yae")
        self.assertEqual(report["valid_original_mips_matrices"],4)
        self.assertFalse(report["gameplay_ready"] if "gameplay_ready" in report
                         else report["original_animation_action_verified"])
        self.assertEqual(LIMB.unpack_from(encoded,HEADER.size)[1],0x0F000120)
        self.assertEqual(LIMB.unpack_from(encoded,
            HEADER.size+LIMB.size+2*MATRIX.size)[1],0x29000020)
    def test_missing_original_cpu_matrix_preserved_not_fabricated(self):
        rig,meta=fixture()
        meta["limbs"][1]["samples"][1].pop("matrix_ieee754_u32")
        meta["limbs"][1]["samples"][1]["blocker"]="original CPU runtime context"
        blob=build_original_isolated_mips_binary(rig,meta)
        report=inspect_original_isolated_mips_binary(blob)
        self.assertEqual(report["blocked_original_mips_matrices"],1)
        self.assertEqual(report["valid_original_mips_matrices"],3)
        self.assertEqual(MATRIX.unpack_from(blob,len(blob)-MATRIX.size),(0,)*16)
    def test_mismatched_source_header_channels_parents_rejected(self):
        rig,base=fixture()
        for issue in ("source_original_skeleton_header","source_raw_srt_channels",
                      "source_parent_pointer"):
            import copy
            meta=copy.deepcopy(base)
            if issue=="source_original_skeleton_header":
                meta[issue]="0x07000300"
            elif issue=="source_raw_srt_channels":
                meta["limbs"][1][issue][0]=42
            else:
                meta["limbs"][1][issue]=None
            with self.assertRaisesRegex(ValueError,"source MIPS|original"):
                build_original_isolated_mips_binary(rig,meta)
    def test_old_alias_based_source_matrices_not_accepted(self):
        rig,meta=fixture()
        meta["format"]="goemon-owner-rom-original-mips-isolated-bone-matrices-v1"
        with self.assertRaisesRegex(ValueError,"not current"):
            build_original_isolated_mips_binary(rig,meta)
        meta["format"]="goemon-owner-rom-original-mips-isolated-bone-matrices-v2"
        meta["output_stack_separate_from_current_mtxf"]=False
        with self.assertRaisesRegex(ValueError,"obsolete aliased"):
            build_original_isolated_mips_binary(rig,meta)

    def test_corrupted_binary_mask_and_trailing_rejected(self):
        rig,meta=fixture()
        binary=build_original_isolated_mips_binary(rig,meta)
        with self.assertRaisesRegex(ValueError,"length"):
            inspect_original_isolated_mips_binary(binary+b"\0")
        bad=bytearray(binary)
        # Limb status mask at +10 in packed 30-byte limb metadata.
        bad[HEADER.size+10]=4
        with self.assertRaisesRegex(ValueError,"identifier"):
            inspect_original_isolated_mips_binary(bytes(bad))

if __name__=="__main__":
    unittest.main()
