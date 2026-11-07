#!/usr/bin/env python3
"""Analyze original MNSG animation *channel indirection*, not fake poses.

The 24-byte Skeleton fields may contain encoded channel selectors, not final
positions. Examples observed in the REAL original NG5E ROM:
  scale:    0xB100 0xB100 0xB100
  rotation: 0xB000 0xB000 0xB000
  later rotation channels: 762, 785, 808, ... (nearby increasing offsets)
These are NOT credible literal affine transforms. Decomp source calls
func_800192D0_19ED0 to evaluate them, using AnimatedSkeleton.animation
and Object.animation_progress.

This script relates each source animation pointer, the lowest reachable
Skeleton record, and the raw 16-bit channel selectors to ORIGINAL ROM bytes.
It DOES NOT claim a decoded clip/timing until the MIPS math is recovered.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Mapping

CHANNEL_MARKERS=(0xB000,0xB100)
CHANNEL_FIELD_NAMES=(
    "scale.x","scale.y","scale.z",
    "rotation.x","rotation.y","rotation.z",
    "translation.x","translation.y","translation.z",
)


def analyze_raw_original_animation_descriptors(
    source_pose:dict, source_07:bytes
) ->dict:
    if source_pose.get("format")!="ng5e-original-rom-skeletal-poses-v1":
        raise ValueError("not original NG5E source Skeleton catalog")
    if len(source_07)<24:
        raise ValueError("original source 0x07 data too short")
    report=[]
    total=Counter()
    source_len=len(source_07)
    for pose in source_pose["original_source_poses"]:
        if pose["source_header_segment"]!="0x07":
            continue
        root=int(pose["original_skeleton_root"],16)
        anim=int(pose["original_animation_pointer"],16)
        if root>>24!=7 or anim>>24!=7:
            continue
        header=int(pose["source_header_offset"])
        nodes=pose["limbs"]
        if not nodes:
            continue
        lowest=min(node["ptr"]&0xFFFFFF for node in nodes)
        highest=max(node["ptr"]&0xFFFFFF for node in nodes)
        start=anim&0xFFFFFF
        if not (0<=start<=lowest<=highest+24<=source_len
                and highest+24<=header+12):
            # Do not promote a coincidental Skeleton-shaped byte sequence.
            total["invalid_animation_or_skeleton_region"]+=1
            continue
        # The stream may include fixed-size clip headers; source packet
        # boundaries are an observation, not an asserted channel codec.
        sample_bytes=lowest-start
        refs=[]
        sentinels=Counter()
        negative_other=Counter()
        for node in nodes:
            for name,field in zip(CHANNEL_FIELD_NAMES,
                                  (*node["scale"],*node["rotation"],
                                   *node["translation"])):
                if not -32768<=field<=32767:
                    raise ValueError("original channel field outside signed 16-bit")
                unsigned=field&0xFFFF
                if unsigned&0xFF00 in CHANNEL_MARKERS:
                    sentinels[f"0x{unsigned&0xFF00:04X}"]+=1
                elif field>=0:
                    refs.append({
                        "field":name,"offset":field,
                        "inside_animation_payload":field<sample_bytes,
                        "inside_source_segment":start+field<source_len,
                    })
                else:
                    negative_other[f"0x{unsigned:04X}"]+=1
        in_bounds=sum(x["inside_animation_payload"] for x in refs)
        total["source_descriptor_candidates"]+=1
        total["numeric_channel_references"]+=len(refs)
        total["references_inside_candidate_payload"]+=in_bounds
        total["0xB000_markers"]+=sentinels.get("0xB000",0)
        total["0xB100_markers"]+=sentinels.get("0xB100",0)
        total["unclassified_negative_words"]+=sum(negative_other.values())
        offsets=sorted({x["offset"] for x in refs if
                        x["inside_animation_payload"]})
        gaps=[b-a for a,b in zip(offsets,offsets[1:])]
        entry={
            "candidate_number":pose["candidate_number"],
            "header_pointer":f"0x{0x07000000|header:08X}",
            "animation_pointer":f"0x{anim:08X}",
            "lowest_reachable_skeleton_byte":lowest,
            "candidate_animation_payload_length":sample_bytes,
            "original_flags":pose["original_animated_skeleton_flags"],
            "original_limb_count":len(nodes),
            "channel_fields":len(nodes)*9,
            "tagged_fields":sum(sentinels.values()),
            "tags":dict(sentinels),
            "negative_other":dict(negative_other),
            "numeric_channel_refs":len(refs),
            "numeric_refs_in_bounds":in_bounds,
            "unique_referenced_offsets":len(offsets),
            "most_common_neighboring_offset_gaps":
                Counter(gaps).most_common(6),
            "first_10_channel_refs":refs[:10],
            "original_keyframe_encoding_decoded":False,
            "original_action_id_verified":False,
        }
        report.append(entry)
    return {
        "character":source_pose["character"],
        "original_animation_descriptors":len(report),
        "stats":dict(total),
        "first_descriptors":report[:8],
        "all_descriptors":report,
        "mips_decoder_source":"func_800192D0_19ED0",
        "anim_data_are_uninterpreted_rom_bytes":True,
        "literal_scale_rotation_claim_valid":False,
    }


def summarize_channel_anomalies(report:dict)->dict:
    source=report["stats"]
    total=source.get("numeric_channel_references",0)
    in_bounds=source.get("references_inside_candidate_payload",0)
    return {
        "character":report["character"],
        "descriptors":report["original_animation_descriptors"],
        "numeric_channel_offsets":total,
        "inside_candidate_animation_payload":in_bounds,
        "fraction_inside":round(in_bounds/total,5) if total else None,
        "marker_B000":source.get("0xB000_markers",0),
        "marker_B100":source.get("0xB100_markers",0),
        "unclassified_negative":source.get("unclassified_negative_words",0),
        "original_clip_decoder_complete":False,
    }
