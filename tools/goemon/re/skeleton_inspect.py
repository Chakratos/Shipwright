#!/usr/bin/env python3
"""Parse original MNSG AnimatedSkeleton and Skeleton records from raw binary files.

This reproduces documented Goemon64Recomp patch structure layout only.
Pointer relocation, display lists, texture decoding and animations are not
implemented; the caller must provide verified offsets in the data file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

SKELETON_SIZE = 24  # 4 + 1 + 1 + 3*6, MIPS big-endian
ANIMATED_SKELETON_HEADER_SIZE = 12

def require(data: bytes, offset: int, size: int):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(f'out of bounds read at 0x{offset:X} (+{size})')

def parse_skeleton(data: bytes, offset: int) -> dict:
    require(data,offset,SKELETON_SIZE)
    dlist, right, left, *numbers = struct.unpack_from('>Ibb9h', data, offset)
    return {
        'file_offset':offset,'display_list_pointer':f'0x{dlist:08X}',
        'offset_right':right,'offset_left':left,
        'scale_raw':numbers[0:3],'rotation_raw':numbers[3:6],
        'translation_raw':numbers[6:9],
    }

def parse_animated_skeleton(data: bytes, offset: int, pointer_count: int = 1) -> dict:
    if not 1 <= pointer_count <= 128:
        raise ValueError('pointer count must be in range 1..128')
    require(data,offset,8+4*pointer_count)
    flags, animation_pointer = struct.unpack_from('>II',data,offset)
    skeleton_pointers=list(struct.unpack_from('>'+('I'*pointer_count),data,offset+8))
    return {
        'file_offset':offset,'flags':f'0x{flags:08X}',
        'animation_pointer':f'0x{animation_pointer:08X}',
        'skeleton_pointers':[f'0x{p:08X}' for p in skeleton_pointers],
        'base_transforms':(flags>>28)&7,
        'additional_transforms':(flags>>24)&15,
        'limb_count':(flags>>8)&0x7fff,
        'animation_parameter_low_byte':flags&255,
        'high_bit_flag':bool(flags & 0x80000000),
    }

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file',type=Path)
    p.add_argument('--offset',type=lambda x: int(x,0),required=True,
                   help='verified record offset relative to provided file (hex supported)')
    p.add_argument('--type',choices=['skeleton','animated'],required=True)
    p.add_argument('--pointer-count',type=int,default=1)
    a=p.parse_args()
    try:
        data=a.file.read_bytes()
        if a.type=='skeleton':
            result=parse_skeleton(data,a.offset)
        else:
            result=parse_animated_skeleton(data,a.offset,a.pointer_count)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':sys.exit(main())
