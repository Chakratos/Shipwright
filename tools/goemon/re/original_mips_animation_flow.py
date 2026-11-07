#!/usr/bin/env python3
"""Static control-flow and register-constant analysis for the ORIGINAL MIPS
Goemon64Recomp skeletal evaluator func_800192D0_19ED0.

The source 245-instruction MIPS routine is taken from the user's OWN ROM.
This analysis models MIPS branch/jump delay slots (including branch-likely),
tracks direct JAL calls and computes LUI+ADDIU/ORI-addressed animation
globals without executing any commercial game code.

It deliberately does NOT pretend to have decoded the compression algorithm
until its actual instructions are inspected and ported.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import json
import struct

ANIMATION_GLOBALS={
    0x801684A0:"active_render_object",
    0x801684B0:"active_original_4x4_matrix",
    0x801684F0:"original_animation_or_limb_pointer",
    0x80168510:"source_animation_progress",
    0x80168514:"source_player_blend_progress",
    0x80168518:"source_animation_flags_low_byte",
    0x8016851C:"source_animation_flags_top_bit",
    0x80168520:"source_animation_data_pointer",
}
_LOAD_OPS={0x20:"lb",0x21:"lh",0x23:"lw",0x24:"lbu",0x25:"lhu",
           0x31:"lwc1"}
_STORE_OPS={0x28:"sb",0x29:"sh",0x2B:"sw",0x39:"swc1"}
_BRANCH_OPS={4,5,6,7,0x14,0x15,0x16,0x17}
_BRANCH_LIKELY={0x14,0x15,0x16,0x17}
_REGIMM_BRANCHES={0,1,2,3,16,17,18,19}
_REGIMM_LIKELY={2,3,18,19}


def signed16(v:int)->int:
    x=v&0xFFFF
    return x-65536 if x&0x8000 else x


@dataclass(frozen=True)
class OriginalMipsTransfer:
    pc:int
    kind:str
    target:int | None
    fallthrough:int | None
    delay_slot:int | None
    annul_delay_if_not_taken:bool=False


def classify_original_mips_transfer(pc:int,word:int)->OriginalMipsTransfer|None:
    op=word>>26
    rs=(word>>21)&31
    rt=(word>>16)&31
    fun=word&63
    target=None
    fallthrough=pc+8
    kind=""
    likely=False
    if op in (2,3):
        target=((pc+4)&0xF0000000)|((word&0x03FFFFFF)<<2)
        kind="jump" if op==2 else "call"
    elif op in _BRANCH_OPS:
        target=(pc+4+signed16(word)*4)&0xFFFFFFFF
        kind="conditional_branch"
        likely=op in _BRANCH_LIKELY
    elif op==1 and rt in _REGIMM_BRANCHES:
        target=(pc+4+signed16(word)*4)&0xFFFFFFFF
        kind="conditional_branch"
        likely=rt in _REGIMM_LIKELY
    elif op==17 and rs==8:
        target=(pc+4+signed16(word)*4)&0xFFFFFFFF
        kind="conditional_branch"
        likely=bool(rt&2)
    elif op==0 and fun in (8,9):
        kind="return" if fun==8 and rs==31 else (
            "indirect_call" if fun==9 else "indirect_jump")
    else:
        return None
    if kind in ("jump","return","indirect_jump"):
        fallthrough=None
    # JAL and JALR return to PC+8 after executing a mandatory delay slot.
    return OriginalMipsTransfer(pc,kind,target,fallthrough,pc+4,likely)


@dataclass(frozen=True)
class OriginalMipsBlock:
    start:int
    stop:int
    successor_pcs:tuple[int,...]
    branch_delay_at:int | None
    terminator:str


def build_original_mips_basic_blocks(
    data:bytes,entry:int
)->dict:
    if not data or len(data)%4:
        raise ValueError("original MIPS function must contain aligned words")
    if entry%4:
        raise ValueError("original MIPS entry unaligned")
    end=entry+len(data)
    words={
        entry+off:struct.unpack_from(">I",data,off)[0]
        for off in range(0,len(data),4)
    }
    transfers={pc:t for pc,word in words.items()
               if (t:=classify_original_mips_transfer(pc,word))}
    leaders={entry}
    delay_slots={t.delay_slot for t in transfers.values()
                 if t.delay_slot in words}
    external_calls=[]
    for t in transfers.values():
        if t.target is not None and t.kind in ("call","indirect_call"):
            external_calls.append({"at":f"0x{t.pc:08X}",
                                   "target":f"0x{t.target:08X}"})
        if t.target in words and t.kind in ("conditional_branch","jump"):
            leaders.add(t.target)
        # Split after all transfer delay slots, including JR/return. The
        # following instructions exist in ROM but are not always reachable.
        if t.pc+8 in words:
            leaders.add(t.pc+8)
    ambiguous_jump_into_delay=sorted(leaders&delay_slots)
    if ambiguous_jump_into_delay:
        # Such control flow is legal in some MIPS programs but requires a
        # two-entry delayed block. Fail closed instead of misanalyzing it.
        raise ValueError("MIPS original function branches into delay slot")
    leaders_sorted=sorted(leaders)
    blocks=[]
    for idx,start in enumerate(leaders_sorted):
        stop=leaders_sorted[idx+1] if idx+1<len(leaders_sorted) else end
        # Find last control transfer including its delay slot in this block.
        last=None
        for pc in range(start,stop,4):
            if pc in transfers and (pc+8<=stop):
                last=transfers[pc]
        if last is None:
            successors=(stop,) if stop in words else ()
            term="linear"
            delay=None
        else:
            candidates=[]
            if last.target in words and last.kind in (
                "conditional_branch","jump"):
                candidates.append(last.target)
            if last.fallthrough in words:
                candidates.append(last.fallthrough)
            successors=tuple(dict.fromkeys(candidates))
            term=last.kind
            delay=last.delay_slot
        blocks.append(OriginalMipsBlock(
            start,stop,successors,delay,term))
    index={b.start:b for b in blocks}
    reachable=set()
    pending=[entry]
    while pending:
        at=pending.pop()
        if at in reachable:
            continue
        if at not in index:
            raise ValueError("original MIPS CFG has non-block successor")
        reachable.add(at)
        pending.extend(x for x in index[at].successor_pcs
                       if x not in reachable)
    out={
        "entry":f"0x{entry:08X}",
        "instructions":len(words),
        "basic_blocks":len(blocks),
        "reachable_blocks":len(reachable),
        "unreachable_blocks":len(blocks)-len(reachable),
        "calls":external_calls,
        "conditional_branch_count":sum(
            t.kind=="conditional_branch" for t in transfers.values()),
        "branch_likely_count":sum(
            t.annul_delay_if_not_taken for t in transfers.values()),
        "delay_slot_count":len(delay_slots),
        "edges":[
            {"from":f"0x{b.start:08X}",
             "to":f"0x{s:08X}",
             "kind":b.terminator}
            for b in blocks for s in b.successor_pcs
        ],
        "blocks":[
            {"start":f"0x{b.start:08X}",
             "end_exclusive":f"0x{b.stop:08X}",
             "reachable":b.start in reachable,
             "terminator":b.terminator,
             "delay_slot":(
                 f"0x{b.branch_delay_at:08X}" if b.branch_delay_at is not None
                 else None),
             "successors":[f"0x{s:08X}" for s in b.successor_pcs]}
            for b in blocks
        ],
    }
    return out


def find_original_animation_global_accesses(
    data:bytes,entry:int
)->list[dict]:
    """Conservative LUI->ADDIU/ORI or LUI->load/store global-address scan.

    Reset constants at every control transfer; do not invent values
    across unknown branches/loops. The emitted memory references can be
    used for a focused disassembly slice around the animation codec.
    """
    if len(data)%4 or entry%4:
        raise ValueError("unaligned source original MIPS data")
    # Known globals can be fields inside an Object, but we explicitly
    # report only direct full virtual addresses from LUI/offset patterns.
    reg: list[int|None]=[None]*32
    reg[0]=0
    accesses=[]
    def write(dest:int,value:int|None):
        if dest!=0:reg[dest]=value
    for off in range(0,len(data),4):
        pc=entry+off
        word=struct.unpack_from(">I",data,off)[0]
        op=word>>26
        rs=(word>>21)&31
        rt=(word>>16)&31
        rd=(word>>11)&31
        imm=word&0xffff
        if op in (*_LOAD_OPS,*_STORE_OPS):
            base=reg[rs]
            if base is not None:
                absolute=(base+signed16(imm))&0xffffffff
                for address,name in ANIMATION_GLOBALS.items():
                    # The original matrix is a 64-byte span.
                    if address==absolute or (
                        address==0x801684B0 and
                        address<=absolute<address+64):
                        accesses.append({
                            "pc":f"0x{pc:08X}",
                            "operation":_LOAD_OPS.get(op,_STORE_OPS.get(op)),
                            "address":f"0x{absolute:08X}",
                            "known_animation_global":name,
                            "base_register":rs,
                            "data_register":rt,
                        })
            if op in _LOAD_OPS and op!=0x31:write(rt,None)
        elif op==0x0f:
            write(rt,imm<<16)
        elif op==0x0d:
            write(rt,((reg[rs]|imm)&0xffffffff)
                  if reg[rs] is not None else None)
        elif op==0x0c:
            write(rt,((reg[rs]&imm)&0xffffffff)
                  if reg[rs] is not None else None)
        elif op in (0x08,0x09):
            write(rt,((reg[rs]+signed16(imm))&0xffffffff)
                  if reg[rs] is not None else None)
        elif op==0 and (word&63)==0x00:
            source=(word>>16)&31
            shift=(word>>6)&31
            write(rd,(reg[source]<<shift)&0xffffffff
                  if reg[source] is not None else None)
        elif op==0 and (word&63) in (0x21,0x25):
            x=reg[rs];y=reg[rt]
            write(rd,((x+y) if (word&63)==0x21 else (x|y))&0xffffffff
                  if x is not None and y is not None else None)
        else:
            # This is a diagnostic, not a register emulator. Unknown
            # register destinations are invalidated conservatively.
            if op in (0x0a,0x0b,0x0e,0x22,0x26):write(rt,None)
            if op==0 and (word&63) in (0x02,0x03,0x20,0x23,0x24,0x26,0x27,0x2a):
                write(rd,None)
        if classify_original_mips_transfer(pc,word) is not None:
            # Delay-slot effects are not propagated across control
            # transfers. A separate CFG-aware analyzer can refine this;
            # report only syntactically local definite LUI references.
            reg=[None]*32
            reg[0]=0
    return accesses


def source_mips_flow_report(source:bytes,entry:int)->dict:
    return {
        "control_flow":build_original_mips_basic_blocks(source,entry),
        "direct_animation_global_memory_accesses":
            find_original_animation_global_accesses(source,entry),
        "limits":[
            "CFG is static: runtime indirect jump/call targets unknown",
            "LUI address recognition is conservative, not a full emulator",
            "No original decoded keyframe or live game context inferred",
        ]
    }
