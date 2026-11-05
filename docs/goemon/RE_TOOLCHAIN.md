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
`soh/soh/Enhancements/Goemon/OriginalMemory.hpp`. This portable header
reads the documented N64 32-bit big-endian structures without reinterpreting
host memory or fabricating unknown physics fields. It currently exposes
PlayerTask character ID, action ID and pointers, plus Object position,
rotation, animation progress and graphics pointer.

```shell
# Test all Python tools and compile/run the native N64 memory-layout test:
python tools/goemon/verify.py --native
```

**Original MIPS inspection** from the pinned decompressed US ROM:

```shell
python tools/goemon/re/mips_inspect.py /path/to/mnsg.z64 \
    /path/to/Goemon64RecompSyms/mnsg.syms.toml \
    func_801DAF54_596E64 --output original_function.json
```

Decodes selected R4300i memory, control-flow and COP1 instructions, with
PC-addressed output and candidates for documented PlayerTask fields. Offset
matches are **not yet register-proven** and do not establish the full
physics-update function on their own.

**Original animated-rig capture**, obtained via the existing
Goemon64Recomp probe, emits `GOEMON_RIG` on original character/graphics
changes. It records original animation, skeleton and overlay pointers.

```shell
python tools/goemon/reference_probe/rig_manifest.py \
    goemon_runtime.log --output rig_manifest.json

# Decoder of known N64 AnimatedSkeleton/Skeleton layout at a verified offset:
python tools/goemon/re/skeleton_inspect.py \
    /private/local/character_file.bin --type animated --offset 0x100

# Resolve a captured segmented/direct pointer to the original graphic file:
python tools/goemon/re/resolve_rig.py \
    rig_manifest.json /private/local/character_file.bin \
    --character-id 0 --file-id 31 --output decoded_rig.json
```

The numeric IDs and offsets in these example commands are **illustrative**.
Use values actually recorded by the target Goemon instance; do not use
example values to claim asset parity.

`resolve_rig.py` compares raw runtime flags, animation pointers and
skeleton pointers with bytes from the extracted file. It supports the
original segment-8 address mode and direct addresses inside the recorded
overlay-zero allocation. Other overlay segments require additional captured
overlay mappings and are explicitly rejected, not silently guessed.

The actual Goemon skeleton traversal is now reconstructed from the
[original patched rendering routines](https://github.com/klorfmorf/Goemon64Recomp/blob/dev/patches/anime.c):
`offset_right` refers to a child bone and `offset_left` to a sibling,
both as signed relative offsets in 24-byte `Skeleton` records.

Use `--hierarchy` to include all reachable bones in the verified rig
manifest, preserving their original raw scale, rotation, translation and
display-list pointers:

```shell
python tools/goemon/re/resolve_rig.py \
    rig_manifest.json /private/local/character_file.bin \
    --character-id 0 --file-id 31 --hierarchy --output decoded_rig.json
```

Alternatively, when the original root Skeleton file offset is already
known, inspect it directly:

```shell
python tools/goemon/re/rig_hierarchy.py \
    /private/local/character_file.bin --root-offset 0x200 \
    --output original_bone_hierarchy.json
```

The example addresses and IDs are illustrative. The topology is derived
from original pointer arithmetic and cycle-checked, not rebuilt to fit
Link's skeleton. Animations, display-list geometry and textures still need
their own decoders and real ROM-based validation.

The resulting JSON is an original record decode. It is **not** yet a
renderable Zelda model: a converter for original display lists, texture data,
complete limb hierarchy and animation frame tables remains to be written.

### Locating original action-state writers and the simulation tick

The MIPS inspection now includes `proven_player_fields`. This field is
produced by bounded, straight-line provenance tracking: a known
`g_player_1_task` global is loaded into a register, then its known
`character_id` / `action_id` / player pointer fields are accessed through
that register. Branches and unknown register writes invalidate the proof.
The goal is to prioritize **original action writers** for decompilation.
Computed/indirect flows can still be missed.

The original Goemon-side diagnostic patch also emits `GOEMON_TICK` records
with `frames_elapsed`, `game_loops_count`, `retraces_per_game_step`,
and `retrace_count` from `SYS_W`. Analyze these locally:

```shell
python tools/goemon/reference_probe/tick_analysis.py \
    goemon_runtime.log --output original_tick_summary.json
```

This identifies repeated or discontinuous loop counts. It **does not**
establish the original physics tick until an update callsite is independently
confirmed in the ROM disassembly.

The test runner supports GCC/Clang and an MSVC `cl` installation exposed
in the Windows developer command prompt. Builds/tests occur exclusively
locally or on explicitly provisioned self-hosted computers; no hosted
GitHub Actions job is created.

## Overlay-wide player-state writer discovery

The new `scan_player.py` combines the pinned Goemon symbol map, actual
instructions from the original decompressed USA ROM, and conservative MIPS
register provenance tracking. It identifies:

- Original `PlayerTask.action_id` and `character_id` reads/writes.
- Loads of the opaque 0x1C0-byte `Player` record through
  `PlayerTask+0x5C`, followed by reads/writes of specific offsets.
- Four original functions with source-documented `PlayerTask*` as the first
  argument; in these functions, MIPS `$a0` is seeded as a known pointer.
- Direct `jal` calls to existing player-function anchors.

Use it on your **own pinned, decompressed Goemon US-ROM**:

```shell
python tools/goemon/re/scan_player.py \
    /path/to/Goemon64Recomp/mnsg.z64 \
    /path/to/Goemon64Recomp/Goemon64RecompSyms/mnsg.syms.toml \
    --top 100 --output /private/local/goemon_player_candidates.json
```

Input validation requires the N64 big-endian ROM signature and the specific
Goemon64Recomp decompressed ROM header CRC. The report includes ROM SHA-256
for reproducibility, raw original addresses and exact instruction offsets.
No original executable code is copied into the Git repository.

**Interpretation:** Priority is based on *evidenced field writes*, not
invented movement names. A candidate containing `Player+0x010` does not
prove that offset represents velocity. An original function receiving a
`Player*` by an unrecognized call chain can be missed. All discovered
fields need follow-up static or live verification before porting.

## First original gameplay algorithm port

`soh/soh/Enhancements/Goemon/OriginalCollision.hpp` ports two actual
decompiled original Goemon collision queries from
[klorfmorf/mnsg `src/27FE0.c`](https://github.com/klorfmorf/mnsg/blob/main/src/27FE0.c):

- `func_80029E58_2AA58`: BSP point query with original per-tree
  scale-dependent bounding boxes and collision-plane distances.
- `func_8002A168_2AD68`: actor-oriented BSP query with its original
  **10.0f lower-Y reach** and unscaled geometry.

It parses original big-endian `COL_TREE` (18 bytes), `COL_NODE` (6 bytes)
and `COL_PLANE` (20 bytes) records, and retains original solid
`0x7FFF` versus empty `0` results. For malformed node indices, planes
or cycles, the native port throws instead of reproducing undefined original
memory access. The native regression test exercises both query variants,
next-tree chaining, and malformed-data handling:

```shell
python tools/goemon/verify.py --native
```

The extracted original collision logic is **not** the complete movement
controller, not yet wired to Zelda collision geometry, and not yet tested
against a real Goemon level. Floating-point bit-exactness also requires
comparison to original ROM results and matching compilation settings.

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

## New verified tooling (original gameplay and graphics, 2026-11-05)

Two user-run Windows Goemon64Recompiled captures have succeeded, including
a **2,375-update** four-character session with full original PlayerTask,
model Object and raw Player memory. The current Windows pipeline uses the
standalone v0.3 NRM mod described in [TRACE_MOD.md](TRACE_MOD.md);
the earlier source-patching probe is retained only for reference.

The full-vector controller now reproduces **261/261** source-observed
ground/air/braking-related movement transitions to 0.012 world units.
The exact vector equation clamps the result **after** combining old
velocity and target-direction impulse, explaining the previously
unresolved frame 36 sharp-turn speed dip. See
[ORIGINAL_VECTOR_STEERING_2026-11-05.md](ORIGINAL_VECTOR_STEERING_2026-11-05.md).

New live Ship world observation: the opt-in `Goemon.ZeldaWorldProbe`
setting makes `ZeldaWorldProbe.cpp` query the actual Ship Zelda wall
and floor collision structures, without modifying Link. It is
**not** a playable Goemon or a complete collision solver; see
[SHIP_WORLD_PROBE_2026-11-05.md](SHIP_WORLD_PROBE_2026-11-05.md).

New metadata-only genuine-character PIC0000 catalog:

```powershell
py -3 tools\goemon\re\pic0000_catalog.py "C:\Pfad\Goemon.z64" --all --output "C:\Pfad\pic_catalog.json"
```

It directly accepts the original owned 16 MiB US ROM, decompresses
it in memory and catalogs **1,810** aligned picture records in **31**
source files (45 next to the four character root IDs), without
writing textures, ROM bytes or other copyrighted assets.
[ORIGINAL_PIC0000_2026-11-05.md](ORIGINAL_PIC0000_2026-11-05.md).

To reprocess an existing game run without replaying:

```powershell
py -3 tools\goemon\diagnostic_mod\reprocess_log.py
```

The updated native tests include the exact sharp-turn vector, a
full-speed steering hand-off, and the abstract world-geometry probe.
**Full Ship Windows build and in-game execution of the new Zelda
collision hook are still pending verification.**
