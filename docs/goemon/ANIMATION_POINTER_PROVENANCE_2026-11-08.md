# Original ROM animation-pointer provenance — 8 November 2026

**Current technical experiment, source only.** Branch feature/goemon-original-controller. **Real original animations are NOT yet recovered or moving.**

## Exact experiment and why

Earlier code divided source bank reads into two large approximate intervals: candidate animation pointer to first source Skeleton node; and from first Skeleton node onward. That showed possible animation-region reads but **did not prove reads were near or derived from the candidate animation pointer**. After the signed-zero correction, none of the 371 structural source candidates produced true numerical pose changes under synthetic Object context.

New code (original ROM data private on owner Windows PC):
- original_mips_vm.py records only (MIPS instruction-PC, source RDRAM read address, read width, count), after a *successful* original CPU load, not original ROM content.
- probe_original_mips_execution.py opt-in capture_source_read_sites returns read-site metadata to private source analysis caller.
- trace_original_animation_pointers.py chooses first structural header, header with most positive numeric raw channel fields, and previously selected geometry-compatible header for each character; invokes real source MIPS on best numeric limb at original progress 0,1,4 with separated MtxF stack.
- Its exact candidate pointer proximity criterion is [candidate_resolved_pointer, candidate_resolved_pointer + 128). It is **only a limited diagnostic window**; it cannot prove no data is read elsewhere.
- Its numerical source-MIPS matrix digest canonicalizes IEEE +0.0 and -0.0. *Observed changing read sites* never imply moving matrices or actual animation.

## Verified result

- Windows runner GitHub Actions: https://github.com/Chakratos/Shipwright/actions/runs/42478639378 (success).
- Portable tests: https://github.com/Chakratos/Shipwright/actions/runs/42478639377 (success).
- **12 source candidate AnimatedSkeleton headers** across Goemon, Ebisumaru, Sasuke, Yae passed original CPU progress 0/1/4 with no errors; **0/12 numeric matrix changes**.
- **11/12** candidate animation pointers had **zero** source reads in the first 128 bytes after the pointer. Exactly **1/12** had reads: Ebisumaru most-numeric candidate source header 0x07029F74, candidate animation pointer 0x070298A0, 13 near-pointer reads per progress. Reader PCs include 0x8001B2F8, 0x8001B330, 0x8001B3CC.
- For many candidates read locations do vary between 0,1,4. Yet numeric returned bone matrices remain constant. This is evidence of *some* source data traversal, not real animation playback or clip identity.
- Several first structural candidates had source candidate animation pointer 0x07000000. These headers being structurally plausible does not prove real live player binding.

## Interpretation, remaining uncertainties and next executable task

**Not yet established:** Which source PlayerTask/Player Object action sets Object.graphics_1 with the 0x60000000 player tag; how object overlay_info[] relocates it into AnimatedSkeleton; which concrete AnimatedSkeleton.animation pointer the **active** player uses; and what original progress/tick enters function func_800192D0_19ED0.

Actual Goemon64Recomp/patches/anime.c case 0x60000000 dereferences these fields and puts the resolved animation address into D_80168520. The synthetic offline MIPS context currently sets guessed offsets, not a captured live player's animation owner; do NOT infer that guessed 0x07 structural headers are real action clips.

**NEXT:** Inspect original renderer plus runtime source code for writers of Object.graphics_1 and PlayerTask.action_id, then implement a compact original-game diagnostic that records (character_id, action_id, graphics_1, graphics_2, overlay_info base/segment, AnimatedSkeleton flags/animation, Object.animation_progress) at an actual player render/update callback, with fields and pointer identity only. Reuse current reference_probe or diagnostic_mod when possible, keep ROM/asset bytes private. Validate one real idle/move/jump action binding and numerically nonzero original MtxF before promoting any frame to GOPA. No extra full Ship build is warranted for source investigation.

This note supplements CURRENT_STATE.md and NEXT_TASKS.md. Older animation-matrix change claims elsewhere in docs are superseded by the signed-zero-corrected 0/371 result.
