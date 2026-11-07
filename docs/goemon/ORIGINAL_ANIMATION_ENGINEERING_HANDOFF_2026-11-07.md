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
