# Original Goemon — ROM geometry and first controllable N64-model player
Date: 2026-11-06. Branch: feature/goemon-original-controller.

## Verified on the owner's original NTSC-U NG5E ROM

Original-ROM SHA-256 and the decompressed ROM hash are checked locally by
`tools/goemon/real_rom_check.py`. The ROM itself stays on the Windows PC,
never on GitHub. The Goemon64Recomp original-game file table is at 0x57FD8.

The MNSG decompilation's `config/usa/splat.yaml` proves that source character
graphics roots 288/292/296/300 map into segment **0x09**, while resource
files 291/295/299/303 map into segment **0x07**. Our old segment-8-only
scanner incorrectly reported no usable display lists.

`tools/goemon/re/original_segmented_scan.py` verifies real F3DEX gSPVertex
DMA commands in segment 7 and resolves their source vertex records from
segment 9. `tools/goemon/re/original_segmented_geometry.py` reconstructs
triangles with source Nintendo 64 F3DEX command packing. Actual measured
results on the owner's original ROM:

| Character | ROM file (Gfx at 0x07) | Raw reconstructed triangles | Complete F3DEX display-list runs |
|---|---:|---:|---:|
| Goemon | 291 | 786 | 24 |
| Ebisumaru | 295 | 554 | 31 |
| Sasuke | 299 | 941 | 53 |
| Yae | 303 | Not recovered | 0 |

All 108 decoded runs terminate with genuine G_ENDDL and have valid vertex
references. A run is a group of F3DEX commands, **not** an established
skeleton limb or guaranteed single visible character pose. The combined
geometry may contain additional parts and poses. Yae's +3 file 303 has
only 464 bytes and no validated gSPVertex; its original geometry source
must be found by further tracing.

### Local original-geometry export — already completed

A GitHub Actions one-shot `[goemon-rom-export]` ran successfully on the
self-hosted Windows runner. It saved **only to this computer**:

```text
C:\actions-runner-goemon\original-rom-meshes\
    original_asset_manifest.json
    Goemon\all_original_parts.obj
    Goemon\manifest.json
    Goemon\gfx_000_at_0x0024a8.obj ... (24 files)
    Ebisumaru\all_original_parts.obj
    Ebisumaru\manifest.json
    Ebisumaru\gfx_...obj ... (31 files)
    Sasuke\all_original_parts.obj
    Sasuke\manifest.json
    Sasuke\gfx_...obj ... (53 files)
```

No ROM, binary meshes, original textures, OBJ files, or artwork are
uploaded to GitHub. These local objects are *untextured limb-local
source-ROM geometry*, not yet a renderable animated skeleton.

### What the existing decomp/recomp DOES and DOES NOT contain

- `Goemon64Recomp/src/game/rom_decompression.cpp`: exact LZKN64 format.
- `klorfmorf/mnsg/config/usa/splat.yaml`: source file IDs, segment maps.
- `Goemon64Recomp/patches/types.h`: C structures for `Skeleton`
  (24 bytes, child/sibling offsets, raw S/R/T) and `AnimatedSkeleton`.
- `Goemon64Recomp/patches/anime.c`: genuine renderer paths
  `func_80016C44_17844` (root), `func_80018CA0_198A0` (player limbs),
  `func_800196F0_1A2F0` (display-list submission).
- `Goemon64Recomp/src/main/rt64_render_context.cpp`: game RDRAM
  display-list handling by RT64.
- The decomp is INCOMPLETE: most character asset files are still treated
  as data, and no ready-to-use source animation/glTF/FBX asset exporter
  is provided.

The next extraction milestone is identifying the exact root
`AnimatedSkeleton`/limb ownership and runtime overlay segment 0x08
assignment through the original engine's active player object, and then
recovering per-action keyframes. Structural pointer guesses from arbitrary
ROM offsets MUST NOT be silently promoted to source-proven rigs.

## First independent character controller in Ship

The complete original-looking static characters from the four locally
placed OBJ+PNG references are already renderable as N64 actors. The new
`OriginalReferenceCharacterActor.cpp` now also contains an explicit
source-motion pilot, separate from the discarded gold-ball feasibility Actor:

- **Render Model ON, Control OFF:** static showroom figure ahead of Link.
- **Render Model ON, Control ON:** selected 3D character moves at the
  player's position with verified original full-stick acceleration,
  original measured braking and jump arc.
- The Zelda world collision is sampled with the existing conservative
  terrain envelope. It is not the original Goemon collision capsule.
- The new actor synchronizes its location to Zelda's underlying Link
  actor, so scene logic and the native Zelda camera stay anchored to
  the moving character. Link's original visual model is hidden during
  valid pilot frames.
- Runtime control is gated by the presence of a successfully loaded
  character mesh, an active matching actor/scene, a controllable Link,
  no legacy debug Actor, and no fatal error.
- On cutscenes/loading/model failures the vanilla player returns rather
  than leaving the gamepad permanently filtered.
- Lateral-stick mapping uses the corrected direction observed in the
  previous in-game prototype. This integration mapping is not claimed
  to be an original Goemon camera/filter implementation.

The character moves with real ROM-derived motion, but this is still
**not the completed original game character**: original rigid limb poses,
animation sequences, weapon hitboxes, wall/fall/ledge handling,
game-specific interactivity and character abilities remain outstanding.

### First playable model test

1. Exit the currently open Goemon Test game before the local Windows
   build completes, allowing the runner to replace the EXE.
2. Start `C:\Users\Chakratos\Desktop\SoH Goemon Test\soh.exe`.
3. In Dev Tools → Goemon, disable the old
   `Spawn Independent Goemon Actor (Prototype)` (and its pilot).
4. Enable `Show Original N64 Character Model`.
5. Enable `Control Original Character (ROM Motion)`.
6. Choose `Original N64 Character`: Goemon, Ebisumaru, Sasuke or Yae.
7. Move, turn and jump. Record problems with model alignment, terrain,
   controls, and scene camera, not cosmetic issues with the old debug ball.

The selected 3D character should now occupy the actual player position
instead of floating ahead of Link. Weapon and item controls are not yet
retargeted. The pilot CVar is OFF by default; the normal test game and
the separate Archipelago installation are unchanged when it is disabled.

## Immediate next work

1. Recover original skeleton ownership from `AnimatedSkeleton` at runtime
   using Goemon64Recomp's object/overlay info, including segment-8 asset
   mappings and raw keyframes; compare against the local source ROM mesh parts.
2. Render original segmented meshes and articulated keyframes in Ship,
   replacing static external OBJ geometry.
3. Complete Goemon-character gameplay actions, collision and interactions
   without depending on a hidden Link motion proxy, then add all four
   character-specific abilities and Randomizer integration.
