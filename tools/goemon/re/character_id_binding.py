#!/usr/bin/env python3
"""Verify original NG5E MIPS character-ID -> graphics-file-ID lookup.

Original function at RAM 0x801DC9C8 / decompressed-ROM offset 0x5988D8:
it indexes the four 16-bit IDs at RAM 0x80204020 (ROM 0x5BFF30)
with the low byte of argument a1. This establishes original numeric
character ID -> original graphics root ID, NOT the four character names.
No original asset data is embedded or exported.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys

FUNCTION_ROM_OFFSET = 0x5988D8
CHARACTER_ROOTS_ROM_OFFSET = 0x5BFF30
EXPECTED_ORIGINAL_INSTRUCTIONS = {
    0x04: 0xAFA50034,  # sw a1, 0x34(sp)
    0x08: 0x93AE0037,  # lbu t6, 0x37(sp) = low byte of a1
    0x0C: 0x3C188020,  # lui t8, 0x8020
    0x14: 0x27184020,  # addiu t8, t8, 0x4020
    0x18: 0x000E7840,  # sll t7, t6, 1 (u16 array index)
    0x1C: 0x01F81021,  # addu v0, t7, t8
    0x28: 0x94590000,  # lhu t9, 0(v0)
    0x38: 0xA4D9003C,  # sh t9, 0x3c(a2)
}


def source_proven_character_graphics(
    decoded_rom: bytes,
    *,
    function_offset: int = FUNCTION_ROM_OFFSET,
    table_offset: int = CHARACTER_ROOTS_ROM_OFFSET,
) -> tuple[int, int, int, int]:
    if len(decoded_rom) < max(function_offset + 0x3C, table_offset + 8):
        raise ValueError("Goemon ROM missing original character graphics code/table")
    for displacement, instruction in EXPECTED_ORIGINAL_INSTRUCTIONS.items():
        observed = struct.unpack_from(">I", decoded_rom,
                                      function_offset + displacement)[0]
        if observed != instruction:
            raise ValueError(
                f"original character-ID lookup opcode differs at "
                f"function+0x{displacement:X}; source mapping is unverified"
            )
    roots = struct.unpack_from(">4H", decoded_rom, table_offset)
    if len(set(roots)) != 4:
        raise ValueError("original character graphics root IDs are not unique")
    return roots


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("original_us_rom", type=Path)
    args = p.parse_args(argv)
    try:
        from decompress_rom import ensure_decompressed_rom
        image = ensure_decompressed_rom(args.original_us_rom.read_bytes())
        roots = source_proven_character_graphics(image)
        print(json.dumps({
            "source": "original NG5E MIPS func_801DC9C8",
            "proof": "a1 low byte indexes 16-bit table at 0x80204020",
            "numeric_character_id_to_graphics_file_id": {
                str(index): root for index, root in enumerate(roots)
            },
            "name_mapping": None,
        }, indent=2))
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
