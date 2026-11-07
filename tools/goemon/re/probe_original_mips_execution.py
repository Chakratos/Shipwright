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
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import OriginalMipsCPU,MipsFault,f32
from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
from decompress_rom import decompress_us_rom
from character_assets import read_file_table
from source_aligned_character_assets import source_align_character_files
from export_offline_original_poses import inspect_source_pose_bank
from analyze_yae_resource_pointers import build_yae_source_animation_catalog
from source_aligned_character_assets import CHARACTER_NAMES

ENTRY=0x800192D0
SOURCE=0x80400000
ACTOR=0x80600000

def run_probe(rom:bytes,progress:float=0.0,*,animated_limb:bool=False,slot:int=0)->dict:
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("original NG5E ROM hash mismatch")
    decoded=decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("original decompressed NG5E ROM hash mismatch")
    if not 0<=slot<4:
        raise ValueError("original source character slot outside four figures")
    files=source_align_character_files(decoded)[slot]
    table=read_file_table(decoded)
    banks={}
    for file in files[2:]:
        entry=table[file.runtime_file_id]
        banks[file.source_segment]=decoded[entry.start:entry.end]
    catalog=(build_yae_source_animation_catalog(banks[7]) if slot==3
             else inspect_source_pose_bank(banks,character=CHARACTER_NAMES[slot]))
    candidate=next((x for x in catalog["original_source_poses"]
                    if x["source_header_segment"]=="0x07"),None)
    if candidate is None:
        raise ValueError("no original ROM Goemon player-resource candidate")
    vm=OriginalMipsCPU()
    # ROM 0x1000 is original program vRAM 0x80000400, +0xC00.
    vm.copy(0x80000400,decoded[0x1000:0x81000])
    vm.copy(SOURCE,banks[7])
    vm.source_region=(SOURCE,SOURCE+len(banks[7]))
    def numeric_channels(bone):
        raw=(*bone["scale"],*bone["rotation"],*bone["translation"])
        return sum(0<x<32768 for x in raw)
    chosen=(max(candidate["limbs"],key=numeric_channels)
            if animated_limb else candidate["limbs"][0])
    limb=SOURCE+(int(chosen["ptr"])&0xFFFFFF)
    anim=SOURCE+(int(candidate["original_animation_pointer"],16)&0xFFFFFF)
    flags=int(candidate["original_animated_skeleton_flags"],16)
    vm.store(0x801684A0,ACTOR)
    # Original func_800192D0 reads D_80168530 as the destination
    # MtxF pointer, then passes it in a0 to func_80019ED8.
    # A null value caused the first real source-ROM MIPS execution fault.
    # Supply an isolated identity MtxF at the known original matrix region.
    # This is test-context initialization, NOT a verified game runtime state.
    vm.store(0x80168530,0x801684B0)
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
    # The original function writes back to its engine MtxF pointer.
    # Only report numerical validity and a digest; never log actual
    # commercial game matrix values or raw asset bytes.
    matrix_words=tuple(vm.load(0x801684B0+index*4) for index in range(16))
    identity=tuple(0x3F800000 if row==col else 0
                   for row in range(4) for col in range(4))
    matrix_bytes=b"".join(word.to_bytes(4,"big") for word in matrix_words)
    result["matrix_finite_elements"]=sum(math.isfinite(f32(w)) for w in matrix_words)
    result["matrix_elements_changed_from_identity"]=sum(
        a!=b for a,b in zip(matrix_words,identity))
    result["matrix_fingerprint_sha256_prefix"]=hashlib.sha256(
        matrix_bytes).hexdigest()[:16]
    result["output_matrix_layout_verified"]=False
    return {
        **result,
        "source":"original NG5E ROM",
        "character":CHARACTER_NAMES[slot],
        "verified_rom_hash":True,
        "input_original_candidate_header":candidate["source_header_offset"],
        "selected_original_limb_pointer":f"0x{chosen['ptr']:08X}",
        "selected_limb_numeric_channels":numeric_channels(chosen),
        "selected_limb_has_source_graphics":bool(chosen["gfx"]),
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
        original=(args.rom or locate_rom()).read_bytes()
        first=run_probe(original,progress=0.0)
        second=run_probe(original,progress=1.0)
        animated0=run_probe(original,progress=0.0,animated_limb=True)
        animated1=run_probe(original,progress=1.0,animated_limb=True)
        more_characters=[]
        for slot in (1,2,3):
            x0=run_probe(original,progress=0.0,animated_limb=True,slot=slot)
            x1=run_probe(original,progress=1.0,animated_limb=True,slot=slot)
            more_characters.append({
                "character":CHARACTER_NAMES[slot],
                "progress_0":x0,"progress_1":x1,
                "both_returned":bool(x0.get("returned") and x1.get("returned")),
                "matrix_changed":(
                    x0["matrix_fingerprint_sha256_prefix"] !=
                    x1["matrix_fingerprint_sha256_prefix"]),
            })
        result={
            "all_character_animation_probes":more_characters,
            "animated_limb_progress_0":animated0,
            "animated_limb_progress_1":animated1,
            "animated_limb_matrix_differs":(
                animated0["matrix_fingerprint_sha256_prefix"] !=
                animated1["matrix_fingerprint_sha256_prefix"]),
            "first_progress":first,
            "second_progress":second,
            "both_original_functions_returned":
                bool(first.get("returned") and second.get("returned")),
            "source_engine_matrix_changed_with_progress":
                first["matrix_fingerprint_sha256_prefix"] !=
                second["matrix_fingerprint_sha256_prefix"],
            "original_action_timing_verified":False,
            "original_frame_matrices_validated_in_game":False,
        }
        path=args.output.resolve()
        repo=Path(__file__).resolve().parents[3]
        if path==repo or repo in path.parents:
            raise ValueError("original owner-ROM CPU execution report outside repository only")
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_MIPS_CPU_EXEC "+json.dumps(first,separators=(",",":")))
        print("GOEMON_MIPS_PROGRESS_DELTA "+json.dumps({
            "both_returned":result["both_original_functions_returned"],
            "progress_0_matrix_finite":first["matrix_finite_elements"],
            "progress_1_matrix_finite":second["matrix_finite_elements"],
            "progress_0_non_identity":first["matrix_elements_changed_from_identity"],
            "progress_1_non_identity":second["matrix_elements_changed_from_identity"],
            "matrix_changed":result["source_engine_matrix_changed_with_progress"],
            "exact_animation_frames_confirmed":False,
        },separators=(",",":")))
        print("GOEMON_MIPS_ANIMATED_LIMB "+json.dumps({
            "source_limb":animated0["selected_original_limb_pointer"],
            "numeric_channels":animated0["selected_limb_numeric_channels"],
            "both_returned":bool(animated0.get("returned") and animated1.get("returned")),
            "executed_at_0":animated0.get("executed"),
            "executed_at_1":animated1.get("executed"),
            "changed_matrix_elements_0":animated0["matrix_elements_changed_from_identity"],
            "changed_matrix_elements_1":animated1["matrix_elements_changed_from_identity"],
            "all_finite_0":animated0["matrix_finite_elements"]==16,
            "all_finite_1":animated1["matrix_finite_elements"]==16,
            "matrix_differs_by_progress":result["animated_limb_matrix_differs"],
            "gameplay_clip_ownership_proven":False,
        },separators=(",",":")))
        for sample in more_characters:
            first=sample["progress_0"]
            second=sample["progress_1"]
            print("GOEMON_MIPS_CHARACTER "+json.dumps({
                "character":sample["character"],
                "original_limb":first["selected_original_limb_pointer"],
                "numeric_channels":first["selected_limb_numeric_channels"],
                "both_returned":sample["both_returned"],
                "executed_at_0":first.get("executed"),
                "executed_at_1":second.get("executed"),
                "matrix_finite_0":first["matrix_finite_elements"],
                "matrix_finite_1":second["matrix_finite_elements"],
                "progress_matrix_changed":sample["matrix_changed"],
                "blocker_0":first.get("blocker"),
                "blocker_1":second.get("blocker"),
                "source_action_timing_verified":False,
            },separators=(",",":")))
        print("GOEMON_MIPS_CPU_EXEC COMPLETE: owner-ROM execution, no ROM uploaded")
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("GOEMON_MIPS_CPU_EXEC FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
