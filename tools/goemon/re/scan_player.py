#!/usr/bin/env python3
"""Rank original Goemon MIPS player-function candidates by actual memory accesses.

Requires a locally owned decompressed NTSC-U Goemon ROM and a matching
N64Recomp symbol TOML. Reports priorities, not proven physics routines.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys
import tomllib

from mips_dataflow import trace_fields

EXPECTED_DECOMPRESSED_HEADER_CRC = (0x9CC11F4B, 0xABAA8538)
PLAYER_ANCHORS = {0x801CB800, 0x801DAF54, 0x801DC9C8, 0x801DCA64}


def enumerate_functions(symbols: dict, section_name: str) -> list[dict]:
    sections = [s for s in symbols.get('section', []) if s.get('name') == section_name]
    if len(sections) != 1:
        raise ValueError(f'exactly one symbol section {section_name!r} required')
    section = sections[0]
    result = []
    for f in section.get('functions', []):
        offset = f['vram'] - section['vram']
        size = f['size']
        if offset < 0 or size <= 0 or size % 4 or offset + size > section['size']:
            raise ValueError(f'function outside ROM section: {f["name"]}')
        result.append({'name': f['name'], 'vram': f['vram'], 'size': size,
                       'rom_offset': section['rom'] + offset})
    if not result:
        raise ValueError(f'no functions found in {section_name}')
    return sorted(result, key=lambda v: v['vram'])


def extract_words(rom: bytes, f: dict) -> list[tuple[int, int]]:
    start = f['rom_offset']; size = f['size']
    if start < 0 or start + size > len(rom):
        raise ValueError(f'ROM missing function {f["name"]}')
    return [(f['vram'] + offset, struct.unpack_from('>I', rom, start + offset)[0])
            for offset in range(0, size, 4)]


def jal_target(pc: int, word: int) -> int | None:
    if word >> 26 != 3:
        return None
    return ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)


def analyze(rom: bytes, symbols: dict, *, section: str = '.file_11',
            validate_crc: bool = True, max_results: int = 100) -> dict:
    if len(rom) < 0x40 or rom[:4] != bytes.fromhex('80371240'):
        raise ValueError('expected a decompressed, big-endian .z64 ROM')
    if validate_crc and struct.unpack_from('>II', rom, 0x10) != EXPECTED_DECOMPRESSED_HEADER_CRC:
        raise ValueError('ROM header CRC does not match Goemon64Recomp decompressed US reference')
    if max_results < 1:
        raise ValueError('max_results must be positive')
    functions = enumerate_functions(symbols, section)
    by_addr = {f['vram']: f['name'] for f in functions}
    result = []
    for f in functions:
        words = extract_words(rom, f)
        accesses = trace_fields(words)
        calls = []
        for pc, word in words:
            target = jal_target(pc, word)
            if target is not None:
                calls.append({'pc': f'0x{pc:08X}', 'target': f'0x{target:08X}',
                              'name': by_addr.get(target)})
        opaque_writes = sum(a['direction'] == 'write' and a.get('object') == 'opaque_player'
                            for a in accesses)
        action_writes = sum(a['direction'] == 'write' and a['field'] == 'action_id'
                            for a in accesses)
        character_writes = sum(a['direction'] == 'write' and a['field'] == 'character_id'
                               for a in accesses)
        reads = sum(a['direction'] == 'read' for a in accesses)
        score = 100 * opaque_writes + 75 * action_writes + 50 * character_writes + 10 * reads
        score += sum(2 for call in calls if int(call['target'], 16) in PLAYER_ANCHORS)
        if accesses or any(int(c['target'], 16) in PLAYER_ANCHORS for c in calls):
            result.append({
                'name': f['name'], 'vram': f'0x{f["vram"]:08X}',
                'rom_offset': f'0x{f["rom_offset"]:08X}',
                'size': f['size'], 'priority_score': score,
                'field_accesses': accesses, 'direct_calls': calls,
            })
    result.sort(key=lambda r: (-r['priority_score'], int(r['vram'], 16)))
    totals = Counter(a['field'] for f in result for a in f['field_accesses'])
    return {
        'rom_sha256': hashlib.sha256(rom).hexdigest(),
        'section': section, 'functions_scanned': len(functions),
        'functions_with_evidence': len(result),
        'accesses_by_field': dict(sorted(totals.items())),
        'candidates': result[:max_results],
        'limitations': [
            'Field evidence is conservatively proven only within straight-line local code.',
            'Functions receiving PlayerTask or Player pointers via arguments may not be recognized.',
            'JALR, calls across overlays and control-flow joins require additional analysis.',
            'Candidate ranking is not an original physics implementation.',
        ]
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decompressed_z64', type=Path)
    parser.add_argument('symbols_toml', type=Path)
    parser.add_argument('--section', default='.file_11')
    parser.add_argument('--top', type=int, default=100)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        report = analyze(args.decompressed_z64.read_bytes(),
                         tomllib.loads(args.symbols_toml.read_text(encoding='utf-8')),
                         section=args.section, max_results=args.top)
        payload = json.dumps(report, indent=2) + '\n'
        if args.output:
            args.output.write_text(payload, encoding='utf-8')
        else:
            print(payload, end='')
    except (ValueError, OSError, tomllib.TOMLDecodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
