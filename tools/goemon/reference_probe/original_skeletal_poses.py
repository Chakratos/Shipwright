#!/usr/bin/env python3
"""Parse ORIGINAL Goemon64Recomp per-limb animation matrices into pose clips.

Source of truth: in-game func_80018CA0_198A0 + func_800192D0_19ED0
capture emitted by diagnostic_mod/src/goemon_skeletal_capture.c.

No inferred, interpolated, retargeted, or synthetic animation is accepted.
Only matching authentic game frames and limb/matrix pairs enter the result.
No asset bytes are downloaded or shared. Local input logs stay local.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import Iterable

NAMES = ("Goemon", "Ebisumaru", "Sasuke", "Yae")
ROOT_TAG = "GOEMON_ANIM_ROOT,"
BONE_TAG = "GOEMON_ANIM_BONE,"
MATRIX_TAG = "GOEMON_ANIM_MATRIX,"
MAX_EVENTS = 500_000
MAX_LIMBS = 96
MAX_SOURCE_FRAMES = 1800
MAX_MATRIX_ABS = 1e8


@dataclass(frozen=True)
class PoseBone:
    frame: int
    character_id: int
    action_id: int
    bone_ptr: int
    display_list_ptr: int
    child_offset: int
    sibling_offset: int
    scale: tuple[int, int, int]
    rotation: tuple[int, int, int]
    translation: tuple[int, int, int]


@dataclass(frozen=True)
class PoseMatrix:
    frame: int
    character_id: int
    action_id: int
    bone_ptr: int
    progress: float
    values: tuple[float, ...]


def parse_bone(line: str) -> PoseBone:
    fields = line.split(",")
    if len(fields) != 16:
        raise ValueError(f"GOEMON_ANIM_BONE has {len(fields)}, expected 16 fields")
    frame, character, action = (int(x) for x in fields[:3])
    bone_ptr, dl_ptr = (int(x, 16) for x in fields[3:5])
    child, sibling = (int(x) for x in fields[5:7])
    transforms = tuple(int(x) for x in fields[7:])
    if not 0 <= character < 4 or frame < 0 or not 0 <= action < 256:
        raise ValueError("invalid original character/frame/action")
    if bone_ptr == 0 or not 0 <= dl_ptr <= 0xFFFFFFFF:
        raise ValueError("invalid original bone/graphics pointer")
    if not -128 <= child <= 127 or not -128 <= sibling <= 127:
        raise ValueError("original limb hierarchy offset outside signed byte")
    if any(not -32768 <= x <= 32767 for x in transforms):
        raise ValueError("invalid original 16-bit skeletal transforms")
    return PoseBone(
        frame, character, action, bone_ptr, dl_ptr, child, sibling,
        transforms[:3], transforms[3:6], transforms[6:9],
    )


def parse_matrix(line: str) -> PoseMatrix:
    fields = line.split(",")
    if len(fields) != 21:
        raise ValueError(f"GOEMON_ANIM_MATRIX has {len(fields)}, expected 21 fields")
    frame, character, action = (int(x) for x in fields[:3])
    bone_ptr = int(fields[3], 16)
    progress = float(fields[4])
    values = tuple(float(x) for x in fields[5:])
    if not 0 <= character < 4 or not 0 <= action < 256 or frame < 0:
        raise ValueError("invalid matrix source frame/character/action")
    if bone_ptr == 0:
        raise ValueError("null original matrix skeleton pointer")
    if not math.isfinite(progress):
        raise ValueError("non-finite original animation progress")
    if len(values) != 16 or any(
        not math.isfinite(x) or abs(x) > MAX_MATRIX_ABS for x in values
    ):
        raise ValueError("invalid original 4x4 animation matrix")
    return PoseMatrix(frame, character, action, bone_ptr, progress, values)


def read_original_animation_log(lines: Iterable[str]) -> dict:
    """Keep exact game engine matrices, with no made-up frames or limb motion."""
    source_events = 0
    seen_bones: dict[tuple[int, int, int, int],
                     deque[PoseBone]] = defaultdict(deque)
    samples: dict[tuple[int, int, int], list[dict]] = defaultdict(list)
    matrix_events = 0
    matched = 0
    unmatched_matrix = 0
    unmatched_bone = 0
    root_events: list[dict] = []
    stop_reached = False
    last_frame = -1
    began = False

    for source_line in lines:
        # Logs may contain timestamps before the payload, but the tag
        # and original CSV fields are always emitted verbatim.
        start = min((n for n in (
            source_line.find(ROOT_TAG),
            source_line.find(BONE_TAG),
            source_line.find(MATRIX_TAG),
            source_line.find("GOEMON_ANIM_BEGIN,"),
            source_line.find("GOEMON_ANIM_END,"),
        ) if n >= 0), default=-1)
        if start == -1:
            continue
        source_events += 1
        if source_events > MAX_EVENTS:
            raise ValueError("original pose capture exceeds bounded event budget")
        value = source_line[start:].strip()
        if value.startswith("GOEMON_ANIM_BEGIN,"):
            began = True
            continue
        if value.startswith("GOEMON_ANIM_END,"):
            stop_reached = True
            continue
        if value.startswith(ROOT_TAG):
            fields = value[len(ROOT_TAG):].split(",")
            if len(fields) != 18:
                raise ValueError("original root overlay capture must have 18 fields")
            frame, character, action = (int(x) for x in fields[:3])
            if not 0 <= character <= 3 or not 0 <= action <= 255:
                raise ValueError("invalid live original player identifier")
            overlay = []
            for i in range(6):
                base = 6 + 2 * i
                overlay.append({
                    "segment": f"0x{8+i:02X}",
                    "file_id": int(fields[base]),
                    "virtual_base": f"0x{int(fields[base+1],16):08X}",
                })
            root_events.append({
                "frame": frame, "character_id": character,
                "action_id": action,
                "root_pointer": f"0x{int(fields[3],16):08X}",
                "graphics_pointer": f"0x{int(fields[4],16):08X}",
                "animation_progress": float(fields[5]),
                "overlays": overlay,
            })
            continue
        if value.startswith(BONE_TAG):
            bone = parse_bone(value[len(BONE_TAG):])
            key = (bone.frame, bone.character_id, bone.action_id, bone.bone_ptr)
            seen_bones[key].append(bone)
            continue

        if value.startswith(MATRIX_TAG):
            pose = parse_matrix(value[len(MATRIX_TAG):])
            matrix_events += 1
            key = (pose.frame, pose.character_id, pose.action_id, pose.bone_ptr)
            waiting = seen_bones.get(key)
            if not waiting:
                unmatched_matrix += 1
                continue
            bone = waiting.popleft()
            matched += 1
            # Each captured limb matches the Gfx pointer in the original
            # object rather than a guessed sprite or the ripped OBJ model.
            gfx_segment = bone.display_list_ptr >> 24
            gfx_offset = bone.display_list_ptr & 0xFFFFFF
            entry = {
                "pointer": f"0x{bone.bone_ptr:08X}",
                "gfx_pointer": f"0x{bone.display_list_ptr:08X}",
                "gfx_segment": gfx_segment,
                "gfx_offset": gfx_offset,
                "child": bone.child_offset,
                "sibling": bone.sibling_offset,
                "scale_raw": list(bone.scale),
                "rotation_raw": list(bone.rotation),
                "translation_raw": list(bone.translation),
                "matrix_global_D_801684B0": list(pose.values),
                "animation_progress": pose.progress,
                "matrix_origin": "original func_800192D0_19ED0 return",
            }
            samples[(pose.character_id, pose.action_id, pose.frame)].append(entry)
            if pose.frame < last_frame:
                # Captures from the original render pipeline can include
                # repeated frames; never silently reorder frame effects.
                raise ValueError("out-of-order original animation frame")
            last_frame = pose.frame

    unmatched_bone = sum(len(p) for p in seen_bones.values())
    if not samples:
        raise ValueError("no paired original skeletal matrices found in runtime capture")

    # Each unique original game update is a frame, NOT an interpolated
    # 60/120/240Hz Ship render frame.
    frames: list[dict] = []
    for (character, action, tick), limbs in sorted(
        samples.items(), key=lambda entry: (entry[0][2], entry[0][0], entry[0][1])
    ):
        if len(limbs) > MAX_LIMBS:
            raise ValueError("too many original limbs in a game frame")
        unique = set()
        for limb in limbs:
            bone = limb["pointer"]
            if bone in unique:
                # Original rendering can be repeated at a higher host FPS,
                # but it must not fabricate additional keyframes.
                raise ValueError("same original limb rendered more than once per game tick")
            unique.add(bone)
        frames.append({
            "original_game_frame": tick,
            "character_id": character,
            "character_name": NAMES[character],
            "action_id": action,
            "limbs": limbs,
        })
    ticks = {f["original_game_frame"] for f in frames}
    if len(ticks) > MAX_SOURCE_FRAMES:
        raise ValueError("original animation exceeds bounded frame budget")
    return {
        "format": "goemon-original-skeletal-poses-v1",
        "source": "MNSG original runtime func_80018CA0/func_800192D0",
        "capture_began": began,
        "capture_ended": stop_reached,
        "original_game_frames": len(ticks),
        "total_matched_original_matrices": matched,
        "unmatched_original_bones": unmatched_bone,
        "unmatched_original_matrices": unmatched_matrix,
        "render_root_mappings": root_events,
        "frames": frames,
        "matrices_are_original_game_values": True,
        "matrix_coordinate_space_verified_for_Ship": False,
        "animation_clips_retargeted_to_Ship": False,
        "note": (
            "Captured unmodified source MtxF after original matrix routine; "
            "matrix coordinate space and Gfx limb binding require verification "
            "before animated playback in Ship."
        ),
    }


def bind_original_mesh_runs(pose_document: dict,
                            source_manifests: dict[int, dict]) -> dict:
    """Associate source 0x07 display-list pointers with extracted ROM Gfx runs.

    A Gfx pointer might start before the first gSPVertex command, so
    ONLY exact matches to the vertex command are confirmed. A narrow
    candidate range can be reported but is never silently treated as proof.
    """
    manifest_index = {}
    for slot, manifest in source_manifests.items():
        spans = manifest.get("per_display_list_objects", [])
        by_start = {}
        for part in spans:
            at = int(part["display_list_offset"])
            if at in by_start:
                raise ValueError("duplicate ROM source display-list start")
            by_start[at] = part
        manifest_index[slot] = by_start
    stats = {"exact_gfx_matches": 0, "unresolved_gfx": 0,
             "non_source_segment07": 0, "nearby_unverified": 0}
    for frame in pose_document["frames"]:
        char = frame["character_id"]
        index = manifest_index.get(char, {})
        for limb in frame["limbs"]:
            pointer = int(limb["gfx_pointer"], 16)
            if pointer >> 24 != 7:
                stats["non_source_segment07"] += 1
                limb["source_mesh_status"] = "non_source_segment07"
                continue
            at = pointer & 0xFFFFFF
            part = index.get(at)
            if part:
                limb["source_mesh_status"] = "exact_source_rom_gfx_match"
                limb["source_obj"] = part["local_obj_file"]
                stats["exact_gfx_matches"] += 1
                continue
            nearby = [
                part["local_obj_file"]
                for start, part in index.items()
                if 0 < start-at <= 128 and
                   int(part["display_list_end"]) > start
            ]
            if nearby:
                limb["source_mesh_status"] = "nearby_header_not_verified"
                limb["possible_source_obj"] = nearby
                stats["nearby_unverified"] += 1
            else:
                limb["source_mesh_status"] = "unresolved_gfx_pointer"
                stats["unresolved_gfx"] += 1
    pose_document["source_rom_graphics_binding"] = stats
    return pose_document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime_log", type=Path)
    parser.add_argument("--meshes-dir", type=Path,
                        help="local original-rom-meshes manifest folder")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.runtime_log.open(encoding="utf-8", errors="replace") as inp:
            poses = read_original_animation_log(inp)
        if args.meshes_dir:
            sources = {}
            for char, name in enumerate(NAMES):
                path = args.meshes_dir / name / "manifest.json"
                if path.is_file():
                    sources[char] = json.loads(path.read_text(encoding="utf-8"))
            bind_original_mesh_runs(poses, sources)
        payload = json.dumps(poses, ensure_ascii=False,
                             separators=(",", ":")) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
            print(f"ORIGINAL GOEMON ANIMATION: {poses['original_game_frames']} source frames, "
                  f"{poses['total_matched_original_matrices']} limb matrices")
        else:
            print(payload, end="")
    except (ValueError, OSError, KeyError) as exc:
        print(f"ORIGINAL GOEMON ANIMATION FAILED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
