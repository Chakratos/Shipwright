#!/usr/bin/env python3
"""Offline evidence for Yae's unconfirmed source 0x09 graphics-bank owner.

The original NG5E decomp maps Yae's 0x07 and 0x08 resources, but
does not identify a persistent 0x09 bank in her contiguous file group.
Evaluate each independently source-verified character 0x09 bank against
Yae's own source-0x07 AnimatedSkeleton candidates, and *execute* their
F3DEX display-list trees. A matching graphics stream is geometric
evidence, never proof of overlay residency or active player identity.

Only high-level counts are printed; no copyrighted ROM bytes are logged,
committed, uploaded, or written inside the repository.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from character_assets import read_file_table
from decompress_rom import decompress_us_rom
from source_aligned_character_assets import source_align_character_files
from analyze_yae_resource_pointers import (
    traverse_yae_bank07_unresolved_skeletons
)
import struct
from decode_original_limb_meshes import decode_original_limb_mesh


def collect_yae_source_gfx_roots(
    y07:bytes
)->tuple[int,set[int],set[int],Counter]:
    """Collect genuine segmented Gfx targets without selecting a graphics bank."""
    # The original player renderer uses (gfx & 0x8FFFFFFF).
    # A tagged 0x29xxxxxx address therefore points into segment 0x09.
    # Preserve all other pointer types as unresolved metadata.
    candidates=0
    gfx_roots=set()
    unsupported_gfx=Counter()
    tagged_roots=set()
    for at in range(0,len(y07)-12+1,4):
        flags,animation,root=struct.unpack_from(">III",y07,at)
        if not 1<=((flags>>8)&0x7FFF)<=128:
            continue
        if root>>24!=7 or animation>>24!=7:
            continue
        try:
            nodes=traverse_yae_bank07_unresolved_skeletons(y07,root)
        except ValueError:
            continue
        if len(nodes)<4:
            continue
        candidates+=1
        for _,raw in nodes:
            if raw==0:
                continue
            normalized=raw & 0x8FFFFFFF
            if normalized>>24==9:
                gfx_roots.add(normalized)
                if raw!=normalized:
                    tagged_roots.add(raw)
            else:
                unsupported_gfx[f"0x{raw>>24:02X}"]+=1
    return candidates,gfx_roots,tagged_roots,unsupported_gfx


def assess_yae_candidate_bank(banks:dict[int,bytes], *,
                              graphics_source_file:int)->dict:
    if 7 not in banks or 9 not in banks:
        raise ValueError("Yae analysis requires authentic source 0x07 and hypothetical 0x09")
    candidates,gfx_roots,tagged_roots,unsupported_gfx = collect_yae_source_gfx_roots(banks[7])
    successes={}
    failures=Counter()
    for ptr in sorted(gfx_roots):
        try:
            mesh=decode_original_limb_mesh(ptr,banks)
            successes[ptr]=len(mesh.faces)
        except ValueError as exc:
            failures[str(exc).split(" at ")[0]]+=1
    return {
        "source_09_runtime_file_id":graphics_source_file,
        "source_07_candidate_skeletons":candidates,
        "distinct_original_limb_display_lists":len(gfx_roots),
        "tagged_0x29_display_list_roots":len(tagged_roots),
        "unsupported_other_gfx_segments":dict(sorted(unsupported_gfx.items())),
        "executed_original_limb_meshes":len(successes),
        "decoded_original_triangles":sum(successes.values()),
        "failed_limb_meshes":sum(failures.values()),
        "decode_failure_classes":dict(sorted(failures.items())),
        "first_6_decoded_gfx_roots":[f"0x{ptr:08X}" for ptr in sorted(successes)[:6]],
        "actual_runtime_bank_residency_verified":False,
        "active_player_skeleton_identity_verified":False,
    }


def compare_yae_banks(candidate_banks:list[tuple[int,bytes]],
                      yae_07:bytes,yae_08:bytes)->dict:
    if not candidate_banks:
        raise ValueError("no source-verified 0x09 bank hypotheses supplied")
    outcomes=[]
    for file_id,data in candidate_banks:
        outcomes.append(assess_yae_candidate_bank(
            {7:yae_07,8:yae_08,9:data},
            graphics_source_file=file_id))
    scores=[(v["executed_original_limb_meshes"],
             v["decoded_original_triangles"]) for v in outcomes]
    ranked=sorted(enumerate(scores),key=lambda x:x[1],reverse=True)
    best=ranked[0]
    runner_up=ranked[1][1] if len(ranked)>1 else (0,0)
    # The comparison is a *plausibility* ranking, not authenticated
    # source-segment residency: never auto-select for production assets.
    distinct=best[1]>(0,0) and best[1]>runner_up
    return {
        "subject":"Yae original 0x09 bank hypothesis",
        "candidate_09_banks":outcomes,
        "unique_geometric_best_candidate_file":(
            outcomes[best[0]]["source_09_runtime_file_id"] if distinct else None),
        "winner_is_runtime_verified":False,
        "safe_to_publish_source_yae_player_rig":False,
        "source_rom_data_uploaded":False,
    }


def probe_original_yae_bank(rom:bytes)->dict:
    from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("original NG5E ROM SHA-256 mismatch")
    decoded=decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("decompressed NG5E ROM SHA-256 mismatch")
    table=read_file_table(decoded)
    groups=source_align_character_files(decoded)
    yae_files=groups[3]
    y07=yae_files[2]
    y08=yae_files[3]
    if y07.source_segment!=7 or y08.source_segment!=8:
        raise ValueError("Yae source segment mapping unexpectedly changed")
    candidates=[]
    for group in groups[:3]:
        source=group[3]
        if source.source_segment!=9:
            raise ValueError("source graphics bank mapping unexpectedly changed")
        file=table[source.runtime_file_id]
        candidates.append((
            source.runtime_file_id,decoded[file.start:file.end]))
    source07=table[y07.runtime_file_id]
    source08=table[y08.runtime_file_id]
    return compare_yae_banks(candidates,
        decoded[source07.start:source07.end],
        decoded[source08.start:source08.end])


def main(argv=None)->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom",type=Path)
    ap.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-yae-source-bank-probe.json"))
    args=ap.parse_args(argv)
    try:
        from real_rom_check import locate_rom
        report=probe_original_yae_bank((args.rom or locate_rom()).read_bytes())
        out=args.output.resolve()
        project=Path(__file__).resolve().parents[3]
        if out==project or project in out.parents:
            raise ValueError("private source ROM report must stay outside repository")
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_YAE_BANK_PROBE "+json.dumps({
            "candidates":[{
                k:v for k,v in candidate.items()
                if k not in ("decode_failure_classes","first_6_decoded_gfx_roots")}
                for candidate in report["candidate_09_banks"]],
            "geometric_best_file":report["unique_geometric_best_candidate_file"],
            "runtime_residency_proven":False,
        },separators=(",",":")))
        print("GOEMON_YAE_BANK_PROBE COMPLETE: source-only, no asset uploads")
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print("GOEMON_YAE_BANK_PROBE FAILED:",exc,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
