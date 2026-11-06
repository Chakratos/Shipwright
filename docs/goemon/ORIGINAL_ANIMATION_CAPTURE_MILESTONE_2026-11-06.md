# Goemon original N64 skeletal animations — runtime capture milestone

2026-11-06, branch `feature/goemon-original-controller`.

**Goal:** Genuine animated Goemon/Ebisumaru/Sasuke/Yae in Ship of Harkinian,
not a static OBJ swap or synthetic sine-wave movement.

## Verified facts

- The original NTSC-U NG5E ROM is available only on the self-hosted
  Windows runner. Its SHA and decompressed file-table checks pass.
- We decoded 108 real F3DEX Gfx runs across Goemon (24), Ebisumaru (31),
  Sasuke (53). Their source geometry is saved only at
  `C:\actions-runner-goemon\original-rom-meshes`. Yae's source Gfx
  bank remains unresolved.
- Original game **actually** animates player Skeleton limbs via
  `func_80018CA0_198A0` and composes matrices in
  `func_800192D0_19ED0`, as explicitly shown in
  `klorfmorf/Goemon64Recomp/patches/anime.c`.
- The original game tracks the live animated root and segment-overlay
  locations in `func_80016C44_17844`. The source decomp provides
  skeleton/limb structures; no ready-to-use animation export exists.

## Implemented code

1. `tools/goemon/diagnostic_mod/src/goemon_skeletal_capture.c`:
   MIPS mod hooks **the original engine**, logging per player/frame:
   root graphics + 0x08..0x0D overlay file IDs and addresses,
   signed Skeleton limb offsets + original S/R/T,
   display-list pointers, and **the original engine 4x4 matrix at
   return from the matrix calculation**.
2. `tools/goemon/reference_probe/original_skeletal_poses.py`:
   pairs bones and matrices on exact original game frame/character/action
   and pointer identity. Reports exact vs nearby/unverified source-ROM
   display-list matches.
3. `tools/goemon/reference_probe/original_pose_archive.py`:
   outputs a compact versioned **GOPA0001** local binary snapshot
   containing source game tick, action, character, skeleton hierarchy fields,
   source graphics pointers, and original 4x4 matrices. No interpolation.
4. `soh/soh/Enhancements/Goemon/OriginalPoseArchive.hpp`:
   matching strict native C++20 decoder and exact-tick pose lookup.
5. `tools/goemon/diagnostic_mod/reprocess_log.py`:
   automatic end-to-end extraction after original game capture, including
   animation-only runs with no legacy GOEMON_REF player-motion samples.
6. `tools/goemon/diagnostic_mod/install_and_record_windows.ps1`:
   one-click local installation and start of original game capture,
   with a desktop CMD wrapper.

**Build evidence:** Windows LLVM 18 MIPS compilation and RecompModTool
packaging of the new NRM succeeded on the owner's self-hosted runner.
The .nrm and launcher were copied to:

```text
C:\Users\Chakratos\Desktop\SoH Goemon Test\
    goemon_original_trace.nrm
    Goemon_Originalanimation_aufnehmen.cmd
```

This build is a **compiled capture instrument, not proof of live runtime
pose capture**. The original game must actually run with the new capture
option enabled. No full Ship build was triggered because the new pose
loader is not yet wired to rendering.

## User-assisted runtime capture (one click, then gameplay)

Double-click
`C:\Users\Chakratos\Desktop\SoH Goemon Test\Goemon_Originalanimation_aufnehmen.cmd`.

This automatically copies the `.nrm` into the interactive Windows user's
Goemon64Recompiled mods directory and launches the original recomp if
found at one of its known locations.

In the **original Goemon64Recompiled** game, go into Mod Settings,
enable the mod and select **Original-Skelettanimationen aufnehmen →
Originalanimation aufnehmen**. Then play enough to capture standing,
running, turning, jumping and attack states. Switch through the four
characters if possible. Close original game to automatically process
the logs. The output is written to a local GoemonTraceRuns folder,
including `original_skeletal_poses.json` and
`original_skeletal_poses.gopa` when matrices were captured.

If the launcher cannot find the original game's EXE, the single missing
detail is its exact path. Do not re-run all setup or ask for the ROM.

## Strict remaining work

1. **Runtime verification**: confirm that the capture produces real root,
   limb and nonconstant game matrices. If not, correct hook gate/offsets.
2. **Original limb ownership**: match captured 0x07 display-list pointers
   and 0x08 overlay mappings to ROM meshes. Do not infer the source of
   Yae's missing 303 geometry.
3. **Ship renderer**: use the source-ROM geometry and captured clip matrices
   to render articulated skeletons. Verify coordinate system, bone transforms,
   bone-local vs world matrices and proper N64 texture material association.
4. **Game controls**: replace the current static reference character
   as the player, preserve Zelda scene logic and Randomizer, and add all
   four original special abilities and weapons.

**Do not claim animated characters are in-game until item 3 is built and
verified visually.** The currently playable Ship version still draws static
reference OBJ characters.
