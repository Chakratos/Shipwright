#!/usr/bin/env python3
"""ROM-private original NG5E player indirect JR/jump-table candidates.

Never serializes instruction words or table contents. Public-source function
boundaries + target-PC/count summaries are diagnostics, not live dispatch proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

PLAYER_DISPATCH_PCS = (0x801DA23C, 0x801E0980)


def table_runs(payload: bytes, low_pc: int, high_pc: int, *,
               min_entries: int = 3, max_results: int = 16) -> list[dict]:
    if len(payload) % 4 or low_pc >= high_pc or min_entries < 2:
        raise ValueError('invalid aligned original overlay region or target bound')
    words = struct.unpack('>' + 'I' * (len(payload) // 4), payload)
    runs = []
    first = None
    targets: list[int] = []

    def flush() -> None:
        nonlocal first, targets
        if first is not None and len(targets) >= min_entries:
            unique = sorted(set(targets))
            runs.append({
                'table_offset_within_original_overlay': f'0x{first * 4:06X}',
                'entry_count': len(targets),
                'unique_in_function_target_count': len(unique),
                'first_unique_target_pcs': [f'0x{x:08X}' for x in unique[:12]],
                'is_verified_active_switch_table': False,
            })
        first, targets = None, []

    for index, value in enumerate(words):
        if low_pc <= value < high_pc and value % 4 == 0:
            if first is None:
                first = index
            targets.append(value)
        else:
            flush()
    flush()
    runs.sort(key=lambda run: (-run['entry_count'],
                               run['table_offset_within_original_overlay']))
    return runs[:max_results]


def inspect_indirect_jump(payload: bytes, base_vram: int, jump_pc: int,
                          function_start: int, function_size: int) -> dict:
    if len(payload) % 4 or not (function_start <= jump_pc <
                                 function_start + function_size):
        raise ValueError('jump outside matched original function')
    offset = jump_pc - base_vram
    if offset < 0 or offset + 4 > len(payload) or offset % 4:
        raise ValueError('jump PC outside original overlay executable')
    word = struct.unpack_from('>I', payload, offset)[0]
    if word >> 26 != 0 or word & 63 != 8:
        raise ValueError('original dispatch site not a MIPS JR instruction')
    reg = (word >> 21) & 31
    if reg == 31:
        raise ValueError('JR ra return is not indirect action dispatch')
    preceding_lw = []
    for index in range(max(0, function_start - base_vram) // 4, offset // 4):
        w = struct.unpack_from('>I', payload, index * 4)[0]
        if w >> 26 == 0x23 and ((w >> 16) & 31) == reg:
            preceding_lw.append(base_vram + index * 4)
    return {
        'jr_pc': f'0x{jump_pc:08X}',
        'original_function_start_pc': f'0x{function_start:08X}',
        'original_function_size': function_size,
        'jr_target_register': f'r{reg}',
        'last_syntactic_lw_to_jr_register_pc': (
            f'0x{preceding_lw[-1]:08X}' if preceding_lw else None),
        'syntactic_lw_count_within_source_function': len(preceding_lw),
        'hypothesis_only_not_original_register_runtime': True,
        'possible_absolute_vram_target_pointer_runs': table_runs(
            payload, function_start, function_start + function_size),
    }


def analyze_original_overlay(payload: bytes, base_vram: int,
                             symbols: list[dict], dispatch_pcs=PLAYER_DISPATCH_PCS) -> dict:
    findings = []
    for pc in dispatch_pcs:
        matches = [f for f in symbols if
                   f['start'] <= pc < f['start'] + f['size']]
        if len(matches) != 1:
            raise ValueError('indirect dispatch not uniquely mapped to pinned symbol')
        f = matches[0]
        finding = inspect_indirect_jump(
            payload, base_vram, pc, f['start'], f['size'])
        finding['source_function_name'] = f['name']
        findings.append(finding)
    return {
        'schema': 'ng5e-player-indirect-jr-address-metadata-v1',
        'source_only_no_original_rom_bytes_serialized': True,
        'confirmed_runtime_action_dispatch': False,
        'indirect_jump_functions': findings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path)
    parser.add_argument('--output', type=Path, default=Path(
        r'C:\actions-runner-goemon\original-player-jump-table-candidates.json'))
    args = parser.parse_args(argv)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from character_assets import read_file_table
        from character_id_binding import source_proven_character_graphics
        from probe_original_mips_execution import verified_decoded_original_rom
        from real_rom_check import locate_rom
        from scan_player_object_writers import (
            PLAYER_ORIGINAL_ROUTINE_ROM, PLAYER_ORIGINAL_ROUTINE_VRAM)
        from trace_player_writer_cfg import read_pinned_player_overlay_functions
        original = verified_decoded_original_rom(
            (args.rom or locate_rom()).read_bytes())
        source_proven_character_graphics(original)
        pinned, symbols = read_pinned_player_overlay_functions()
        matches = [f for f in read_file_table(original)
                   if f.start <= PLAYER_ORIGINAL_ROUTINE_ROM < f.end]
        if len(matches) != 1:
            raise ValueError('player routine not in unique owner ROM file')
        entry = matches[0]
        expected = pinned['provenance']
        base = PLAYER_ORIGINAL_ROUTINE_VRAM - (
            PLAYER_ORIGINAL_ROUTINE_ROM - entry.start)
        if (entry.file_id != 10 or
                entry.start != int(expected['rom_start'], 16) or
                entry.end - entry.start != int(expected['size'], 16) or
                base != int(expected['vram_start'], 16)):
            raise ValueError('owner-ROM player executable differs from pinned symbols')
        payload = original[entry.start:entry.end]
        report = analyze_original_overlay(payload, base, symbols)
        report['original_overlay_file_id'] = entry.file_id
        root = Path(__file__).resolve().parents[3]
        output = args.output.resolve()
        if output == root or root in output.parents:
            raise ValueError('private original game report must stay outside checkout')
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        for row in report['indirect_jump_functions']:
            print('GOEMON_INDIRECT_JR', row['jr_pc'],
                  'source_function=', row['original_function_start_pc'],
                  'reg=', row['jr_target_register'],
                  'last_lw_pc=', row['last_syntactic_lw_to_jr_register_pc'],
                  'absolute_vram_table_candidates=',
                  len(row['possible_absolute_vram_target_pointer_runs']))
            for run in row['possible_absolute_vram_target_pointer_runs'][:5]:
                print('GOEMON_INDIRECT_TABLE_CANDIDATE',
                      row['jr_pc'],
                      'local_offset=', run['table_offset_within_original_overlay'],
                      'count=', run['entry_count'],
                      'unique_target_pc_count=', run['unique_in_function_target_count'])
        print('GOEMON_INDIRECT_JR COMPLETE: static table hypotheses only')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print('GOEMON_INDIRECT_JR FAILED:', exc, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
