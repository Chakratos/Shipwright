# TECHNICAL_DECISIONS — stable architecture and conventions

## Ground-truth/claim hierarchy

These labels are intentionally different:
- Structural candidate: raw 0x07 resources / possible source skeleton; neither active game player owner nor animation clip is confirmed.
- Original CPU executed: actual NG5E machine code returned successfully in an artificially configured MIPS interpreter; NOT a moving pose.
- Original animation stream dereferenced: source-memory load trace intersects a verified active animation pointer; only direct address+PC evidence establishes this, not the current approximate bank interval heuristic.
- Numerically moving bone: at least one finite matrix element changes by a nonzero amount, with source player state, signed-zero normalization and real original progress.
- Drawable moving original bodypart: actual sourced N64 triangle coordinates change numerically under the verified pose transform.
- Authentic playable action: verified real game action/clip/tick and visuals within SoH player world, with representative gameplay tests.
Do not conflate stages or claim later ones from earlier ones.

## Source and binary conventions

- NG5E NTSC-US original N64 ROM stays user-owned on PC. Splat-style extracted file labels are actual ROM file table indexes **plus 1**; never guess segment/file ID.
- Source AnimatedSkeleton and skeleton data are mostly source segment 0x07; original character graphics often segment 0x09. Yae has additional 0x29/0x0F tagged graphics pointers and unresolved source graphics bank details.
- Original player renderer uses Object graphics tag 0x60000000, source function func_80016C44_17844 and func_80018CA0_198A0, and matrix evaluator func_800192D0_19ED0. Live Object.graphics_1 and AnimatedSkeleton.animation ownership still unverified.
- MIPS matrix global D_80168530 points to destination stack; each push is normally 64 bytes but some Sasuke cases 128 bytes. D_801684B0 is NOT the same underlying address. Do not alias these globals in tests.
- The original skeleton is **not simply an ordinary child/sibling node**: uses relative offset_right recursion/offset_left iteration, object changes, and 0x4000 pop flags. Source parent indices in package are a useful approximation but not a complete original player traversal.
- GOSKEL01 holds source geometry, raw Skeleton structure and candidate header; GOANIM01 contains raw unassigned compressed channel bytes (not decoded clips); GOPA0001 is frame matrix container with synthetic test coverage but no validated original live frames; GOMIPS01 contains only controlled source CPU matrix snapshots (not gameplay frames). Source v4 uses progress 0 and 4 and preserves one MIPS CPU across source bones; yet neither numeric animated movement nor live clip ownership is verified.
- Matrix layout selection (row- versus column-major) remains experimental, original textures/materials not yet restored, and first rig has missing mesh links for some figures. Do not publish preview as final.
- MIPS IEEE signed-zero: convert +/-0.0 to equal **numeric** zeros before animation change comparisons. A raw digest difference is not motion. Strongly prefer explicit numerical diff test plus transformed real N64 triangle test.
- Physical controller/physics implementation is source-trace based, but some SoH collision/camera adapters are diagnostic approximations. Prior ball/ghost limitations are documented in docs/goemon/LIVE_CONTROLLER_INTEGRATION.md. User requests **no more feasibility-ball debugging**; prioritize real character port.
- Inputs, attacks, special actions and world/randomizer milestone follow docs/goemon/PORTING.md and GOEMON_ZELDA_ABILITY_MAPPING.md. Original Goemon action logic—not Link's attack animation—determines final behavior.

## Private source and CI workflow

- Branch feature/goemon-original-controller, repo Chakratos/Shipwright.
- .github/workflows/goemon-selfhosted.yml runs source-only Python/C++ tests automatically on relevant pushes. Its commit markers opt into private experiments. Search the workflow for existing marker before adding a new step; avoid duplicative stale scripts and never chain failing experimental steps to copying old assets.
- Build marker [goemon-build] triggers one full cached Ship Windows build; omit in docs-only and offline reverse-engineering commits. The first successful rig-preview build is run 42396981715.
- The runner may execute as Windows NetworkService and cannot reliably read interactive AppData. Private source files live under C:\actions-runner-goemon; isolated test game is C:\Users\Chakratos\Desktop\SoH Goemon Test.
- Absolutely never touch C:\Users\Chakratos\Desktop\SoH AP.
- No ROM data, extracted meshes, textures, animations or raw machine code in commits, Actions artifacts, test outputs or user-visible diagnostic logs. Numeric summaries, known source symbols/offsets and hashed state are fine.
- Pin external Goemon64Recomp/mnsg revisions per tools/goemon/re/source_revisions.json; actively check drift before quoting external HEAD. Do not mistake historic "latest" status from chat or old docs for branch HEAD.

## Documentation protocol / no-chat-dependency

- Root AGENTS.md is universally discoverable agent instruction. START_HERE.md is the resume entry point.
- CURRENT_STATE.md contains only verified current claims, negative results and CI URLs.
- NEXT_TASKS.md contains prioritized acceptance gates and immediate runnable work.
- This TECHNICAL_DECISIONS.md records stable constraints and root causes.
- The long ORIGINAL_ANIMATION_ENGINEERING_HANDOFF_2026-11-07.md remains historical chronological investigation; it includes disproven hypotheses and is NOT the status document.
- For every meaningful commit: update tests and these docs when facts changed. Do not leave important reasoning only in comments, GitHub issues or chat. Add one concise reproducible test/evidence note and the exact next blocker to repo docs.
