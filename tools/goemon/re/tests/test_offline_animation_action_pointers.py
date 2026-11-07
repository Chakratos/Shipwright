"""Offline source ROM animation dispatch pointer search, all synthetic bytes."""
from pathlib import Path
import json
import tempfile
import sys
from unittest.mock import patch
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from character_assets import FileEntry
from source_aligned_character_assets import (
    SOURCE_SPLAT_GROUP_FILES,SourceAlignedFile
)
from offline_animation_action_pointers import (
    scan_source_animation_pointer_tables,scan_split_mips_pose_references
)


class SourceROMActionPointerTests(unittest.TestCase):
    def test_exact_split_mips_pointer_matches_without_claiming_action(self):
        # LUI t0,0x0700 ; ORI t1,t0,0x0048
        # LUI t2,0x6700 ; ADDIU t2,t2,0x0050
        blob=b"".join(x.to_bytes(4,"big") for x in (
            (0x0f<<26)|(8<<16)|0x0700,
            (0x0d<<26)|(8<<21)|(9<<16)|0x48,
            (0x0f<<26)|(10<<16)|0x6700,
            (0x09<<26)|(10<<21)|(10<<16)|0x50,
        ))
        found=scan_split_mips_pose_references(blob,{
            0x07000048:1,0x67000050:2})
        self.assertEqual([x["pose_candidate_index"] for x in found],[1,2])
        self.assertEqual([x["combinator"] for x in found],["ori","addiu"])
        self.assertTrue(all(not x["verified_executable_or_action_owner"]
                            for x in found))
        self.assertEqual(scan_split_mips_pose_references(blob,{
            0x07000049:2}),[])

    def test_real_segmented_and_tagged_pose_header_references(self):
        src={id:(offset,seg) for id,offset,seg
             in SOURCE_SPLAT_GROUP_FILES}
        table=[FileEntry(i,0,0) for i in range(304)]
        groups=[]
        for root in (288,292,296,300):
            group=[]
            for i in range(root,root+4):
                start,seg=src[i+1]
                end=src[i+2][0]
                table[i]=FileEntry(i,start,end)
                group.append(SourceAlignedFile(i,i+1,start,end-start,seg))
            groups.append(tuple(group))
        rom=bytearray(src[305][0])
        # Main has three consecutive original 0x07 pose header pointers.
        for i,at in enumerate((0x40,0x48,0x50)):
            rom[0x1000+i*4:0x1004+i*4]=(0x07000000+at).to_bytes(4,"big")
        # Goemon root file contains a type-tagged 0x60000000 pointer.
        loc=src[289][0]
        rom[loc+16:loc+20]=(0x67000040).to_bytes(4,"big")
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)
            for name in ("Goemon","Ebisumaru","Sasuke"):
                (path/(name+"_original_source_poses.json")).write_text(
                    json.dumps({
                        "original_source_poses":[
                            {"candidate_number":i,
                             "source_header_segment":"0x07",
                             "source_header_offset":off}
                            for i,off in enumerate((0x40,0x48,0x50))
                        ]
                    }),encoding="utf-8")
            with patch("offline_animation_action_pointers.read_file_table",
                       return_value=table):
                with patch("offline_animation_action_pointers.source_align_character_files",
                           return_value=tuple(groups)):
                    r=scan_source_animation_pointer_tables(bytes(rom),path)
        goemon=r["characters"][0]
        self.assertEqual(goemon["source_reference_count"],4)
        self.assertEqual(goemon["distinct_referenced_pose_headers"],3)
        self.assertEqual(goemon["references_by_source_file"]["original_main_code_data"],3)
        self.assertEqual(goemon["references_by_source_file"]["original_file_288"],1)
        self.assertEqual(len(goemon["potential_animation_dispatch_tables"]),1)
        self.assertEqual(goemon["potential_animation_dispatch_tables"][0]["entries"],3)
        self.assertEqual(goemon["potential_animation_dispatch_tables"][0]["pose_indices"],[0,1,2])
        self.assertFalse(goemon["original_action_ids_proven"])
        self.assertEqual(goemon["split_mips_pointer_candidate_count"],0)
        self.assertEqual(len(r["characters"]),3)
        self.assertTrue(r["no_runtime_capture"])

if __name__=="__main__":
    unittest.main()
