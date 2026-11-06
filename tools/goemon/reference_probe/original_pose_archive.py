#!/usr/bin/env python3
"""Lossless original animation-pose archive for future native Ship playback.

GOPA0001: little-endian container of actual Goemon64Recomp game-tick matrices
and raw skeleton fields, linked by original N64 limb and display-list pointers.
NO generated/approximated frames or animation interpolation. The exact capture
must be provided locally; missing original poses are a hard error.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import struct
import sys

MAGIC = b"GOPA0001"
HEADER = struct.Struct("<8sII")
FRAME = struct.Struct("<IBBH")
BONE = struct.Struct("<IIbb9h16f")
MAX_FRAMES = 1800 * 4
MAX_TOTAL_BONES = 300000


def encode_pose_archive(source: dict) -> bytes:
    if source.get("format") != "goemon-original-skeletal-poses-v1" or not (
        source.get("matrices_are_original_game_values") is True
    ):
        raise ValueError("requires authentic original skeletal capture")
    records = source.get("frames")
    if not isinstance(records, list) or not 1 <= len(records) <= MAX_FRAMES:
        raise ValueError("invalid original animation frame count")
    out = bytearray(HEADER.pack(MAGIC, len(records), 0))
    last_tick = -1
    total_bones = 0
    for frame in records:
        tick = frame["original_game_frame"]
        character = frame["character_id"]
        action = frame["action_id"]
        bones = frame["limbs"]
        if not (isinstance(tick, int) and 0 <= tick < (1 << 32)
                and tick >= last_tick):
            raise ValueError("source animation frames out of tick order")
        last_tick = tick
        if not 0 <= character < 4 or not 0 <= action < 256:
            raise ValueError("source character/action outside original range")
        if not isinstance(bones, list) or not 1 <= len(bones) <= 96:
            raise ValueError("source limb count outside original source limit")
        out.extend(FRAME.pack(tick, character, action, len(bones)))
        pointers = set()
        for bone in bones:
            ptr = int(bone["pointer"], 16)
            gfx = int(bone["gfx_pointer"], 16)
            child = bone["child"]
            sibling = bone["sibling"]
            rotations = (bone["scale_raw"] + bone["rotation_raw"]
                         + bone["translation_raw"])
            mtx = bone["matrix_global_D_801684B0"]
            if (ptr == 0 or not 0 <= ptr <= 0xFFFFFFFF or
                    not 0 <= gfx <= 0xFFFFFFFF or
                    ptr in pointers):
                raise ValueError("invalid or duplicated source skeleton limb")
            pointers.add(ptr)
            if len(rotations) != 9 or len(mtx) != 16:
                raise ValueError("incomplete original skeleton/matrix fields")
            if any(not isinstance(n, int) or n < -32768 or n > 32767
                   for n in rotations):
                raise ValueError("invalid original signed 16-bit limb transform")
            if any(not math.isfinite(float(n)) or abs(float(n)) > 1e8
                   for n in mtx):
                raise ValueError("nonfinite or implausible original matrix")
            out.extend(BONE.pack(ptr, gfx, child, sibling, *rotations, *mtx))
            total_bones += 1
            if total_bones > MAX_TOTAL_BONES:
                raise ValueError("original animation archive bone budget exceeded")
    HEADER.pack_into(out, 0, MAGIC, len(records), total_bones)
    return bytes(out)


def inspect_pose_archive(blob: bytes) -> dict:
    if len(blob) < HEADER.size:
        raise ValueError("truncated original pose archive header")
    magic, frame_count, bone_count = HEADER.unpack_from(blob)
    if magic != MAGIC:
        raise ValueError("unknown source animation archive magic")
    if not 1 <= frame_count <= MAX_FRAMES or not 1 <= bone_count <= MAX_TOTAL_BONES:
        raise ValueError("original pose archive count outside limits")
    offset = HEADER.size
    frames = []
    seen_bones = 0
    last_tick = -1
    for _ in range(frame_count):
        if offset + FRAME.size > len(blob):
            raise ValueError("truncated original pose frame")
        tick, character, action, count = FRAME.unpack_from(blob, offset)
        offset += FRAME.size
        if tick < last_tick or character > 3 or not 1 <= count <= 96:
            raise ValueError("invalid original source game frame")
        last_tick = tick
        limbs = []
        seen = set()
        for _ in range(count):
            if offset + BONE.size > len(blob):
                raise ValueError("truncated original bone matrix")
            fields = BONE.unpack_from(blob, offset)
            offset += BONE.size
            ptr, gfx, child, sibling = fields[:4]
            transform = fields[4:13]
            matrix = fields[13:]
            if ptr == 0 or ptr in seen or len(matrix) != 16:
                raise ValueError("invalid original bone record")
            seen.add(ptr)
            if any(not math.isfinite(m) or abs(m) > 1e8 for m in matrix):
                raise ValueError("nonfinite original captured matrix")
            limbs.append({
                "ptr": ptr, "gfx": gfx, "child": child,
                "sibling": sibling, "raw_transform": transform,
                "matrix": matrix,
            })
            seen_bones += 1
        frames.append({
            "original_game_frame": tick, "character_id": character,
            "action_id": action, "limbs": limbs,
        })
    if offset != len(blob) or seen_bones != bone_count:
        raise ValueError("original animation archive has length/count mismatch")
    return {
        "format": MAGIC.decode("ascii"),
        "frame_count": frame_count,
        "original_bone_matrices": bone_count,
        "frames": frames,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("original_skeletal_poses_json", type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        doc = json.loads(args.original_skeletal_poses_json.read_text("utf-8"))
        encoded = encode_pose_archive(doc)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
        summary = inspect_pose_archive(encoded)
        print("ORIGINAL ANIMATION ARCHIVE:",
              summary["frame_count"], "game frames,",
              summary["original_bone_matrices"], "actual bone matrices,",
              len(encoded), "bytes (all local)")
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        print(f"ORIGINAL ANIMATION ARCHIVE FAILED: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
