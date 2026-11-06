#!/usr/bin/env python3
"""Find original action/animation table references to ROM-authored poses.

Read source MNSG AnimatedSkeleton headers (0x07), scan source character
groups + original game code for references to those exact 0x07 addresses
or packed 0x60000000 player-graphics pointers, as used in
Goemon64Recomp/patches/anime.c func_80016C44_17844.

Original clip/action mapping remains *unverified* until the exact
referencing instruction/table owner is established. Only pointer addresses
and counts are logged, not any code or copyrighted art bytes.
"""
from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from character_assets import read_file_table
from decompress_rom import decompress_us_rom
from source_aligned_character_assets import (
    source_align_character_files, CHARACTER_NAMES
)


def scan_source_animation_pointer_tables(
    decoded_rom:bytes, poses_dir:Path
) -> dict:
    groups=source_align_character_files(decoded_rom)
    table=read_file_table(decoded_rom)
    original_main=decoded_rom[:0x80000]
    results=[]
    for slot,name in enumerate(CHARACTER_NAMES[:3]):
        source=json.loads(
            (poses_dir/(name+"_original_source_poses.json"))
            .read_text(encoding="utf-8"))
        headers={}
        for item in source["original_source_poses"]:
            if item["source_header_segment"]!="0x07":
                continue
            at=item["source_header_offset"]
            headers[0x07000000+at]=item["candidate_number"]
        # Source code uses (graphics & 0x8FFFFFFE), where graphics is an
        # object-type-tagged 0x60000000 | segmented pointer.
        tagged={ptr|0x60000000:number for ptr,number in headers.items()}
        all_ptrs={**headers,**tagged}
        group=groups[slot]
        blobs={"original_main_code_data":original_main}
        for entry in group:
            file=table[entry.runtime_file_id]
            blobs[f"original_file_{entry.runtime_file_id}"] = (
                decoded_rom[file.start:file.end])
        occurrences=[]
        for blobname,data in blobs.items():
            # Scan aligned original big-endian word tables.
            for off in range(0,len(data)-3,4):
                word=struct.unpack_from(">I",data,off)[0]
                index=all_ptrs.get(word)
                if index is None:
                    continue
                occurrences.append({
                    "source_file":blobname,
                    "local_offset":off,
                    "pose_candidate_index":index,
                    "original_pointer_type":(
                        "0x60000000_player_object_type_tag"
                        if (word & 0x60000000)==0x60000000
                        else "0x07_segmented_pointer"
                    ),
                })
        counts=Counter(x["source_file"] for x in occurrences)
        paired={item["pose_candidate_index"] for item in occurrences}
        # Group four-byte-adjacent pointer references into probable
        # dispatch tables. This does not prove action IDs.
        tables=[]
        for filename in blobs:
            entries=sorted(
                (x for x in occurrences if x["source_file"]==filename),
                key=lambda x:x["local_offset"])
            run=[]
            for item in entries:
                if run and item["local_offset"] != run[-1]["local_offset"]+4:
                    if len(run)>=3:
                        tables.append({
                            "file":filename,
                            "offset":run[0]["local_offset"],
                            "entries":len(run),
                            "pose_indices":[p["pose_candidate_index"] for p in run],
                        })
                    run=[]
                run.append(item)
            if len(run)>=3:
                tables.append({
                    "file":filename,
                    "offset":run[0]["local_offset"],
                    "entries":len(run),
                    "pose_indices":[p["pose_candidate_index"] for p in run],
                })
        results.append({
            "character":name,
            "total_source_pose_headers":len(headers),
            "distinct_referenced_pose_headers":len(paired),
            "source_reference_count":len(occurrences),
            "references_by_source_file":dict(sorted(counts.items())),
            "potential_animation_dispatch_tables":tables[:20],
            "first_references":occurrences[:20],
            "original_action_ids_proven":False,
        })
    return {
        "analysis":"Original ROM direct source animation header references",
        "no_runtime_capture":True,
        "characters":results,
        "source_code_disassembly_uploaded":False,
    }


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--poses-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-poses"))
    p.add_argument("--output",type=Path)
    args=p.parse_args(argv)
    try:
        from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
        original=(args.rom or locate_rom()).read_bytes()
        if hashlib.sha256(original).hexdigest()!=ORIGINAL_SHA256:
            raise ValueError("wrong original source ROM")
        decoded=decompress_us_rom(original)
        if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
            raise ValueError("wrong original decompressed ROM")
        result=scan_source_animation_pointer_tables(decoded,args.poses_dir)
        for character in result["characters"]:
            print("GOEMON_OFFLINE_ACTION_POINTERS "+
                  json.dumps({
                      key:val for key,val in character.items()
                      if key!="first_references"
                  },separators=(",",":")))
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_OFFLINE_ACTION_POINTERS COMPLETE: no game capture")
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f"GOEMON_OFFLINE_ACTION_POINTERS FAILED: {exc}",file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
