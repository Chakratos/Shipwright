# NEXT_TASKS — ordered implementation backlog and acceptance gates

**Update this file after every meaningful work unit.** A fresh agent picks the first OPEN gate, runs tests, commits evidence and updates CURRENT_STATE + this queue. Do not retry disproven approaches under another name. The project is not complete until real Goemon movement/animations/abilities are playable inside OoT with Randomizer support.

## P0 / G1 — Find genuine original player animation object / active stream (OPEN, NEXT)

**Why:** Corrected all-371 sweep produced zero numerically changing matrices because controlled source Object and animation context are incomplete/wrong, not because the 371 structural headers are proof of real animation. Narrow focus to original *live* player AnimatedSkeleton and action selection.

**Sources to inspect**
- Original renderer: Goemon64Recomp patches/anime.c, function func_80016C44_17844, case 0x60000000; func_80018CA0_198A0; the original numeric evaluator func_800192D0_19ED0.
- Original Object fields: Object.graphics_1, graphics_2, overlay_info[0..], animation_progress at Object+0x28, unknown_70; AnimatedSkeleton.flags, animation, skeletons[0]; PlayerTask.action_id +0xCC, character ID +0x60, root Object global 0x801FC614.
- Local code: tools/goemon/re/probe_original_mips_execution.py, original_mips_vm.py, offline_animation_action_pointers.py, analyze_yae_resource_pointers.py, profile_original_animation_channels.py, source-aligned file index mappings.
- Existing original-game instrumentation: tools/goemon/reference_probe and tools/goemon/diagnostic_mod; private owner runner has the NG5E ROM. Prefer deterministic offline trace first.

**Concrete engineering steps**
1. **DONE (run 42478639378):** precise original MIPS CPU read tracing with PC/address/width and source-bank candidate pointer proximity; all 12 tested candidate contexts return no numeric pose motion. See docs/goemon/ANIMATION_POINTER_PROVENANCE_2026-11-08.md. This is pointer provenance, **not** proof of live D_80168520 ownership.
2. Decode the REAL private ROM AnimatedSkeleton header/animation pointer **including overlay relocation** as performed in original anime.c. Audit current original_source_context: which candidate is chosen? What is actual object.graphics_1? Why are source candidate “actions” not proven? Do not confuse header indices with action enum values.
3a. **DONE: exact ROM player action/graphics offset scan** (Windows [run 42480203308](https://github.com/Chakratos/Shipwright/actions/runs/42480203308)): 10 syntactic action_id +0xCC byte-store candidates and 131 graphics_1 +0x2C word-store candidates in original player overlay file ID 10. Next **offline code step**: follow register r4/r16 provenance and call sites around those 10 candidate action setter PCs; filter Object.graphics_1 matches that use stack register r29. Addresses and limitations: docs/goemon/ORIGINAL_PLAYER_OBJECT_WRITERS_2026-11-08.md. Do not assume candidate offset means real player pointer.

3b. **IMPLEMENTED, awaiting private ROM run:** tools/goemon/re/trace_player_writer_provenance.py performs conservative straight-line MIPS r4/r16/global load provenance, drops r29 graphics stores, and records static direct-JAL callers to *heuristic* function prologues (never claims a verified function boundary). Synthetic tests: test_trace_player_writer_provenance.py, 7/7 passed locally. One-shot marker: **[goemon-player-writer-provenance]** on self-hosted workflow; inspect actual output, then prioritize proving incoming call arguments / tracked registers across real control flow. Static evidence alone cannot close G1.

3. **PARTIAL DONE — runtime capture instrument compiled, no actual new game run:** corrected diagnostic_mod/src/goemon_skeletal_capture.c to accept model Object D_801FC60C and root D_801FC614 and emit live GOEMON_ANIM_OWNER, ACTIVE and MATRIX_CURSOR. Corrected matrix capture from D_80168530-64. NRM staged by [run 42479222793](https://github.com/Chakratos/Shipwright/actions/runs/42479222793). Local parser/reprocessor tests [run 42479506702](https://github.com/Chakratos/Shipwright/actions/runs/42479506702) pass. **NEXT:** obtain actual original-game runtime capture using the pre-staged one-click launcher, or trace PlayerTask.action_id / Object.graphics_1 writers offline if interactive original game is not running. See docs/goemon/LIVE_ORIGINAL_ANIMATION_OWNER_2026-11-08.md. Do not mark real live player owner verified based on synthetic tests.
4. Feed that authentic captured state into the N64 CPU evaluator; test progress across genuine original tick steps and assert actual numeric MtxF element changes. Build a source ROM-only regression with synthetic falsifiable controls.
5. Log **metadata**: source header/animation owner address, action id (when verified), original instruction-PC readers, number of nonzero numerical changes, reference runtime/commit and Windows Actions run id. Do not upload original matrix arrays or ROM bytes.

**Acceptance G1:** A verified real player action/state binds to an exact original animation stream and produces at least one **nonzero numeric** source bone transform change over actual original frame progression. Merely calling original MIPS, reading some source bank, or changed IEEE signed-zero is NOT enough.

**Relevant fast commands:** python tools/goemon/verify.py ; python tools/goemon/verify.py --native. For owner-ROM-only analysis, add/reuse a one-shot marker in .github/workflows/goemon-selfhosted.yml. Push marker commit, then READ LOGS and record run ID. Never run an unnecessary full Ship build.

## P0 / G2 — Recover original animation timeline and complete per-limb poses (OPEN, blocked by G1)

Map verified player actions (idle, walking/running/turning, jumping, landing, weapons, abilities, switching, water/damage) to actual original ROM animation pointer(s), progress semantics and clip frames; reconstruct original stack right/left, object transitions, 0x4000 pops and any 128-byte pushes. Confirm per-source bone *and drawable vertex* positions numerically differ when expected; confirm identity/parent stack and interpolation semantics against actual original runtime traces. Only now generate genuine GOPA per-frame native assets. Regression must reject zero-motion fake clips, guessed durations and unowned candidate animations.

## P1 / G3 — Visually validate original player rig in OoT (OPEN, blocked by G2)

Convert real original sourced matrices + original source bodyparts, resolve missing mesh tags, texture bindings, scale and orientation. Draw complete coherent original player rig in SoH as character, replacing static source proxy. Run one cached Windows Ship build after renderer changes; validate in test install only, capture in-game image/trace. Existing first successful build run 42396981715 is **static experimental geometry only**.

## P1 / G4 — Four playable original controllers and world integration (OPEN, blocked by G3)

Finish original movement, collision, camera and player-state transition parity; attacks, weapons, abilities and interaction bridge with OoT. Disable or remove abandoned feasibility ball/ghost from product UI once replaced. Validate switching all four original characters without breaking saves, door NPC/scene flow, death/loading and item interactions. Character-specific features are documented in docs/goemon/GOEMON_ZELDA_ABILITY_MAPPING.md and original traces in docs/goemon/REAL_GAME_*.md. Do not claim full parity merely because controller unit tests succeed.

## P2 / G5 — OoT quest, Randomizer and ship-ready asset delivery (OPEN, blocked by G4)

Complete four-character abilities as OoT traversal/quest items; implement corresponding Randomizer logic and test solvability/edge cases, package original assets locally from owner ROM with deterministic version/hash checks, verify OoT whole-game journey and source attribution. No proprietary game assets in Git or Actions artifacts. Keep isolated Goemon Test separate from SoH AP forever.

## Engineering operating rules

- Every new/changed experiment: commit source and tests, run portable and where necessary private Windows source experiment, record exact GitHub Actions URLs (success/failure) in CURRENT_STATE, update this queue with next single blocker. Repo docs are authoritative; old chat is never required.
- Source-only test results are NOT successful game integration. Stages and gates may not be advanced speculatively.
- **No 10-minute full Ship builds without renderer/player integration code that justifies them.**
- New agents must continue from the next OPEN gate, not restart the whole research loop, unless a falsifying regression requires re-evaluation.
