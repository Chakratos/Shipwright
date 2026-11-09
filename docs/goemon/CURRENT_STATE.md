# CURRENT_STATE — authoritative verified status

**Last audit:** 2026-11-08. **Branch:** feature/goemon-original-controller. **Status:** IN PROGRESS; no authentic animated gameplay clips in SoH. Evidence references are actual recorded GitHub Actions run IDs. New work MUST update this document on the same branch; never rewrite test failures as successes.

## Große Original-Funktionszeigerregion (2026-11-09)

- Owner-ROM [42607985211](https://github.com/Chakratos/Shipwright/actions/runs/42607985211) **391/391 Python + native PASS**. Die zweite JR-Funktion 0x801E0944 liegt bei Originaldatenadresse 0x80203E78 in einem zusammenhängenden Block von **232 gepinnten Funktionsanfangsadressen**. Einzig diese statische Adressstruktur ist verifiziert; es ist noch keine logische Gameplay-Action-Tabelle nachgewiesen.
- Neue Metadaten erfassen Anfang/Ende, Slotposition, unterschiedliche Funktionsziele und Überschneidungen mit den zehn Kandidaten für PlayerTask.action_id-Schreibstellen. Keine Original-Funktionszeigerliste wird exportiert; Original-Runtime-Besitz bleibt unbewiesen. Ein synthetischer Test, privater Owner-ROM-Nachweis mit [goemon-player-jump-tables] steht aus. G1 offen.

## Funktionseintrag-Referenzen des originalen JR-Dispatchers (2026-11-09)

- Privater Owner-ROM [42607558009](https://github.com/Chakratos/Shipwright/actions/runs/42607558009), **388/388 Python + native C++20 PASS**. Der zweite JR-Dispatcher 0x801E0944 wird in Original-ROM-Metadaten zweimal syntaktisch referenziert: exaktes unrelociertes Funktionsadresswort bei 0x80203E78, LUI/Low-Konstruktion bei 0x801DD5F8/0x801DD608. Dies ist eine stärkere **statische Funktionsreferenz**, noch kein erwiesener aktiver Callback. Erster JR-Dispatcher 0x801D9E9C zeigt keine solche Referenz im Overlay, aber einen direkten JAL-Aufruf.
- Neuer CFG-Datenfluss prüft nach diesen Adresskonstruktionen echte MIPS SW-Schreibstellen, deren Register nach allen bekannten lokalen Pfaden exakt die Dispatcher-Funktionsadresse enthält. Ausgabefelder: Speicher-Offset und abstrakte Herkunft des Ziel-Basisregisters; zusätzlich prüft die Analyse, ob das direkte Funktionsadresswort neben weiteren bekannten Funktionsadressen liegt (Callbacktabellen-Kandidat). Drei synthetische Regressionen, Owner-ROM-Rerun per [goemon-player-jump-tables] ausstehend. Das ist keine Bestätigung eines laufenden Spieler-Callbacks. G1 offen.

## Indirekte Originalspieler-Dispatcher-Registrierung (2026-11-09)

- Owner-ROM [42607234758](https://github.com/Chakratos/Shipwright/actions/runs/42607234758) erfolgreich: **385/385 Python, C++20 bestanden**. Erster Dispatcher 0x801D9E9C: ein direkter JAL-Aufrufer mit unvollständiger Herkunft; zweiter Dispatcher 0x801E0944: **kein einziger direkter JAL-Aufrufer** im Player-Overlay. Keine bekannten originalen Player-Global-Roots. Deshalb ist die vorherige reine JAL-Rekursion nicht ausreichend; indirekte Funktionszeiger bzw. externes Overlay sind zu untersuchen.
- Neuer privater ROM-Metadaten-Scan sucht direkte, noch nicht relocatete Funktionsadresswörter und ununterbrochene LUI/ADDIU/ORI-Adresskonstruktionen für beide originalen Dispatcher. Drei synthetische Regressionen gegen Register-Clobber/Branch-Fehlzuordnung. Ein fehlender Treffer beweist **nicht** das Fehlen einer Laufzeitregistrierung, weil Relokationen, externe Calls und Callback-Tabellen nicht vollständig erfasst werden. Marker [goemon-player-jump-tables] startet Windows-Prüfung; G1 unverändert offen.

## Original-Dispatcher: a0 im MIPS-JAL-Delay-Slot (2026-11-09)

- [42606446315](https://github.com/Chakratos/Shipwright/actions/runs/42606446315) **382 Python und native C++20 bestanden**. Beim ersten JR ergibt der echte lokale CFG-Index UNKNOWN trotz syntaktischem Kandidaten 1; die vorherige Annahme war nicht ausreichend. Beim zweiten JR ist die symbolische entry-a0 -> LW +0x5C -> LHU +0x30-Kette im lokalen Original-ROM-CFG bestätigt; Typ des Parameters unbestätigt.
- Neue Vorwärtsherkunft führt jetzt den JAL-Delay-Slot aus, bevor sie die übergebene a0-Herkunft klassifiziert. Vorher wurde jeder a0-schreibende Slot pauschal verworfen, obwohl MIPS häufig dort Argumente setzt. Zusätzlich werden gepinnte direkte Aufrufer beider JR-Dispatcher über bis zu fünf Ebenen untersucht. Drei synthetische Regressionen; neue Owner-ROM-Ergebnisse stehen aus. Original-Animation G1 OFFEN.

## Original-MIPS-CFG: Index- und verschachtelte Feldherkunft (2026-11-09)

- Privater ROM-Lauf [42584776027](https://github.com/Chakratos/Shipwright/actions/runs/42584776027) **377/377 Python + native C++20 erfolgreich**. Erste JR-Tabelle: syntaktischer Indexkandidat 1, ein dazwischenliegender Kontrollflussübergang; nicht als Laufzeitaktion bestätigt.
- Neuer echter CFG-Datenfluss am Index-Shift-PC statt nur nächstliegender rückwärts gefundener Definition; wertet konstante ADDIU- und Schiebeoperationen aus. Für zweite JR-Tabelle transportiert die abstrakte Analyse die Feldherkunft aus *Funktionsargument a0* → LW +0x5C → LHU +0x30 auch über Kontrollfluss zusammen. Ergebnis ist ausdrücklich ein Typ-unbestätigter Strukturbeweis, **kein** echter PlayerTask-/Animationsbesitz.
- Fünf neue synthetische Regressionstests. Windows-ROM-Rerun mit [goemon-player-jump-tables] noch ausstehend. G1 offen; keine Originalbewegung bestätigt.

## JR selector constant-source correction (2026-11-09)

- Source-free evaluator now reduces a zero-register-anchored ADDIU/ORI/shift chain to a numeric syntactic selector candidate, rather than treating the entire index as zero because its earliest input is r0. Variable shift forms fail closed. Control-transfer count and permanent alternative-path warning remain visible; these are not animation/action proofs.
- Four synthetic regression tests added; the opt-in private-ROM [goemon-player-jump-tables] check remains to be verified. Source-only change, no full Ship build. G1 OPEN.

## Original player JR dispatch offline ROM evidence (2026-11-08)

- Owner ROM [42484532406](https://github.com/Chakratos/Shipwright/actions/runs/42484532406) **358/358 Python plus native C++20 PASS**: indirect JR PC 0x801DA23C (r12, LW 0x801DA238) has a contiguous 10-entry, 9-unique-target table at private original player overlay offset 0x03FAA0. JR 0x801E0980 (r24, LW 0x801E097C) has a 6-entry, 6-unique-target table at offset 0x03FD78. Both target PCs lie within pinned original functions. Structural candidates, NOT live action streams.
- [42484757248](https://github.com/Chakratos/Shipwright/actions/runs/42484757248) 360/360 PASS: each source target table matches one high LUI plus signed-low LW plus indexed ADDU provenance. [42484877490](https://github.com/Chakratos/Shipwright/actions/runs/42484877490) 362/362 PASS: five previous bounded-unreachable action-offset stores are reachable *when* the static original table targets are injected as hypothetical CFG edges, all five flagged incomplete structural paths. Four other sites directly inherit entry-a0, one unknown. **9/10 structural candidates are locally reachable; none are proven actual PlayerTask writers**.
- [42485168086](https://github.com/Chakratos/Shipwright/actions/runs/42485168086) 364/364 PASS: second switch source index uses halfword load +0x30(r3) at PC 0x801E0964, but r3 owner is still unknown. [42485342018](https://github.com/Chakratos/Shipwright/actions/runs/42485342018) 365/365 PASS, [42485490918](https://github.com/Chakratos/Shipwright/actions/runs/42485490918) 366/366 PASS, [42485638269](https://github.com/Chakratos/Shipwright/actions/runs/42485638269) 367/367 PASS, [42485758402](https://github.com/Chakratos/Shipwright/actions/runs/42485758402) **368/368 Python plus native PASS**: first switch selector contains shifts and ADDIU (shift at 0x801DA1FC), source producer still before current limited backwards window. These selectors must NOT be conflated with PlayerTask.action_id +0xCC.
- No authentic AnimatedSkeleton.animation owner or numerical original animated pose is proven; G1 remains OPEN. Full proof and test links: [PLAYER_INDIRECT_DISPATCH_EVIDENCE_2026-11-08.md](PLAYER_INDIRECT_DISPATCH_EVIDENCE_2026-11-08.md).

## Player direct-call provenance beyond one function, 2026-11-08

- MIPS CFG improved after real ROM blocker classification. Initial new [run 42483311867](https://github.com/Chakratos/Shipwright/actions/runs/42483311867) failed only because an obsolete unit test still expected unsupported branch-likely; updated regression [run 42483433237](https://github.com/Chakratos/Shipwright/actions/runs/42483433237) passed 345/345 Python and C++20 native. This failure was corrected, not suppressed.
- [Run 42483632507](https://github.com/Chakratos/Shipwright/actions/runs/42483632507) passed 348/348 Python and native. Correctly distinguishing COP1 float arithmetic from actual control instructions changed action writer analysis from 9 false-unreachable candidates to **four source-function entry-a0 parameter origins** (PCs 0x801CC3DC, 0x801DAED4, 0x801DD640, 0x801DD6B4); one unknown; five still bounded-unreachable via genuine **indirect jr** dispatch PCs 0x801DA23C and 0x801E0980. These are **candidate field-offset writes**, not verified PlayerTask owners.
- [Run 42483948947](https://github.com/Chakratos/Shipwright/actions/runs/42483948947) passed 351/351 Python and native. Pinned public Goemon64RecompSyms **complete inventory of 906 original player-overlay function boundaries** now in tools/goemon/re/player_overlay_function_symbols.json, not copyrighted ROM binary. Verified all seven original direct-JAL caller targets in private ROM. Five caller a0 inputs inherit function-entry a0; two have a0 overwritten by an unresolved JAL delay slot.
- [Run 42484165983](https://github.com/Chakratos/Shipwright/actions/runs/42484165983) passed **353/353 Python plus native C++20**. A bounded backward interprocedural direct-JAL graph follows inherited a0 through at most five levels; **ZERO** exact pinned player-global loads found on explored paths. For candidate function 0x801DAD68, 380 direct-call edges visited, many incomplete CFG/delay-slot/unknown roots. That negative result applies only to direct JAL paths in the same overlay under bounded abstract analysis; indirect dispatch and caller-entry origin remain unresolved. It is NOT proof no real PlayerTask action exists. Source tool now limits root-chaining to action-id writer candidates, excluding unrelated graphics stores.
- **G1 unchanged:** no authenticated live AnimatedSkeleton.animation owner, no numerically changing MtxF source poses, no playable original animations in OoT. Next: resolve indirect jr switch targets and incoming PlayerTask a0 arguments, then active graphics1/animation owner. Do not run a full Ship build for pure disassembly work.

## Original player MIPS CFG + pinned source symbols, 2026-11-08

- **Verified Windows private-ROM run [42482341951](https://github.com/Chakratos/Shipwright/actions/runs/42482341951): 339/339 Python and native C++20 tests PASS.** New bounded MIPS CFG register-origin analysis handles conditional branch path merging, delay slots, and caller-saved versus s0 register behavior; 10 synthetic source-free tests were added. Old *heuristic* function entries yielded action candidate origins 9 "unreachable"/1 "unknown", but these are **not gameplay reachability results**: limited CFG control-flow models and missing indirect paths produce false-unreachable under an assumed entry.
- Source breakthrough: pinned Goemon64RecompSyms commit 49f4e3269f05c737cb4bf698b9ef7142c92f1ac7, file mnsg.syms.toml, **section .file_11** (ROM 0x00587370, VRAM 0x801CB460, size 0x41400). Owner ROM overlay ID 10 exactly matches the section. Public function start/size spans uniquely cover **all 10** action +0xCC stores and **all 7** candidate JAL callers; multiple other overlays share similar VRAM addresses, so selecting .file_11 is crucial.
- **Verified follow-up Windows run [42482887968](https://github.com/Chakratos/Shipwright/actions/runs/42482887968): 342/342 Python and native C++20 tests PASS.** Pinned symbol spans matched the same current CFG summary: 9/10 action stores locally "unreachable" with **incomplete CFG**, 1 "unknown"; graphics non-stack candidates 4 "unreachable", 1 "incomplete", 16 not in the deliberately bounded symbol manifest. **These labels cannot exclude actual live original player stores.** The metadata-only pinned function manifest is tools/goemon/re/player_overlay_function_symbols.json; all owner-ROM checks passed, no ROM/asset upload.
- Genuine original active player AnimatedSkeleton/animation, complete MIPS control-flow dispatch and any numerically changing authentic pose remain UNVERIFIED. G1 stays OPEN. Next step is diagnose original CFG termination reasons, support the actual branch/jump forms or use genuine runtime owner sampling for corroboration. No full Ship build justified for source-only reverse engineering.

## Conservative player writer provenance work unit (2026-11-08)

- Added source-free MIPS local register-origin tracing and direct-JAL-to-prologue *hints* for player overlay action_id +0xCC and non-stack graphics_1 +0x2C store candidates. The provenance engine recognizes only exact pinned player pointer globals loaded with lw; it stops at branches, calls and unknown writes rather than inventing interprocedural ownership. Stack r29 graphics stores are excluded.
- First Windows run [42481382788](https://github.com/Chakratos/Shipwright/actions/runs/42481382788) succeeded: 327/327 Python tests and native C++20 tests passed, including seven new source-free cases. Verified owner-ROM scan found **10/10 action candidates with no local known-player-global pointer-load proof**; action base origins: nine control-flow boundaries and one unresolved r4. Of 131 original +0x2C overlay stores, **21 are non-r29**; zero have local known-player-global pointer-load proof. Static call-to-prologue *hint counts* across the ten action sites: 1,1,0,3,2,0,0,0,0,0. This is a negative result only for the bounded local analysis, not disproof of actual player animation.
- Second Windows run [42481566704](https://github.com/Chakratos/Shipwright/actions/runs/42481566704) **passed**: 329/329 Python tests and native C++20. Added static direct-JAL caller `a0` origin hints with JAL delay-slot invalidation (9 new synthetic tests total). Across seven matching JAL callsites associated with unverified prologue hints, **zero** had a local pre-JAL known player-global `a0` proof. Callsite PCs: 0x801CB7DC; 0x801D9F88; 0x801DAC9C, 0x801DACF0, 0x801DAD24; 0x801DD4E8, 0x801DD5A0 (seven sites total). No actual owner/clip confirmed. Opt-in marker: [goemon-player-writer-provenance]; private report path: C:\actions-runner-goemon\original-player-writer-provenance.json. This is static evidence only, not live original action/animation verification. G1 remains OPEN. See ORIGINAL_PLAYER_WRITER_PROVENANCE_2026-11-08.md.

## Latest original player-overlay original ROM writer scan (2026-11-08)

- Original NG5E source MIPS syntactic field-offset scan identified **player overlay file ID 10** (known player function at ROM 0x5988D8 / VRAM 0x801DC9C8), with 267264 scanned bytes; 10 potential byte stores at PlayerTask.action_id offset +0xCC, and 131 potential word stores at Object.graphics_1 offset +0x2C. These are NOT proven object owners. Main executable had 0 action-offset hits and 248 graphics-offset matches, many stack-based.
- Original action-offset candidate PCs: 0x801CC3DC, 0x801D9E74, 0x801DA5D8, 0x801DAED4, 0x801DD640, 0x801DD6B4, 0x801E0AEC, 0x801E0B98, 0x801E0BD0, 0x801E0BE0. All base r4 or r16. One first non-stack graphics candidate: PC 0x801CBC70 (base r4, word value r2). See [ORIGINAL_PLAYER_OBJECT_WRITERS_2026-11-08.md](ORIGINAL_PLAYER_OBJECT_WRITERS_2026-11-08.md) for evidence and limitations.
- Actual private Windows run [42480203308](https://github.com/Chakratos/Shipwright/actions/runs/42480203308) **passed**, 320/320 Python and native C++20 tests. **Next:** prove original MIPS base-register/function-call provenance and actual runtime PlayerTask/Object pointer identities. True active animation owner, exact action mapping and numeric animation remain unverified.

## Latest original-game capture instrumentation (2026-11-08)

- **Real runtime owner instrument is prepared and compiled, NOT played:** diagnostic_mod/src/goemon_skeletal_capture.c now accepts actual player-model Object D_801FC60C as well as root D_801FC614, resolves live tagged graphics_1 through overlay_info into AnimatedSkeleton and the animation pointer, emits GOEMON_ANIM_OWNER / GOEMON_ANIM_ACTIVE, and captures the actual per-limb final stack MtxF from D_80168530-64, with a cursor event for 64/128-byte pushes. Original model/root gate had been too restrictive.
- Windows mod compilation and staging [run 42479222793](https://github.com/Chakratos/Shipwright/actions/runs/42479222793), 313/313 Python tests and native checks passed. New NRM is locally staged under SoH Goemon Test, not yet known to be executed in-game.
- New automatic live owner/action and pointer-match parser, integrated with local original-game reprocess_log.py; source-free parser+pipeline tests [run 42479506702](https://github.com/Chakratos/Shipwright/actions/runs/42479506702), **317/317** Python tests and native C++20 checks passed.
- **No actual GOEMON_ANIM_OWNER/ACTIVE trace captured yet.** Pointer ownership from real game remains unknown, and therefore numerical animated original bone motion also unknown.
- Complete technical instructions: [LIVE_ORIGINAL_ANIMATION_OWNER_2026-11-08.md](LIVE_ORIGINAL_ANIMATION_OWNER_2026-11-08.md).

## Latest ROM experiment — exact source pointer provenance (2026-11-08)

- New exact-PC/read-address/width tracing: tools/goemon/re/trace_original_animation_pointers.py and original_mips_vm.py; proven source-free regression in test_original_mips_vm.py and test_trace_original_animation_pointers.py.
- **Verified Windows run [42478639378](https://github.com/Chakratos/Shipwright/actions/runs/42478639378)**, hosted tests [42478639377](https://github.com/Chakratos/Shipwright/actions/runs/42478639377). Tested three source headers per character (first structural, most numeric channels, historical mesh-matched) at source progress 0/1/4, 12 candidates total.
- **0 of 3 Goemon, 0 of 3 Sasuke, 0 of 3 Yae, and 1 of 3 Ebisumaru** candidate pointers had any original MIPS source-bank reads in the **first 128 bytes at or after that candidate animation pointer**. Ebisumaru candidate header 0x07029F74, candidate animation pointer 0x070298A0 showed 13 near-pointer reads at each progress value, including original MIPS reader PCs 0x8001B2F8 and 0x8001B3CC.
- **0/12** candidates produced numeric MtxF change at progress 0/1/4, even though some *read locations* changed with progress. A change of read addresses, instruction paths or signed-zero raw bits is not an animation.
- The 128-byte vicinity is a **diagnostic window**, not a complete proof of stream absence. The structural candidate header's animation pointer may not be the active player's animation owner; it may reference another table.
- **Next task is now precise:** recover Object.graphics_1 / actual AnimatedSkeleton.animation from active player Object/overlay dispatch in original game, and compare that address with the static guessed candidate pointers before changing pose decoding. The original F3DEX geometry/rig import does not need repeating.

## Product state

| Area | What is implemented and proven | What is NOT proven / not done |
| --- | --- | --- |
| Original movement physics | Original Goemon horizontal controls, heading, jump/gravity and bounded trace comparisons were investigated; source-specific C++ tests exist. Ship controller ghost / prototype actor and basic reference character steering have compiled. | Complete seamless playable controller parity in all OoT scenes, camera/collision correctness, quest integration, all four original abilities. Do not re-invest time debugging the old cyan ball. |
| Reference models / source geometry | Source-aligned original ROM meshes, parts and structural GOSKEL01 rigs, with four characters and native geometry preview in a Windows Ship build. | Authentic complete rendering material/texture rig, all missing bodypart meshes, all original animation playing in game, verified source root skeleton owner. |
| Original MIPS executor | Executes N64 matrix evaluator func_800192D0 at 0x800192D0. Correctly separate current MtxF from D_80168530 destination. 64-byte matrix pushes ordinarily; two Sasuke cases 128-byte pushes. 71 source bones and 142 MtxF evaluations for two controlled samples were completed. | Authentic active player Object/AnimatedSkeleton/overlay configuration and full renderer object-transition, 0x4000 stack-pop semantics. |
| Binary integration | GOSKEL01 source geometry and GOMIPS01 C++ reader and source vertex preview; private original.goskel + isolated.gomips staged into separate Goemon Test installation. Ship compiled and installed with opt-in preview. | Native game animation is not visually confirmed. The preview is not a real running/jumping animation, even though it compiles and draws source geometry. |
| Original animation | Code paths for original animated 0x60000000 player graphics, Object.graphics_1, animation_progress and D_80168520 identified in public Goemon64Recomp patches/anime.c. Original MIPS executor reads original source-bank data for some numeric-channel test cases. | Live animated player ownership, clip/action table, correct original animation key decoding/time base, numerically moving source vertices. |
| Abilities / Randomizer | Mapping/intent in docs/goemon/GOEMON_ZELDA_ABILITY_MAPPING.md. | Gameplay and Randomizer completion; not currently implemented. |

## Crucial disproven claims

- **“69 animation descriptors changing”: FALSE.** On 2026-11-08 exact numeric comparison canonicalizing IEEE signed-zero, all 371 structural candidates yielded **ZERO** numerically changing source matrices at artificial source animation progress 0,1,4. Split: Goemon 0/89, Ebisumaru 0/81, Sasuke 0/83, Yae 0/118.
- **“3 Goemon / 3 Ebisumaru / 2 Sasuke / 8 Yae bodyparts animate”: FALSE AS ANIMATION CLAIM.** Earlier raw matrix bit differences were signed-zero artifacts, not actual floating-point movement. Numeric transformed vertex hashes are identical at controlled 0 vs 4 in both tested matrix conventions.
- **“142 MIPS matrices pass”: TRUE AS EXECUTION/PACKAGING.** It is NOT proof of authored motion. Original MIPS machine instructions run and return, but current object context doesn't activate actual movement.
- The four “best animated” descriptor headers 0x07014F30, 0x07001CF8, 0x070105B0, 0x07023F60 are only structural/geometry-compatible candidates, **not confirmed action owners**.
- The source-bank read counter uses an approximate region boundary (animation pointer through earliest skeleton pointer). **It is NOT exact proof that a particular live animation keyframe was used.** Further memory provenance and actual object pointer resolution required.

## Evidence index

- Original ROM extraction / native rig + source owner tests: [run 42368756132](https://github.com/Chakratos/Shipwright/actions/runs/42368756132).
- Original C++ native source-rig reading and offline geometry pairing: [run 42396694311](https://github.com/Chakratos/Shipwright/actions/runs/42396694311).
- First successful full Windows Ship source-geometry preview build and copy into isolated Test installation: [run 42396981715](https://github.com/Chakratos/Shipwright/actions/runs/42396981715).
- Four original source graphics from owner ROM in native renderer (not visible animation): [run 42397502772](https://github.com/Chakratos/Shipwright/actions/runs/42397502772).
- Source MIPS destination fixes; full original MIPS matrices valid: [run 42398554677](https://github.com/Chakratos/Shipwright/actions/runs/42398554677).
- Original MIPS source parent matrix/pointer experiments: [run 42472657686](https://github.com/Chakratos/Shipwright/actions/runs/42472657686).
- One CPU across full source Skeleton, 64 and 128 byte native pushes: [run 42473523620](https://github.com/Chakratos/Shipwright/actions/runs/42473523620).
- 0 vs 4 preview, native N64 vertices unchanged: [run 42473943648](https://github.com/Chakratos/Shipwright/actions/runs/42473943648).
- Definitive numeric signed-zero finding: [run 42474227448](https://github.com/Chakratos/Shipwright/actions/runs/42474227448).
- **Corrected 371-source descriptor sweep: zero numeric time-dependent poses**: [run 42474422364](https://github.com/Chakratos/Shipwright/actions/runs/42474422364).
- Source-bank read instrumentation: [run 42474726311](https://github.com/Chakratos/Shipwright/actions/runs/42474726311). First Goemon structural node: 0 candidate animation reads/12 skeleton reads. Other chosen nodes: Ebisumaru 13, Sasuke 14, Yae 14 *region-classified* source reads. This does not identify active live player action.

## Immediately relevant source

- tools/goemon/re/probe_original_mips_execution.py: artificially initializes candidate source skeleton MIPS globals.
- tools/goemon/re/original_mips_vm.py: bounded original N64 instruction interpreter, RDRAM source read counters.
- tools/goemon/re/sweep_original_mips_descriptors.py: source-skeleton progress scan; compares numerical zero-normalized hashes.
- tools/goemon/re/original_continuous_mips_skeleton.py: one-CPU source graph stack experiment with dynamic push width; does not replicate original object transitions.
- tools/goemon/re/export_original_continuous_mips_preview.py and package_original_mips_samples.py: controlled 0 and 4 previews (not live action clips).
- soh/soh/Enhancements/Goemon/OriginalReferenceCharacterActor.cpp and OriginalIsolatedMipsPreview.hpp: source-geometry native preview.
- docs/goemon/ORIGINAL_ANIMATION_ENGINEERING_HANDOFF_2026-11-07.md: detailed historical source comments plus corrections. Read last, not first.

## Last confirmed gate and next step

**Gate G1: find a real current player AnimatedSkeleton owner and correctly dereferenced animation stream. OPEN.** Current source bank guesses may not be an active animation. The renderer resolves Object.graphics_1 through overlay_info to AnimatedSkeleton, then AnimatedSkeleton.animation to D_80168520. Need to instrument a valid object/action or resolve runtime dispatch in original decompressed game to demonstrate nonzero numerical MtxF changes.

**No newer verified native gameplay build.** Any future agent should check Actions and git HEAD for newer evidence. Historical status should never override this file.
