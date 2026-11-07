#!/usr/bin/env python3
"""Run genuine original MIPS skeletal-matrix code with deterministic local context.

Only owner-hash-verified NG5E ROM bytes are loaded and executed. The initial
render state is a controlled approximation, not proven live player state.
No source instructions, ROM bytes, or engine matrices leave the Windows PC.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import OriginalMipsCPU,MipsFault
from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
from decompress_rom import decompress_us_rom
from character_assets import read_file_table
from source_aligned_character_assets import source_align_character_files
from export_offline_original_poses import inspect_source_pose_bank

ENTRY=0x800192D0
SOURCE=0x80400000
ACTOR=0x80600000

def run_probe(rom:bytes,progress:float=0.0)->dict:
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("original NG5E ROM hash mismatch")
    decoded=decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("original decompressed NG5E ROM hash mismatch")
    files=source_align_character_files(decoded)[0]
    table=read_file_table(decoded)
    banks={}
    for file in files[2:]:
        entry=table[file.runtime_file_id]
        banks[file.source_segment]=decoded[entry.start:entry.end]
    catalog=inspect_source_pose_bank(banks,character="Goemon")
    candidate=next((x for x in catalog["original_source_poses"]
                    if x["source_header_segment"]=="0x07"),None)
    if candidate is None:
        raise ValueError("no original ROM Goemon player-resource candidate")
    vm=OriginalMipsCPU()
    # ROM 0x1000 is original program vRAM 0x80000400, +0xC00.
    vm.copy(0x80000400,decoded[0x1000:0x81000])
    vm.copy(SOURCE,banks[7])
    vm.source_region=(SOURCE,SOURCE+len(banks[7]))
    limb=SOURCE+(int(candidate["original_skeleton_root"],16)&0xFFFFFF)
    anim=SOURCE+(int(candidate["original_animation_pointer"],16)&0xFFFFFF)
    flags=int(candidate["original_animated_skeleton_flags"],16)
    vm.store(0x801684A0,ACTOR)
    vm.store(0x801684F0,anim)
    vm.store(0x80168520,anim)
    vm.put_float(0x80168510,progress)
    vm.put_float(0x80168514,0.0)
    vm.put_float(0x80168518,float(flags&255))
    vm.store(0x8016851C,(flags>>31)&1)
    for row in range(4):
        for col in range(4):
            vm.put_float(0x801684B0+(row*4+col)*4,
                         1.0 if row==col else 0.0)
    for axis in range(3):
        vm.put_float(ACTOR+0x1c+4*axis,1.0)
    vm.put_float(ACTOR+0x28,progress)
    vm.r[4]=limb
    vm.r[5]=ACTOR
    try:
        result=vm.run(ENTRY,budget=200000)
    except (MipsFault,ValueError,OverflowError,ZeroDivisionError) as ex:
        result={
            "returned":False,
            "blocker":str(ex),
            "executed":vm.executed,
            "distinct_instructions":len(vm.visited),
            "last_pc":f"0x{vm.pc:08X}",
            "calls":dict(vm.calls),
            "first_original_function_calls":vm.first_calls,
            "first_a0_register_source_transitions":vm.a0_source_changes,
            "first_original_memory_read_dependencies":vm.initial_memory_reads,
            "read_regions":dict(vm.reads),
            "write_regions":dict(vm.writes),
        }
    return {
        **result,
        "source":"original NG5E ROM",
        "verified_rom_hash":True,
        "input_original_candidate_header":candidate["source_header_offset"],
        "controlled_progress":progress,
        "live_gameplay_object_state_verified":False,
        "animation_bone_matrices_verified":False,
        "actual_clip_owner_verified":False,
        "rom_asset_bytes_uploaded":False,
    }

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-mips-cpu-probe.json"))
    args=p.parse_args(argv)
    try:
        result=run_probe((args.rom or locate_rom()).read_bytes())
        path=args.output.resolve()
        repo=Path(__file__).resolve().parents[3]
        if path==repo or repo in path.parents:
            raise ValueError("original owner-ROM CPU execution report outside repository only")
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_MIPS_CPU_EXEC "+json.dumps(result,separators=(",",":")))
        print("GOEMON_MIPS_CPU_EXEC COMPLETE: owner-ROM execution, no ROM uploaded")
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("GOEMON_MIPS_CPU_EXEC FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
