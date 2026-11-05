#!/usr/bin/env python3
"""Reconstruct the original Goemon Skeleton child/sibling hierarchy.

Goemon64Recomp patches/anime.c func_80018908_19508 and func_80018CA0_198A0
follow 'skeleton + offset_right' as a child and 'skeleton + offset_left'
as the sibling. These are signed offsets in 24-byte Skeleton elements.
Results retain raw N64 transforms; no guessed retargeting or angle scale.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from skeleton_inspect import SKELETON_SIZE, parse_skeleton


def traverse_hierarchy(data: bytes, root_offset: int, *, max_nodes: int = 256) -> dict:
    if max_nodes < 1:
        raise ValueError('max_nodes must be positive')
    if root_offset < 0 or root_offset % 4:
        raise ValueError('root skeleton file offset must be 4-byte aligned')
    visited: set[int] = set()
    nodes: list[dict] = []
    edges: list[dict] = []

    def visit(offset: int, parent: int | None, relation: str) -> None:
        if offset in visited:
            raise ValueError(f'cycle or shared node in original skeleton at 0x{offset:X}')
        if len(visited) >= max_nodes:
            raise ValueError('original skeleton node count exceeds configured limit')
        item = parse_skeleton(data, offset)
        visited.add(offset)
        nodes.append({'offset': offset, 'parent_offset': parent,
                      'relationship': relation, **item})
        if parent is not None:
            edges.append({'from_offset': parent, 'to_offset': offset, 'relation': relation})
        right = item['offset_right']
        left = item['offset_left']
        if right:
            visit(offset + right * SKELETON_SIZE, offset, 'child')
        if left:
            visit(offset + left * SKELETON_SIZE, parent, 'sibling')

    visit(root_offset, None, 'root')
    return {'root_offset': root_offset, 'node_count': len(nodes),
            'nodes': nodes, 'edges': edges,
            'warning': 'Raw N64 transforms; original animation decode and model conversion pending.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_graphics_bin',type=Path)
    p.add_argument('--root-offset',required=True,type=lambda x:int(x,0))
    p.add_argument('--max-nodes',type=int,default=256)
    p.add_argument('--output',type=Path)
    a=p.parse_args(argv)
    try:
        report=traverse_hierarchy(a.original_graphics_bin.read_bytes(),
                                  a.root_offset,max_nodes=a.max_nodes)
        payload=json.dumps(report,indent=2)+'\n'
        if a.output:a.output.write_text(payload,encoding='utf-8')
        else:print(payload,end='')
    except (OSError,ValueError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
