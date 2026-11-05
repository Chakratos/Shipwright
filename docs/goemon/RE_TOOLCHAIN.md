# Goemon reverse-engineering toolchain

Everything in this folder is intended to run locally or on a **self-hosted**
computer. No GitHub Actions builds or workflow executions are required.

## Sources (pinned)

See `tools/goemon/re/source_revisions.json` for the exact source and
submodule commits. The reference version under analysis is Goemon64Recomp
`6661abc439327b9ed9e235c391720f9034f61a78`, with
Goemon64RecompSyms `49f4e3269f05c737cb4bf698b9ef7142c92f1ac7`
and decompilation submodule `be85f9018b1fb2ffa332270d6abfb9f8c3cae323`.
The Ship of Harkinian base commit is `d4bf6528a3bb242bc5d862e4f1ab2b6d385c157b`.

No ROMs, decompressed code or Konami game assets belong in this Git branch.

## Local tool tests (stdlib Python 3.11+)

From the Shipwright checkout:

```shell
python tools/goemon/verify.py
```

This discovers and runs all source-free test suites under `tools/goemon/`.
It does not build either game, launch ROMs or invoke Actions.

## Recover the original Goemon player function references

The original N64 player functions are not all available as high-level C source.
The original game overlay containing the known player entry points is
`.file_11`. The code is present in the user's **decompressed USA ROM**.

```shell
python tools/goemon/re/analyze_rom.py \
    /path/to/Goemon64Recomp/mnsg.z64 \
    /path/to/Goemon64Recomp/Goemon64RecompSyms/mnsg.syms.toml \
    --output original_player_calls.json
```

This maps MIPS `jal` callsites and searches for LUI+load/store references to
known player globals. The output identifies investigation targets and direct
callers of four symbols from the published headers.

It **does not** fully disassemble or decompile the game. In particular, it
misses indirect calls (`jalr`) and pointer arithmetic, and its global
reference findings must be checked in a disassembler.

Initial original function anchors (Goemon `.file_11`):

| Name | MIPS VRAM | Size (source symbol map) |
| --- | --- | --- |
| `func_801CB800_587710` | `0x801CB800` | `0x24` |
| `func_801DAF54_596E64` | `0x801DAF54` | `0x10C` |
| `func_801DC9C8_5988D8` | `0x801DC9C8` | `0x9C` |
| `func_801DCA64_598974` | `0x801DCA64` | `0x28C` |

The exact roles of these functions still require call-site analysis.

## Identify and extract the original character graphics resources

Goemon64Recomp's own `src/game/rom_decompression.cpp` uses file table
`0x57FD8` in the decompressed image. The original
`D_80204020_5BFF30[4]` table is at ROM offset `0x5BFF30`
(the offset follows from `.file_11` symbol mapping).

```shell
# Inspection only; writes no raw ROM assets
python tools/goemon/re/character_assets.py /path/to/Goemon64Recomp/mnsg.z64

# Explicit local extraction; raw binary files stay outside Git
python tools/goemon/re/character_assets.py /path/to/Goemon64Recomp/mnsg.z64 \
    --output-dir /private/local/goemon-original-assets \
    --manifest /private/local/goemon-asset-manifest.json
```

Output: four file slots with their original graphics-file IDs, lengths,
ROM offsets and SHA-256 checksums. `character_name` remains null until
a character-switching trace proves the four slot mappings. The extracted
binary files are **not yet decoded** into models, skeletons or textures.
An actual converter must be developed from the identified asset encoding.

## Discover game state and movement memory

The Goemon64Recomp patch-side `PlayerTask` structure contains:
- `PlayerTask + 0x60`: `character_id`
- `PlayerTask + 0xCC`: `action_id`
- `PlayerTask + 0x5C`: opaque `Player*` (0x1C0 bytes)
- `g_player_1_root_object`: render-object position, orientation, animation.

To sample the genuine running game, install the local diagnostic patch:

```shell
python tools/goemon/reference_probe/install_probe.py /path/to/Goemon64Recomp
```

Build and launch **that separate Goemon64Recomp checkout** with a verified
original US ROM, then save its console output into a local log. The additional
patch emits:
- `GOEMON_REF` for player action, stick/buttons and rendered root state.
- `GOEMON_MEM` for a throttled, bounded raw dump of the original 0x1C0-byte
  `Player` memory record, to recover still-unknown fields.

It samples up to 12,000 render callback records and up to 256 raw-memory
records (every fourth render callback); recording does not last forever.
The patch is NOT part of the Ship of Harkinian build.

Extract the action trace and investigate which unknown Float fields track
the root object's motion:

```shell
python tools/goemon/reference_probe/log_to_csv.py goemon_runtime.log goemon_raw.csv
python tools/goemon/reference_probe/memory_candidates.py goemon_runtime.log --min-r2 0.9
python tools/goemon/reference_probe/action_transitions.py goemon_raw.csv \
    --format dot --output original_action_graph.dot

# Revert the local diagnostic source additions to the separate Goemon checkout
python tools/goemon/reference_probe/install_probe.py /path/to/Goemon64Recomp --remove
```

The memory-correlation script searches aligned 32-bit float candidates in
both byte orders and reports correlations with rendered-object X/Y/Z. It
never automatically names a field `physics_position` or assumes coordinate
system equivalence. A high correlation is only a clue. Confirm any field by
following the original MIPS write/read sites and validating game behavior.

Action graphs use **numeric action IDs**, never guessed actions. To identify
one, replay the same controlled input sequence repeatedly, observe state
changes, then correlate with direct original-game function calls.

## Compare reconstructed movement

`soh/soh/Enhancements/Goemon/ReferenceTrace.cpp` writes a Ship sample trace
if CVar `gSettings.Goemon.ShipTrace` is enabled (off by default).

Only **after** the Goemon side has a physics-tick-aligned trace and a verified
coordinate-unit conversion, run:

```shell
python tools/goemon/compare_traces.py normalized_goemon_trace.csv \
    goemon_ship_trace.csv --reference-scale 1
```

This checks position, relative yaw, and grounded-state parity. It deliberately
rejects missing or mismatched frame sequences. The raw render-state logs are
**not** accepted as a physics parity reference until separately normalized.

## New original-code and animation tools

The following components have passed standalone unit tests with synthetic
original-format data. A real Goemon ROM capture is still needed.

**Native C++20 player structure views** are in
\`soh/soh/Enhancements/Goemon/OriginalMemory.hpp\`. This portable header
reads the documented N64 32-bit big-endian structures without reinterpreting
host memory or fabricating unknown physics fields. It currently exposes
PlayerTask character ID, action ID and pointers, plus Object position,
rotation, animation progress and graphics pointer.

\`\`\`shell
# Test all Python tools and compile/run the native N64 memory-layout test:
python tools/goemon/verify.py --native
\`\`\`

**Original MIPS inspection** from the pinned decompressed US ROM:

\`\`\`shell
python tools/goemon/re/mips_inspect.py /path/to/mnsg.z64 \
    /path/to/Goemon64RecompSyms/mnsg.syms.toml \
    func_801DAF54_596E64 --output original_function.json
\`\`\`

Decodes selected R4300i memory, control-flow and COP1 instructions, with
PC-addressed output and candidates for documented PlayerTask fields. Offset
matches are **not yet register-proven** and do not establish the full
physics-update function on their own.

**Original animated-rig capture**, obtained via the existing
Goemon64Recomp probe, emits \`GOEMON_RIG\` on original character/graphics
changes. It records original animation, skeleton and overlay pointers.

\`\`\`shell
python tools/goemon/reference_probe/rig_manifest.py \
    goemon_runtime.log --output rig_manifest.json

# Decoder of known N64 AnimatedSkeleton/Skeleton layout at a verified offset:
python tools/goemon/re/skeleton_inspect.py \
    /private/local/character_file.bin --type animated --offset 0x100

# Resolve a captured segmented/direct pointer to the original graphic file:
python tools/goemon/re/resolve_rig.py \
    rig_manifest.json /private/local/character_file.bin \
    --character-id 0 --file-id 31 --output decoded_rig.json
\`\`\`

The numeric IDs and offsets in these example commands are **illustrative**.
Use values actually recorded by the target Goemon instance; do not use
example values to claim asset parity.

\`resolve_rig.py\` compares raw runtime flags, animation pointers and
skeleton pointers with bytes from the extracted file. It supports the
original segment-8 address mode and direct addresses inside the recorded
overlay-zero allocation. Other overlay segments require additional captured
overlay mappings and are explicitly rejected, not silently guessed.

The resulting JSON is an original record decode. It is **not** yet a
renderable Zelda model: a converter for original display lists, texture data,
complete limb hierarchy and animation frame tables remains to be written.

## Next runtime-dependent work

1. Obtain the original Goemon physics/collision update loop from the pinned ROM.
2. Investigate calls to the four anchor functions and writers of action state.
3. Capture deterministic controller trials for each character and action.
4. Confirm which game-memory fields control world position, acceleration,
   velocity and grounded state.
5. Decode original graphics, skeleton and animation files from the extracted
   assets and provide a user-ROM-based conversion tool.
6. Integrate a standalone **original-behavior controller runtime** in the SoH
   enhancement folder, with only narrow hooks into Zelda collision/items.
7. Add tests against recorded ground truth, then Randomizer progression logic.

No substitute movement code should be accepted as original behavior.
