# Goemon × Ocarina of Time — START HERE (agent restart entry)

> **Authoritative resume document.** Read this page, then CURRENT_STATE.md, NEXT_TASKS.md and TECHNICAL_DECISIONS.md before editing code. Repository state is authoritative over any AI chat history. Last project audit: **2026-11-08**.

## Mission / definition of done

Port the four original playable characters **Goemon, Ebisumaru, Sasuke, Yae** from *Mystical Ninja Starring Goemon* (N64, NG5E US) into the **Ship of Harkinian** (SoH) OoT world. Use authentic original N64 character geometry and skeletons, real authored motion driven by the original action states, measured movement and character abilities, and allow world quest and Randomizer progression. The game must feel like playing Goemon inside OoT, not Link wearing a skin. The original game is the behavioral source of truth.

**NOT DONE** until all four can walk, jump, animate, attack, switch and use their respective abilities in OoT with appropriate Zelda collision/interactions; assets come from a user-owned original game; action fidelity is benchmarked; Randomizer can reason about needed abilities and game can be played through. Intermediate experiments are not finished work.

## Repo and locations

- GitHub: https://github.com/Chakratos/Shipwright
- Development branch: **feature/goemon-original-controller** (inspect head SHA every session; do not assume an earlier SHA remains current)
- Ship Goemon code: soh/soh/Enhancements/Goemon/
- Ship Dev Tools: soh/soh/SohGui/SohMenuDevTools.cpp
- MIPS/offline tools: tools/goemon/re/
- Reference gameplay probe: tools/goemon/reference_probe/ and tools/goemon/diagnostic_mod/
- CI: .github/workflows/goemon-selfhosted.yml (private original ROM tests on self-hosted Windows), .github/workflows/goemon-source-tests.yml (portable)
- Private runner workspace: C:\actions-runner-goemon
- **Only** test game: C:\Users\Chakratos\Desktop\SoH Goemon Test
- **Never modify** C:\Users\Chakratos\Desktop\SoH AP (Archipelago).
- Local original source skeletal assets are in subfolders of C:\Users\Chakratos\Desktop\SoH Goemon Test\character-original; files original.goskel and isolated.gomips, generated locally and never committed. Optional GOEMON_ORIGINAL_CHARACTER_ASSETS env var selects asset root.
- Reference sources, pinned commits: tools/goemon/re/source_revisions.json. Goemon64Recomp dev patches/anime.c contains the original player render flow; klorfmorf/mnsg is partial decomp.

## Reading order (avoid historical contradictions)

1. **CURRENT_STATE.md** — only current *verified* facts and evidence; latest limitations first.
2. **NEXT_TASKS.md** — priority, exact files/commands, acceptance tests and stop conditions.
3. **TECHNICAL_DECISIONS.md** — non-negotiable design rationale, source addresses, data formats and build workflow.
4. docs/goemon/PORTING.md — broader feature target and historical plan; some paragraphs are old.
5. docs/goemon/ORIGINAL_ANIMATION_ENGINEERING_HANDOFF_2026-11-07.md — detailed *chronological* investigation; contains superseded hypotheses and explicit signed-zero corrections toward the end. It is evidence history, **not** current status.
6. docs/goemon/RE_TOOLCHAIN.md, docs/goemon/RE_SOURCE_MAP.md, docs/goemon/REAL_ROM_BASELINE.md — tool details and ROM/source layout. If they contradict current state, fix/document discrepancy.
7. Source code and the CI logs: never trust documentation claims over a failing test or actual source bytes.

## Session operating loop

1. Fetch branch HEAD, read AGENTS.md and all three canonical docs, inspect git diff and latest workflows. Select highest task marked OPEN.
2. Inspect actual related files and pinned reference source. Keep facts/uncertainties separate.
3. Make code changes, add regression cases that test the *specific invariant* and run targeted Python/C++ portable tests.
4. When a ROM-only check is needed, add a documented one-shot marker-gated step to goemon-selfhosted.yml (or reuse an existing exact marker), push, inspect actual private runner log, record run ID + result. Do **not** create artifacts containing ROM-derived bytes.
5. A source diagnostic is not the same as gameplay verification. Do not announce real motion without numeric nonzero transforms of drawable source vertices and eventually visual checks.
6. Commit source and tests. Update **CURRENT_STATE.md and NEXT_TASKS.md in the same completed work unit**, giving verifiable run links, decisions, open blocker and next command; update any affected guide. If an experiment failed, record it and what it disproved.
7. Repeat step 1 while practical work remains. Don't give time promises or claim future background execution.

## Minimum commands

From checkout root:

    python tools/goemon/verify.py
    python tools/goemon/verify.py --native

On Windows use py -3 instead of python if appropriate. These portable tests do not require the private ROM. The self-hosted workflow normally runs them automatically; optional [goemon-build] triggers a cached full SoH build. Run only precise opt-in offline ROM stages as NEXT_TASKS explains.

## Current biggest correction

The old “69 time-sensitive skeletons / visibly animated characters” conclusion was FALSE: it counted IEEE-754 +0.0 versus -0.0 as movement. **Corrected full scan: 0/371 numerically changing matrices at progress 0/1/4** with the current artificial original Object initialization. The original MIPS code does read some plausible animation-bank addresses for numeric-channel nodes, but action ownership / real pointer setup is unverified. Therefore the immediate task is **recovering the genuine active player AnimatedSkeleton/animation pointer and object/overlay state**. Do not start with another model conversion or fake animation loop.

## New-agent one-line handoff prompt

"Read AGENTS.md and docs/goemon/START_HERE.md in Chakratos/Shipwright on feature/goemon-original-controller. Continue the highest-priority unfinished task, implement/test/commit your work, and update the repository handoff before ending. Our target is four genuinely playable original Goemon characters in OoT; do not rely on our chat history."
