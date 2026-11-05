#!/usr/bin/env python3
"""Decompress an OWNED NTSC-U Mystical Ninja Starring Goemon ROM in memory.

Source algorithm: Goemon64Recomp/src/game/rom_decompression.cpp.
The original data is never uploaded or committed by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct
import sys

FILE_TABLE = 0x57FD8
MAX_ROM_SIZE = 0x4000000
US_ROM_SIZE = 0x1000000
DECOMPRESSED_CRC = (0x9CC11F4B, 0xABAA8538)
MAGIC = bytes.fromhex("80371240")
US_GAME_CODE = b"NG5E"


def _u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def decode_lzkn64(block: bytes, *, max_size: int = MAX_ROM_SIZE) -> bytes:
    """Decode original LZKN64 sliding-window/RLE stream with bounds checks."""
    if len(block) < 4:
        raise ValueError("truncated compressed file header")
    compressed_size = _u32(block, 0)
    if not 4 <= compressed_size <= len(block):
        raise ValueError("invalid LZKN64 compressed file size")
    output = bytearray()
    index = 4
    while index < compressed_size:
        command = block[index]
        index += 1
        if command <= 0x7F:
            if index >= compressed_size:
                raise ValueError("truncated LZKN64 backreference")
            length = ((command & 0x7C) >> 2) + 2
            offset = (((command & 0x03) << 8) | block[index]) & 0x3FF
            index += 1
            if offset == 0 or offset > len(output):
                raise ValueError("invalid LZKN64 sliding-window offset")
            if len(output) + length > max_size:
                raise ValueError("LZKN64 output exceeds size limit")
            for _ in range(length):
                output.append(output[-offset])
        elif command <= 0x9F:
            length = command & 0x1F
            if index + length > compressed_size:
                raise ValueError("truncated LZKN64 raw copy")
            if len(output) + length > max_size:
                raise ValueError("LZKN64 output exceeds size limit")
            output.extend(block[index:index + length])
            index += length
        elif command <= 0xDF:
            length = (command & 0x1F) + 2
            if index >= compressed_size:
                raise ValueError("truncated LZKN64 repeated value")
            value = block[index]
            index += 1
            if len(output) + length > max_size:
                raise ValueError("LZKN64 output exceeds size limit")
            output.extend(bytes([value]) * length)
        elif command <= 0xFE:
            length = (command & 0x1F) + 2
            if len(output) + length > max_size:
                raise ValueError("LZKN64 output exceeds size limit")
            output.extend(bytes(length))
        else:
            if index >= compressed_size:
                raise ValueError("truncated LZKN64 long-zero run")
            length = block[index] + 2
            index += 1
            if len(output) + length > max_size:
                raise ValueError("LZKN64 output exceeds size limit")
            output.extend(bytes(length))
    return bytes(output)


def decompress_us_rom(data: bytes) -> bytes:
    """Return a byte-identical-formatted Goemon64Recomp decompressed ROM."""
    if len(data) != US_ROM_SIZE or data[:4] != MAGIC or data[0x3B:0x3F] != US_GAME_CODE:
        raise ValueError("expected original 16 MiB NTSC-U NG5E big-endian .z64 ROM")
    output = bytearray(data)
    address = _u32(data, FILE_TABLE) & 0x7FFFFFFF
    if address < FILE_TABLE + 8 or address >= MAX_ROM_SIZE:
        raise ValueError("invalid Goemon original file-table starting offset")
    count = 0
    for count in range(4096):
        index = FILE_TABLE + count * 4
        if index + 8 > len(data):
            raise ValueError("Goemon source ROM file table overrun")
        current = _u32(data, index)
        after = _u32(data, index + 4)
        if not current or not after:
            break
        start = current & 0x7FFFFFFF
        end = after & 0x7FFFFFFF
        if end < start or end > len(data):
            raise ValueError(f"Goemon compressed table range invalid at file {count}")
        if current & 0x80000000:
            decoded = decode_lzkn64(data[start:end], max_size=MAX_ROM_SIZE - address)
        else:
            decoded = data[start:end]
        aligned = (len(decoded) + 0xF) & ~0xF
        if address + aligned > MAX_ROM_SIZE:
            raise ValueError("decompressed Goemon image exceeds 64 MiB limit")
        if len(output) < address + aligned:
            output.extend(bytes(address + aligned - len(output)))
        output[address:address + len(decoded)] = decoded
        struct.pack_into(">I", output, index, address)
        struct.pack_into(">I", output, index + 4, address + aligned)
        address += aligned
    else:
        raise ValueError("Goemon file table exceeds 4096 entries")

    # The original decompressor rounds to a power of two, then updates CRC.
    final_size = 1 << (address - 1).bit_length()
    if final_size > MAX_ROM_SIZE:
        raise ValueError("invalid decompressed ROM size")
    if len(output) < final_size:
        output.extend(bytes(final_size - len(output)))
    output = output[:final_size]
    struct.pack_into(">II", output, 0x10, *DECOMPRESSED_CRC)
    return bytes(output)


def ensure_decompressed_rom(data: bytes) -> bytes:
    if len(data) >= US_ROM_SIZE and data[:4] == MAGIC and data[0x3B:0x3F] == US_GAME_CODE and (
        _u32(data, 0x10), _u32(data, 0x14)
    ) == DECOMPRESSED_CRC:
        return data
    return decompress_us_rom(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_rom", type=Path)
    parser.add_argument("output_rom", type=Path, help="local output (never commit or share)")
    args = parser.parse_args(argv)
    try:
        result = ensure_decompressed_rom(args.input_rom.read_bytes())
        args.output_rom.write_bytes(result)
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Decompressed locally: {len(result)} bytes, SHA-256 {hashlib.sha256(result).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
