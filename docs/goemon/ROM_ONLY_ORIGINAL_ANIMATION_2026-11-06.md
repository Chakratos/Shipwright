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

## Further automatic ROM-only results (23:24 CET)

The corrected `export_original_models.py` now reads 0x09 vertex data
from **the source-mapped 0x09 bank itself**, NOT the unrelated root
bytes. Its new local directory is
`C:\\actions-runner-goemon\\original-rom-meshes-source-aligned`.

- Goemon 786 triangles in 24 F3DEX geometry runs
- Ebisumaru 647 triangles in 48 geometry runs
- Sasuke 941 triangles in 53 geometry runs
- Yae: unresolved source graphic segment mapping

The old `original-rom-meshes` directory is superseded and must not be
used as proof of correct original vertex geometry.

New `original_n64_display_list_graph.py` interprets actual F3DEX
`G_DL` call/branch instructions, following the exact original graphics
pointer stored in each source Skeleton limb rather than relying on
nearest-memory-address heuristics. Real ROM verification produced:

| Character | Distinct original skeleton Gfx pointers | Proper G_ENDDL | Gfx roots linked to decoded mesh parts |
| --- | ---: | ---: | ---: |
| Goemon | 18 | 18 | 11 |
| Ebisumaru | 35 | 35 | 31 |
| Sasuke | 28 | 28 | 21 |
| **Total** | **81** | **81** | **63** |

Source paths:
- `tools/goemon/re/original_n64_display_list_graph.py`
- `tools/goemon/re/trace_original_bone_display_lists.py`
- `tools/goemon/re/offline_animation_action_pointers.py`

The linked data are saved only on the Windows PC under
`C:\\actions-runner-goemon\\original-rom-poses\\original_recursive_gfx_links.json`.
The automated pointer-table search examined the source main-code/data
and character files for directly embedded animation header pointers
(`0x07...` and player type `0x67...`). No direct references
were found, so it **did not** establish animation action IDs or
frame-time progression. The action-selected animation pointer may
be calculated dynamically by the original MIPS code; that mechanism
needs explicit disassembly/reconstruction.

**Current verified result:** source-authored raw limb poses and
consistent source-geometry ownership are extracted. The character
animation interpolation/timeline remains unported. The current
Ship executable still renders static original-looking models.

**Do not request manual gameplay recording as a prerequisite:** the
ROM, the original MIPS code and the decomp/recomp source are already
available. Runtime capture is an optional validation fallback only.


## 2026-11-07: Critical encoded-channel correction

The 261 source-ROM records previously called poses are structurally
plausible AnimatedSkeleton descriptors, NOT decoded physical matrices
or verified chronological original game frames.

Original raw Skeleton fields contain repeated 0xB000 and 0xB100 words
inside scale, rotation and translation records, plus increasing values
such as 762, 785, 808. They cannot be passed to Ship's matrix rotation
or scale functions as literal angle/size values. The original MIPS
function func_800192D0_19ED0 evaluates these descriptors with the
AnimatedSkeleton.animation pointer and Object.animation_progress.

New code:
- decode_original_limb_meshes.py: recursively decodes genuine nested
  F3DEX source limb triangles; needs the owner ROM for final output.
- package_original_rig.py and OriginalSourceRig.hpp: preserve exact
  original encoded source Skeleton fields, not playable animations.
- analyze_original_animation_channels.py: counts tagged channel words
  and analyzes offsets into the original source animation stream.
- archive_original_animation_streams.py and OriginalAnimationStreams.hpp:
  lossless GOANIM01 byte-stream package plus strict native C++20 reader.
- disasm_original_animation_mips.py: inspect original 0x800192D0
  through 0x800196A4 MIPS evaluator offline (ROM 0x19ED0..0x1A2A4).
- .github/workflows/goemon-source-tests.yml: hosted synthetic unit tests
  which run independently of the private ROM and Windows runner.

Local original-ROM paths when the owner runner is online:
  C:\actions-runner-goemon\original-animation-streams
  C:\actions-runner-goemon\original-animation-mips

WARNING: do not claim the earlier 261 structures are decoded animation
frames, nor that true MNSG animations already play in Ship. The codec
and state-to-clip mapping must be established before enabling them.
