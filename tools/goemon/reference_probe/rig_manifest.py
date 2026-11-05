#!/usr/bin/env python3
"""Summarize original Goemon character rig pointers captured in GOEMON_RIG logs.

The original N64 pointer values are preserved without pretending that they
are direct offsets into a ROM file. The overlay load address and file ID are
recorded so correct relocation can be established after reference runs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PREFIX = 'GOEMON_RIG,'
UNRESOLVED = 'GOEMON_RIG_UNRESOLVED,'
KEYS = ('frame','character_id','action_id','graphics_pointer','flags',
        'animation_pointer','skeleton_pointer','overlay_zero_base','overlay_zero_file_id')

def parse_log(lines: list[str]) -> dict:
    captures = []
    unresolved = []
    prev_frame = -1
    for line_number,line in enumerate(lines,1):
        if PREFIX in line:
            rec = line[line.index(PREFIX)+len(PREFIX):].strip().split(',')
            if len(rec)!=9:
                raise ValueError(f'line {line_number}: GOEMON_RIG must have 9 fields')
            try:
                values = [int(x,10) if i<3 else int(x,16) for i,x in enumerate(rec)]
            except ValueError as exc:
                raise ValueError(f'line {line_number}: invalid rig value') from exc
            entry = dict(zip(KEYS,values))
            if entry['frame'] < prev_frame:
                raise ValueError(f'line {line_number}: out-of-order rig frame')
            if entry['character_id'] not in range(256):
                raise ValueError(f'line {line_number}: character index outside byte range')
            prev_frame=entry['frame']
            captures.append(entry)
        elif UNRESOLVED in line:
            rec=line[line.index(UNRESOLVED)+len(UNRESOLVED):].strip().split(',')
            if len(rec)!=3:
                raise ValueError(f'line {line_number}: unresolved record must have 3 fields')
            try:
                unresolved.append({'frame':int(rec[0]),'character_id':int(rec[1]),
                                   'graphics_pointer':int(rec[2],16)})
            except ValueError as exc:
                raise ValueError(f'line {line_number}: invalid unresolved record') from exc
    if not captures and not unresolved:
        raise ValueError('no original Goemon rig records found')
    return {'rig_captures':captures,'unresolved_captures':unresolved,
            'warning':'Graphics pointers and animation/skeleton pointers are still original N64 virtual addresses.'}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('log_file',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    try:
        data=parse_log(a.log_file.read_text(encoding='utf-8',errors='replace').splitlines())
        output=json.dumps(data,indent=2)+'\n'
        if a.output:a.output.write_text(output,encoding='utf-8')
        else:print(output,end='')
    except (ValueError,OSError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
