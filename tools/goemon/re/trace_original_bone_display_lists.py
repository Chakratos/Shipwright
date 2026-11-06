#!/usr/bin/env python3
"""Prove source ROM animated Skeleton limbs own specific source N64 geometry.

Runs fully offline against verified user-local NG5E ROM, previously exported
original Skeleton pose catalog, and source-aligned original F3DEX mesh runs.
Traverses genuine gSPDisplayList/gSPBranchList calls before locating
gSPVertex. Does not guess a body part based on spatial proximity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from character_assets import read_file_table
from decompress_rom import decompress_us_rom
from original_n64_display_list_graph import link_original_skeleton_gfx_roots
from source_aligned_character_assets import source_align_character_files

CHARACTERS=("Goemon","Ebisumaru","Sasuke")


def analyze_real_original_display_lists(rom:bytes,poses_dir:Path,models_dir:Path) -> dict:
    from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("source ROM does not match user's original NG5E hash")
    decoded=decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("decompressed ROM hash mismatch")
    groups=source_align_character_files(decoded)
    table=read_file_table(decoded)
    results=[]
    for index,name in enumerate(CHARACTERS):
        group=groups[index]
        bank_data={}
        for f in group[2:4]:
            file=table[f.runtime_file_id]
            bank_data[f.source_segment]=decoded[file.start:file.end]
        pose=json.loads((poses_dir/(name+"_original_source_poses.json"))
                        .read_text(encoding="utf-8"))
        model=json.loads((models_dir/name/"manifest.json").read_text("utf-8"))
        linked=link_original_skeleton_gfx_roots(pose,bank_data,model)
        if linked["character"]!=name:
            raise ValueError("original character name mismatch")
        results.append(linked)
    return {
        "format":"source-original-skeleton-display-list-ownership-v1",
        "source":"Original ROM + real F3DEX display-list traversal",
        "characters":results,
        "animation_source_frames_playback_ready":False,
        "user_gameplay_capture_needed":False,
        "asset_upload_performed":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--poses-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-poses"))
    p.add_argument("--meshes-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-meshes-source-aligned"))
    p.add_argument("--output",type=Path)
    args=p.parse_args(argv)
    try:
        from real_rom_check import locate_rom
        source=args.rom or locate_rom()
        result=analyze_real_original_display_lists(
            source.read_bytes(),args.poses_dir,args.meshes_dir)
        for entry in result["characters"]:
            print("GOEMON_GFX_RECURSIVE_SOURCE "+json.dumps({
                k:v for k,v in entry.items() if k!="sources"
            },separators=(",",":")))
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_GFX_RECURSIVE_SOURCE COMPLETE: no user input, no game launch")
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(f"GOEMON_GFX_RECURSIVE_SOURCE FAILED: {exc}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
