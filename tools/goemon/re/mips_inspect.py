#!/usr/bin/env python3
"""Decode original MIPS R4300i player-overlay instructions, without exporting ROM code.

This is an analyst's disassembly aid, not a physics implementation. Field-offset
matches are candidates until register provenance and semantics are verified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys
import tomllib
from mips_dataflow import trace_fields

REGS = (
    'zero', 'at', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3',
    't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7',
    's0', 's1', 's2', 's3', 's4', 's5', 's6', 's7',
    't8', 't9', 'k0', 'k1', 'gp', 'sp', 'fp', 'ra',
)
MEMORY = {0x20:'lb',0x21:'lh',0x23:'lw',0x24:'lbu',0x25:'lhu',
          0x28:'sb',0x29:'sh',0x2b:'sw',0x31:'lwc1',0x39:'swc1',
          0x35:'ldc1',0x3d:'sdc1'}
FIELDS = {0x5c:'PlayerTask.player_ptr',0x60:'PlayerTask.character_id',
          0xcc:'PlayerTask.action_id'}

def sign16(n: int) -> int:
    return (n & 0xffff) - (0x10000 if n & 0x8000 else 0)

def decode(pc: int, word: int) -> dict:
    op = word >> 26
    rs, rt, rd = (word >> 21)&31, (word >> 16)&31, (word >> 11)&31
    imm = sign16(word)
    output = {'pc':f'0x{pc:08X}', 'opcode':f'0x{word:08X}', 'mnemonic':'unknown'}
    if op in MEMORY:
        output.update(mnemonic=MEMORY[op], source=REGS[rs], destination=REGS[rt], offset=imm)
        if (word & 0xffff) in FIELDS:
            output['candidate_field'] = FIELDS[word & 0xffff]
            output['field_unconfirmed'] = True
    elif op in (2,3):
        dest = ((pc+4)&0xf0000000) | ((word & 0x03ffffff)<<2)
        output.update(mnemonic='jal' if op==3 else 'j', target=f'0x{dest:08X}')
    elif op == 0:
        fn = word & 63
        if fn in (8,9):
            output.update(mnemonic='jalr' if fn==9 else 'jr', source=REGS[rs])
        elif word==0:
            output['mnemonic']='nop'
        elif fn in (0,2,3):
            output.update(mnemonic={0:'sll',2:'srl',3:'sra'}[fn],destination=REGS[rd], source=REGS[rt], shift=(word>>6)&31)
    elif op in (4,5,6,7):
        dest=(pc+4+(imm<<2))&0xffffffff
        output.update(mnemonic={4:'beq',5:'bne',6:'blez',7:'bgtz'}[op], source=REGS[rs], destination=REGS[rt], target=f'0x{dest:08X}')
    elif op in (8,9,0x0c,0x0d,0x0f):
        output.update(mnemonic={8:'addi',9:'addiu',12:'andi',13:'ori',15:'lui'}[op], source=REGS[rs], destination=REGS[rt], immediate=imm if op in (8,9) else word & 65535)
    elif op==0x11:
        fmt=(word>>21)&31
        funct=word&63
        if fmt in (16,17) and funct in (0,1,2,3,6,7,0x20,0x21):
            output.update(mnemonic={0:'add',1:'sub',2:'mul',3:'div',6:'mov',7:'neg',0x20:'cvt.s',0x21:'cvt.d'}[funct]+('.s' if fmt==16 else '.d'), f_dest=(word>>6)&31, f_src=(word>>11)&31, f_other=(word>>16)&31)
    return output

def find_function(table: dict, name: str) -> tuple[int,int,int,str]:
    for section in table.get('section', []):
        for f in section.get('functions', []):
            if f['name'] == name:
                section_vram = section['vram']; fn_vram=f['vram']; size=f['size']
                if not section_vram <= fn_vram or fn_vram+size>section_vram+section['size'] or size % 4:
                    raise ValueError('symbol bounds inconsistent with ROM section')
                return section['rom']+(fn_vram-section_vram),fn_vram,size,section['name']
    raise ValueError(f'unknown function {name}')

def inspect(rom: bytes, table: dict, func_name: str) -> dict:
    if rom[:4] != b'\x80\x37\x12\x40':
        raise ValueError('expected big-endian decompressed .z64 ROM')
    rom_start,vram,size,section=find_function(table,func_name)
    if rom_start<0 or rom_start+size>len(rom):
        raise ValueError('function extends outside ROM')
    words=[(vram+o,struct.unpack_from('>I',rom,rom_start+o)[0]) for o in range(0,size,4)]
    instructions=[decode(pc, word) for pc, word in words]
    return {'function':func_name,'section':section,'rom_start':f'0x{rom_start:08X}',
            'instructions':instructions,'proven_player_fields':trace_fields(words),'field_candidates':[x for x in instructions if 'candidate_field' in x],
            'direct_calls':[x['target'] for x in instructions if x['mnemonic']=='jal'],
            'limitations':['Field-offset matches have no base-register provenance.',
                           'COP1 decoding is partial; indirect calls unresolved.']}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',type=Path)
    p.add_argument('symbols',type=Path)
    p.add_argument('function_name')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        report=inspect(a.rom.read_bytes(),tomllib.loads(a.symbols.read_text('utf-8')),a.function_name)
        content=json.dumps(report,indent=2)+'\n'
        if a.output:a.output.write_text(content,encoding='utf-8')
        else: print(content,end='')
    except (OSError,ValueError,tomllib.TOMLDecodeError) as ex:
        print(f'ERROR: {ex}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
