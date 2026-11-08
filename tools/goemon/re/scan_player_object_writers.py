#!/usr/bin/env python3
"""Map ORIGINAL NG5E player animation/graphics WRITER CANDIDATES offline.

Only inspects hash-verified decompressed original US ROM *executable
regions*. Emits addresses, field offsets, register numbers, counts, and
compact caller-context metadata. No ROM machine-code bytes, raw
instructions, models or matrices are uploaded or logged.

Important: an instruction 'sb rX, 0xCC(rY)' merely matches the
PlayerTask.action_id field OFFSET. Other structs have identical offsets.
It is only a writer CANDIDATE until base-register provenance / call
context proves that rY is an actual original PlayerTask pointer.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from character_assets import read_file_table
from character_id_binding import source_proven_character_graphics
from probe_original_mips_execution import verified_decoded_original_rom
from real_rom_check import locate_rom

# Corroborated by pinned Goemon64Recomp patches/types.h / variables.h.
FIELDS={
    ("sb",0xCC):"PlayerTask.action_id_candidate",
    ("sh",0xCC):"PlayerTask.action_id_wrong_width_or_other_struct",
    ("sw",0xCC):"Other_struct_field_0xCC",
    ("sw",0x2C):"Object.graphics_1_candidate",
    ("sw",0x30):"Object.graphics_2_candidate",
    ("sw",0x28):"Object.animation_progress_bits_candidate",
    ("sw",0x38):"Object.overlay_info_0.vram_base_candidate",
    ("sw",0x40):"Object.overlay_info_1.vram_base_candidate",
    ("sw",0x48):"Object.overlay_info_2.vram_base_candidate",
    ("sw",0x50):"Object.overlay_info_3.vram_base_candidate",
    ("sw",0x58):"Object.overlay_info_4.vram_base_candidate",
    ("sw",0x60):"Object.overlay_info_5.vram_base_or_other_field",
}
STORES={0x28:"sb",0x29:"sh",0x2B:"sw"}
MAIN_ROM_BEGIN=0x1000
MAIN_ROM_END=0x81000
MAIN_VRAM_BEGIN=0x80000400
PLAYER_ORIGINAL_ROUTINE_ROM=0x5988D8
PLAYER_ORIGINAL_ROUTINE_VRAM=0x801DC9C8
MAX_REPORTED_SITES_PER_FIELD=16


def decode_store_field(word:int)->dict|None:
    if type(word)!=int or not 0<=word<=0xFFFFFFFF:
        raise ValueError("expected one big-endian 32-bit MIPS instruction")
    mnemonic=STORES.get(word>>26)
    if mnemonic is None:
        return None
    signed=word&0xFFFF
    if signed>=0x8000:
        signed-=0x10000
    field=FIELDS.get((mnemonic,signed))
    if field is None:
        return None
    return {
        "field_candidate":field,
        "store_instruction":mnemonic,
        "base_register":(word>>21)&31,
        "value_register":(word>>16)&31,
        "signed_field_offset":signed,
        "base_register_is_zero":(word>>21)&31==0,
    }


def find_writer_candidates(code:bytes,*,source_rom_offset:int,
                           code_vram_base:int,source_file:str)->dict:
    if not code or len(code)%4 or source_rom_offset%4 or code_vram_base%4:
        raise ValueError("unaligned or empty original executable scan region")
    if len(code)>8*1024*1024:
        raise ValueError("unbounded original executable code scan")
    words=struct.unpack(">"+("I"*(len(code)//4)),code)
    sites=[]
    totals=Counter()
    per_field=Counter()
    for idx,word in enumerate(words):
        decoded=decode_store_field(word)
        if decoded is None:
            continue
        pc=code_vram_base+idx*4
        if pc>0xFFFFFFFF:
            raise ValueError("invalid source original executable VRAM")
        preceding=words[max(0,idx-24):idx]
        follows=words[idx+1:idx+9]
        # These are *MIPS instruction-class* hints only, not proof
        # of actual base-register or function ownership.
        tagged_luis=sum(
            1 for w in preceding
            if w>>26==0x0F and (w&0xFFFF) in (0x6000,0x6700,0x7000))
        calls=sum(1 for w in preceding+follows if w>>26==3)
        known_direct_calls=sum(
            1 for w in preceding+follows
            if w>>26==3 and
            (((pc+4)&0xF0000000)|((w&0x03FFFFFF)<<2))==
            PLAYER_ORIGINAL_ROUTINE_VRAM)
        role=decoded["field_candidate"]
        totals[role]+=1
        per_field[(role,decoded["base_register"],decoded["value_register"])]+=1
        sites.append({
            **decoded,
            "source":source_file,
            "original_rom_offset":f"0x{source_rom_offset+idx*4:08X}",
            "original_mips_pc":f"0x{pc:08X}",
            "nearby_tagged_player_type_lui_count":tagged_luis,
            "nearby_direct_jal_count":calls,
            "nearby_original_character_handler_call_count":known_direct_calls,
            "target_pointer_register_provenance_verified":False,
            "original_player_field_writer_verified":False,
        })
    by_field={}
    for field in sorted(totals):
        matches=[site for site in sites if site["field_candidate"]==field]
        by_field[field]={
            "candidate_instruction_count":totals[field],
            "first_candidates_by_source_pc":matches[:MAX_REPORTED_SITES_PER_FIELD],
            "base_register_frequency":{
                f"r{reg}":n for (role,reg,val),n in sorted(per_field.items())
                if role==field
            },
            "proven_writers":0,
        }
    return {
        "source":source_file,
        "source_original_rom_offset":f"0x{source_rom_offset:08X}",
        "source_original_vram_base":f"0x{code_vram_base:08X}",
        "code_bytes_scanned":len(code),
        "scan_is_static_syntactic_only":True,
        "total_field_offset_store_candidates":len(sites),
        "fields":by_field,
    }


def scan_original_player_executable(rom:bytes)->dict:
    if len(rom)<PLAYER_ORIGINAL_ROUTINE_ROM+0x40:
        raise ValueError("original NG5E ROM too small for player source overlay")
    source_proven_character_graphics(rom)
    table=read_file_table(rom)
    matches=[
        f for f in table
        if f.start<=PLAYER_ORIGINAL_ROUTINE_ROM<f.end
    ]
    if len(matches)!=1:
        raise ValueError("original player routine ROM address not in unique file")
    entry=matches[0]
    player_vram_base=(
        PLAYER_ORIGINAL_ROUTINE_VRAM-
        (PLAYER_ORIGINAL_ROUTINE_ROM-entry.start))
    if player_vram_base<0x80000000 or player_vram_base>0x80800000:
        raise ValueError("original player overlay VRAM base outside N64 RDRAM")
    regions=[
        ("original_main_executable",rom[MAIN_ROM_BEGIN:MAIN_ROM_END],
         MAIN_ROM_BEGIN,MAIN_VRAM_BEGIN),
        (f"original_player_overlay_file_{entry.file_id}",
         rom[entry.start:entry.end],entry.start,player_vram_base),
    ]
    scans=[]
    for name,code,offset,base in regions:
        # Runtime code is organized in big-endian aligned words; file
        # entries typically have 4-byte alignment. Fail closed if not.
        if len(code)%4:
            raise ValueError("non-aligned original ROM source player executable")
        scans.append(find_writer_candidates(
            code,source_rom_offset=offset,
            code_vram_base=base,source_file=name))
    return {
        "schema":"ng5e-original-player-struct-offset-store-candidates-v1",
        "original_player_graphics_file_id_proven":True,
        "original_player_overlay_runtime_file_id":entry.file_id,
        "original_player_overlay_rom_start":f"0x{entry.start:08X}",
        "original_player_overlay_vram_base":f"0x{player_vram_base:08X}",
        "verified_gameplay_pointer_owner":False,
        "all_original_object_writer_sites_proven":False,
        "original_rom_bytes_uploaded":False,
        "source_region_scans":scans,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-player-object-writer-sites.json"))
    args=p.parse_args(argv)
    try:
        binary=(args.rom or locate_rom()).read_bytes()
        decoded=verified_decoded_original_rom(binary)
        root=Path(__file__).resolve().parents[3]
        out=args.output.resolve()
        if out==root or root in out.parents:
            raise ValueError("source writer metadata must remain outside Git checkout")
        report=scan_original_player_executable(decoded)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        for region in report["source_region_scans"]:
            compact={
                "source":region["source"],
                "code_bytes_scanned":region["code_bytes_scanned"],
                "candidate_store_instruction_total":
                    region["total_field_offset_store_candidates"],
                "potential_player_action_writes":region["fields"].get(
                    "PlayerTask.action_id_candidate",{}).get(
                    "candidate_instruction_count",0),
                "potential_player_graphics_1_writes":region["fields"].get(
                    "Object.graphics_1_candidate",{}).get(
                    "candidate_instruction_count",0),
                "first_action_candidates":region["fields"].get(
                    "PlayerTask.action_id_candidate",{}).get(
                    "first_candidates_by_source_pc",[])[:10],
                "first_graphics_candidates":region["fields"].get(
                    "Object.graphics_1_candidate",{}).get(
                    "first_candidates_by_source_pc",[])[:10],
            }
            print("GOEMON_PLAYER_OBJECT_WRITER_SCAN "+
                  json.dumps(compact,separators=(",",":")))
        print("GOEMON_PLAYER_OBJECT_WRITER_SCAN COMPLETE: static candidates only")
    except (OSError,ValueError,TypeError,KeyError) as e:
        print("GOEMON_PLAYER_OBJECT_WRITER_SCAN FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
