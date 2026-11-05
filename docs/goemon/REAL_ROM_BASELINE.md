# First validated original Goemon ROM baseline — 2026-11-05

These findings were independently checked using the user's **original NTSC-U
NG5E cartridge image** and the JSON reports from the first Windows collector
run. **Only metadata is committed here**: no original ROM bytes, model files,
audio, MIPS disassembly or copyrighted resource payloads.

## Genuine input verification

| Evidence | Value |
|---|---|
| Original N64 ROM | 16,777,216 bytes, N64 big-endian, NG5E |
| Original ROM SHA-1 | `df8083a54296b8c151917c5333e1c85f014a2a66` |
| Original ROM SHA-256 | `1603be37427a33548857fc3d2e8867ede71121c353fb631b79b44f1d94845d80` |
| Goemon64Recomp-format decompressed ROM | 33,554,432 bytes |
| Decompressed SHA-1 | `6ea0ed71032ce08fc2745f412d84936382197494` |
| Decompressed SHA-256 | `e40bee20508c2e29e651dca4e47504e40f908f0a2186e34a582784bf5a64be4c` |
| Original Goemon64Recomp source | `6661abc439327b9ed9e235c391720f9034f61a78` |
| Symbols | `49f4e3269f05c737cb4bf698b9ef7142c92f1ac7` |
| Collector base commit | `f0224ecd96c8334c79052f3e26d527ff34bb7805` |

Our independent decompression matched the uploaded collector report's full
SHA-256 **exactly**, not merely by filename or ROM header. The original and
decompressed SHA-1s also match the known Goemon64Recomp reference hashes.

## Original resource directory: verified and fixed

The original ROM's decompressed file table starts at `0x57FD8` and consists
of **overlapping adjacent 32-bit offsets** at a 4-byte stride.
Iteration terminates if *either* current or next entry is zero, exactly as in
`Goemon64Recomp/src/game/rom_decompression.cpp`.

Measured on the genuine ROM:

- **1,311** valid table entries; **227** of them are zero-length.
- The sentinel following the final entry is one zero word, **not** an
  all-zero two-word pair.
- The former `character_assets.py` parser required both words to be zero,
  wrongly interpreting the sentinel as file 1311. This caused the collector
  to fail. Fixed in commit `f8d7befd8a85257506be80fcabbbb92eada9a056`.
- An independent, source-free regression now reproduces the 1,311-entry
  table and one-word sentinel without embedding any ROM data.

The character graphics ID table at ROM offset `0x5BFF30` yields:

| Original character slot | Resource file ID | Decompressed ROM offset | Size |
|---|---:|---:|---:|
| 0 | 288 | `0xE2AE80` | 61,440 bytes |
| 1 | 292 | `0xE72890` | 28,672 bytes |
| 2 | 296 | `0xEB41A0` | 53,248 bytes |
| 3 | 300 | `0xF04C60` | 53,248 bytes |

Adjacent files **289, 293, 297 and 301** start with the `PIC0000`
signature; other neighboring files contain data from the same four-file
groups. This is useful to focus resource-format reverse engineering, but
it does **not** yet prove which graphics slot corresponds to Goemon,
Ebisumaru, Sasuke or Yae, or how the assets are split into textures,
geometry and animation.

**No original resource bytes are checked in.**

## Real ROM Player overlay scan

The first `tools/goemon/re/scan_player.py` report observed:

| Quantity | Result |
|---|---:|
| Functions scanned in `.file_11` | 906 |
| Functions with a recognized original-player access or anchor call | 23 |
| Candidate original-player global references in callgraph scan | 63 |

The most actionable, **confirmed-location** writes in that report:

| Original function | Referenced original `Player` offsets |
|---|---|
| `func_801F770C_5B361C` | `0x000`, `0x002`, `0x0A4` |
| `func_801F3C10_5AFB20` | `0x0B4` |
| `func_801F3B30_5AFA40` | `0x0B4` |
| `func_801D27A4_58E6B4` | `0x078` |

These are field write **locations**, not recovered movement semantics.
Their visible instructions include short/word stores, including stores of
zero. They are not yet evidence that these offsets hold position, speed,
gravity or jump state. The first ranking was intended to prioritize
inspection; **do not call these four functions the movement controller**.

One original function of particular interest for action-state analysis is
`func_801DAF54_596E64`, which accesses both `character_id` and
`action_id` on a known `PlayerTask*` argument. Its original direct caller
is `func_801DAD68_596C78`. Other observed links:

- `func_801CBC40_587B50`, `func_801E0944_59C854` and
  `func_801E0BF8_59CB08` call the two original character-handling
  routines `func_801DC9C8_5988D8` and `func_801DCA64_598974`.
- The scan is limited to confidently recognized accesses; indirect
  pointers and control-flow joins are not yet fully recovered.
- No original movement-physics update loop has been verified from these
  findings alone.

## Collector regression, then next source of evidence

The uploaded `run-_zj58ice.zip` reports **86 tests**, with
**81 passed, 2 failures, 3 errors**. All five are in
`test_character_assets.py` or `test_decompress_rom.py`, from the
wrong one-word file table termination. They are not five unrelated
original-game failures. The parser is fixed and the real ROM's four
character file ranges were independently validated; the complete
re-run of `tools/goemon/verify.py` after this fix is still required
before claiming an all-green full suite.

The next high-value evidence is **runtime**: record the actual Goemon
action transitions and raw original player memory during identical
controller-input trials. This identifies which of the unlabelled
`Player` fields are used as velocity, grounded state, collision,
animation or attack state.

Use the local Goemon64Recomp diagnostic probe from
[RE_TOOLCHAIN.md](RE_TOOLCHAIN.md). Keep all original ROM/graphics
data outside version control. No GitHub-hosted Actions jobs are required.
