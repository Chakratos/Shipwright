#!/usr/bin/env python3
"""Package exact ORIGINAL-MIPS isolated bone matrices for C++ source preview.

The GOMIPS01 file is NOT a gameplay-frame GOPA archive. The original MIPS
machine code was executed independently per limb at two controlled
animation_progress inputs with an identity parent matrix. Its owning
animation/action, real tick interval, rendering matrix order and full
original matrix stack are not yet known. Keep bytes solely on the owner PC.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import f32
from verify_original_rig_animation_pair import parse_rig_descriptors
from source_aligned_character_assets import CHARACTER_NAMES

MAGIC=b"GOMIPS01"
HEADER=struct.Struct("<8sIIIIff")
LIMB=struct.Struct("<IIhH9h")
MATRIX=struct.Struct("<16I")
SAMPLE_PROGRESS=(0.0,1.0)


def validate_original_sample(sample:dict,progress:float)->list[int]|None:
    if sample.get("original_animation_progress")!=progress:
        raise ValueError("original MIPS sample progress does not match header")
    raw=sample.get("matrix_ieee754_u32")
    if raw is None:
        if not sample.get("blocker"):
            raise ValueError("missing source MIPS output without explicit blocker")
        return None
    if not isinstance(raw,list) or len(raw)!=16 or any(
        type(bits)!=int or not 0<=bits<=0xFFFFFFFF or
        not __import__("math").isfinite(f32(bits)) for bits in raw
    ):
        raise ValueError("invalid original MIPS matrix word sequence")
    return raw


def build_original_isolated_mips_binary(rig:bytes,samples:dict)->bytes:
    slot,_,rigs=parse_rig_descriptors(rig)
    allowed=("goemon-owner-rom-original-mips-isolated-bone-matrices-v2",
             "goemon-owner-rom-original-mips-predecessor-bone-matrices-v3",
             "goemon-owner-rom-original-mips-continuous-skeleton-bone-matrices-v4")
    if samples.get("format") not in allowed:
        raise ValueError("not current source-MIPS-controlled isolated matrices")
    if (samples.get("format")==allowed[1] and
        samples.get("controlled_source_parent_stack_inheritance") is not True):
        raise ValueError("source predecessor MIPS matrices require lineage provenance")
    if (samples.get("format")==allowed[2] and
        samples.get("continuous_original_cpu_state_preserved") is not True):
        raise ValueError("continuous original MIPS source CPU lineage absent")
    if samples.get("actual_original_renderer_stack_pop_verified") is True:
        raise ValueError("source experimental predecessor not a verified live game renderer")
    if (samples.get("original_mtxf_output_pointer_global")!="D_80168530" or
        samples.get("output_stack_separate_from_current_mtxf") is not True or
        samples.get("previous_alias_based_matrix_samples_invalidated") is not True):
        raise ValueError("obsolete aliased original MIPS matrix samples must not be packaged")
    if samples.get("character_slot")!=slot or samples.get("character")!=CHARACTER_NAMES[slot]:
        raise ValueError("original source character/sample identity mismatch")
    if (samples.get("source_game_action_verified") is not False or
        samples.get("source_tick_mapping_verified") is not False or
        samples.get("parent_world_composition_verified") is not False or
        samples.get("engine_matrix_memory_layout_verified") is not False):
        raise ValueError("GOMIPS01 requires unverified isolated matrix provenance")
    source_progress=((0.0,4.0) if samples.get("format")==allowed[2]
                     else SAMPLE_PROGRESS)
    if samples.get("controlled_animation_progress_values")!=list(source_progress):
        raise ValueError("unexpected source sample progress sequence")
    header=int(samples["source_original_skeleton_header"],16)
    if header not in rigs:
        raise ValueError("source MIPS samples do not belong to packaged ROM rig")
    flags,rig_bones=rigs[header]
    if int(samples["original_animated_skeleton_flags"],16)!=flags:
        raise ValueError("original source AnimatedSkeleton flags mismatch")
    nodes=samples["limbs"]
    if len(nodes)!=len(rig_bones) or not 1<=len(nodes)<=128:
        raise ValueError("original rig and isolated matrix bone count mismatch")
    source_indices={}
    for idx,node in enumerate(nodes):
        ptr=int(node["source_limb_pointer"],16)
        if ptr>>24!=7 or ptr in source_indices:
            raise ValueError("source MIPS Skeleton nodes duplicated/wrong segment")
        source_indices[ptr]=idx
    out=bytearray(HEADER.pack(
        MAGIC,slot,header,len(nodes),len(source_progress),*source_progress))
    for idx,(node,rig_bone) in enumerate(zip(nodes,rig_bones)):
        gfx,parent,raw=rig_bone
        node_gfx=int(node["raw_original_gfx_pointer"],16)
        node_raw=tuple(node["source_raw_srt_channels"])
        parent_ptr=node.get("source_parent_pointer")
        node_parent=source_indices[int(parent_ptr,16)] if parent_ptr is not None else -1
        if (node_gfx!=gfx or node_parent!=parent or
            node_raw!=raw or not -1<=node_parent<idx):
            raise ValueError("source MIPS bone does not match original ROM rig descriptor")
        records=node["samples"]
        if len(records)!=2:
            raise ValueError("missing controlled progress samples")
        values=[validate_original_sample(record,source_progress[j])
                for j,record in enumerate(records)]
        mask=sum(1<<j for j,words in enumerate(values) if words is not None)
        ptr=int(node["source_limb_pointer"],16)
        out.extend(LIMB.pack(ptr,gfx,parent,mask,*raw))
        for words in values:
            out.extend(MATRIX.pack(*(words if words is not None else [0]*16)))
    # Exact byte length prevents accidentally shipping a partial asset.
    if len(out)!=HEADER.size+len(nodes)*(LIMB.size+2*MATRIX.size):
        raise ValueError("invalid original source MIPS packaging size")
    return bytes(out)


def inspect_original_isolated_mips_binary(blob:bytes)->dict:
    if len(blob)<HEADER.size:
        raise ValueError("source MIPS preview package truncated")
    magic,slot,header,bones,samples,p0,p1=HEADER.unpack_from(blob)
    if (magic!=MAGIC or slot>3 or header>>24!=7 or
        not 1<=bones<=128 or samples!=2 or (p0,p1) not in (SAMPLE_PROGRESS,(0.0,4.0))):
        raise ValueError("invalid isolated original MIPS preview header")
    if len(blob)!=HEADER.size+bones*(LIMB.size+samples*MATRIX.size):
        raise ValueError("isolated original MIPS preview package length mismatch")
    used=set()
    valid=0
    missing=0
    for index in range(bones):
        base=HEADER.size+index*(LIMB.size+samples*MATRIX.size)
        ptr,gfx,parent,mask,*channels=LIMB.unpack_from(blob,base)
        if ptr>>24!=7 or ptr in used or not -1<=parent<index or mask&~3:
            raise ValueError("invalid original source MIPS limb identifier")
        used.add(ptr)
        if gfx and (gfx>>24) not in (9,0x29,0x0F):
            raise ValueError("unexpected original source graphics tag")
        for j in range(2):
            words=MATRIX.unpack_from(blob,base+LIMB.size+j*MATRIX.size)
            if mask&(1<<j):
                if any(not __import__("math").isfinite(f32(w)) for w in words):
                    raise ValueError("nonfinite original MIPS matrix in valid sample")
                valid+=1
            elif any(words):
                raise ValueError("missing original MIPS matrix contains unverified data")
            else:
                missing+=1
    return {
        "character":CHARACTER_NAMES[slot],
        "original_segmented_header":f"0x{header:08X}",
        "original_limb_count":bones,
        "valid_original_mips_matrices":valid,
        "blocked_original_mips_matrices":missing,
        "original_animation_action_verified":False,
        "original_game_frame_timing_verified":False,
        "parent_matrix_stack_verified":False,
        "original_source_matrix_layout_verified":False
    }


def package_local_original_source_mips(matrix_dir:Path,rig_dir:Path,
                                       output_dir:Path)->dict:
    root=Path(__file__).resolve().parents[3]
    target=output_dir.resolve()
    if target==root or root in target.parents:
        raise ValueError("source MIPS assets must not be saved into Git checkout")
    target.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for name in CHARACTER_NAMES:
        rig=(rig_dir/name/"original.goskel").read_bytes()
        sample=json.loads((matrix_dir/(name+"_source_mips_matrices.json")).read_text("utf-8"))
        blob=build_original_isolated_mips_binary(rig,sample)
        report=inspect_original_isolated_mips_binary(blob)
        directory=target/name
        directory.mkdir(exist_ok=True)
        (directory/"isolated.gomips").write_bytes(blob)
        summaries.append(report)
        print("GOEMON_ORIGINAL_MIPS_PREVIEW_PACKAGE "+json.dumps(
            report,separators=(",",":")))
    manifest={
        "format":"goemon-isolated-native-mips-limb-preview-v1",
        "source":"owner-private original NG5E ROM",
        "original_mips_matrix_action_mapping_verified":False,
        "gameplay_ready":False,
        "private_original_assets_uploaded":False,
        "characters":summaries
    }
    (target/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",
                                         encoding="utf-8")
    return manifest


def main(argv=None)->int:
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--matrix-dir",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-mips-isolated-limb-matrices"))
    a.add_argument("--rig-dir",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-rom-rigs"))
    a.add_argument("--output-dir",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-source-mips-preview"))
    opt=a.parse_args(argv)
    try:
        package_local_original_source_mips(opt.matrix_dir,opt.rig_dir,opt.output_dir)
        print("GOEMON_ORIGINAL_MIPS_PREVIEW_PACKAGE COMPLETE: owner-only native binaries, not gameplay frames")
    except (OSError,ValueError,KeyError,TypeError,struct.error) as e:
        print("GOEMON_ORIGINAL_MIPS_PREVIEW_PACKAGE FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
