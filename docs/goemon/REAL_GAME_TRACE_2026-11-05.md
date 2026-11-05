# Real Goemon original-game telemetry — 2026-11-05

Source: the user-supplied `run-20261105-111710.zip` recorded through
**Goemon Original Reference Trace v0.2** from a genuine Goemon64Recompiled
playthrough. This report contains derived measurements and counts **only**:
no ROM, character data, textures or raw game code.

The submitted ZIP SHA-256 is
`217ba7270a97efe288f346b58511a2a873b8865c317f413f513aeef699e4fe23`.

## Capture validation

- **1,691** sequential `GOEMON_REF` and `GOEMON_TICK` records.
- **128** `GOEMON_MEM` snapshots, each **448 bytes**, spread over the first
  1,024 recording frames. All six automated parsers exited successfully.
- Original game trace emitted `GOEMON_TRACE_ARMED`,
  `GOEMON_TRACE_BEGIN`, and `GOEMON_TRACE_END,1691,128,manual_stop`.
- **26** distinct numerical `action_id` values.
- **9 actual character-ID changes** across **10 contiguous character segments**.
  The original `PlayerTask.character_id` and global selected-character ID
  matched in **all 1,691 records**.
- One approximately **1,565 game-frame gap** in the original
  `frames_elapsed` counter between samples 1530 and 1531, together with
  a large position and altitude change. Never compute speed across this gap.
  It is a discontinuity, not an observed movement trajectory.

| Original character ID | Captured updates | Distinct action IDs | 448-byte Player snapshots |
|---|---:|---:|---:|
| 0 | 493 | 16 | 34 |
| 1 | 349 | 14 | 40 |
| 2 | 254 | 13 | 28 |
| 3 | 595 | 16 | 26 |

The recording is a valid **four-character gameplay trace**, not a
single-character capture with corrupted IDs. The player deliberately changed
characters and used multiple weapons. Weapon identity and equipment state
are **not directly decoded** by trace v0.2.

## Verified inputs and original action-state transitions

`0x0004` was associated with **every actual change** in the
character-ID field. All nine character-switch transitions entered
`action_id=186` for exactly **28 consecutive recording updates** and
then returned to `0`. Some extra `0x0004` presses occurred during the
existing switch action and did not produce an additional switch.

`0x8000` (N64 A button) triggered five fully observed start events.
Across all five, the first three contiguous phases were the same:

| Phase | Original action ID | Duration, updates |
|---|---:|---:|
| First phase | 23 | 7 |
| Second phase | 25 | 7 |
| Third phase | 26 | 5 |
| Final / landing phase | 28 | Variable |

These are **empirical state durations**, not reconstructed jump heights,
acceleration or gravity. The last phase can be interrupted by other actions.

`0x4000` (N64 B button) triggered several different attack paths:

- Character 0: `112 → 113 → 114 → 0`, also `124 → 0`;
  the common `88 → 89 → 90 → 93 → 0` path also appeared.
- Character 1: distinctive `140`, and `88 → 91 → 0`
  or `88 → 89 → 92 → 0`.
- Character 2: distinctive `144 → 0`; common 88/89/90/93
  states also present.
- Character 3: distinctive `162 → 163 → 0`; common
  88/89/90/93 states also present.

The weapon names or exact input/equipment conditions for those paths
are **not proven**. The long `162` segment lasted **190 updates**
before `163` appeared for **13 updates**. It was followed by a
large scene/timing discontinuity; do not interpret the 190 updates as
an intrinsic attack duration until a controlled trial.

## Original horizontal movement calibration

Take the Euclidean horizontal displacement of **the observed root object**
between consecutive rows only when (a) both rows belong to the same
character, (b) `game_frames` increases by exactly one, and
(c) the displacement is under 20 world units to exclude scene teleports.

In this capture:

| Character ID | Moving intervals | Intervals at 2.80 ± 0.005 | Largest continuous-update horizontal displacement |
|---|---:|---:|---:|
| 0 | 50 | 36 | 2.80 |
| 1 | 103 | 84 | 2.80 |
| 2 | 82 | 57 | 2.80 |
| 3 | 87 | 60 | 2.80 |
| **Total** | **322** | **237** | **2.80** |

The value **2.80 original world units per captured game update**
is an independently observed, shared maximum on the tested traversals.
During clearly identifiable starts from rest, the first displacements
include **0.84, 1.38, 1.92, 2.46, 2.80**, consistent with successive
increases of approximately **0.54** until clamping.
This is **empirical calibration**, not proof of the exact underlying
physics equations or all possible speed modifiers.

The renderer hook is known, but it has not been identified with the
authoritative original movement simulation tick. No exact world-units/s
value is asserted from render timing.

## Why this capture does not yet prove original jumping physics

- The original root object's Y position was **-165.0** during the first
  **1,531** captured frames, **including observed jumps**. After the
  large discontinuity it was near **230–231**.
- `root_animation_progress` was identically **0.0** in all 1,691 records.
- Therefore the root alone is not an adequate source for jump height,
  vertical velocity, model animation progress or airborne collision.
- The old 128-snapshot cap stopped recording `Player` memory
  at about sample 1016, although character input/action data continued.
- The earlier `memory_candidates.py` output includes, for example,
  an unverified `Player+0x074` float correlated with root Z for
  character 2 (R² ~ 0.964). Correlation does **not** prove the field
  is authoritative position or velocity.

## Instrumentation update for the next controlled capture

The standalone diagnostic mod has been upgraded to **v0.3**:

1. Capture the full original **`PlayerTask` (0xF0 bytes) each update**,
   including previously unlabelled floats that may control velocity,
   airborne states and animation.
2. Sample the **distinct player-model `Object`** (position, rotation,
   animation progress), instead of relying only on the stable render root.
3. Preserve full `Player` memory at **every fourth update** over the
   entire run, with a higher storage budget (**3,072 snapshots**).
4. Expand the maximum recording to **12,000 updates**, still with the
   previous off-by-default manual start and stop in the mod menu.

Every original-data stream is **observational only**.
Existing `GOEMON_REF` / `GOEMON_MEM` records retain their parsing schema.

**Next development milestone:** use the new real-game PlayerTask and
animated-object samples to identify authentic vertical velocity,
gravity, ground-contact state, acceleration, and model animation state,
then map their call sites back to the original overlay. The full Ship
game port and playable character integration are **not yet done**.
