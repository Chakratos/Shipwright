#!/usr/bin/env python3
"""Conservative proof of original Goemon PlayerTask field accesses.

Tracks MIPS LUI/ORI/ADDIU constants, LW of known original player globals,
and field accesses through the resulting register. All provenance is dropped
at branches/calls; this intentionally misses some valid delayed accesses.
"""
from __future__ import annotations
from typing import Iterable

PLAYER_GLOBALS = {0x801FC604: 'g_player_1_task', 0x801FC608:'g_player_2_task'}
FIELDS = {0x5C:'player',0x60:'character_id',0x64:'camera_task',0xCC:'action_id'}
LOADS = {0x20,0x21,0x23,0x24,0x25,0x31,0x35}
STORES = {0x28,0x29,0x2B,0x39,0x3D}

def sign16(n:int)->int:
    n=n&0xffff
    return n-65536 if n>=32768 else n

def trace_fields(instructions:Iterable[tuple[int,int]])->list[dict]:
    reg: dict[int,tuple[str,int|str]] = {0:('const',0)}
    proof=[]
    for pc,word in instructions:
        op=word>>26
        rs=(word>>21)&31;rt=(word>>16)&31;rd=(word>>11)&31
        imm=word&0xffff
        value=None
        base=reg.get(rs)
        if op==0x0F:
            value=('const',imm<<16)
        elif op in (0x09,0x08,0x0d):
            if base and base[0]=='const':
                delta=imm if op==0x0d else sign16(imm)
                value=('const',((base[1] | delta) if op==0x0d else (base[1]+delta))&0xffffffff)
            elif base and base[0]=='task' and op in (0x08,0x09) and sign16(imm)==0:
                value=base
        elif op in LOADS|STORES:
            offset=sign16(imm)
            if base and base[0]=='const' and op==0x23:
                address=(base[1]+offset)&0xffffffff
                if address in PLAYER_GLOBALS:
                    value=('task',PLAYER_GLOBALS[address])
            if base and base[0]=='task' and offset in FIELDS:
                proof.append({
                    'pc':f'0x{pc:08X}', 'global':base[1],
                    'field':FIELDS[offset], 'offset':f'0x{offset:02X}',
                    'direction':'write' if op in STORES else 'read',
                })
        elif op==0:
            fn=word&63
            if fn in (0x21,0x20,0x25):
                a=reg.get(rs);b=reg.get(rt)
                if rs==0: value=b
                elif rt==0: value=a
                if rd:
                    if value is None:reg.pop(rd,None)
                    else:reg[rd]=value
            elif fn in (8,9):
                reg={0:('const',0)}
            elif rd and fn not in (8,9):
                reg.pop(rd,None)
        # Drop register provenance on unmodelled I-type writes. FPU loads
        # and memory stores do not overwrite an integer-register target.
        writes_rt = {0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,
                     0x20,0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x30,0x32,0x33,0x37}
        if op in writes_rt and rt:
            if value is None:reg.pop(rt,None)
            else:reg[rt]=value
        if op in (0x02,0x03,0x04,0x05,0x06,0x07,0x14,0x15,0x16,0x17):
            reg={0:('const',0)}
    return proof
