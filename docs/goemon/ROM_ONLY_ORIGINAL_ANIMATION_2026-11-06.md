# Correction: source-aligned original Goemon animation reconstruction (ROM only)

2026-11-06, branch `feature/goemon-original-controller`.

## Important correction to earlier research

Source `klorfmorf/mnsg/config/usa/splat.yaml` uses **file labels
one higher** than the original decompressed ROM's 0-based file table IDs.
This was verified by exact absolute uncompressed start/end offsets for
all 16 character resources, NOT by scanning for similar content.

| Character | ROM root | PIC0000 | Splat 0x07 source ID | Splat second gfx segment |
| --- | ---: | ---: | ---: | --- |
| Goemon | 288 | 289 | 290 (190944 bytes) | 0x09: 291 (31984 bytes) |
| Ebisumaru | 292 | 293 | 294 (195568 bytes) | 0x09: 295 (34176 bytes) |
| Sasuke | 296 | 297 | 298 (225040 bytes) | 0x09: 299 (42192 bytes) |
| Yae | 300 | 301 | 302 (264336 bytes) | 0x08: 303 (464 bytes) |

Previous scripts misrepresented the source segmentation, particularly
Yae's data: file 303 is not the 0x07 graphics bank. The formerly
exported `original-rom-meshes` objects may contain incorrect vertex
coordinates because the decoder used a wrong 0x09 vertex bank. **Do not
promote those objects to final character meshes without regenerating
them from the source-aligned banks.** The earlier 108 count describes
F3DEX command runs, not independently verified final meshes.

## Major ROM-only animation finding

Using exact source segment mappings and 24-byte `Skeleton` records
from `Goemon64Recomp/patches/types.h`, plus original traversal order
from `patches/anime.c`, the new `tools/goemon/re/offline_original_rigs.py`
reconstructs valid, linked original skeleton hierarchies **without
running or recording the game**:

- Goemon: 89 structural AnimatedSkeleton candidates, first 14/17 limbs
- Ebisumaru: 88 structural candidates, first 15/18 limbs
- Sasuke: 84 structural candidates, first 18/19 limbs
- Yae: requires additional 0x09 source overlay mapping; testing
  source-listed shared-bank possibilities separately

Actual source pointer examples from the user's hash-verified ROM:

Goemon `0x070005C4`, 14 limbs, 13 graphics limbs pointing to 0x09;
root header in source 0x07 at offset `0x63C`;
flags `0x80000111`.

Ebisumaru `0x07000394`, 15 limbs, 14 graphics limbs pointing to 0x09;
root header offset `0x4B4`, flags `0x8000010C`.

Sasuke `0x07000650`, 18 limbs, 17 graphics limbs pointing to 0x09;
root header offset `0x758`, flags `0x80000114`.

These flags, original animation pointers and every per-limb scale,
rotation, translation and source graphics pointer are in the ROM.

These are **valid structural candidates** and are NOT yet proven
character/action-specific frame sequences. The exact animation
interpolation, state-to-clip association and N64 matrix order must
still be recovered from the original MIPS functions.

## Implemented automation

- `source_aligned_character_assets.py`: verifies file indexing
  against original absolute ROM source boundaries.
- `offline_original_rigs.py`: recovers linked Skeleton trees and
  checks source Gfx references. Also tests Yae's hypothesized shared
  source segment 0x09.
- `export_offline_original_poses.py`: exports full source-authored raw
  skeletal poses to `C:\actions-runner-goemon\original-rom-poses`
  as local JSON, including original raw angles/translation/scale,
  parent-child graph and original animation pointers.
- `[goemon-offline-poses]` commit marker triggers the offline
  export on the Windows runner. No original game launcher, no manual
  capture, no GitHub assets.

The MIPS runtime capture mod is retained only as an optional debugging
fallback. It is NOT a prerequisite for continuing this project.

## Next engineering steps

1. Determine the exact skeleton animation time evolution from the
   original MIPS routine and map each ROM-authored pose to original
   action IDs. The decomp's MIPS original code is available in the ROM.
2. Rebuild authentic per-limb graphics using the corrected segment
   banks and extract the actual original textures/materials.
3. Add genuine articulated per-frame original animation in Ship,
   rather than animating one whole character OBJ or using Link bones.
4. Extend to Yae and all four characters' actual skills/weapons,
   while preserving Zelda world/scene/Randomizer integration.

No user interaction is necessary for the offline reverse-engineering
and extraction work.
