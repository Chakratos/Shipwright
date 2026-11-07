# Original Goemon animation port — engineering handoff (2026-11-07)

Branch: `feature/goemon-original-controller` in `Chakratos/Shipwright`.

This document defines the **verified data path** and its blockers. The goal
is actual animated **Goemon / Ebisumaru / Sasuke / Yae** as distinct original
characters within Ship of Harkinian, not a Link skeleton skin, static model
swap, synthetic sway, or debug ball. The user's Archipelago installation
at `C:\Users\Chakratos\Desktop\SoH AP` is never to be modified.

## Source of truth

- Original NG5E N64 ROM exists privately on user's Windows runner; ROM
  SHA-256 is validated by `tools/goemon/real_rom_check.py`.
- Public decomp `klorfmorf/mnsg` supplies source-aligned file table and
  decompressed ROM layout; its `config/usa/splat.yaml` uses file labels
  **one higher** than the ROM's own file-table index.
- Public recomp `klorfmorf/Goemon64Recomp`, especially
  `patches/anime.c` and `patches/types.h`, supplies source-authored
  player skeleton traversal and structure definitions.
- The actual MIPS matrix evaluator is
  `func_800192D0_19ED0`, 245 instructions, PC `0x800192D0`,
  decompressed ROM file `0x19ED0..0x1A2A4`. This was not decompiled
  into C in the public sources; a correct reconstruction requires those
  exact original instructions, which are only accessible on the private
  runner after it is online.

### Recomp facts — player and actor are NOT identical

See `Goemon64Recomp/patches/anime.c`:

- Player render branch is `func_80016C44_17844`,
  `case 0x60000000`. It uses `AnimatedSkeleton.flags`,
  `AnimatedSkeleton.animation`, and the first skeleton root.
- The player `animation_progress` lives in an `Object`;
  the original evaluator receives `func_800192D0_19ED0(skeleton, object)`.
  Original globals include `D_80168520` (resolved animation data),
  `D_80168510` (time/progress) and `D_801684B0` (render matrix).
- `func_80018CA0_198A0` traverses the player skeleton. Its
  `offset_right` and `offset_left` are *relative 24-byte node* links
  whose actual draw and object-transition behavior involves
  `func_80018F3C_19B3C` and `func_8001904C_19C4C`.
  They must not automatically be treated as a conventional engine-neutral
  child/sibling skeleton when animation ownership is unresolved.
- A `rotation` field bit `0x4000` controls matrix-stack popping in the
  original renderer. The raw 16-bit words are therefore more than
  unqualified Euler rotations.
- The earlier 261 ROM-scanned skeleton structures are structural
  **candidates**, not 261 verified animations, poses or chronological
  keyframes. Source words include `0xB000` / `0xB100`; passing these
  unmodified to `Matrix_Rotate` would be wrong.

## Source asset mapping

Goemon / Ebisumaru / Sasuke source character groups have validated
`0x07` and `0x09` resource segments. Yae has a source `0x07`
bank and a small `0x08` file, and her source `0x09` graphic bank
ownership remains unresolved. The ROM cannot be represented by simply
assuming `file ID == splat file label`.

The previous offline N64 graphics work has 81 structurally executable
Skeleton-owned display-list addresses, including 63 with confirmed
F3DEX-to-mesh associations. These are **geometry bindings only**,
not proof of player animation progress.

## Implemented, tested binary pipeline

| Component | Purpose | Validated? |
|---|---|---|
| `decode_original_limb_meshes.py` | F3DEX nested calls to separate per-limb triangle meshes | Synthetic Python |
| `package_original_rig.py` | `GOSKEL01` original triangles + encoded Skeleton fields | Synthetic Python |
| `OriginalSourceRig.hpp` | C++20 binary reader for `GOSKEL01` | Hosted native C++20 |
| `archive_original_animation_streams.py` | `GOANIM01` raw animation data and channel words | Synthetic Python |
| `OriginalAnimationStreams.hpp` | C++20 `GOANIM01` reader, marker classification | Hosted native C++20 |
| `disasm_original_animation_mips.py` | Decode original source 245-instruction evaluator locally | Synthetic Python; real ROM pending |
| `original_mips_animation_flow.py` | Branch/delay-slot CFG + direct animation-global references | Hosted Python |
| `OriginalPoseArchive.hpp` | `GOPA0001` actual original-frame 4×4 matrices | Hosted native C++20 |
| `OriginalArticulatedFrame.hpp` | Source N64 mesh + exact-game matrix → separate transformed limbs | Hosted native C++20 |

The **cross-language end-to-end test** builds two synthetic source N64
limb meshes and **two consecutive game-tick matrix frames** in Python,
writes authentic-format `.goskel` and `.gopa` files, parses them via
the C++ readers, and proves that the two limbs animate independently
with strict tick/action matching. The test input contains no ROM assets.

`OriginalSourceRig.hpp` explicitly no longer has arbitrary time-based
pose cycling. Grouping identical source Skeleton layouts does not
establish an animation, clip owner, frame duration or action.

### Explicit runtime gate

The in-game original-character renderer remains a static external
N64-looking OBJ/PNG reference mesh with a guarded original movement
pilot. **No original source-character bone animation is in Ship yet.**
The actual N64 animation channel decoder must be reconstructed from
MIPS first. Do not suggest synthetic moving limbs as its substitute.
Source game matrices must be accompanied by an experimentally confirmed
memory convention before in-game display; both row and column layouts
are supported and tested, but neither is automatically inferred.

## Private Windows runner — queued work

One explicit final batch commit containing these literal markers
runs three independent source-ROM jobs when the private runner is online:

- `[goemon-rig-limbs]`: validate genuine ROM Skeleton-linked F3DEX
  mesh extraction. Local output:
  `C:\actions-runner-goemon\original-rig-limbs`.
- `[goemon-animation-codec]`: disassemble original evaluator,
  generate MIPS CFG/direct-global report and extract raw compressed
  animation data. Local output:
  `C:\actions-runner-goemon\original-animation-mips` and
  `C:\actions-runner-goemon\original-animation-streams`.
- `[goemon-rig-package]`: package `GOSKEL01` limb archives.
  Local output:
  `C:\actions-runner-goemon\original-rom-rigs`.
  When possible, stage `.goskel` and `.goanim` files locally under
  `C:\Users\Chakratos\Desktop\SoH Goemon Test\character-original`.

The source runner workflow has `always()` on independent extraction
jobs so a failed limb-decoder experiment cannot suppress MIPS analysis.
Failed steps still fail the overall run. **Never** upload ROM assets,
object geometry, textures or MIPS disassembly to GitHub. Do not overwrite
`C:\Users\Chakratos\Desktop\SoH AP`.

## Next critical engineering decisions

1. After Windows runner is online, inspect the private
   `original_mips_animation_flow.json`, `func_800192D0_19ED0.txt` and
   `channel_metadata.json`. Identify the real memory reads and helper
   call targets; derive channel decoding, flags, interpolation/time units.
   Keep the machine code/disassembly local, and commit only the resulting
   original algorithm **implementation**, not code bytes or raw ROM data.
2. Verify source pointer graph against original player `0x60000000`
   renderer, not the more permissive generic Actor parser. Reject
   unproven structural candidates from final playback.
3. Convert validated per-frame transforms (correct matrix convention)
   and F3DEX meshes into the existing `OriginalArticulatedFrame`
   pipeline; add real Ship draw batches with original material/texture
   binding. No approximate pose sequences or time rates.
4. Integrate run/jump/attack/idle action selection from real original
   game logic, then individual Goemon/Ebisu/Sasuke/Yae abilities.
5. Build and test Ship on private Windows runner; compare in-game poses
   with original screenshots/behavior, not synthetic numbers.

**Immediate user involvement required:** none. The original ROM is already
on the Windows runner, and GitHub-hosted synthetic tests work without it.


## Verified continuation — 7 November 2026, after runner resumed

The previous chat was exported and the user requested development to resume.
Two commits were completed directly on this branch:

- `5a81768`: preserve disassembly when a target overlaps a MIPS delay
  slot; filter out non-`0x07` skeleton header candidates instead of
  asserting they belong to the source player; block stale test-deployment
  if source-ROM jobs fail.
- `0dcb450`: instruction-entry CFG with delayed transfers modelled
  atomically and conservative branch-likely annulment; preserve explicit
  CFG ambiguity rather than inventing false basic blocks.

These changes passed the hosted portable tests and private Windows
ROM analyses (runs `42368756132` and `42369022592`). No full
Ship Windows build was triggered.

### Exact verified original-ROM results

| Character | Player-resource candidate descriptors | Decoded source meshes in packaged rig | Triangles | Raw candidate animation bytes |
| --- | ---: | ---: | ---: | ---: |
| Goemon | 89 | 12 | 330 | 121,300 |
| Ebisumaru | 81 | 14 | 430 | 121,120 |
| Sasuke | 83 | 15 | 386 | 134,516 |

Total: 253 **structural candidate descriptors** (NOT confirmed
keyframes), 41 packaged limb mesh roots, 1,146 triangles and
376,936 raw candidate stream bytes. The script excluded 7 Ebisumaru
and 1 Sasuke structural records from segment `0x09` because those
must not be serialized as segment-`0x07` player headers.

All six `original.goskel`/`original.goanim` assets are staged
in `C:\Users\Chakratos\Desktop\SoH Goemon Test\character-original`.
No copyrighted source assets were uploaded.

### MIPS decoder details now verified against actual private ROM

- Matrix evaluator: 245 original MIPS instructions.
- Instruction-entry reachability: 193 entries.
- One branch-target/delay-slot overlap:
  transfer at `0x80019508` branches to `0x80019514`, which is
  independently the delay slot belonging to `0x80019510`.
  No reachable nested branch-in-delay was detected.
- The older simple basic-block graph is still flagged **unverified**;
  the newer instruction-entry report is the viable analysis path.
- Identified JAL targets: `0x80019ED8`, `0x8001F5F8`,
  `0x8001F2D8`, `0x8001E634`, `0x80043D10`.
  Their math/codec semantics are NOT yet decoded.
- Original frame timing, channel math, interpolation, active player
  clip ownership, rendering matrices and Yae's graphics bank remain
  unresolved. Raw stream archives are not playable animations.

### Next focused implementation

1. Establish which original call targets evaluate channel samples versus
   3D matrix transforms, using ROM-local analysis and public Recomp calls.
2. Resolve original `0xB000`/`0xB100` encoded S/R/T channels
   against the source animation data with real animation-progress values.
3. Only when verified, bake original tick-specific pose matrices into
   `GOPA0001` and feed `OriginalArticulatedFrame.hpp`.
4. Then integrate actual articulated batches into Ship and perform one
   full Windows build plus an in-game check. Do not use synthetic
   animation or claim original playback before validation.

This handoff is checked into source to make another chat interruption
recoverable. The existing Archipelago installation must stay untouched.


### Additional ROM reference scans — verified negative result

Runs `42369208597` and `42369357583` passed. The 253 structural
Skeleton candidates had **zero** references across all three characters
from both (a) aligned literal 32-bit `0x07xxxxxx` / `0x67xxxxxx`
source pointers and (b) conservative MIPS `LUI` + `ORI/ADDIU`
pointer construction scans.

This is a negative finding **for those two detection strategies only**:
the original game can compute overlay offsets dynamically, and the
scan has not identified player `Object.graphics_1` initialization.
It does not prove the candidates are unused, nor can they be called
verified animation clips.

Prioritize tracing actual player `Object.graphics_1` / overlay
relocation and `AnimatedSkeleton.animation` from
`Goemon64Recomp/patches/anime.c` before assigning any source
descriptors to active Goemon actions. In-game true original animation
remains blocked on verified channel decoding and player rig ownership.


## Source-ROM four-character asset milestone — 2026-11-07 16:10 CET

The current branch continued after the previous handoff. The owner has
not been asked to manually launch the original game, capture animation
frames, upload ROM bytes, or download GitHub build artifacts. Full Ship
builds were **not** triggered in this batch; portable and Windows native
tests plus ROM-derived offline jobs were used.

### Authentic Yae source resolution

The previous Yae bank-search implementation was wrong to reject her
0x29xxxxxx Skeleton Gfx words as addresses in nonexistent segment 0x29.
The original Recomp player renderer masks display-list source pointers
with `0x8FFFFFFF`, so `0x29xxxxxx` resolves to `0x09xxxxxx`.
An independent read of Yae's authentic source-`0x07` bank found
**118** traversable source-Skeleton candidate headers, with raw Gfx
pointer segment frequencies 0x09=2044, 0x29=236, 0x0F=52 across candidate
nodes. These are aggregate references, not distinct meshes.

Execution of all **40 distinct masked Yae display-list roots** with
the original F3DEX decoder established a unique geometrically complete
source-`0x09` candidate: decompressed runtime file **299**, the bank
also used by Sasuke. All **40/40** roots yielded real N64 geometry,
**901 triangles**, zero invalid display-list roots. Alternative 0x09
banks 291 and 295 yielded 14 and 22 decoded roots respectively.
This is strong *geometric* evidence of reuse; runtime overlay residency
and player animation ownership have **not** been independently established.

The unrecognized original `0x0F` Gfx words are retained in raw rig
descriptors and channel archives; do not coerce them to 0x09 or invent
geometry. This affects 52 aggregate Yae source records.

### Fully local original source assets

| Character | Original 0x07 candidate descriptors | Original .goskel mesh roots | Rig triangles | Raw .goanim bytes |
| --- | ---: | ---: | ---: | ---: |
| Goemon | 89 | 12 | 330 | 121,300 |
| Ebisumaru | 81 | 14 | 430 | 121,120 |
| Sasuke | 83 | 15 | 386 | 134,516 |
| Yae | 118 | 40 | 901 | 203,220 |
| Total | 371 | 81 | 2,047 | 580,156 |

The independent OBJ geometry-limb diagnostic export has 12 + 30 +
23 + 40 = **105** decoded source meshes; this is not the same
strictly-filtered set as the 81 meshes in the `.goskel` packages.

All eight `original.goskel` and `original.goanim` files are staged
on the owner's private Windows machine beneath:
`C:\Users\Chakratos\Desktop\SoH Goemon Test\character-original`.
Separate original source OBJ limb exports are in
`C:\actions-runner-goemon\original-rig-limbs` (including Yae).
No game ROM or original assets uploaded to GitHub.

### Verified binary linkage

A cross-archive pair validator now compares original header, flags,
bone ordering, parent, **raw original Gfx pointer**, and all nine
encoded S/R/T channel words from `GOSKEL01` and `GOANIM01`.
Result: **371/371 descriptors match exactly**, including all 118
Yae candidate headers, with 81 distinct linked source meshes.

Per-character source-linked mesh roots: Goemon 12, Ebisumaru 14,
Sasuke 15, Yae 40. Other normalized geometry roots still unresolved
from strict rigs: 6 Goemon, 5 Ebisumaru, 5 Sasuke, zero Yae.
The original 52 Yae `0x0F` source records remain unclassified.

Successful native test + source-ROM run:
`https://github.com/Chakratos/Shipwright/actions/runs/42384999730`.
Key implementation commits:
`a56e287` (Yae source-bank probe), `67ed0a4` (independent
0x07 scan), `00fae6f` (0x29 graphics-mask correction),
`4266eea` (Yae OBJ export), `c198451` (raw GOANIM01 Yae),
`21a2ca1` (Yae GOSKEL01), `c062a30` and `11d9c12`
(cross-archive validation and regression fix).

### Priority after this handoff

**STOP polishing geometry diagnostics unless blocking the original
animation output.** The data pipeline now supports all four figures.
Prioritize `func_800192D0_19ED0` and its MIPS helper call chain
(0x80019ED8, 0x8001F5F8, 0x8001F2D8, 0x8001E634, 0x80043D10).
Prove the math for `0xB000`/`0xB100` encoded channel selectors,
source animation progress, actual clip ownership and per-bone matrix
convention, then generate **real GOPA0001 animation frames** and connect
them to the in-game original articulated renderer.

Do not call structural candidates actual frames or infer timelines from
catalog order. No random motion, no fake animation, no Link-model swap
as the final result. The baseline external static models can remain only
until authentic per-limb rendering is validated.


## Native original MIPS animation execution milestone — 7 November 2026 (16:17 CET)

**Do not lose this recovery point.** The project has advanced beyond
disassembly / raw stream exports to ACTUALLY EXECUTING original
hash-verified NG5E ROM MIPS instructions, with big-endian RDRAM, real
MIPS branch-delay rules, integer arithmetic and COP1 single/double
precision. This is experimental isolated-rig execution, NOT established
real gameplay clip selection or complete in-game animation.

### Proven implementation

- Original CPU interpreter: tools/goemon/re/original_mips_vm.py
- Verified owner-ROM launch/context: tools/goemon/re/probe_original_mips_execution.py
- Local per-bone matrix batch: tools/goemon/re/export_original_mips_matrix_samples.py
- Synthetic portable tests: test_original_mips_vm.py and
  test_export_original_mips_matrix_samples.py
- Only tested source-ROM-derived original CPU code ever executes locally.
  No ROM bytes, disassembly, or raw matrix data committed/uploaded.
- The original renderer global at **0x80168530** was shown by true MIPS
  execution to be the source pointer passed in a0 to 0x80019ED8.
  Public Goemon64Recomp/patches/variables.h independently declares it
  as **MtxF *D_80168530_169130**. The controlled test context sets
  it to 0x801684B0 (the separately declared MtxF), without asserting
  that is exactly how the live original renderer initializes it.

### Confirmed original execution

Goemon's first static root completes the exact MIPS evaluator,
588 executed instructions / 422 distinct instruction addresses,
including original callee routines 0x80003F30, 0x80019ED8,
0x8001A8E4, 0x8001AABC, and 0x8001ADBC.

A source limb with six numeric animation selectors (Goemon original
pointer 0x070005DC) executes **968 instructions at progress=0** and
**990 at progress=1**; both resulting 4x4 MtxF outputs have 16 finite
float values and DIFFER. This demonstrates real time-dependent
source-original math under a controlled runtime context, without fake
interpolation or artificial bone motion.

The same MIPS run returns with 16 finite matrix fields for selected
limbs in Ebisumaru, Sasuke, and Yae; Goemon and Yae's selected
limbs differ between 0 and 1. Selecting a constant limb does not imply
its character has no animation.

### Private complete source-limb matrix batch

One source AnimatedSkeleton candidate per character; all its limb
pointers; original MIPS evaluated separately against controlled
animation_progress 0.0 and 1.0 using identity parent MtxF.
This is **NOT** the verified live game composite bone hierarchy.

| Character | Source candidate limbs | Different MtxF between progress 0/1 | Same MtxF | Blocked |
|---|---:|---:|---:|---:|
| Goemon | 14 | 4 | 10 | 0 |
| Ebisumaru | 15 | 3 | 12 | 0 |
| Sasuke | 18 | 5 | 11 | 2 |
| Yae | 20 | 6 | 14 | 0 |
| **Total** | **67** | **18** | **47** | **2** |

**132/134** individual source MIPS executions generated finite 4x4
matrices. Two Sasuke limb pointers **0x070005A8** and **0x070005C0**
remain blocked by a source-engine matrix-helper store at 0x8001F664
attempting RDRAM address 0x3F800000 under synthetic initialization.
Do NOT silently map that address as memory; track down the original
parent-matrix stack or object state and test the actual ABI.

Files are on the user's Windows PC at:

C:\actions-runner-goemon\original-mips-isolated-limb-matrices

Each original limb has a private, lossless IEEE-754 16-word matrix
at both controlled progress values. Individual local JSON files carry
explicit "action_id": null, "source_tick_mapping_verified": false,
"parent_world_composition_verified": false and
"engine_matrix_memory_layout_verified": false.

The final successful source-batch run was:
https://github.com/Chakratos/Shipwright/actions/runs/42390415262
and earlier:
https://github.com/Chakratos/Shipwright/actions/runs/42388995482
(full first real MIPS return), and:
https://github.com/Chakratos/Shipwright/actions/runs/42389891083
(first all-limb batch).

### Required next implementation — no diagnostic churn

1. Recover EXACT live renderer global 0x80168530 parent matrix-stack
   owner, initialize the real player Object context and resolve the two
   Sasuke nodes. The public Recomp declares MtxF*, which is hard evidence.
2. Validate source parent-child transform composition and original memory
   matrix convention on real player nodes. Avoid confusing isolated bone
   math with full world-space animated poses.
3. Prove owner of actual player AnimatedSkeleton and original action/tick
   timing; the 371 ROM descriptors are not confirmed clips or timeline.
4. Generate genuine GOPA0001 per-game-frame matrices only after those
   invariants are verified. Integrate GOSKEL source geometry with
   the original articulated renderer in Ship, and then run one isolated
   full Windows game build and compare in-game behavior.
5. Do not modify the separate SoH AP Archipelago installation or copy
   unverified animations into game runtime as if they were validated.

All tests up to this checkpoint passed. No full Ship build was run,
and no actual animation has yet been rendered inside Ship.


## Native source-MIPS original-rig rendering bridge — November 7, 2026

The current branch has advanced from isolated original MIPS calculations
to a source-only data bridge callable by the actual Ship rendering Actor.

- Python source tool: tools/goemon/re/package_original_mips_samples.py
  encodes GOMIPS01. It validates original source AnimatedSkeleton header,
  character, bone count/order, parent graph, original graphics pointer
  (including Yae 0x29/0x0F tags), and all nine original signed channel
  words against the private local GOSKEL01 archive.
- GOMIPS01 stores exactly two controlled original-CPU
  animation_progress inputs (0.0,1.0), not original gameplay ticks.
  A missing matrix is represented with an explicit unavailable bit,
  never an invented identity matrix.
- Native C++20 reader and isolated bone renderer:
  soh/soh/Enhancements/Goemon/OriginalIsolatedMipsPreview.hpp.
  Source N64 bodypart triangles are transformed using the original
  MIPS-evaluated 4x4 matrices, with an explicitly selected memory layout.
  Neither hierarchical world matrix stack nor real action timing is
  claimed to be established.
- Ship opt-in renderer: OriginalReferenceCharacterActor.cpp.
  Real bodypart mesh triangles render via the original character Actor;
  vertex colors come from original N64 vertices. Textures/UV materials
  and verified hierarchical composition remain upcoming work. The
  existing reference character path remains available as fallback
  when the experimental option is disabled.
- User-facing Dev Tools > Goemon controls:
  Goemon.UseOriginalMipsRigPreview (default off),
  Goemon.SourceMipsProgressSample (0 or 1; no fake looping),
  Goemon.SourceMipsMatrixLayout (row/column, both unverified).
- Original data remain on the owner's machine only:
  C:\actions-runner-goemon\original-source-mips-preview
  and in the isolated test installation:
  C:\Users\Chakratos\Desktop\SoH Goemon Test\character-original.
  Source preview load requires both original.goskel and isolated.gomips
  under each character subdirectory. The root can be overridden through
  GOEMON_ORIGINAL_CHARACTER_ASSETS.

Verified owner ROM package result:
Goemon 28/28, Ebisumaru 30/30, Sasuke 32/36, Yae 40/40.
Total 130/134 isolated original CPU matrix evaluations valid.
The earlier statement 132/134 was inaccurate: the two unhandled
Sasuke limbs fail at BOTH progress inputs (four matrices).
The precise original engine matrix-stack state is still needed for them.

Source package/test workflow succeeded on GitHub Actions
run 42396245338. Native C++ source geometry/preview test and
281/281 Python tests passed on run 42396694311.
No copyright-protected source files are uploaded.

The first full Ship integration build has now been intentionally
requested via [goemon-build] on this documentation commit, after
the separate native tests succeeded. This build has to verify the
actual game Actor source render integration. Before observing the
game visually, do NOT claim original gameplay animations function:
the preview only displays exact source-calculated isolated matrices,
not recovered action IDs or original timed clips. Link/OoT quest
integration remains incomplete. Never modify SoH AP/Archipelago.
