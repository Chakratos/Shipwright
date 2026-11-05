#!/usr/bin/env python3
"""Resolve captured Goemon rig pointers into an original graphic binary.

Supports original segment 8 and direct N64 addresses inside the recorded
segment-8 overlay. It verifies runtime flags and pointers against the
provided asset; no heuristic mapping or substitute rig is used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from skeleton_inspect import parse_animated_skeleton, parse_skeleton

def resolve_pointer(pointer: int, overlay_base: int, file_length: int) -> int:
    if pointer == 0:
        raise ValueError('null original asset pointer')
    segment = (pointer >> 24) & 0xFF
    if 0x08 <= segment <= 0x0D:
        if segment != 0x08:
            raise ValueError(f'segment 0x{segment:02X} needs a separate overlay mapping')
        offset = pointer & 0x00FFFFFF
    elif pointer & 0x80000000:
        if overlay_base == 0:
            raise ValueError('direct N64 pointer requires recorded overlay base')
        offset = pointer - overlay_base
    else:
        raise ValueError(f'unsupported N64 pointer 0x{pointer:08X}')
    if not 0 <= offset < file_length:
        raise ValueError(f'pointer 0x{pointer:08X} maps outside {file_length} bytes')
    return offset

def decode_rig(binary: bytes, capture: dict, expected_file_id: int) -> dict:
    if capture['overlay_zero_file_id'] != expected_file_id:
        raise ValueError('captured overlay file ID does not match extracted graphic file ID')
    graphics = capture['graphics_pointer']
    if (graphics & 0x70000000) != 0x60000000:
        raise ValueError('not a Goemon player-skeleton graphics object')
    ptr = graphics & 0x8FFFFFFE
    base = capture['overlay_zero_base']
    root_offset = resolve_pointer(ptr, base, len(binary))
    header = parse_animated_skeleton(binary, root_offset)
    if int(header['flags'],16) != capture['flags']:
        raise ValueError('original AnimatedSkeleton flags differ from runtime trace')
    if int(header['animation_pointer'],16) != capture['animation_pointer']:
        raise ValueError('original animation pointer differs from runtime trace')
    if int(header['skeleton_pointers'][0],16) != capture['skeleton_pointer']:
        raise ValueError('original skeleton pointer differs from runtime trace')
    bone_offset = resolve_pointer(capture['skeleton_pointer'], base, len(binary))
    skeleton = parse_skeleton(binary, bone_offset)
    return {
        'character_id':capture['character_id'],
        'overlay_file_id':expected_file_id,
        'root_animated_skeleton':header,
        'first_skeleton':skeleton,
        'note':'Original records decoded; full limb hierarchy, animation and display lists still need conversion.'
    }

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rig_manifest',type=Path)
    p.add_argument('extracted_graphics_bin',type=Path)
    p.add_argument('--character-id',type=int,required=True)
    p.add_argument('--file-id',type=int,required=True)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        records=json.loads(a.rig_manifest.read_text(encoding='utf-8'))['rig_captures']
        capture=next((r for r in records if r['character_id']==a.character_id and
                      r['overlay_zero_file_id']==a.file_id),None)
        if capture is None:
            raise ValueError('no matching original character/overlay capture in rig manifest')
        result=decode_rig(a.extracted_graphics_bin.read_bytes(),capture,a.file_id)
        output=json.dumps(result,indent=2)+'\n'
        if a.output:a.output.write_text(output,encoding='utf-8')
        else:print(output,end='')
    except (ValueError,OSError,KeyError,StopIteration) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
