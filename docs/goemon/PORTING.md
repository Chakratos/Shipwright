# Mystical Ninja Starring Goemon — original-behavior port

## Non-negotiable target

Integrate **Goemon, Ebisumaru, Sasuke and Yae** from the Nintendo 64 game
*Mystical Ninja Starring Goemon* into the world and Randomizer of **Ship of
Harkinian**. Character movement, animation, combat, special abilities, audio,
scale and camera feel must originate in measured / reconstructed **Goemon**
behavior, not lookalike Zelda cheats or re-skinned Link animations.

This is temporarily developed in a Shipwright fork because the standalone
Asset Mod API cannot replace the player controller. Keep code confined to
`soh/soh/Enhancements/Goemon/` plus minimal, documented integration points
so the work can move to a standalone code mod when an appropriate API exists.

The Goemon ROM's original resources are **not committed** to this repository.
An eventual public distribution should obtain game assets from a user-supplied
source and distribute only original tools/patches. Do not check in extracted
ROM data.

## Source of truth

* [Goemon64Recomp](https://github.com/klorfmorf/Goemon64Recomp) — runnable
  original game behavior through N64 recompilation; original ROM and game
  runtime are necessary for authoritative behavior measurement.
* [Goemon64RecompSyms](https://github.com/klorfmorf/Goemon64RecompSyms) —
  address / function symbol maps used for analysis; pin a version matching the
  corresponding Goemon64Recomp revision before recording addresses.
* [mnsg decompilation](https://github.com/klorfmorf/mnsg) — partial recovered
  C source. **Not** a full C implementation of all four player controllers.
* [Shipwright](https://github.com/HarbourMasters/Shipwright) — target engine.
  Player logic is in `soh/src/overlays/actors/ovl_player_actor/z_player.c`.
  Hooks include `OnPlayerUpdate`, `VB_PLAYER_MODIFY_RUN_SPEED` and
  `VB_PLAYER_LIMIT_JUMP_SPEED`.

The first concrete original-game symbols and their unresolved semantics are\nlisted in [RE_SOURCE_MAP.md](RE_SOURCE_MAP.md).\n\nAn existing Ship of Harkinian `RocsFeather.cpp` / `MoonJump.cpp` illustrates
how player velocity is changed by hooks. **Those enhancements are not Goemon
reference behavior** and must never be used as a substitute for it.

## Fidelity pipeline

1. **Inventory the original**. Identify the MNSG player actor state, controller
   input handling, animation pointer selection, frame sequencing, physics,
   collision, attack shapes, inventory abilities, camera and character switch.
   Store original address and source revision for each identified routine.
2. **Capture ground-truth runs in Goemon64Recomp**. Use deterministic
   controller sequences, fixed simulation ticks, fixed level geometry, and
   produce synchronized traces of input and observed results. Do this for all
   four characters, each ability, and edge cases (airborne attacks, landing,
   ledge detection, water, damage, switching during animation).
3. **Extract original player resources**: hierarchy, bone indices, display
   lists, textures, animation frame tables, effects, and audio; verify actual
   animation lengths and skeleton transforms. Build a reproducible converter
   from a *locally provided* Goemon ROM.
4. **Port the Goemon state machines** to a self-contained controller runtime.
   Implement an adapter to Ship's actor, collision, camera, item and sound
   interfaces. Preserve measured movement and action timing; do not change
   input semantics to make it feel like Link.
5. **Run trace-based acceptance tests**, first on controlled flat geometry and
   then on representative Zelda scenes. Record / justify every adapter-level
   difference caused by Zelda collision or gameplay rules. Never declare
   'exact' parity from visual inspection alone.
6. **Integrate Zelda world interactions** (switches, NPC triggers, attacks,
   doors, ocarina warps) and Randomizer access logic. Original Goemon actions
   can unlock routes; the Randomizer must understand those reachable states.
7. **Package and maintain**: keep original controller code isolated, track
   upstream Shipwright updates, package game resources from users' own input,
   then evaluate migrating the same controller module to an upstream code-mod API.

## Implemented first: Ship trace capture

`soh/soh/Enhancements/Goemon/ReferenceTrace.cpp` registers a read-only
`OnPlayerUpdate` hook. It is **disabled by default**. Set the Ship CVar
`gSettings.Goemon.ShipTrace` (the expanded\n`CVAR_SETTING("Goemon.ShipTrace")`) to integer `1` in the running game
(configuration / developer tooling), then set it to `0` to close the trace.
It writes `goemon_ship_trace.csv` in Ship's current **working directory**.
The file is overwritten when each capture session starts. The hook does not
change the player, camera, input, physics, or Randomizer state.

One row represents one observed player update. Columns:

| Column group | Meaning |
| --- | --- |
| `frame`, `scene` | Sequential capture frame, current OoT scene |
| `buttons`, `stick_x`, `stick_y` | Physical Ship input sample |
| `pos_x/y/z`, `velocity_x/y/z` | Observed OoT player world position / velocity |
| `linear_velocity`, `yaw` | OoT running speed and signed 16-bit binary angle |
| `grounded`, `state_flags1/2` | OoT collision / player state diagnostics |

**Known limitations**: This currently records the *Zelda* player only. There
is no Goemon reference recorder or asset converter yet. The sample format is
not proof of parity by itself. Fixed-step timing, axis orientation and position
units must be calibrated between game engines before comparing traces.
Physical button masks also differ; map equivalent **actions** when producing
replay inputs instead of assuming equal raw button numbers.

## Exploratory Goemon64Recomp probe

The separate diagnostic source at
`tools/goemon/reference_probe/goemon_probe.c` reads **actual original-game**
character/action identifiers, controller values, root-object position and
animation progress. It is designed for a **separate local Goemon64Recomp**
checkout, not linked into Ship.

To install the additional Goemon-side capture with a reversible source edit:

```sh
python tools/goemon/reference_probe/install_probe.py /path/to/Goemon64Recomp
# Build and run that separate Goemon64Recomp checkout using its own instructions.
# Save the application console output as goemon_runtime.log.
python tools/goemon/reference_probe/log_to_csv.py goemon_runtime.log goemon_raw.csv
python tools/goemon/reference_probe/install_probe.py /path/to/Goemon64Recomp --remove
```

The installer changes only `patches/main.c` and adds
`patches/goemon_trace_probe.c` inside the supplied working copy. Its Makefile
already compiles patch sources by wildcard. There is no GH Actions workflow.

**Important**: the probe currently samples the *render callback* in
`main_initialize_display_lists`, not a proven physics-update callback. The
CSV is intentionally labeled `root_pos_*` and `root_rot_*`, not normalized
`pos_*` and `yaw`. The original renderer masks object rotations to 10-bit
values; those are NOT OoT 16-bit yaw units. This probe is for discovering the
original state machine and choosing the correct physics trace hook. It does
**not** demonstrate movement parity yet.

Run tooling tests locally without GitHub Actions:

```sh
python -m unittest discover -s tools/goemon/reference_probe/tests -v
```

## Comparison tool and validation

`tools/goemon/compare_traces.py` takes normalized per-frame reference and
candidate traces. Required CSV columns:
`frame,pos_x,pos_y,pos_z,yaw,grounded`.

* Frames must start at 0 and be continuous; both recordings must contain the
  same number of simulation ticks.
* Position differences are computed relative to each run's initial location;
  the user must explicitly provide any measured reference-to-Ship unit scale.
* Both sources must use the same X/Y/Z axis conventions and signed 16-bit
  binary-angle yaw representation. No unverified automatic coordinate
  conversion or scale fitting is applied.
* Reports maximum horizontal / vertical error, horizontal RMS, relative yaw
  error in degrees, and grounded-state disagreement.
* Zero is the default tolerance: acceptance criteria must be justified by
  original measurements and specified explicitly, not invented.

From the repository root:

```sh
python tools/goemon/verify.py
python -m unittest discover -s tools/goemon/tests -v
python tools/goemon/compare_traces.py goemon_trace_normalized.csv goemon_ship_trace.csv
```

The second command requires a genuine, aligned Goemon reference capture and
returns non-zero on missing source data or unacceptable error.

## Implementation status

- [x] Isolate project in feature branch and define original-fidelity contract.
- [x] Install read-only Zelda player instrumentation (off by default).
- [x] Add a frame-by-frame comparison tool and unit tests.
- [x] Identify initial original player task, action, root-object and input structures.
- [x] Add a reversible exploratory Goemon64Recomp render-state probe (not yet build-tested).
- [x] Add bounded raw Player memory capture and float-field correlation tooling.
- [x] Add numeric action-transition inventory from original Goemon runtime traces.
- [x] Implement an offline MIPS callsite/global-reference scanner for the decompressed ROM.
- [x] Implement four-character original graphics-resource identification and raw extraction.
- [x] Pin matching Goemon, decompilation, symbol and Ship source revisions.
- [x] Create local unit tests and a one-command test runner.
- [x] Decode selected original MIPS instructions (memory, branches, calls, COP1).
- [x] Track original MIPS register provenance from player globals into action/character field reads and writes.
- [x] Capture and analyze Goemon SYS_W frame/loop/retrace counters for update-loop identification.
- [x] Find original `COL_TREE` / `COL_NODE` / `COL_PLANE` collision code in the Goemon decompilation.
- [x] Port original scaled-point and actor BSP queries to standalone C++20, with native tests.
- [x] Scan original `.file_11` for writes to `PlayerTask` and the opaque `Player` record.
- [x] Seed proven MIPS `PlayerTask*` function arguments in four original entry points.
- [x] Decode original 24-byte Skeleton and variable-pointer AnimatedSkeleton records.
- [x] Capture original character rig / animation pointers when source character changes.
- [x] Resolve runtime segment-8/direct pointers against locally extracted original graphics files.
- [x] Implement byte-accurate original PlayerTask / Player / Object memory views in native C++20.
- [x] Compile and execute native C++20 unit checks and 19 new Python tests locally.
- [ ] Identify the actual Goemon physics tick and movement-state routines.
- [ ] Instrument the original Goemon runtime, obtain synchronized captures.
- [ ] Reconstruct and integrate the original character models and animations.
- [ ] Port authentic player controller and character switching.
- [ ] Port combat / abilities / Zelda interaction adapter.
- [ ] Update Randomizer reachability and item placement.
- [ ] Validate playable builds and automated tests.

## Build policy

No new GitHub Actions workflows. The fork inherits upstream workflows;
**do not trigger hosted CI** for this feature. Builds will be driven locally
or with an explicitly configured **self-hosted** runner once available.
The Ship CMake configuration uses `GLOB_RECURSE` for `soh/*.cpp`, so the
trace source is picked up without changing `z_player.c` or the CMake file.

**Current state:** Original memory views, a register-aware
original-game Player writer scanner, N64 skeleton/rig analysis, and two
source-derived Goemon collision BSP queries are implemented. The new ROM
scanner and collision port were locally exercised against synthetic data.
**No real game ROM was available for validation.** The Goemon diagnostic
patch and Ship executable have not been built against the complete game
sources. The full original Goemon player physics, models and animations are
**not yet ported**, and no playable Goemon character exists yet.
