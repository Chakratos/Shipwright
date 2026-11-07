#!/usr/bin/env python3
"""Extract original ROM-authored skeletal pose records WITHOUT gameplay capture.

Reads the verified decompressed NG5E ROM and exact source-aligned 0x07/0x09
character resource segments. Outputs complete original 24-byte Skeleton limb
trees with signed S/R/T, a source AnimatedSkeleton flags record, its animation
pointer and N64 graphics pointers. No procedural/keyframe interpolation.

Data semantics: original *pose descriptors*, not proven timeline/frame or
action IDs. The game animator's exact update logic must still be ported
from its original MIPS instructions before character animation playback.

Output only onto user's local Windows PC, outside the Git checkout.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from character_assets import read_file_table
from decompress_rom import decompress_us_rom
from offline_original_rigs import (
    candidate_animated_skeletons, traverse_original_skeleton,
    scan_yae_shared_09_hypotheses
)
from source_aligned_character_assets import (
    source_align_character_files, CHARACTER_NAMES
)


def inspect_source_pose_bank(banks: dict[int,bytes],
                             *, character: str) -> dict:
    report=candidate_animated_skeletons(
        banks, min_limbs=4, max_candidates=512)
    clips=[]
    signatures=defaultdict(list)
    pose_signatures=defaultdict(list)
    for n,item in enumerate(report["first_valid_candidates"]):
        ptr=int(item["root_skeleton_pointer"],16)
        graph=traverse_original_skeleton(ptr,banks)
        nodes=graph["nodes"]
        if len(nodes) != item["actual_traversed_limbs"]:
            raise ValueError("original skeleton graph changed during export")
        # One graphic pointer per rigid body part; preserve exact
        # character-specific 0x09 segmented source pointers.
        gfx_layout=tuple(
            (node["relation"],node["child"],node["sibling"],node["gfx"])
            for node in nodes)
        pose=tuple(
            (*node["scale"], *node["rotation"], *node["translation"])
            for node in nodes)
        layout_hash=hashlib.sha256(
            repr(gfx_layout).encode("ascii")).hexdigest()[:16]
        pose_hash=hashlib.sha256(
            repr(pose).encode("ascii")).hexdigest()[:16]
        record={
            "candidate_number":n,
            "source_header_segment":item["header_segment"],
            "source_header_offset":item["header_offset"],
            "original_animated_skeleton_flags":item["flags"],
            "original_animation_pointer":item["animation_pointer"],
            "original_skeleton_root":item["root_skeleton_pointer"],
            "original_low_byte_parameter":int(item["flags"],16)&0xFF,
            "source_limb_count":len(nodes),
            "source_graphic_parts":graph["graphics_limb_count"],
            "graphics_layout_sha256_prefix":layout_hash,
            "pose_values_sha256_prefix":pose_hash,
            "limbs":nodes,
            "animation_frame_index":None,
            "original_action_id":None,
            "animation_clip_owner":None,
            "raw_animation_channel_fields_preserved":True,
            "literal_affine_transforms_decoded":False,
            "animation_timeline_decoded":False,
        }
        clips.append(record)
        signatures[layout_hash].append(n)
        pose_signatures[pose_hash].append(n)

    return {
        "character":character,
        "format":"ng5e-original-rom-skeletal-poses-v1",
        "origin":"Original unmodified ROM source-aligned 0x07/0x09 files",
        "structurally_valid_poses":len(clips),
        "distinct_graphics_layouts":len(signatures),
        "distinct_raw_transform_poses":len(pose_signatures),
        "graphics_layout_groups":{
            k:list(v) for k,v in sorted(signatures.items())
        },
        "original_source_poses":clips,
        "actual_animation_frames_recovered":0,
        "gameplay_capture_required":False,
        "note":"Source 16-bit fields are raw encoded animation-channel controls (not proven physical S/R/T). Actual transforms, timing and actions require original func_800192D0 MIPS decode."
    }


def export_offline_original_poses(rom:bytes, destination:Path) -> dict:
    from real_rom_check import ORIGINAL_SHA256, DECOMPRESSED_SHA256
    if hashlib.sha256(rom).hexdigest() != ORIGINAL_SHA256:
        raise ValueError("not verified original NG5E ROM")
    decoded=decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest() != DECOMPRESSED_SHA256:
        raise ValueError("not verified original decompressed NG5E ROM")
    groups=source_align_character_files(decoded)
    table=read_file_table(decoded)
    project=Path(__file__).resolve().parents[3]
    output=destination.expanduser().resolve()
    if output == project or project in output.parents:
        raise ValueError("original assets must stay outside Git checkout")
    output.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for slot, group in enumerate(groups):
        banks={}
        for file in group[2:4]:
            entry=table[file.runtime_file_id]
            banks[file.source_segment] = decoded[entry.start:entry.end]
        # Yae's segment 9 is absent from its contiguous group and
        # cannot be conclusively assigned without analyzing overlay lifetime.
        # Do not pretend it has zero animation assets, just mark unresolved.
        if slot==3:
            summary={
                "character":CHARACTER_NAMES[slot],
                "source_0x07_runtime_file":group[2].runtime_file_id,
                "source_0x08_runtime_file":group[3].runtime_file_id,
                "status":"pending_segment09_graphics_lifetime",
                "candidate_shared_segment09":scan_yae_shared_09_hypotheses(decoded),
            }
            (output/"Yae_source_status.json").write_text(
                json.dumps(summary,indent=2)+"\n",encoding="utf-8")
            summaries.append(summary)
            continue
        doc=inspect_source_pose_bank(banks,character=CHARACTER_NAMES[slot])
        doc["source_segments"]= {
            f"0x{file.source_segment:02X}":file.runtime_file_id
            for file in group[2:4]}
        target=output/(CHARACTER_NAMES[slot]+"_original_source_poses.json")
        target.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
        summaries.append({
            "character":doc["character"],
            "original_pose_records":doc["structurally_valid_poses"],
            "distinct_raw_transform_poses":doc["distinct_raw_transform_poses"],
            "distinct_graphics_layouts":doc["distinct_graphics_layouts"],
            "file_name":target.name,
            "action_timing_verified":False,
        })
    result={
        "schema":"ng5e-rom-original-skeletal-poses-local-v1",
        "characters":summaries,
        "original_source_rom_sha256":hashlib.sha256(rom).hexdigest(),
        "output_location":str(output),
        "source_animation_timelines_ready":False,
        "original_rom_data_uploaded":False,
        "runtime_capture_performed":False
    }
    (output/"catalog_summary.json").write_text(
        json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom",type=Path)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        from real_rom_check import locate_rom
        path=args.rom or locate_rom()
        report=export_offline_original_poses(path.read_bytes(),args.output_dir)
        for item in report["characters"]:
            print("GOEMON_OFFLINE_SOURCE_POSES "+json.dumps(
                item,separators=(",",":")))
        print("GOEMON_OFFLINE_SOURCE_POSES COMPLETE: ROM-derived skeletal transforms, no capture/upload")
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(f"GOEMON_OFFLINE_SOURCE_POSES FAILED: {e}",file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
