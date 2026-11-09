"""Bounded forward MIPS CFG provenance, with no original binary output.

The function entry is a heuristic until separately proven. CFG facts do not
establish active player ownership or an original animated action.
"""
from collections import deque
from trace_player_writer_provenance import PLAYER_GLOBALS, sign16, written_register

UNKNOWN = ('unknown', None)
ZERO = ('constant', 0)
PARAM_A0 = ('entry_a0', None)
CALLER_SAVED = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 24, 25, 31)


def initial_state():
    state = [UNKNOWN] * 32
    state[0], state[4] = ZERO, PARAM_A0
    return tuple(state)


def join(a, b):
    return tuple(x if x == y else UNKNOWN for x, y in zip(a, b))


def read(state, reg):
    return ZERO if reg == 0 else state[reg]


def is_control(w):
    op = w >> 26
    return (op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17) or
            (op in (0x10, 0x11, 0x12, 0x13) and ((w >> 21) & 31) == 8) or
            (op == 0 and (w & 63) in (8, 9)))


def plain(w, state):
    op, rs, rt, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xffff
    a, b = read(state, rs), read(state, rt)
    dest = written_register(w)
    value = UNKNOWN
    # COPn MFCx/CFCx read floating/control registers INTO the GPR rt.
    # Ordinary COP1 floating arithmetic does not modify GPRs or branch.
    if op in (0x10, 0x11, 0x12, 0x13) and rs in (0, 2):
        dest = rt
    if op == 15 and rs == 0:
        dest, value = rt, ('constant', imm << 16)
    elif op in (9, 13):
        if a[0] == 'constant':
            n = (int(a[1]) + sign16(imm) if op == 9 else int(a[1]) | imm)
            dest, value = rt, ('constant', n & 0xffffffff)
        elif imm == 0:
            dest, value = rt, a
    elif op == 35:
        if a[0] == 'constant':
            address = (int(a[1]) + sign16(imm)) & 0xffffffff
            if address in PLAYER_GLOBALS:
                dest, value = rt, ('player_global_load', PLAYER_GLOBALS[address])
        elif a == PARAM_A0:
            dest, value = rt, ('entry_a0_lw_field', sign16(imm))
    elif op == 0x25 and a[0] == 'entry_a0_lw_field':
        dest, value = rt, ('entry_a0_lw_lhu_fields', (a[1], sign16(imm)))
    elif op in (0x0C, 0x0E) and a[0] == 'constant':
        dest = rt
        value = ('constant', ((int(a[1]) & imm) if op == 0x0C
                              else (int(a[1]) ^ imm)) & 0xffffffff)
    elif op == 0 and (w & 63) in (0, 2, 3) and b[0] == 'constant':
        shift = (w >> 6) & 31
        n = int(b[1])
        if (w & 63) == 0:
            result = n << shift
        elif (w & 63) == 2:
            result = n >> shift
        else:
            signed = n - 0x100000000 if n & 0x80000000 else n
            result = signed >> shift
        dest, value = (w >> 11) & 31, ('constant', result & 0xffffffff)
    elif op == 0 and (w & 63) in (0x21, 0x25) and ((w >> 6) & 31) == 0:
        dest = (w >> 11) & 31
        if a == ZERO:
            value = b
        elif b == ZERO:
            value = a
        elif a[0] == b[0] == 'constant':
            n = int(a[1]) + int(b[1]) if (w & 63) == 0x21 else int(a[1]) | int(b[1])
            value = ('constant', n & 0xffffffff)
    if dest in (None, 0):
        return state
    out = list(state)
    out[dest] = value
    return tuple(out)


def successors(words, index, base_pc, state, indirect_jr_targets=None):
    w = words[index]
    op = w >> 26
    if not is_control(w):
        return [(index + 1, plain(w, state))], False
    if index + 1 >= len(words) or is_control(words[index + 1]):
        return [], True
    after = plain(words[index + 1], state)
    fallthrough = index + 2
    if op in (4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17) or (op == 1 and ((w >> 16) & 31) in (0, 1)):
        rs, rt = (w >> 21) & 31, (w >> 16) & 31
        a, b = read(state, rs), read(state, rt)
        taken = None
        if op in (4, 5, 0x14, 0x15) and a[0] == b[0] == 'constant':
            taken = (a[1] == b[1]) if op in (4, 0x14) else (a[1] != b[1])
        if op in (6, 7, 0x16, 0x17, 1) and a[0] == 'constant':
            v = int(a[1])
            signed = v - 0x100000000 if v & 0x80000000 else v
            if op in (6, 0x16):
                taken = signed <= 0
            elif op in (7, 0x17):
                taken = signed > 0
            else:
                taken = signed >= 0 if rt == 1 else signed < 0
        target = index + 1 + sign16(w)
        likely = op in (0x14, 0x15, 0x16, 0x17)
        skipped = state if likely else after
        if taken is True:
            return [(target, after)], False
        if taken is False:
            return [(fallthrough, skipped)], False
        return [(target, after), (fallthrough, skipped)], False
    if op in (2, 3):
        pc = base_pc + index * 4
        target_pc = ((pc + 4) & 0xf0000000) | ((w & 0x3ffffff) << 2)
        if op == 2:
            return [((target_pc - base_pc) // 4, after)], False
        out = list(after)
        for reg in CALLER_SAVED:
            out[reg] = UNKNOWN
        return [(fallthrough, tuple(out))], False
    if op == 0 and (w & 63) == 8:
        if ((w >> 21) & 31) == 31:
            return [], False  # jr ra: normal return
        target_pcs = (indirect_jr_targets or {}).get(base_pc + index * 4)
        if target_pcs:
            return [((pc - base_pc) // 4, after) for pc in sorted(set(target_pcs))], False
        return [], True  # unresolved indirect jr
    return [], True



def blocker_kind(w):
    """Only structural MIPS instruction category, never raw code payload."""
    op = w >> 26
    if op == 1:
        return 'unhandled_regimm_control'
    if op == 0 and (w & 63) == 9:
        return 'indirect_jalr'
    if op == 0 and (w & 63) == 8:
        return 'indirect_jr' if ((w >> 21) & 31) != 31 else 'return_jr_ra'
    if op in (0x10, 0x11, 0x12, 0x13) and ((w >> 21) & 31) == 8:
        return 'coprocessor_branch'
    return 'unsupported_control_or_delay'

def origin_at(words, base_pc, entry_index, site_index, register,
              *, max_window=2048, max_steps=80000, indirect_jr_targets=None):
    """Join all locally reachable paths from a *hypothetical* entry."""
    if not (0 <= entry_index <= site_index < len(words)):
        return {'origin': 'invalid_entry', 'complete': False}
    if site_index - entry_index > max_window:
        return {'origin': 'window_limit', 'complete': False}
    known = {entry_index: initial_state()}
    queue = deque([entry_index])
    incomplete, steps = False, 0
    blockers = {}
    first_blocker = {}

    def record(kind, index):
        blockers[kind] = blockers.get(kind, 0) + 1
        first_blocker.setdefault(kind, f'0x{base_pc + 4 * index:08X}')
    while queue:
        index = queue.popleft()
        steps += 1
        if steps > max_steps:
            incomplete = True
            record('analysis_step_limit', index)
            break
        if index == site_index:
            continue
        if index + 1 == site_index and is_control(words[index]):
            # Delay-slot store executes on ordinary branches, calls and jumps;
            # for branch-likely it executes ONLY if branch may be taken.
            word = words[index]
            op = word >> 26
            take_slot = True
            if op in (0x14, 0x15, 0x16, 0x17):
                rs, rt = (word >> 21) & 31, (word >> 16) & 31
                a, b = read(known[index], rs), read(known[index], rt)
                if op in (0x14, 0x15) and a[0] == b[0] == 'constant':
                    take_slot = (a[1] == b[1]) if op == 0x14 else (a[1] != b[1])
                if op in (0x16, 0x17) and a[0] == 'constant':
                    v = int(a[1])
                    v = v - 0x100000000 if v & 0x80000000 else v
                    take_slot = v <= 0 if op == 0x16 else v > 0
            follow = [(site_index, known[index])] if take_slot else []
            unsupported = False
        else:
            follow, unsupported = successors(
                words, index, base_pc, known[index], indirect_jr_targets)
            word = words[index]
            if (word >> 26 == 0 and (word & 63) == 8 and
                    ((word >> 21) & 31) != 31 and
                    indirect_jr_targets and base_pc + index * 4 in indirect_jr_targets):
                # Statically plausible ROM table targets, NOT a runtime-verified
                # live jump or proof of all future player states.
                record('static_table_target_hypothesis', index)
                incomplete = True
        incomplete |= unsupported
        if unsupported:
            record(blocker_kind(words[index]), index)
        elif not follow and is_control(words[index]):
            record(blocker_kind(words[index]), index)
        for dest, state in follow:
            if dest < entry_index:
                incomplete = True
                record('branch_before_assumed_entry', index)
                continue
            if dest > site_index:
                continue
            old = known.get(dest)
            merged = join(old, state) if old is not None else state
            if old is None or merged != old:
                known[dest] = merged
                queue.append(dest)
    diagnostics = {'blocker_classes': dict(sorted(blockers.items())),
                   'first_blocker_pc_by_class': dict(sorted(first_blocker.items()))}
    if site_index not in known:
        return {'origin': 'unreachable', 'complete': not incomplete, 'steps': steps,
                **diagnostics}
    origin, symbol = read(known[site_index], register)
    if incomplete:
        return {'origin': 'incomplete_cfg', 'complete': False, 'steps': steps,
                'bounded_origin': origin,
                'bounded_symbol': symbol if origin == 'player_global_load' else None,
                'bounded_constant_value': symbol if origin == 'constant' else None,
                **diagnostics}
    return {'origin': origin,
            'symbol': symbol if origin == 'player_global_load' else None,
            'constant_value': symbol if origin == 'constant' else None,
            'entry_a0_field_offsets': list(symbol) if origin == 'entry_a0_lw_lhu_fields' else None,
            'complete': True, 'steps': steps, **diagnostics}


def analyze_cfg(words, base_pc, sites):
    report = {}
    for site in sites:
        pc = site['pc']
        entry_pc = site.get('nearby_function_prologue_hint')
        if entry_pc is None:
            report[pc] = {'origin': 'no_entry_hint', 'complete': False}
            continue
        entry = (int(entry_pc, 16) - base_pc) // 4
        index = (int(pc, 16) - base_pc) // 4
        report[pc] = origin_at(words, base_pc, entry, index,
                               int(site['base_register'][1:]))
        report[pc]['assumed_entry_pc'] = entry_pc
        report[pc]['original_player_owner_verified'] = False
    return report


def read_pinned_player_overlay_functions(path=None):
    """Read source symbol metadata, rejecting overlapping or mismatched overlays."""
    import json
    from pathlib import Path
    location = Path(path) if path is not None else Path(__file__).with_name(
        'player_overlay_function_symbols.json')
    data = json.loads(location.read_text(encoding='utf-8'))
    origin = data['provenance']
    if (data['schema'] != 'ng5e-player-overlay-pinned-recompiler-functions-v1' or
            origin['commit'] != '49f4e3269f05c737cb4bf698b9ef7142c92f1ac7' or
            origin['section'] != '.file_11' or
            origin['runtime_file_table_id'] != 10 or
            int(origin['rom_start'], 16) != 0x587370 or
            int(origin['vram_start'], 16) != 0x801CB460 or
            int(origin['size'], 16) != 0x41400):
        raise ValueError('pinned original player source symbols mismatch')
    functions = []
    for row in data['functions']:
        start, size = int(row['start'], 16), int(row['size'], 16)
        if (start % 4 or size % 4 or size <= 0 or start < 0x801CB460 or
                start + size > 0x801CB460 + 0x41400):
            raise ValueError('invalid pinned source function span')
        functions.append({'start': start, 'size': size, 'name': row['name']})
    if len({f['start'] for f in functions}) != len(functions):
        raise ValueError('duplicate source function start')
    functions.sort(key=lambda function: function['start'])
    if len(functions) != 906 or origin.get('function_count') != 906:
        raise ValueError('pinned original player function inventory incomplete')
    for previous, current in zip(functions, functions[1:]):
        if current['start'] < previous['start'] + previous['size']:
            raise ValueError('overlapping functions in pinned player overlay')
    for section in ('action_sites', 'direct_caller_sites', 'graphics_example_site'):
        for site in data[section]:
            pc, expected = int(site['pc'], 16), int(site['start'], 16)
            match = [f for f in functions if f['start'] <= pc < f['start'] + f['size']]
            if len(match) != 1 or match[0]['start'] != expected:
                raise ValueError('site not uniquely covered by its source function')
    for caller in data['direct_caller_sites']:
        target = int(caller['target'], 16)
        if not any(f['start'] == target for f in functions):
            raise ValueError('direct caller target missing from public source symbols')
    if len(data['action_sites']) != 10 or len(data['direct_caller_sites']) != 7:
        raise ValueError('expected source site inventory incomplete')
    return data, functions


def analyze_cfg_from_pinned_functions(words, base_pc, sites, functions):
    """Use source-defined function boundaries; never label actual player ownership."""
    answer = {}
    for site in sites:
        pc = int(site['pc'], 16)
        matches = [f for f in functions
                   if f['start'] <= pc < f['start'] + f['size']]
        if len(matches) != 1:
            answer[site['pc']] = {'origin': 'no_unique_pinned_source_function',
                                  'complete': False, 'live_player_owner_verified': False}
            continue
        f = matches[0]
        result = origin_at(words, base_pc, (f['start'] - base_pc) // 4,
                           (pc - base_pc) // 4,
                           int(site['base_register'][1:]))
        result['pinned_function_pc'] = f"0x{f['start']:08X}"
        result['pinned_function_name'] = f['name']
        result['live_player_owner_verified'] = False
        answer[site['pc']] = result
    return answer


def inspect_pinned_caller_a0(words, base_pc, source, functions):
    """Correlate exact JAL source PCs with a0 from their source function spans.

    Delay-slot a0 writes remain unresolved, and no dynamic game ownership is
    inferred. The verified owner-ROM JAL target must match pinned metadata.
    """
    results = []
    from trace_player_writer_provenance import written_register
    for caller in source['direct_caller_sites']:
        pc = int(caller['pc'], 16)
        idx = (pc - base_pc) // 4
        expected = int(caller['target'], 16)
        w = words[idx]
        target = (((pc + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2))
        if w >> 26 != 3 or target != expected:
            raise ValueError('original owner ROM JAL does not target expected pinned function')
        entries = [f for f in functions
                   if f['start'] <= pc < f['start'] + f['size']]
        if len(entries) != 1:
            raise ValueError('direct JAL caller not in unique source function')
        pre = origin_at(words, base_pc,
                        (entries[0]['start'] - base_pc) // 4, idx, 4)
        slot = words[idx + 1]
        cop_writes_a0 = ((slot >> 26) in (0x10, 0x11, 0x12, 0x13)
                          and ((slot >> 21) & 31) in (0, 2)
                          and ((slot >> 16) & 31) == 4)
        slot_writes_a0 = written_register(slot) == 4 or cop_writes_a0
        results.append({
            'jal_pc': caller['pc'],
            'verified_jal_target_function_pc': caller['target'],
            'source_caller_function_pc': f"0x{entries[0]['start']:08X}",
            'a0_pre_delay_slot_origin': pre['origin'],
            'a0_pre_delay_slot_symbol': pre.get('symbol'),
            'a0_delay_slot_overwrites': slot_writes_a0,
            'call_argument_candidate_origin': (
                'delay_slot_overwrite_unknown' if slot_writes_a0 else pre['origin']),
            'function_extent_from_pinned_public_symbols': True,
            'live_player_action_owner_verified': False,
            'cfg_complete': pre['complete'],
            'control_blocker_classes': pre.get('blocker_classes', {}),
        })
    return results


def index_direct_jal_callers(words, base_pc, functions):
    """Exact original overlay JAL destinations, indexed by known source function."""
    from bisect import bisect_right
    starts = [f['start'] for f in functions]
    reverse = {}
    for idx, word in enumerate(words):
        if word >> 26 != 3:
            continue
        pc = base_pc + idx * 4
        target = ((pc + 4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
        if target not in starts:
            continue
        loc = bisect_right(starts, pc) - 1
        if loc < 0 or pc >= functions[loc]['start'] + functions[loc]['size']:
            continue
        reverse.setdefault(target, []).append({
            'jal_pc': f'0x{pc:08X}',
            'jal_index': idx,
            'source_function_pc': f"0x{functions[loc]['start']:08X}",
            'source_function_start_index': (functions[loc]['start'] - base_pc) // 4,
        })
    return reverse


def follow_direct_call_a0_origin(words, base_pc, functions, action_function_pcs,
                                 *, max_depth=5, max_explored=400):
    """Bounded inverse direct-JAL chain for inherited a0, never dynamic execution.

    A path qualifies only when each local entry-to-callsite analysis is
    complete and passes a0 unchanged through the call delay slot.
    """
    reverse = index_direct_jal_callers(words, base_pc, functions)
    result = {}
    for original_target in action_function_pcs:
        start = int(original_target, 16)
        visited = set()
        stack = [(start, tuple())]
        roots, endings = [], []
        traversed = 0
        while stack and traversed < max_explored:
            target, path = stack.pop(0)
            if (target, len(path)) in visited:
                continue
            visited.add((target, len(path)))
            edges = reverse.get(target, [])
            if not edges:
                endings.append('no_pinned_direct_callers')
            for edge in edges:
                traversed += 1
                caller_pc = int(edge['jal_pc'], 16)
                idx = edge['jal_index']
                local = origin_at(words, base_pc,
                                  edge['source_function_start_index'], idx, 4)
                delay_word = words[idx + 1] if idx + 1 < len(words) else 0
                cop_writes_a0 = (
                    (delay_word >> 26) in (0x10, 0x11, 0x12, 0x13)
                    and ((delay_word >> 21) & 31) in (0, 2)
                    and ((delay_word >> 16) & 31) == 4)
                clobber = written_register(delay_word) == 4 or cop_writes_a0
                route = (edge['jal_pc'],) + path
                if clobber:
                    endings.append('delay_slot_overwrites_a0')
                elif not local['complete']:
                    endings.append('incomplete_caller_cfg')
                elif local['origin'] == 'player_global_load':
                    roots.append({
                        'global': local.get('symbol'),
                        'caller_function_pc': edge['source_function_pc'],
                        'direct_jal_chain_pcs': list(route),
                        'depth': len(route),
                        'proven_live_player_owner': False,
                    })
                elif local['origin'] == 'entry_a0' and len(route) < max_depth:
                    stack.append((int(edge['source_function_pc'], 16), route))
                elif local['origin'] == 'entry_a0':
                    endings.append('depth_limit')
                else:
                    endings.append(local['origin'])
                if traversed >= max_explored:
                    break
        if stack:
            endings.append('exploration_limit')
        from collections import Counter
        result[original_target] = {
            'verified_direct_call_edges_traversed': traversed,
            'static_global_entry_paths': roots[:30],
            'known_global_path_count': len(roots),
            'terminal_reasons': dict(sorted(Counter(endings).items())),
            'all_function_boundaries_from_pinned_symbols': True,
            'only_direct_jal_in_same_overlay': True,
            'verified_live_player_action_owner': False,
        }
    return result
