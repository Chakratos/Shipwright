#!/usr/bin/env python3
"""Classify Yae's actual source-0x07 animation structures before bank matching.

This scanner intentionally does not require a guessed 0x09 bank to traverse
a Skeleton node. It enumerates candidate headers in the source-aligned 0x07
resource and reports the *actual encoded* limb Gfx pointer segments.
A structurally consistent tree is NOT proof of the active player rig.
No source ROM bytes or instructions leave the private Windows runner.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from source_aligned_character_assets import source_align_character_files
from character_assets import read_file_table
from decompress_rom import decompress_us_rom

_ANIMATED=struct.Struct(">III")
_SKELETON=struct.Struct(">Ibb9h")


def traverse_yae_bank07_unresolved_skeletons(
    bank07:bytes,root:int,max_nodes:int=128
)->list[tuple[int,int]]:
    if root>>24!=7:
        raise ValueError("root not in original Yae 0x07 bank")
    pending=[root]
    visited=set()
    limbs=[]
    while pending:
        current=pending.pop()
        offset=current&0xFFFFFF
        if (current>>24)!=7 or offset%4 or offset+_SKELETON.size>len(bank07):
            raise ValueError("unresolvable original Yae Skeleton link")
        if current in visited or len(visited)>=max_nodes:
            raise ValueError("cyclic or excessively large source Skeleton tree")
        visited.add(current)
        gfx,right,left,*_= _SKELETON.unpack_from(bank07,offset)
        limbs.append((current,gfx))
        if left:
            pending.append(current+24*left)
        if right:
            pending.append(current+24*right)
    return limbs


def traverse_yae_source07_animation_nodes(
    bank07:bytes,root:int,max_nodes:int=128
)->list[dict]:
    """Return original 24-byte Skeleton records with correct node links.

    Source Gfx pointers, including 0x29 tags and unresolved 0x0F records,
    remain EXACT raw words. They are not reinterpreted as physical S/R/T
    or silently dropped from the candidate animation source archive.
    """
    if root>>24!=7:
        raise ValueError("Yae animation root not in 0x07")
    todo=[(root,None)]
    visited=set()
    out=[]
    while todo:
        current,parent=todo.pop()
        offset=current&0xFFFFFF
        if current>>24!=7 or offset%4 or offset+_SKELETON.size>len(bank07):
            raise ValueError("Yae source animation Skeleton pointer outside 0x07")
        if current in visited or len(visited)>=max_nodes:
            raise ValueError("Yae source animation Skeleton cycle or size limit")
        visited.add(current)
        gfx,right,left,*raw=_SKELETON.unpack_from(bank07,offset)
        out.append({
            "ptr":current,"parent":parent,"gfx":gfx,
            "scale":tuple(raw[0:3]),
            "rotation":tuple(raw[3:6]),
            "translation":tuple(raw[6:9]),
        })
        if left:
            todo.append((current+24*left,parent))
        if right:
            todo.append((current+24*right,current))
    return out


def build_yae_source_animation_catalog(bank07:bytes)->dict:
    """Preserve candidate animation data without claiming valid gameplay clips."""
    if len(bank07)<_ANIMATED.size+_SKELETON.size:
        raise ValueError("Yae original bank too short")
    candidates=[]
    root_seen=set()
    skipped=Counter()
    for offset in range(0,len(bank07)-_ANIMATED.size+1,4):
        flags,anim,root=_ANIMATED.unpack_from(bank07,offset)
        if not 1<=((flags>>8)&0x7FFF)<=128 or anim>>24!=7 or root>>24!=7:
            continue
        if root in root_seen:
            skipped["duplicate_skeleton_root"]+=1
            continue
        try:
            limbs=traverse_yae_source07_animation_nodes(bank07,root)
        except ValueError:
            skipped["invalid_graph"]+=1
            continue
        if len(limbs)<4:
            continue
        begin=anim&0xFFFFFF
        first_limb=min(n["ptr"]&0xFFFFFF for n in limbs)
        if not 0<=begin<=first_limb<=len(bank07) or first_limb-begin>1024*1024:
            skipped["unresolved_source_animation_region"]+=1
            continue
        root_seen.add(root)
        candidates.append({
            "candidate_number":len(candidates),
            "source_header_segment":"0x07",
            "source_header_offset":offset,
            "original_animated_skeleton_flags":f"0x{flags:08X}",
            "original_animation_pointer":f"0x{anim:08X}",
            "original_skeleton_root":f"0x{root:08X}",
            "limbs":limbs,
            "original_action_id":None,
            "animation_frame_index":None,
            "raw_animation_channel_fields_preserved":True,
            "active_player_ownership_verified":False,
        })
    if not candidates:
        raise ValueError("no source-validated Yae animation descriptor regions")
    return {
        "character":"Yae",
        "format":"ng5e-original-rom-skeletal-poses-v1",
        "original_source_poses":candidates,
        "excluded_candidates":dict(skipped),
        "original_animation_frames_recovered":0,
        "actual_gameplay_action_ids_verified":False,
    }


def characterize_yae_bank07(bank07:bytes)->dict:
    if len(bank07)<_SKELETON.size+_ANIMATED.size:
        raise ValueError("original Yae 0x07 bank truncated")
    root_segments=Counter()
    graphics_segments=Counter()
    animation_segments=Counter()
    candidate_sizes=Counter()
    records=[]
    structural=0
    for offset in range(0,len(bank07)-_ANIMATED.size+1,4):
        flags,animation,root=_ANIMATED.unpack_from(bank07,offset)
        flags_hint=(flags>>8)&0x7FFF
        if not 1<=flags_hint<=128 or (root>>24)!=7:
            continue
        if animation and animation>>24 not in (7,8,9):
            continue
        try:
            limbs=traverse_yae_bank07_unresolved_skeletons(bank07,root)
        except ValueError:
            continue
        if len(limbs)<4:
            continue
        gfx_segments=Counter(ptr>>24 for _,ptr in limbs if ptr!=0)
        if not gfx_segments:
            continue
        structural+=1
        root_segments[f"0x{root>>24:02X}"]+=1
        animation_segments[f"0x{animation>>24:02X}"]+=1
        graphics_segments.update({f"0x{seg:02X}":v for seg,v in gfx_segments.items()})
        candidate_sizes[len(limbs)]+=1
        if len(records)<24:
            records.append({
                "header_offset":offset,
                "limb_count":len(limbs),
                "flags_upper_byte":f"0x{flags>>24:02X}",
                "animation_segment":f"0x{animation>>24:02X}",
                "root_segment":f"0x{root>>24:02X}",
                "limb_gfx_segments":{f"0x{key:02X}":val for key,val
                                     in sorted(gfx_segments.items())},
                "player_identity_not_confirmed":True,
            })
    return {
        "resource":"Yae source 0x07",
        "structurally_traversable_headers":structural,
        "original_header_root_segments":dict(sorted(root_segments.items())),
        "candidate_animation_segments":dict(sorted(animation_segments.items())),
        "original_limb_graphics_pointer_segments":dict(sorted(graphics_segments.items())),
        "source_skeleton_limb_counts":dict(sorted(candidate_sizes.items())),
        "first_candidate_metadata":records,
        "gameplay_action_mapping_verified":False,
        "graphics_09_bank_residency_verified":False,
        "source_animation_codec_decoded":False,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-yae-source07-pointers.json"))
    args=p.parse_args(argv)
    try:
        from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
        rom=(args.rom or locate_rom()).read_bytes()
        if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
            raise ValueError("original NG5E ROM SHA-256 mismatch")
        decoded=decompress_us_rom(rom)
        if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
            raise ValueError("original decompressed NG5E ROM SHA-256 mismatch")
        files=source_align_character_files(decoded)[3]
        source07=files[2]
        if source07.source_segment!=7:
            raise ValueError("Yae source segment 0x07 not verified")
        file=read_file_table(decoded)[source07.runtime_file_id]
        report=characterize_yae_bank07(decoded[file.start:file.end])
        out=args.output.resolve()
        checkout=Path(__file__).resolve().parents[3]
        if out==checkout or checkout in out.parents:
            raise ValueError("ROM pointer report cannot be placed in Git source")
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        summary={k:v for k,v in report.items()
                 if k not in ("first_candidate_metadata",)}
        print("GOEMON_YAE_SOURCE07 "+json.dumps(summary,separators=(",",":")))
        print("GOEMON_YAE_SOURCE07 COMPLETE: no asset uploads")
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("GOEMON_YAE_SOURCE07 FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
