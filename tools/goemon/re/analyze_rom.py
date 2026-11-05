#!/usr/bin/env python3
"""Inspect original MIPS call sites and player-global references in a user-owned ROM.

Input must be a decompressed US Mystical Ninja Starring Goemon N64 .z64 ROM
and the matching Goemon64RecompSyms/mnsg.syms.toml symbol table.

No game assets or machine code are copied to the project. The output is a
structural index, NOT a reconstructed player physics implementation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys
import tomllib


PLAYER_GLOBALS = {
    0x801FC604: "player_1_task",
    0x801FC608: "player_2_task",
    0x801FC614: "player_1_root_object",
    0x801FC618: "player_2_root_object",
    0x8015C5DC: "current_player_character_id",
}
PLAYER_ENTRYPOINTS = {
    0x801CB800: "func_801CB800_587710",
    0x801DAF54: "func_801DAF54_596E64",
    0x801DC9C8: "func_801DC9C8_5988D8",
    0x801DCA64: "func_801DCA64_598974",
}
MEMORY_READ_OPS = {0x20, 0x21, 0x23, 0x24, 0x25, 0x30, 0x31, 0x37}
MEMORY_WRITE_OPS = {0x28, 0x29, 0x2B, 0x38, 0x39, 0x3F}
MEMORY_OPS = MEMORY_READ_OPS | MEMORY_WRITE_OPS


@dataclass(frozen=True)
class Function:
    name: str
    vram: int
    size: int
    rom: int
    section: str


def signed16(word: int) -> int:
    v = word & 0xffff
    return v - 0x10000 if v & 0x8000 else v


def functions_in_section(symbol_table: dict, section_name: str) -> list[Function]:
    result = []
    for section in symbol_table.get("section", []):
        if section.get("name") != section_name:
            continue
        rom, vram, size = (section[key] for key in ("rom", "vram", "size"))
        for item in section.get("functions", []):
            addr, length = item["vram"], item["size"]
            if addr < vram or addr + length > vram + size or length < 4 or length % 4:
                raise ValueError(f"invalid function bounds: {item['name']}")
            result.append(Function(item["name"], addr, length, rom + addr - vram, section_name))
    if not result:
        raise ValueError(f"no functions in symbol-table section {section_name}")
    return sorted(result, key=lambda function: function.vram)


def words_in_function(rom: bytes, function: Function):
    if function.rom < 0 or function.rom + function.size > len(rom):
        raise ValueError(f"function {function.name} exceeds ROM bounds")
    for offset in range(0, function.size, 4):
        yield function.vram + offset, struct.unpack_from(">I", rom, function.rom + offset)[0]


def jal_destination(pc: int, word: int) -> int | None:
    if word >> 26 != 0x03:
        return None
    return (((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)) & 0xFFFFFFFF


def writes_register(word: int, register: int) -> bool:
    op = word >> 26
    if op == 0:
        return ((word >> 11) & 0x1F) == register and register != 0
    if op in {
        0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
        0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
        0x30, 0x31, 0x32, 0x33, 0x37,
    }:
        return ((word >> 16) & 0x1F) == register
    return False


def global_references(instructions: list[tuple[int, int]], max_gap: int = 12):
    """Find LUI + memory-access candidate pairs, accounting for signed offsets.

    This heuristic can miss control-flow-dependent register values, and false
    positives remain possible. Always confirm candidates in disassembly.
    """
    for index, (pc, word) in enumerate(instructions):
        if word >> 26 != 0x0F:
            continue
        reg = (word >> 16) & 0x1F
        if reg == 0:
            continue
        high = (word & 0xFFFF) << 16
        for later_pc, later_word in instructions[index + 1:index + 1 + max_gap]:
            op = later_word >> 26
            base = (later_word >> 21) & 0x1F
            if op in MEMORY_OPS and base == reg:
                target = (high + signed16(later_word)) & 0xFFFFFFFF
                if target in PLAYER_GLOBALS:
                    yield {
                        "lui_pc": pc, "access_pc": later_pc, "target": target,
                        "global": PLAYER_GLOBALS[target],
                        "access": "read" if op in MEMORY_READ_OPS else "write",
                    }
            if writes_register(later_word, reg) or op in (0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
                break


def analyze(rom: bytes, table: dict, section: str = ".file_11") -> dict:
    if len(rom) < 4 or rom[:4] != bytes.fromhex("80371240"):
        raise ValueError("expected a big-endian .z64 ROM, not .n64/.v64")
    functions = functions_in_section(table, section)
    addresses = {f.vram: f for f in functions}
    callers: dict[int, list[dict[str, int | str]]] = {addr: [] for addr in PLAYER_ENTRYPOINTS}
    references = []
    for function in functions:
        instructions = list(words_in_function(rom, function))
        for pc, word in instructions:
            dest = jal_destination(pc, word)
            if dest in callers:
                callers[dest].append({"caller": function.name, "callsite": pc})
        for ref in global_references(instructions):
            references.append({"function": function.name, **ref})

    return {
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "section": section,
        "functions_scanned": len(functions),
        "known_entrypoints": [
            {"name": name, "vram": address,
             "rom": addresses[address].rom if address in addresses else None,
             "size": addresses[address].size if address in addresses else None,
             "callers": callers[address]}
            for address, name in PLAYER_ENTRYPOINTS.items()
        ],
        "player_global_references": references,
        "limitations": [
            "Global references are a LUI/address heuristic and require disassembly confirmation.",
            "Indirect JALR calls and computed accesses are not included.",
            "Overlay-relative relocations must be inspected separately.",
            "Calls and globals identify candidates, not the meanings of player physics fields.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decompressed_z64", type=Path)
    parser.add_argument("symbols_toml", type=Path)
    parser.add_argument("--section", default=".file_11")
    parser.add_argument("--output", type=Path, help="optional output JSON file")
    args = parser.parse_args(argv)
    try:
        rom = args.decompressed_z64.read_bytes()
        table = tomllib.loads(args.symbols_toml.read_text(encoding="utf-8"))
        report = analyze(rom, table, args.section)
        result = json.dumps(report, indent=2)
        if args.output:
            args.output.write_text(result + "\n", encoding="utf-8")
        else:
            print(result)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
