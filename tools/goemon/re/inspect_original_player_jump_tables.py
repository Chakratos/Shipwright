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




def link_candidate_table_to_lui(payload: bytes, base_vram: int,
                                function_start: int, lw_pc: int,
                                candidate_table_vram: int) -> dict:
    """Match exact LUI high+LW signed offset; source register flow still a hint."""
    from trace_player_writer_provenance import sign16, written_register
    lw_offset = lw_pc - base_vram
    lw = struct.unpack_from('>I', payload, lw_offset)[0]
    if lw >> 26 != 0x23:
        raise ValueError('candidate jump source is not LW')
    load_rs = (lw >> 21) & 31
    desired_lui_base = (candidate_table_vram - sign16(lw)) & 0xFFFFFFFF
    result = {
        'candidate_table_vram': f'0x{candidate_table_vram:08X}',
        'last_lw_base_register': f'r{load_rs}',
        'exact_lui_plus_lw_offset_match_count': 0,
        'direct_or_indexed_base_register_chain_count': 0,
        'first_lui_match_pc': None,
        'actual_runtime_jump_table_verified': False,
    }
    if desired_lui_base & 0xFFFF:
        return result
    begin = max((function_start - base_vram) // 4, lw_offset // 4 - 48)
    end = lw_offset // 4
    words = struct.unpack_from('>' + 'I' * (end - begin),
                               payload, begin * 4)
    expected_high = desired_lui_base >> 16
    for pos, word in enumerate(words):
        if word >> 26 != 0x0F or (word & 0xFFFF) != expected_high:
            continue
        source_reg = (word >> 16) & 31
        result['exact_lui_plus_lw_offset_match_count'] += 1
        if result['first_lui_match_pc'] is None:
            result['first_lui_match_pc'] = f'0x{base_vram + (begin + pos) * 4:08X}'
        if source_reg != load_rs:
            continue
        writes = [(begin + k, w) for k, w in enumerate(words[pos + 1:], pos + 1)
                  if written_register(w) == source_reg]
        # Direct LUI->LW base or exactly one self-referential ADDU (indexed table).
        if not writes:
            result['direct_or_indexed_base_register_chain_count'] += 1
        elif len(writes) == 1:
            _, update = writes[0]
            if (update >> 26 == 0 and (update & 63) == 0x21 and
                    (update >> 11) & 31 == load_rs and
                    load_rs in (((update >> 21) & 31), ((update >> 16) & 31))):
                result['direct_or_indexed_base_register_chain_count'] += 1
    return result




def reconstruct_zero_register_selector_candidate(transforms, scale):
    """Evaluate a syntactic r0-anchored selector; never prove game execution.

    Transforms are private (operation, original decoded word) pairs, ordered
    from consumer to producer. Only reduced integer metadata leaves this scope.
    """
    from trace_player_writer_provenance import sign16
    value = 0
    for operation, word in reversed(transforms):
        imm = word & 0xFFFF
        if operation in ('addi', 'addiu'):
            value = (value + sign16(imm)) & 0xFFFFFFFF
        elif operation == 'andi':
            value &= imm
        elif operation == 'ori':
            value |= imm
        elif operation == 'xori':
            value ^= imm
        elif operation in ('slti', 'sltiu'):
            lhs = value if operation == 'sltiu' or value < 0x80000000 else value - 0x100000000
            rhs = imm if operation == 'sltiu' else sign16(imm)
            value = int(lhs < rhs)
        elif operation in ('sll', 'srl', 'sra'):
            shift = (word >> 6) & 31
            if operation == 'sll':
                value = (value << shift) & 0xFFFFFFFF
            elif operation == 'srl':
                value >>= shift
            else:
                signed = value - 0x100000000 if value & 0x80000000 else value
                value = (signed >> shift) & 0xFFFFFFFF
        elif operation == 'move_via_addu_or':
            continue
        else:
            return {'candidate_index': None, 'scaled_byte_offset': None,
                    'evaluation_complete': False}
    return {'candidate_index': value,
            'scaled_byte_offset': (value << scale) & 0xFFFFFFFF,
            'evaluation_complete': True}

def trace_index_register_load(payload: bytes, base_pc: int,
                              function_pc: int, lw_pc: int) -> dict:
    """Trace source metadata from JR-target LW base via ADDU, SLL, LBU.

    A backward instruction walk is *syntactic*, not a proof over all original
    branch paths. It reports source register, field offset, load width and
    static instruction PCs only, never original opcode/ROM bytes.
    """
    from trace_player_writer_provenance import sign16, written_register
    from trace_player_writer_cfg import is_control
    if ((len(payload) & 3) or function_pc < base_pc or
            lw_pc < function_pc or lw_pc + 4 > base_pc + len(payload)):
        raise ValueError('unbounded or unaligned selector trace')
    words = struct.unpack('>' + 'I' * (len(payload) // 4), payload)
    begin = (function_pc - base_pc) // 4
    lw_idx = (lw_pc - base_pc) // 4
    load_word = words[lw_idx]
    if load_word >> 26 != 0x23:
        raise ValueError('indirect target load is not LW')
    address_reg = (load_word >> 21) & 31

    def definition(reg, before):
        if reg == 0:
            # MIPS r0 is immutable: decoding NOP (sll r0,r0,0) as a
            # definition creates a wholly false selector ancestry.
            return None, None
        # Function-bound search; previously fixed 64 words hid earlier definitions.
        for idx in range(before - 1, begin - 1, -1):
            if written_register(words[idx]) == reg:
                return idx, words[idx]
        return None, None

    add_idx, add_word = definition(address_reg, lw_idx)
    report = {
        'jr_target_lw_pc': f'0x{lw_pc:08X}',
        'effective_address_reg': f'r{address_reg}',
        'indexed_addu_pc': None,
        'index_scale_shift_pc': None,
        'index_scale': None,
        'index_source_register': None,
        'selector_load_pc': None,
        'selector_load_width': None,
        'selector_field_offset': None,
        'selector_object_register': None,
        'selector_transform_chain': [],
        'selector_chain_stop_reason': None,
        'constant_selector_candidate_index': None,
        'constant_selector_candidate_scaled_byte_offset': None,
        'constant_selector_candidate_control_transfers': None,
        'constant_selector_candidate_ignores_alternative_paths': True,
        'selector_chain_stop_pc': None,
        'selector_chain_stop_instruction_category': None,
        'selector_offset_cc_syntactic_candidate': False,
        'index_ancestry_within_source_function': False,
        'effective_address_definition_kind': None,
        'indexed_operand_registers': [],
        'indexed_operand_definition_kinds': [],
        'selector_load_to_jr_control_transfer_count': None,
        'selector_source_straight_line_proven': False,
        'no_live_player_pointer_or_action_proven': True,
    }
    if add_idx is None:
        return report
    report['effective_address_definition_kind'] = (
        'addu' if add_word >> 26 == 0 and (add_word & 63) == 0x21
        else 'other_mips_definition')
    if add_word >> 26 != 0 or (add_word & 63) != 0x21:
        return report
    if ((add_word >> 11) & 31) != address_reg:
        return report
    operands = ((add_word >> 21) & 31, (add_word >> 16) & 31)
    report['indexed_addu_pc'] = f'0x{base_pc + add_idx * 4:08X}'
    report['indexed_operand_registers'] = [f'r{x}' for x in operands]
    for reg in operands:
        def_index, instruction = definition(reg, add_idx)
        if def_index is None:
            report['indexed_operand_definition_kinds'].append('inherited')
            continue
        op, fun = instruction >> 26, instruction & 63
        kind = ('sll' if op == 0 and fun == 0 else
                'addu' if op == 0 and fun == 0x21 else
                'lui' if op == 15 else
                'load' if op in (0x20, 0x21, 0x23, 0x24, 0x25) else
                'other')
        report['indexed_operand_definition_kinds'].append(kind)
    # Either operand can be the scaled index register.
    for reg in operands:
        shift_idx, shift = definition(reg, add_idx)
        if shift_idx is None:
            continue
        if (shift >> 26 != 0 or (shift & 63) != 0 or
                (shift >> 11) & 31 != reg or
                (shift >> 21) & 31 != 0):
            continue
        scale = (shift >> 6) & 31
        source_reg = (shift >> 16) & 31
        report['index_scale_shift_pc'] = f'0x{base_pc + shift_idx * 4:08X}'
        report['index_scale'] = scale
        report['index_source_register'] = f'r{source_reg}'
        cursor_reg, cursor = source_reg, shift_idx
        syntactic_transform_words = []  # decoded words never serialized
        for _ in range(8):
            if cursor_reg == 0:
                candidate = reconstruct_zero_register_selector_candidate(
                    [(name, word) for name, word, _ in syntactic_transform_words],
                    scale)
                if candidate['evaluation_complete']:
                    report['constant_selector_candidate_index'] = candidate['candidate_index']
                    report['constant_selector_candidate_scaled_byte_offset'] = candidate['scaled_byte_offset']
                    earliest = (min(i for _, _, i in syntactic_transform_words)
                                if syntactic_transform_words else shift_idx)
                    report['constant_selector_candidate_control_transfers'] = sum(
                        is_control(w) for w in words[earliest + 1:lw_idx])
                report['selector_chain_stop_reason'] = 'constant_zero_register'
                return report
            load_idx, load = definition(cursor_reg, cursor)
            if load_idx is None:
                report['selector_chain_stop_reason'] = 'inherited_or_no_local_definition'
                return report
            op, rs, rt = load >> 26, (load >> 21) & 31, (load >> 16) & 31
            widths = {0x20: 'lb', 0x24: 'lbu', 0x21: 'lh',
                      0x25: 'lhu', 0x23: 'lw'}
            if op in widths:
                offset = sign16(load)
                report['selector_load_pc'] = f'0x{base_pc + load_idx * 4:08X}'
                report['selector_load_width'] = widths[op]
                report['selector_field_offset'] = offset
                report['selector_object_register'] = f'r{rs}'
                report['selector_offset_cc_syntactic_candidate'] = (
                    offset == 0xCC and widths[op] in ('lbu', 'lb'))
                report['index_ancestry_within_source_function'] = True
                report['selector_load_to_jr_control_transfer_count'] = sum(
                    is_control(w) for w in words[load_idx + 1:lw_idx])
                report['selector_source_straight_line_proven'] = (
                    report['selector_load_to_jr_control_transfer_count'] == 0)
                report['selector_chain_stop_reason'] = 'memory_field_load'
                return report
            name = None
            next_reg = None
            if op in (8, 9, 10, 11, 12, 13, 14) and rt == cursor_reg:
                name = {8: 'addi', 9: 'addiu', 10: 'slti', 11: 'sltiu',
                        12: 'andi', 13: 'ori', 14: 'xori'}[op]
                next_reg = rs
            elif op == 0 and (load & 63) in (0, 2, 3, 4, 6, 7):
                fun = load & 63
                if ((load >> 11) & 31) == cursor_reg:
                    # Pure bit-shifts change selector value but preserve its
                    # data ancestry. Variable shift amount is not resolved.
                    name = {0: 'sll', 2: 'srl', 3: 'sra',
                            4: 'sllv', 6: 'srlv', 7: 'srav'}[fun]
                    next_reg = rt
            elif op == 0 and (load & 63) in (0x21, 0x25):
                a, b = rs, rt
                if a == 0 or b == 0:
                    name = 'move_via_addu_or'
                    next_reg = b if a == 0 else a
            if next_reg is None:
                fun = load & 63
                category = (
                    'comparison' if op == 0 and fun in (0x2A, 0x2B) else
                    'shift' if op == 0 and fun in (0, 2, 3, 4, 6, 7) else
                    'arithmetic' if op == 0 and fun in (0x20, 0x21, 0x22, 0x23) else
                    'bitwise' if op == 0 and fun in (0x24, 0x25, 0x26, 0x27) else
                    'special_unhandled' if op == 0 else
                    'immediate_unhandled' if op < 0x20 else
                    'memory_or_coprocessor')
                report['selector_chain_stop_reason'] = 'unmodeled_register_transform'
                report['selector_chain_stop_pc'] = f'0x{base_pc + load_idx * 4:08X}'
                report['selector_chain_stop_instruction_category'] = category
                return report
            report['selector_transform_chain'].append({
                'pc': f'0x{base_pc + load_idx * 4:08X}',
                'operation': name,
            })
            syntactic_transform_words.append((name, load, load_idx))
            cursor_reg, cursor = next_reg, load_idx
        report['selector_chain_stop_reason'] = 'bounded_hop_limit'
        return report
    return report



def inspect_selector_object_base(payload: bytes, base_vram: int,
                                 function_start: int, selector_load_pc: int) -> dict:
    """Nearest syntactic definition of the pointer used by source selector load.

    Not a dataflow proof across branches; records only PC, instruction class,
    offset and registers, and never exports original instruction words.
    """
    from trace_player_writer_provenance import sign16, written_register
    words = struct.unpack('>' + 'I' * (len(payload) // 4), payload)
    i = (selector_load_pc - base_vram) // 4
    first = (function_start - base_vram) // 4
    if not (0 <= first <= i < len(words)):
        raise ValueError('selector base load outside source function')
    source = words[i]
    if source >> 26 not in (0x20, 0x21, 0x23, 0x24, 0x25):
        raise ValueError('selector instruction is not source memory load')
    register = (source >> 21) & 31
    report = {
        'selector_source_object_register': f'r{register}',
        'selector_object_nearest_definition_pc': None,
        'selector_object_nearest_definition_kind': 'inherited_or_unknown',
        'selector_object_nearest_definition_base_register': None,
        'selector_object_nearest_definition_offset': None,
        'actual_player_object_owner_verified': False,
    }
    if register == 0:
        report['selector_object_nearest_definition_kind'] = 'zero_register'
        return report
    for idx in range(i - 1, first - 1, -1):
        word = words[idx]
        if written_register(word) != register:
            continue
        op = word >> 26
        report['selector_object_nearest_definition_pc'] = f'0x{base_vram + idx * 4:08X}'
        if op in (0x20, 0x21, 0x23, 0x24, 0x25):
            report['selector_object_nearest_definition_kind'] = {
                0x20:'lb',0x21:'lh',0x23:'lw',0x24:'lbu',0x25:'lhu'}[op]
            report['selector_object_nearest_definition_base_register'] = (
                f'r{(word >> 21) & 31}')
            report['selector_object_nearest_definition_offset'] = sign16(word)
        elif op in (8, 9, 12, 13, 14, 15):
            report['selector_object_nearest_definition_kind'] = {
                8:'addi',9:'addiu',12:'andi',13:'ori',14:'xori',15:'lui'}[op]
            report['selector_object_nearest_definition_base_register'] = (
                f'r{(word >> 21) & 31}')
        elif op == 0 and (word & 63) in (0x21, 0x25):
            report['selector_object_nearest_definition_kind'] = (
                'addu' if (word & 63) == 0x21 else 'or')
        else:
            report['selector_object_nearest_definition_kind'] = 'other'
        return report
    return report

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
    report = {
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
    report['syntactic_jump_index_ancestry'] = (
        trace_index_register_load(payload, base_vram, function_start, preceding_lw[-1])
        if preceding_lw else None)
    for run in report['possible_absolute_vram_target_pointer_runs']:
        table_address = base_vram + int(
            run['table_offset_within_original_overlay'], 16)
        run['table_address_provenance'] = (
            link_candidate_table_to_lui(
                payload, base_vram, function_start, preceding_lw[-1],
                table_address)
            if preceding_lw else None)
    return report


def analyze_original_overlay(payload: bytes, base_vram: int,
                             symbols: list[dict], dispatch_pcs=PLAYER_DISPATCH_PCS,
                             action_sites=None) -> dict:
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
    report = {
        'schema': 'ng5e-player-indirect-jr-address-metadata-v1',
        'source_only_no_original_rom_bytes_serialized': True,
        'confirmed_runtime_action_dispatch': False,
        'indirect_jump_functions': findings,
    }
    if action_sites is not None:
        from trace_player_writer_cfg import origin_at
        from trace_player_writer_provenance import sign16
        target_map = {}
        for item in findings:
            runs = item['possible_absolute_vram_target_pointer_runs']
            if len(runs) != 1:
                continue
            run = runs[0]
            evidence = run.get('table_address_provenance')
            if (evidence is None or
                    evidence['direct_or_indexed_base_register_chain_count'] != 1):
                continue
            off = int(run['table_offset_within_original_overlay'], 16)
            count = run['entry_count']
            # Original values stay in private memory, never logged or serialized.
            target_map[int(item['jr_pc'], 16)] = list(set(
                struct.unpack_from('>' + 'I' * count, payload, off)))
        from trace_player_writer_cfg import origin_at
        original_words = struct.unpack('>' + 'I' * (len(payload) // 4), payload)
        for finding in findings:
            ancestry = finding.get('syntactic_jump_index_ancestry')
            if not ancestry or not ancestry['selector_load_pc']:
                continue
            selector_pc = int(ancestry['selector_load_pc'], 16)
            owner_register = int(ancestry['selector_object_register'][1:])
            entry_pc = int(finding['original_function_start_pc'], 16)
            ptr = origin_at(original_words, base_vram,
                            (entry_pc - base_vram) // 4,
                            (selector_pc - base_vram) // 4, owner_register)
            ancestry['selector_object_base_cfg_origin'] = ptr['origin']
            ancestry['selector_object_base_cfg_symbol'] = ptr.get('symbol')
            ancestry['selector_object_base_cfg_complete'] = ptr['complete']
            source_def = inspect_selector_object_base(
                payload, base_vram, entry_pc, selector_pc)
            if (source_def['selector_object_nearest_definition_pc'] and
                    source_def['selector_object_nearest_definition_base_register'] and
                    source_def['selector_object_nearest_definition_kind'] == 'lw'):
                def_pc = int(source_def['selector_object_nearest_definition_pc'], 16)
                base_register = int(
                    source_def['selector_object_nearest_definition_base_register'][1:])
                base_origin = origin_at(
                    original_words, base_vram,
                    (entry_pc - base_vram) // 4,
                    (def_pc - base_vram) // 4,
                    base_register)
                source_def['nested_pointer_load_base_origin'] = base_origin['origin']
                source_def['nested_pointer_load_base_symbol'] = base_origin.get('symbol')
                source_def['nested_pointer_load_base_cfg_complete'] = base_origin['complete']
            ancestry['selector_object_nearest_source_definition'] = source_def
        cases = []
        for site in action_sites:
            pc = int(site['pc'], 16)
            idx = (pc - base_vram) // 4
            instr = struct.unpack_from('>I', payload, idx * 4)[0]
            if instr >> 26 != 0x28 or sign16(instr) != 0xCC:
                raise ValueError('original action writer differs from source site')
            owners = [f for f in symbols if f['start'] <= pc < f['start'] + f['size']]
            if len(owners) != 1:
                raise ValueError('action site missing unique pinned source function')
            finding = origin_at(
                struct.unpack('>' + 'I' * (len(payload) // 4), payload),
                base_vram, (owners[0]['start'] - base_vram) // 4,
                idx, (instr >> 21) & 31, indirect_jr_targets=target_map)
            cases.append({
                'action_store_pc': site['pc'],
                'pinned_function_pc': f"0x{owners[0]['start']:08X}",
                'possible_source_base_origin': finding['origin'],
                'bounded_symbolic_origin': finding.get('bounded_origin'),
                'table_hypothesis_blockers': finding.get('blocker_classes', {}),
                'real_original_player_writer_verified': False,
            })
        report['action_sites_with_indirect_table_hypotheses'] = cases
        report['structural_jr_table_target_map_count'] = len(target_map)
    return report


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
        report = analyze_original_overlay(
            payload, base, symbols, action_sites=pinned['action_sites'])
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
                  'index_source=', row['syntactic_jump_index_ancestry']['selector_load_pc']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'index_offset=', row['syntactic_jump_index_ancestry']['selector_field_offset']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'index_base_reg=', row['syntactic_jump_index_ancestry']['selector_object_register']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'index_width=', row['syntactic_jump_index_ancestry']['selector_load_width']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'selector_base_origin=', row['syntactic_jump_index_ancestry'].get('selector_object_base_cfg_origin')
                      if row['syntactic_jump_index_ancestry'] else None,
                  'index_addu=', row['syntactic_jump_index_ancestry']['indexed_addu_pc']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'index_operand_reg=', row['syntactic_jump_index_ancestry']['indexed_operand_registers']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'index_operand_def=', row['syntactic_jump_index_ancestry']['indexed_operand_definition_kinds']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'literal_index_candidate=', row['syntactic_jump_index_ancestry'].get('constant_selector_candidate_index')
                      if row['syntactic_jump_index_ancestry'] else None,
                  'literal_index_path_controls=', row['syntactic_jump_index_ancestry'].get('constant_selector_candidate_control_transfers')
                      if row['syntactic_jump_index_ancestry'] else None,
                  'literal_index_not_live_action=', True,
                  'selector_chain=', row['syntactic_jump_index_ancestry']['selector_transform_chain']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'selector_stop=', row['syntactic_jump_index_ancestry']['selector_chain_stop_reason']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'selector_stop_pc=', row['syntactic_jump_index_ancestry']['selector_chain_stop_pc']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'selector_stop_category=', row['syntactic_jump_index_ancestry']['selector_chain_stop_instruction_category']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'selector_object_nearest_def=', (
                      row['syntactic_jump_index_ancestry'].get('selector_object_nearest_source_definition')
                      if row['syntactic_jump_index_ancestry'] else None),
                  'source_path_controls=', row['syntactic_jump_index_ancestry']['selector_load_to_jr_control_transfer_count']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'straight_line=', row['syntactic_jump_index_ancestry']['selector_source_straight_line_proven']
                      if row['syntactic_jump_index_ancestry'] else None,
                  'absolute_vram_table_candidates=',
                  len(row['possible_absolute_vram_target_pointer_runs']))
            for run in row['possible_absolute_vram_target_pointer_runs'][:5]:
                print('GOEMON_INDIRECT_TABLE_CANDIDATE',
                      row['jr_pc'],
                      'local_offset=', run['table_offset_within_original_overlay'],
                      'count=', run['entry_count'],
                      'unique_target_pc_count=', run['unique_in_function_target_count'],
                      'lui_matches=', (
                          run['table_address_provenance']['exact_lui_plus_lw_offset_match_count']
                          if run['table_address_provenance'] else None),
                      'direct_or_indexed_chains=', (
                          run['table_address_provenance']['direct_or_indexed_base_register_chain_count']
                          if run['table_address_provenance'] else None))
        for entry in report.get('action_sites_with_indirect_table_hypotheses', []):
            print('GOEMON_JR_CASE_CFG', entry['action_store_pc'],
                  entry['possible_source_base_origin'],
                  'bounded_origin=', entry['bounded_symbolic_origin'],
                  'blockers=', json.dumps(entry['table_hypothesis_blockers'], sort_keys=True))
        print('GOEMON_INDIRECT_JR COMPLETE: static table hypotheses only')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print('GOEMON_INDIRECT_JR FAILED:', exc, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
