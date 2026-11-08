#!/usr/bin/env python3
"""Conservative NG5E MIPS player writer provenance (ROM remains private).

Reports only PCs, known symbol names, counts and uncertainty flags. Local
straight-line slices are NOT proof that a site runs on the live player.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

PLAYER_GLOBALS = {
    0x801FC604: 'player_1_task',
    0x801FC608: 'player_2_task',
    0x801FC60C: 'player_1_model_object',
    0x801FC610: 'player_2_model_object',
    0x801FC614: 'player_1_root_object',
    0x801FC618: 'player_2_root_object',
}
MAX_BACK = 96


def sign16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def control_transfer(word: int) -> bool:
    op = word >> 26
    if op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17):
        return True
    if op == 0:
        return (word & 63) in (8, 9)  # jr, jalr
    if op in (0x10, 0x11, 0x12, 0x13):
        return True  # conservative: unknown coprocessor/control side effects
    return False


def written_register(word: int) -> int | None:
    op = word >> 26
    if op == 0:
        funct = word & 63
        if funct in (0, 2, 3, 4, 6, 7, 0x10, 0x12, 0x20, 0x21,
                     0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x2A, 0x2B):
            return (word >> 11) & 31
        return None
    if op in (8, 9, 10, 11, 12, 13, 14, 15, 0x20, 0x21, 0x22,
              0x23, 0x24, 0x25, 0x26, 0x27, 0x30, 0x31, 0x32, 0x33,
              0x34, 0x35, 0x36, 0x37):
        return (word >> 16) & 31
    return None


def trace_register(words: tuple[int, ...] | list[int], before: int,
                   reg: int, *, budget: int = MAX_BACK) -> tuple[str, int | str | None]:
    """Find a local straight-line definition; stop at ALL control transfers.

    No assumption is made about inherited a0/s0 register values, indirect
    calls, delay slots, or paths across branches. This deliberately undercounts.
    """
    if reg == 0:
        return ('constant', 0)
    if budget <= 0:
        return ('unresolved', None)
    stop = max(0, before - budget)
    for pos in range(before - 1, stop - 1, -1):
        word = words[pos]
        if control_transfer(word):
            return ('control_flow_boundary', None)
        if written_register(word) != reg:
            continue
        op = word >> 26
        rs, rt = (word >> 21) & 31, (word >> 16) & 31
        imm = word & 0xFFFF
        remaining = budget - (before - pos)
        if op == 15 and rs == 0:  # lui
            return ('constant', (imm << 16) & 0xFFFFFFFF)
        if op in (9, 13):  # addiu, ori
            prior_kind, prior_value = trace_register(words, pos, rs, budget=remaining)
            if prior_kind == 'constant':
                operand = sign16(imm) if op == 9 else imm
                value = (int(prior_value) + operand if op == 9 else
                         int(prior_value) | operand)
                return ('constant', value & 0xFFFFFFFF)
            if imm == 0:
                return prior_kind, prior_value
            return ('unresolved', None)
        if op == 0 and (word & 63) in (0x21, 0x25):  # addu, or (move)
            lhs = trace_register(words, pos, rs, budget=remaining)
            rhs = trace_register(words, pos, rt, budget=remaining)
            if lhs == ('constant', 0):
                return rhs
            if rhs == ('constant', 0):
                return lhs
            if lhs[0] == rhs[0] == 'constant':
                result = (int(lhs[1]) + int(rhs[1]) if (word & 63) == 0x21
                          else int(lhs[1]) | int(rhs[1]))
                return ('constant', result & 0xFFFFFFFF)
            return ('unresolved', None)
        if op == 0x23:  # lw from exactly one pinned pointer global
            base_kind, base_value = trace_register(words, pos, rs, budget=remaining)
            if base_kind == 'constant':
                address = (int(base_value) + sign16(imm)) & 0xFFFFFFFF
                if address in PLAYER_GLOBALS:
                    return ('known_player_pointer_global_load', PLAYER_GLOBALS[address])
            return ('unresolved', None)
        return ('unresolved', None)  # register overwritten by any other instruction
    return ('unresolved', None)


def local_function_entry_hint(words: tuple[int, ...] | list[int], site: int,
                              base_pc: int) -> int | None:
    """Nearest conventional stack prologue; not a verified function boundary."""
    for pos in range(site - 1, max(-1, site - 1024), -1):
        w = words[pos]
        if w >> 26 == 9 and (w >> 21) & 31 == 29 and (w >> 16) & 31 == 29:
            if sign16(w) < 0:
                return base_pc + 4 * pos
    return None


def direct_callers(words: tuple[int, ...] | list[int], base_pc: int,
                   target_pc: int) -> list[str]:
    """Static jal matches only; indirect calls and actual execution unknown."""
    callers = []
    for i, w in enumerate(words):
        if w >> 26 == 3:
            pc = base_pc + 4 * i
            target = ((pc + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
            if target == target_pc:
                callers.append(f'0x{pc:08X}')
    return callers


def analyze_words(words: tuple[int, ...] | list[int], base_pc: int) -> dict:
    """Identify action sb +CC and non-stack graphics sw +2C sites."""
    if base_pc & 3:
        raise ValueError('MIPS VRAM base is not word-aligned')
    sites = []
    for idx, w in enumerate(words):
        op, offset = w >> 26, sign16(w)
        if not ((op == 0x28 and offset == 0xCC) or
                (op == 0x2B and offset == 0x2C)):
            continue
        base_reg = (w >> 21) & 31
        kind = 'action_id_offset' if op == 0x28 else 'graphics_1_offset'
        if kind == 'graphics_1_offset' and base_reg == 29:
            continue  # stack-frame writes aren't Object owner evidence
        origin, symbol = trace_register(words, idx, base_reg)
        entry = local_function_entry_hint(words, idx, base_pc)
        callers = direct_callers(words, base_pc, entry) if entry is not None else []
        caller_argument_hints = []
        for caller_pc in callers:
            caller_idx = (int(caller_pc, 16) - base_pc) // 4
            arg_origin, arg_symbol = trace_register(words, caller_idx, 4)
            # The JAL delay-slot may set a0. Do NOT attribute preceding a0 to
            # the call without checking that slot (a common source of false proofs).
            delay_slot_writes_a0 = (caller_idx + 1 < len(words) and
                                    written_register(words[caller_idx + 1]) == 4)
            caller_argument_hints.append({
                'direct_jal_pc': caller_pc,
                'pre_jal_a0_origin': arg_origin,
                'pre_jal_known_player_global': (
                    arg_symbol if arg_origin == 'known_player_pointer_global_load' else None),
                'delay_slot_may_override_a0': delay_slot_writes_a0,
                'player_argument_candidate': (
                    arg_origin == 'known_player_pointer_global_load' and
                    not delay_slot_writes_a0),
                'callee_identity_verified': False,
            })
        sites.append({
            'pc': f'0x{base_pc + 4 * idx:08X}',
            'kind': kind,
            'base_register': f'r{base_reg}',
            'base_origin': origin,
            'known_player_global': symbol if origin == 'known_player_pointer_global_load' else None,
            'nearby_function_prologue_hint': f'0x{entry:08X}' if entry is not None else None,
            'direct_jal_to_prologue_hint_count': len(callers),
            'first_direct_jal_to_prologue_hint_pcs': callers[:8],
            'caller_a0_known_player_global_hint_count': sum(
                c['player_argument_candidate'] for c in caller_argument_hints),
            'direct_jal_caller_a0_hints': caller_argument_hints[:16],
            'prologue_is_verified_function_boundary': False,
            'live_player_writer_verified': False,
        })
    by_kind = {}
    for kind in ('action_id_offset', 'graphics_1_offset'):
        selected = [s for s in sites if s['kind'] == kind]
        by_kind[kind] = {
            'non_stack_candidate_count': len(selected),
            'known_global_pointer_load_count': sum(
                s['base_origin'] == 'known_player_pointer_global_load' for s in selected),
            'sites': selected,
        }
    return {'schema': 'ng5e-player-writer-static-provenance-v1',
            'base_pc': f'0x{base_pc:08X}',
            'linear_local_provenance_only': True,
            'execution_or_active_animation_verified': False,
            'original_rom_payload_in_report': False,
            'by_kind': by_kind}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path)
    parser.add_argument('--output', type=Path, default=Path(
        r'C:\actions-runner-goemon\original-player-writer-provenance.json'))
    args = parser.parse_args(argv)
    try:
        # Private ROM import remains inside main, so source-free tests don't
        # require owner files, and no copyrighted payload is serialized.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from character_assets import read_file_table
        from character_id_binding import source_proven_character_graphics
        from probe_original_mips_execution import verified_decoded_original_rom
        from real_rom_check import locate_rom
        from scan_player_object_writers import (PLAYER_ORIGINAL_ROUTINE_ROM,
                                                PLAYER_ORIGINAL_ROUTINE_VRAM)
        rom = verified_decoded_original_rom((args.rom or locate_rom()).read_bytes())
        source_proven_character_graphics(rom)
        entries = [e for e in read_file_table(rom)
                   if e.start <= PLAYER_ORIGINAL_ROUTINE_ROM < e.end]
        if len(entries) != 1:
            raise ValueError('player handler does not belong to unique ROM file')
        overlay = entries[0]
        payload = rom[overlay.start:overlay.end]
        if len(payload) % 4:
            raise ValueError('unaligned player overlay')
        base_pc = (PLAYER_ORIGINAL_ROUTINE_VRAM -
                   (PLAYER_ORIGINAL_ROUTINE_ROM - overlay.start))
        words = struct.unpack('>' + 'I' * (len(payload) // 4), payload)
        result = analyze_words(words, base_pc)
        from trace_player_writer_cfg import analyze_cfg
        sites = [s for block in result['by_kind'].values() for s in block['sites']]
        result['assumed_entry_cfg'] = analyze_cfg(words, base_pc, sites)
        from trace_player_writer_cfg import (
            read_pinned_player_overlay_functions, analyze_cfg_from_pinned_functions)
        pinned, functions = read_pinned_player_overlay_functions()
        origin = pinned['provenance']
        if (overlay.file_id != 10 or
                overlay.start != int(origin['rom_start'], 16) or
                base_pc != int(origin['vram_start'], 16) or
                len(payload) != int(origin['size'], 16)):
            raise ValueError('owner ROM overlay and pinned player symbol mapping disagree')
        result['pinned_function_cfg'] = analyze_cfg_from_pinned_functions(
            words, base_pc, sites, functions)
        result['pinned_symbols_source_commit'] = origin['commit']
        from trace_player_writer_cfg import inspect_pinned_caller_a0
        result['pinned_direct_caller_a0'] = inspect_pinned_caller_a0(
            words, base_pc, pinned, functions)
        from trace_player_writer_cfg import follow_direct_call_a0_origin
        entry_a0_functions = sorted({
            v['pinned_function_pc'] for v in result['pinned_function_cfg'].values()
            if v['origin'] == 'entry_a0' and v.get('pinned_function_pc')
        })
        result['transitive_player_a0_provenance'] = follow_direct_call_a0_origin(
            words, base_pc, functions, entry_a0_functions)
        result['source_file_id'] = overlay.file_id
        checkout_root = Path(__file__).resolve().parents[3]
        out = args.output.resolve()
        if out == checkout_root or checkout_root in out.parents:
            raise ValueError('private source-derived report must stay outside Git checkout')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        for kind, block in result['by_kind'].items():
            print('GOEMON_WRITER_PROVENANCE', kind,
                  'sites=', block['non_stack_candidate_count'],
                  'local_known_global_loads=', block['known_global_pointer_load_count'])
            if kind == 'action_id_offset':
                for s in block['sites']:
                    print('GOEMON_ACTION_SITE', s['pc'], s['base_register'],
                          s['base_origin'], s['known_player_global'],
                          'direct_prologue_callers=', s['direct_jal_to_prologue_hint_count'],
                          'candidate_global_a0_callers=', s['caller_a0_known_player_global_hint_count'],
                          'direct_callsite_pcs=', s['first_direct_jal_to_prologue_hint_pcs'])
        for kind, block in result['by_kind'].items():
            from collections import Counter
            counts = Counter(result['assumed_entry_cfg'][s['pc']]['origin']
                             for s in block['sites'])
            print('GOEMON_CFG_ORIGIN_SUMMARY', kind,
                  json.dumps(dict(sorted(counts.items())), sort_keys=True))
            if kind == 'action_id_offset':
                for site in block['sites']:
                    finding = result['assumed_entry_cfg'][site['pc']]
                    print('GOEMON_ACTION_CFG', site['pc'],
                          finding['origin'], finding.get('symbol'),
                          'assumed_entry=', finding.get('assumed_entry_pc'),
                          'complete=', finding.get('complete'))
        for kind, block in result['by_kind'].items():
            from collections import Counter
            counts = Counter(result['pinned_function_cfg'][s['pc']]['origin']
                             for s in block['sites'])
            print('GOEMON_PINNED_CFG_SUMMARY', kind,
                  json.dumps(dict(sorted(counts.items())), sort_keys=True))
            if kind == 'action_id_offset':
                for site in block['sites']:
                    finding = result['pinned_function_cfg'][site['pc']]
                    print('GOEMON_PINNED_ACTION', site['pc'],
                          finding.get('pinned_function_pc'),
                          finding['origin'], finding.get('symbol'),
                          'complete=', finding['complete'],
                          'blockers=', json.dumps(finding.get('blocker_classes', {}), sort_keys=True),
                          'first_blocker_pcs=', json.dumps(finding.get('first_blocker_pc_by_class', {}), sort_keys=True))
        for caller in result['pinned_direct_caller_a0']:
            print('GOEMON_PINNED_CALLER_A0', caller['jal_pc'],
                  'target=', caller['verified_jal_target_function_pc'],
                  'source_function=', caller['source_caller_function_pc'],
                  'origin=', caller['call_argument_candidate_origin'],
                  'global=', caller['a0_pre_delay_slot_symbol'],
                  'cfg_complete=', caller['cfg_complete'],
                  'blockers=', json.dumps(caller['control_blocker_classes'], sort_keys=True))
        for function_pc, finding in result['transitive_player_a0_provenance'].items():
            print('GOEMON_TRANSITIVE_A0_ROOT', function_pc,
                  'direct_edges=', finding['verified_direct_call_edges_traversed'],
                  'global_roots=', finding['known_global_path_count'],
                  'endings=', json.dumps(finding['terminal_reasons'], sort_keys=True))
            for root in finding['static_global_entry_paths'][:8]:
                print('GOEMON_TRANSITIVE_A0_CANDIDATE', function_pc,
                      root['global'], 'jal_pcs=', root['direct_jal_chain_pcs'])
        print('GOEMON_WRITER_PROVENANCE COMPLETE: static evidence only; no live owner confirmed')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print('GOEMON_WRITER_PROVENANCE FAILED:', exc, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
