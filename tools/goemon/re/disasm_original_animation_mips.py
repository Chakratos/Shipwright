#!/usr/bin/env python3
"""Disassemble original MIPS skeletal-matrix evaluator, offline on user's ROM.

Source symbol: func_800192D0_19ED0 through func_800196A4_1A2A4.
The original target virtual address is 0x800192D0; after the N64 loader
and ROM mapping its file offset is exactly 0x19ED0. Disassembled instructions
are saved ONLY on the owner's Windows PC (no original ROM byte uploads).

Purpose: reconstruct actual semantics of tagged 0xB000/0xB100 Skeleton
channel values, animation_progress and per-channel reference offsets.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_rom_check import (
    ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
)
from decompress_rom import decompress_us_rom

START_VRAM=0x800192D0
START_ROM=0x19ED0
END_ROM=0x1A2A4
REGISTER_NAMES=(
    "zero","at","v0","v1","a0","a1","a2","a3",
    "t0","t1","t2","t3","t4","t5","t6","t7",
    "s0","s1","s2","s3","s4","s5","s6","s7",
    "t8","t9","k0","k1","gp","sp","fp","ra",
)
R_OPS={
    0x00:"sll",0x02:"srl",0x03:"sra",0x04:"sllv",0x06:"srlv",
    0x07:"srav",0x08:"jr",0x09:"jalr",0x10:"mfhi",0x12:"mflo",
    0x18:"mult",0x19:"multu",0x1A:"div",0x1B:"divu",
    0x20:"add",0x21:"addu",0x22:"sub",0x23:"subu",
    0x24:"and",0x25:"or",0x26:"xor",0x27:"nor",
    0x2A:"slt",0x2B:"sltu"
}
I_OPS={
    0x08:"addi",0x09:"addiu",0x0A:"slti",0x0B:"sltiu",
    0x0C:"andi",0x0D:"ori",0x0E:"xori",0x0F:"lui",
    0x20:"lb",0x21:"lh",0x22:"lwl",0x23:"lw",
    0x24:"lbu",0x25:"lhu",0x26:"lwr",
    0x28:"sb",0x29:"sh",0x2A:"swl",0x2B:"sw",
    0x2E:"swr",0x31:"lwc1",0x39:"swc1",
}
BRANCHES={4:"beq",5:"bne",6:"blez",7:"bgtz",
          0x14:"beql",0x15:"bnel"}

@dataclass(frozen=True)
class MIPSInstruction:
    pc:int
    mnemonic:str
    operands:str
    source_word:int
    def line(self)->str:
        return f"0x{self.pc:08X}: {self.mnemonic:<8} {self.operands}"

def signed16(value:int)->int:
    value &= 0xFFFF
    return value-0x10000 if value&0x8000 else value

def decode_instruction(pc:int,word:int)->MIPSInstruction:
    op=word>>26
    rs=(word>>21)&31
    rt=(word>>16)&31
    rd=(word>>11)&31
    shift=(word>>6)&31
    funct=word&63
    imm=word&65535
    r=REGISTER_NAMES
    if word==0:
        return MIPSInstruction(pc,"nop","",word)
    if op==0:
        name=R_OPS.get(funct,f"special_0x{funct:02X}")
        if funct in (0,2,3):
            args=f"${r[rd]}, ${r[rt]}, {shift}"
        elif funct in (4,6,7):
            args=f"${r[rd]}, ${r[rt]}, ${r[rs]}"
        elif funct in (8,):
            args=f"${r[rs]}"
        elif funct in (9,):
            args=f"${r[rd]}, ${r[rs]}"
        elif funct in (16,18):
            args=f"${r[rd]}"
        elif funct in (24,25,26,27):
            args=f"${r[rs]}, ${r[rt]}"
        else:
            args=f"${r[rd]}, ${r[rs]}, ${r[rt]}"
    elif op in (2,3):
        name="j" if op==2 else "jal"
        destination=((pc+4)&0xF0000000)|((word&0x03FFFFFF)<<2)
        args=f"0x{destination:08X}"
    elif op in BRANCHES:
        name=BRANCHES[op]
        target=(pc+4+signed16(imm)*4)&0xFFFFFFFF
        args=(f"${r[rs]}, ${r[rt]}, 0x{target:08X}"
              if op in (4,5,0x14,0x15)
              else f"${r[rs]}, 0x{target:08X}")
    elif op==1:
        regimm={0:"bltz",1:"bgez",16:"bltzal",17:"bgezal"}
        name=regimm.get(rt,f"regimm_0x{rt:02X}")
        args=f"${r[rs]}, 0x{(pc+4+signed16(imm)*4)&0xFFFFFFFF:08X}"
    elif op in I_OPS:
        name=I_OPS[op]
        if op==15:
            args=f"${r[rt]}, 0x{imm:04X}"
        elif op in (12,13,14):
            args=f"${r[rt]}, ${r[rs]}, 0x{imm:04X}"
        elif op in (32,33,34,35,36,37,38,40,41,42,43,46,49,57):
            destination=f"$f{rt}" if op in (49,57) else f"${r[rt]}"
            args=f"{destination}, {signed16(imm)}(${r[rs]})"
        else:
            args=f"${r[rt]}, ${r[rs]}, {signed16(imm)}"
    elif op==17:
        fmt=rs
        fop=word&63
        fs=(word>>11)&31
        ft=(word>>16)&31
        fd=(word>>6)&31
        if fmt in (0,2,4,6):
            name={0:"mfc1",2:"cfc1",4:"mtc1",6:"ctc1"}[fmt]
            args=f"${r[rt]}, $f{fs}"
        elif fmt in (16,17,20,21):
            types={16:".s",17:".d",20:".w",21:".l"}
            ops={
                0:"add",1:"sub",2:"mul",3:"div",4:"sqrt",
                5:"abs",6:"mov",7:"neg",
                12:"round.w",13:"trunc.w",14:"ceil.w",15:"floor.w",
                32:"cvt.s",33:"cvt.d",36:"cvt.w",48:"c.f",
                50:"c.eq",60:"c.lt",62:"c.le",
            }
            name=ops.get(fop,f"cop1_0x{fop:02X}")+types[fmt]
            args=f"$f{fd}, $f{fs}, $f{ft}"
        elif fmt==8:
            name="bc1t" if rt&1 else "bc1f"
            args=f"0x{(pc+4+signed16(imm)*4)&0xFFFFFFFF:08X}"
        else:
            name=f"cop1_fmt_{fmt:02X}"
            args=f"0x{word&0x1FFFFF:06X}"
    else:
        name=f"op_0x{op:02X}"
        args=f"0x{word&0x03FFFFFF:07X}"
    return MIPSInstruction(pc,name,args,word)


def analyze_original_matrix_mips(source:bytes)->dict:
    if len(source)!=END_ROM-START_ROM or len(source)%4:
        raise ValueError("original animation matrix function length mismatch")
    parsed=[
        decode_instruction(START_VRAM+i,
                           struct.unpack_from(">I",source,i)[0])
        for i in range(0,len(source),4)
    ]
    histogram=Counter(x.mnemonic for x in parsed)
    calls=[x.operands for x in parsed if x.mnemonic=="jal"]
    # Immediate constants are derived from original MIPS instruction fields,
    # never print executable bytes or source game assets.
    immediates=Counter()
    memory=[]
    for row in parsed:
        if row.mnemonic in ("lui","andi","ori","xori","slti","sltiu"):
            immediates[row.operands.split(",")[-1].strip()]+=1
        if row.mnemonic in ("lb","lbu","lh","lhu","lw","lwc1",
                            "sb","sh","sw","swc1"):
            memory.append({
                "pc":f"0x{row.pc:08X}",
                "op":row.mnemonic,"args":row.operands})
    return {
        "original_virtual_start":f"0x{START_VRAM:08X}",
        "verified_original_ROM_offset":f"0x{START_ROM:X}",
        "ends_before_original_function":f"0x{END_ROM:X}",
        "instruction_count":len(parsed),
        "opcode_frequency":dict(sorted(histogram.items())),
        "direct_mips_call_targets":calls,
        "immediate_values":dict(sorted(immediates.items())),
        "memory_accesses":memory,
        "mips_instructions":parsed,
        "original_animation_math_extracted":False,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output-dir",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-animation-mips"))
    a=p.parse_args(argv)
    try:
        original=(a.rom or locate_rom()).read_bytes()
        if hashlib.sha256(original).hexdigest()!=ORIGINAL_SHA256:
            raise ValueError("wrong private original NG5E ROM")
        decoded=decompress_us_rom(original)
        if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
            raise ValueError("wrong decompressed MNSG ROM")
        result=analyze_original_matrix_mips(decoded[START_ROM:END_ROM])
        target=a.output_dir.resolve()
        project=Path(__file__).resolve().parents[3]
        if target==project or project in target.parents:
            raise ValueError("MIPS disassembly must stay outside source repository")
        target.mkdir(parents=True,exist_ok=True)
        (target/"func_800192D0_19ED0.txt").write_text(
            "\n".join(x.line() for x in result["mips_instructions"])+"\n",
            encoding="utf-8")
        metadata={
            key:value for key,value in result.items()
            if key!="mips_instructions"
        }
        (target/"original_animation_matrix_function_summary.json").write_text(
            json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_MIPS_MATRIX_FUNCTION "+json.dumps({
            "instructions":result["instruction_count"],
            "calls":result["direct_mips_call_targets"],
            "opcode_frequency":result["opcode_frequency"],
            "important_imm":{k:v for k,v in result["immediate_values"].items()
                             if k.lower() in (
                                 "0xb000","0xb100","0x00ff","0x03ff",
                                 "0x7fff","0x8000","0xffff","0x0003")},
            "memory_accesses_first_12":result["memory_accesses"][:12],
            "local_disassembly":str(target/"func_800192D0_19ED0.txt"),
        },separators=(",",":")))
        print("GOEMON_MIPS_MATRIX_FUNCTION COMPLETE: original source MIPS locally decoded")
    except (OSError,ValueError) as exc:
        print("GOEMON_MIPS_MATRIX_FUNCTION FAILED:",exc,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
