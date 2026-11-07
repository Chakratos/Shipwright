#!/usr/bin/env python3
"""Build a tiny SYNTHETIC source-rig + exact-frame pair for native E2E tests.

No original Goemon ROM data. This exercises two existing on-disk formats
at their byte boundaries: Python GOSKEL01/GO**A**0001 exporters and C++
SourceRigReader/OriginalAnimationArchiveReader/ArticulatedFrame assembly.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RE = HERE.parent
sys.path.insert(0,str(RE))
sys.path.insert(0,str(RE.parent/"reference_probe"))
from original_f3dex_geometry import N64Mesh,N64Vertex
from package_original_rig import create_original_rig_package
from original_pose_archive import encode_pose_archive


def mesh(offset:int) -> N64Mesh:
    vertices=(
        N64Vertex(1,0,0,0,0,0,255,0,0,255),
        N64Vertex(0,2,0,0,32,0,0,255,0,255),
        N64Vertex(0,0,3,0,0,32,0,0,255,255),
    )
    return N64Mesh(vertices,((0,1,2),),offset,3,{})


def make_synthetic_articulated_fixtures(out:Path)->tuple[Path,Path]:
    out.mkdir(parents=True,exist_ok=True)
    rig_data={
        "format":"ng5e-original-rom-skeletal-poses-v1",
        "original_source_poses":[{
            "source_header_segment":"0x07",
            "source_header_offset":0x100,
            "original_animated_skeleton_flags":"0x80000111",
            "limbs":[
                {"ptr":0x07000200,"parent":None,"gfx":0,
                 "scale":(0,0,0),"rotation":(-20480,-20480,-20480),
                 "translation":(0,0,0)},
                {"ptr":0x07000218,"parent":0x07000200,"gfx":0x09000100,
                 "scale":(-20224,-20224,-20224),
                 "rotation":(0,0,0),"translation":(0,0,0)},
                {"ptr":0x07000230,"parent":0x07000200,"gfx":0x09000200,
                 "scale":(-20224,-20224,-20224),
                 "rotation":(0,0,0),"translation":(0,0,0)},
            ]
        }]
    }
    mesh_entries={"0x09000100":mesh(0x09000100),
                  "0x09000200":mesh(0x09000200)}
    rigs=out/"synthetic.goskel"
    rigs.write_bytes(create_original_rig_package(0,rig_data,mesh_entries))

    def bone(ptr:int,gfx:int,translation_x:float):
        return {
            "pointer":f"0x{ptr:08X}",
            "gfx_pointer":f"0x{gfx:08X}",
            "child":0,"sibling":0,
            "scale_raw":[-20224,-20224,-20224],
            "rotation_raw":[0,0,0],
            "translation_raw":[0,0,0],
            "matrix_global_D_801684B0":[
                1.0,0.0,0.0,0.0,
                0.0,1.0,0.0,0.0,
                0.0,0.0,1.0,0.0,
                translation_x,20.0,30.0,1.0],
        }
    source={
        "format":"goemon-original-skeletal-poses-v1",
        "matrices_are_original_game_values":True,
        "frames":[{
            "original_game_frame":123,
            "character_id":0,
            "action_id":15,
            "limbs":[
                bone(0x07000218,0x09000100,10.0),
                bone(0x07000230,0x09000200,-10.0),
            ],
        }]
    }
    poses=out/"synthetic.gopa"
    poses.write_bytes(encode_pose_archive(source))
    return rigs,poses


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir",type=Path,required=True)
    args=p.parse_args(argv)
    rigs,poses=make_synthetic_articulated_fixtures(args.output_dir)
    print(f"SYNTHETIC_ANIM_PIPELINE: {rigs.name} + {poses.name}, no ROM assets")


if __name__=="__main__":
    main()
