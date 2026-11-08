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
    return (op in (1, 2, 3, 4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17,
                   0x10, 0x11, 0x12, 0x13) or
            (op == 0 and (w & 63) in (8, 9)))


def plain(w, state):
    op, rs, rt, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xffff
    a, b = read(state, rs), read(state, rt)
    dest = written_register(w)
    value = UNKNOWN
    if op == 15 and rs == 0:
        dest, value = rt, ('constant', imm << 16)
    elif op in (9, 13):
        if a[0] == 'constant':
            n = (int(a[1]) + sign16(imm) if op == 9 else int(a[1]) | imm)
            dest, value = rt, ('constant', n & 0xffffffff)
        elif imm == 0:
            dest, value = rt, a
    elif op == 35 and a[0] == 'constant':
        address = (int(a[1]) + sign16(imm)) & 0xffffffff
        if address in PLAYER_GLOBALS:
            dest, value = rt, ('player_global_load', PLAYER_GLOBALS[address])
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


def successors(words, index, base_pc, state):
    w = words[index]
    op = w >> 26
    if not is_control(w):
        return [(index + 1, plain(w, state))], False
    if index + 1 >= len(words) or is_control(words[index + 1]):
        return [], True
    after = plain(words[index + 1], state)
    fallthrough = index + 2
    if op in (4, 5, 6, 7) or (op == 1 and ((w >> 16) & 31) in (0, 1)):
        rs, rt = (w >> 21) & 31, (w >> 16) & 31
        a, b = read(state, rs), read(state, rt)
        taken = None
        if op in (4, 5) and a[0] == b[0] == 'constant':
            taken = (a[1] == b[1]) if op == 4 else (a[1] != b[1])
        if op in (6, 7, 1) and a[0] == 'constant':
            v = int(a[1])
            signed = v - 0x100000000 if v & 0x80000000 else v
            if op == 6:
                taken = signed <= 0
            elif op == 7:
                taken = signed > 0
            else:
                taken = signed >= 0 if rt == 1 else signed < 0
        target = index + 1 + sign16(w)
        if taken is True:
            return [(target, after)], False
        if taken is False:
            return [(fallthrough, after)], False
        return [(target, after), (fallthrough, after)], False
    if op in (0x14, 0x15, 0x16, 0x17):
        return [], True  # branch-likely skips delay slot when not taken
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
        return [], ((w >> 21) & 31) != 31  # jr ra vs unknown indirect jump
    return [], True


def origin_at(words, base_pc, entry_index, site_index, register,
              *, max_window=2048, max_steps=80000):
    """Join all locally reachable paths from a *hypothetical* entry."""
    if not (0 <= entry_index <= site_index < len(words)):
        return {'origin': 'invalid_entry', 'complete': False}
    if site_index - entry_index > max_window:
        return {'origin': 'window_limit', 'complete': False}
    known = {entry_index: initial_state()}
    queue = deque([entry_index])
    incomplete, steps = False, 0
    while queue:
        index = queue.popleft()
        steps += 1
        if steps > max_steps:
            incomplete = True
            break
        if index == site_index:
            continue
        if index + 1 == site_index and is_control(words[index]):
            # The site is itself a branch/call delay-slot store.
            follow = [(site_index, known[index])]
            unsupported = False
        else:
            follow, unsupported = successors(words, index, base_pc, known[index])
        incomplete |= unsupported
        for dest, state in follow:
            if dest < entry_index:
                incomplete = True
                continue
            if dest > site_index:
                continue
            old = known.get(dest)
            merged = join(old, state) if old is not None else state
            if old is None or merged != old:
                known[dest] = merged
                queue.append(dest)
    if site_index not in known:
        return {'origin': 'unreachable', 'complete': not incomplete, 'steps': steps}
    origin, symbol = read(known[site_index], register)
    if incomplete:
        return {'origin': 'incomplete_cfg', 'complete': False, 'steps': steps,
                'bounded_origin': origin,
                'bounded_symbol': symbol if origin == 'player_global_load' else None}
    return {'origin': origin,
            'symbol': symbol if origin == 'player_global_load' else None,
            'complete': True, 'steps': steps}


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
