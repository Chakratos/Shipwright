# Real player AnimatedSkeleton owner and matrix-stack capture (2026-11-08)

**Status:** Hook code is compiled and locally staged; no actual original-game runtime capture using the new hook has yet been confirmed. This file is a permanent technical handoff, not a chat summary.

## Source-grounded discovery

Goemon64Recomp pinned source patches/variables.h distinguishes:
- D_801FC60C_5B851C: **player model Object**.
- D_801FC614_5B8524: separate **player root Object**.
- D_801684B0_1690B0: current/root MtxF.
- D_80168530_169130: **MtxF *stack destination cursor**.
- D_80168520_169120: original **resolved active animation pointer**.

In original player renderer (patches/anime.c, func_80016C44_17844, type 0x60000000), Object.graphics_1 is a tagged AnimatedSkeleton pointer. It is relocated using that Object's overlay_info[] base; its AnimatedSkeleton.animation field is separately resolved and stored into D_80168520. The original func_80018CA0 then traverses limbs, calling original func_800192D0 per bone.

Earlier diagnostic_mod/src/goemon_skeletal_capture.c accepted **only the player root** and sampled D_801684B0 as the post-animation matrix. Both were wrong for the original model/render workflow: the active 0x60000000 animation owner can be the separate player model; the latest original CPU-calculated per-limb matrix is at D_80168530 **minus 64 bytes** after evaluation. Sasuke may push two matrices (128 bytes total).

## Changes now committed

- GoemonAnim_CaptureRoot accepts a matching actual player root **or** the separate model Object; still refuses arbitrary scene NPC objects and non-0x60000000 render types.
- ResolvePlayerObjectPointer mirrors the original overlay relocation branch from patches/anime.c (direct/high-bit pointers; default segment base or 0x08–0x0D slot).
- NEW GOEMON_ANIM_OWNER event on active owner/action/overlay changes, with actual player Object pointer, tagged graphics_1, resolved AnimatedSkeleton address, flags, raw animation pointer, resolved source animation pointer and first Skeleton pointer.
- NEW GOEMON_ANIM_ACTIVE event at real player limb entry, recording actual original D_80168520 pointer, D_80168530 stack cursor, original source action and animation_progress.
- NEW GOEMON_ANIM_MATRIX_CURSOR event per source MIPS bone after original matrix calculation, with before/after stack pointers and exact push width. Captures **actual final stack MtxF** instead of static root D_801684B0; preserves GOEMON_ANIM_MATRIX schema for existing original_pose_archive converter.
- All events are emitted only when original mod capture_animation is enabled, with bounded frame count and player-movement gate. No assets leave owner PC.
- New tools/goemon/reference_probe/animation_owner_trace.py correlates GOEMON_ANIM_OWNER with GOEMON_ANIM_ACTIVE per real Object/action, reports exact matching or mismatching original engine pointer and 64/128-byte stack pushes. Does NOT assert numeric animation or actual SoH playback from pointer equality alone.
- tools/goemon/diagnostic_mod/reprocess_log.py runs the owner-correlator automatically when a new original runtime log contains these events and saves original_live_animation_owner.json into the **private local run folder**. Extra tags do not break prior GOEMON_ANIM_BONE/MATRIX pairing.

## Evidence

- Self-hosted Windows source MIPS mod build and staging: [run 42479222793](https://github.com/Chakratos/Shipwright/actions/runs/42479222793), successful. 313/313 Python plus native C++20 regression passed. The newer mod is staged in C:\Users\Chakratos\Desktop\SoH Goemon Test\goemon_original_trace.nrm and C:\actions-runner-goemon\original-animation-capture.
- Updated live-owner parser / reprocessing synthetic integration: [run 42479506702](https://github.com/Chakratos/Shipwright/actions/runs/42479506702), successful, 317/317 Python tests plus C++20 native tests.
- **These are compilation/synthetic tests.** No real GOEMON_ANIM_OWNER/ACTIVE stream has been observed in an actual original game playthrough yet. Thus active player animation pointer and source keyframes remain UNVERIFIED.

## Next runtime verification, when original game is running

The original-game capture is prepared: C:\Users\Chakratos\Desktop\SoH Goemon Test\Goemon_Originalanimation_aufnehmen.cmd. It uses tools/goemon/diagnostic_mod/install_and_record_windows.ps1 to put the NRM in the interactive user's original Goemon64Recompiled mods directory and launch the original game. The user must activate **Original-Skelettanimationen aufnehmen** in the original recomp mod menu, move the character, and ideally perform idle/walk/jump/attack and switch all four characters. The owner Windows service runner **cannot guarantee an interactive desktop game launch** and must not claim this happened automatically. No further Ship full build is required for capture.

Once original game exits, capture_windows.ps1 and reprocess_log.py write private GoemonTraceRuns/run-*/goemon_runtime.log, original_live_animation_owner.json and the GOPA archive if validated original per-limb matrices exist. The new parser checks pointer matches within source game runtime events.

Alternative if a prior original-game log is available locally:

    py -3 tools\goemon\reference_probe\animation_owner_trace.py "C:\path\to\goemon_runtime.log" --output "C:\path\to\original_live_animation_owner.json"

Do not commit that raw log, or original pose matrices/geometry. Update CURRENT_STATE, NEXT_TASKS, agent_state.json and exact evidence once verified. If no runtime sample is accessible, continue static original game Object.graphics_1 writer/action dispatch reverse engineering before requesting user assistance.

## Acceptance for source G1

A trace of actual playing player Object (not a guessed structural ROM record) must correlate:
(character_id, action_id, true player model Object, graphics_1, resolved AnimatedSkeleton, raw animation pointer, resolved active D_80168520, progress/tick) and show a **nonzero numerical difference** in authentic source MtxF across two genuine progress samples. Matching pointers alone passes the ownership subtask but **does not close G1**.

The original visible source mesh and isolated game build are unaffected by this mod change. Keep SoH AP/Archipelago untouched.
