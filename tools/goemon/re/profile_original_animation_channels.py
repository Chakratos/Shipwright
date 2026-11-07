#!/usr/bin/env python3
"""Profile genuine original compressed animation channel descriptors on owner PC.

Original ROM and source-authored 261 candidate AnimatedSkeleton structures
remain local. Emits short metadata to CI; full report stored locally only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
from decompress_rom import decompress_us_rom
from character_assets import read_file_table
from source_aligned_character_assets import source_align_character_files
from analyze_original_animation_channels import (
    analyze_raw_original_animation_descriptors,summarize_channel_anomalies
)


def profile_original_animation(rom:bytes, poses_dir:Path)->dict:
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("not the user's source-verified original ROM")
    image=decompress_us_rom(rom)
    if hashlib.sha256(image).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("source decompressed ROM failed authenticity check")
    source=source_align_character_files(image)
    files=read_file_table(image)
    characters=[]
    for slot,name in enumerate(("Goemon","Ebisumaru","Sasuke")):
        source07=source[slot][2]
        if source07.source_segment!=7:
            raise ValueError("wrong MNSG 0x07 animation/Skeleton source segment")
        entry=files[source07.runtime_file_id]
        data=image[entry.start:entry.end]
        poses=json.loads((poses_dir/(name+"_original_source_poses.json"))
                         .read_text("utf-8"))
        report=analyze_raw_original_animation_descriptors(poses,data)
        characters.append(report)
    return {
        "format":"ng5e-original-animation-channel-hypotheses-v1",
        "characters":characters,
        "original_animation_code_ported":False,
        "runtime_capture_required":False,
        "original_raw_asset_upload_performed":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--poses-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-poses"))
    p.add_argument("--output",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-poses\channel_analysis.json"))
    args=p.parse_args(argv)
    try:
        source=(args.rom or locate_rom()).read_bytes()
        result=profile_original_animation(source,args.poses_dir)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        for c in result["characters"]:
            print("GOEMON_ANIMATION_CHANNELS "+
                  json.dumps(summarize_channel_anomalies(c),separators=(",",":")))
        print("GOEMON_ANIMATION_CHANNELS COMPLETE: unmodified original ROM analyzed offline")
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print("GOEMON_ANIMATION_CHANNELS FAILED:",exc,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
