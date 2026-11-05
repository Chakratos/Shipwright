# Goemon64Recomp player memory reconnaissance

This is a **source-grounded map**, not a completed physics reverse engineering.
The names and offsets below refer to the 32-bit Nintendo 64 layout in the
Goemon64Recomp patch headers. Do not apply them as host C++ struct offsets.

## Verified symbols and layouts

Source:
- [`patches/variables.h`](https://github.com/klorfmorf/Goemon64Recomp/blob/dev/patches/variables.h)
- [`patches/types.h`](https://github.com/klorfmorf/Goemon64Recomp/blob/dev/patches/types.h)
- [`patches/functions.h`](https://github.com/klorfmorf/Goemon64Recomp/blob/dev/patches/functions.h)
- [`patches/anime.c`](https://github.com/klorfmorf/Goemon64Recomp/blob/dev/patches/anime.c)
- [`include/common.h`](https://github.com/klorfmorf/mnsg/blob/main/include/common.h)

| MIPS address / field | Known meaning | Limitation |
| --- | --- | --- |
| `0x801FC604` (`D_801FC604_5B8514`) | player 1 `PlayerTask*` | May be null during transitions |
| `0x801FC608` (`D_801FC608`) | player 2 `PlayerTask*` | Local-player semantics still need validation |
| `0x801FC614` (`D_801FC614_5B8524`) | player 1 root `Object*` | Graphics-object position may not equal authoritative physics position |
| `0x801FC618` (`D_801FC618_5B8528`) | player 2 root `Object*` | Same qualification |
| `0x8015C5DC` (`D_8015C5DC_15D1DC`) | global current character ID | Enum mapping needs independent verification |
| `0x80204020` (`D_80204020_5BFF30`) | four character-graphics file IDs | File IDs must be interpreted through ROM resource tables |
| `PlayerTask + 0x60` | `character_id` (u8) | Index mapping not yet verified |
| `PlayerTask + 0xCC` | `action_id` (u8) | Action enum meanings not recovered |
| `PlayerTask + 0x5C` | `Player*` | Currently **opaque** 0x1C0-byte record in `types.h` |
| `Object + 0x08` | position (Vec3f) | Rendering space / physics space must be established |
| `Object + 0x14` | rotation (Vec3s) | Rendering code masks angles to 10-bit values |
| `Object + 0x28` | animation progress (f32) | Animation tables and time base not yet decoded |

Additional recovered original-routine entry points:

- `func_801CB800_587710(PlayerTask*)`
- `func_801DAF54_596E64(PlayerTask*)`
- `func_801DC9C8_5988D8(PlayerTask*, u8 character_id)`
- `func_801DCA64_598974(PlayerTask*, u32, u8*)`

These signatures are taken from `patches/functions.h`. Their precise roles
are **not established** by the signatures alone. Do not label them movement
functions without investigating call sites.

The original controller input structure `CONTROLLER_W` in `mnsg/include/common.h`
includes `button_held_down`, `button_pressed`, `stick_raw_x`,
`stick_raw_y`, `stick_x`, `stick_y`, and `stick_magnitude`.
The Goemon game-system struct (`SYS_W`) contains `frames_elapsed`,
`retraces_per_game_step` and controller arrays. These provide candidate input
and time-base sampling sites.

## Immediate RE tasks

1. Pin the precise Goemon64Recomp commit and its matching decomp/symbol-map
   revision; record ROM revision. Do not assume future `dev` HEAD offsets
   remain valid.
2. Trace the writers of `PlayerTask.action_id`, character switching, and the
   `Player*` record, using original MIPS routines / recompilation output.
3. Determine which original game-update callback represents **one physics
   simulation tick**. An arbitrary render callback is insufficient for exact
   frame-by-frame comparison.
4. Resolve genuine player world position, grounded state, velocities and input
   state. Do not equate rendered `Object` transforms with collision state
   without cross-checking.
5. Capture per-character deterministic trials: acceleration/deceleration,
   idle, turning, walking, jumping, aerial actions, hitstun and ability usage.
6. Only after step 4 build a Goemon reference-trace exporter into the canonical
   fields expected by `tools/goemon/compare_traces.py`.

## Current evidence

The root-object and action-state pointers establish promising entry points,
but no original movement equations, animation timing constants, hitbox geometry
or ability logic have been recovered **yet**. Exact-feeling Goemon gameplay
cannot be claimed until those pieces are measured and ported.
