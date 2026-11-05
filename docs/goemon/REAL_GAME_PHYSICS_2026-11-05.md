# Original NG5E movement and jump physics — real trace v0.3

Captured with **Goemon Original Reference Trace 0.3** using the official
Goemon64Recompiled executable on Windows and a real NTSC-U ROM.

Submitted user file: `run-20261105-123100.zip`;
SHA-256:
`e37f13d3670a819bff61a33bb8cb50d45e614aa7ec763c13bb695c6eddbd91ab`.

No copyrighted game bytes or game assets are committed to Git.
All measurements below are derived from the real user capture;
replay/regression inputs use *only numeric observations*.

## Capture integrity

- **2,375** consecutive reference samples; **2,375** matching
  original PlayerTask (240-byte) and player-model Object records.
- **594** original Player (448-byte) snapshots, every fourth sample.
- **All four** character-ID values observed (0,1,2,3), with
  **7** real character switches, **8** contiguous character segments.
- **26** distinct original numerical action IDs.
- Raw original character IDs match their globally selected IDs
  for all 2,375 samples.
- The original log confirms manual arm, start, and stop:
  `GOEMON_TRACE_END,2375,594,manual_stop`.
- One original frame-counter discontinuity at sample **1849**
  (delta **1,441** frames) coincides with a scene/spatial transition.
  Never interpolate speed, gravity, action durations or trajectories
  across this gap.

| Character ID | Updates | Original Player snapshots | Unique actions |
|---|---:|---:|---:|
| 0 | 434 | 107 | 19 |
| 1 | 725 | 182 | 17 |
| 2 | 620 | 156 | 15 |
| 3 | 596 | 149 | 17 |

The model Object's animation-progress fields are now nonzero and distinct
from the root's always-zero animation-progress fields.

## Decoded PlayerTask memory layout (N64 big-endian floats)

Original source still labels most of these fields `unknown_*`.
The trace proves their **numerical behavior**:

| PlayerTask byte offset | Recovered meaning | Independent trace validation |
|---|---|---|
| `+0x68` | horizontal X movement component | matches 2,289 of 2,356 continuous next-frame X displacements |
| `+0x6C` | **actual applied vertical movement per original update** | matches **2,356 / 2,356** consecutive Object Y displacements |
| `+0x70` | horizontal Z movement component | matches 2,289 of 2,356 continuous next-frame Z displacements |
| `+0xA4` | vertical movement prepared for next update | decays by 2/3 during normal airborne motion; reset at ground/early-release changes |

The remaining **67** horizontal mismatches are the same frames in X and Z,
when a nonzero task movement vector persisted despite an **unchanged**
root-object position (observed movement blocking, e.g. collision).
The field is a movement vector and must **not** always be interpreted as
successfully applied world displacement.

The vertical position needed for jumping is the **player-model Object Y**
(`D_801FC60C_5B851C`), not the often stationary
root Object Y (`D_801FC614_5B8524`).

### Normal jump physics reconstructed numerically

An isolated flat-ground model reproduces the observed trajectories:

1. Initial upward movement on A-button jump: **+6.0** world units.
2. Each subsequent game update decreases vertical movement by exactly
   **2/3** world units/update².
3. At an upward **A-button release**, if the upcoming upward movement
   would exceed **+2.0**, it is capped to **+2.0** *immediately*.
4. Ground contact clamps the last downward movement to the remaining
   height, then clears the next vertical velocity to zero.
5. A fully held normal jump reaches **30.0** units of height and
   returns to its original height after **19 applied vertical steps**
   (including the first upward and the final ground-contact step).

Original full-jump heights for the 19 applied movement steps:

`6, 11.333333, 16, 20, 23.333333, 26, 28, 29.333333,
30, 30, 29.333333, 28, 26, 23.333333, 20, 16,
11.333333, 6, 0`.

All four character IDs exhibit the same **normal flat-ground impulse**
and gravity.

### Held A versus early A release (measured)

| A held for initial updates | Max height | Flat-ground movement steps until contact |
|---:|---:|---:|
| 1 | 10.000 | 10 |
| 3 | 20.000 | 15 |
| 4 | 24.000 | 16 |
| 5 | 27.333 | 18 |
| Long enough | 30.000 | 19 |

The original 2.0 cap is validated by actual examples:
at recording frame 173, keeping A for one step yields original
vertical steps `6, 2, 1.3333, 0.6667, 0, -0.6667, ...`.
A held for three steps produces
`6, 5.3333, 4.6667, 2, 1.3333, 0.6667, ...`.

**Special-case evidence:** recording frames **2081** and **2096**
(character ID 1 after the scene transition) begin with **+2.0**
instead of +6.0, and reach only **4.0** height in **7**
movement steps, despite A remaining held. Their activation condition
is **not yet identified**. Do not hardcode normal +6.0 in every
environment without investigating original state/geometry.

## Independent full-trajectory replay

`tools/goemon/reference_probe/jump_trace_fit.py` deterministically
uses original inputs, original action IDs, original root/model positions
and byte-decoded `PlayerTask` values to replay the flight, without
using any ROM bytes, magic teleport, or guessed animation rates.

From the user's actual v0.3 ZIP:

- **27 jump start events** observed.
- **25 complete flat-ground jump trajectories** matched the reconstructed
  height, current vertical step and next vertical step to **<0.002**
  units per measured update (maximum observed numerical error
  approximately **0.000011**).
- **2 remaining jumps** occurred while the measured root ground
  position moved (one before launch, one during the arc). These
  were **excluded from flat-ground completion**, not counted as
  model failures.
- **0 flat-ground trajectory mismatches**.

This is strong **behavioral equivalence for the tested jump states**.
The precise original collision/camera/animation handlers are separate
porting work. We have not shown source-code identity of the
reverse-engineered recurrence with every original executable callsite.

## Horizontal movement

- `PlayerTask+0x68` (X) and `PlayerTask+0x70` (Z) are directly
  observed movement components, with a vector-length **2.80**
  original world units/update on normal full-speed movement
  across all four characters.
- A normal grounded full-stick start reached observed vector speeds:
  **0.70, 1.24, 1.78, 2.3196, 2.80** over five consecutive
  original game updates.
- Direction rotates gradually even when speed is at the 2.80
  limit. Acceleration, input smoothing, cornering and collision
  handling still need independently verified original controller code.
- At least one stationary/collision-blocked interval has a
  nonzero task horizontal velocity. Do **not** blindly apply the
  desired vector without Zelda-world collision adaptation.

## Action/animation coverage

This capture includes new original attack/ability states in addition
to common `88–93` states: ID 0 has `112–114, 124, 127`,
ID 1 has `140, 142, 143`, ID 3 has `162–163`.
Weapon **identities and equipment changes are not yet directly
decoded**. Treat these as original numerical action states, not
as formally named attacks or animations.

## Implementation and next work

The feature branch now has a **standalone C++20** header
`soh/soh/Enhancements/Goemon/OriginalJump.hpp` implementing the
tested vertical equations, with native regressions
`tools/goemon/re/tests/test_original_jump.cpp` for normal,
one-/three-/four-update A holds and the special measured +2 impulse.

`PlayerTaskView` in
`soh/soh/Enhancements/Goemon/OriginalMemory.hpp` exposes
byte-correct movement fields for subsequent runtime integration.
The new deterministic Python replay runs during
`reprocess_log.py` and creates `physics_fit.json`
for compatible future reference captures.

**Not yet playable in Ship of Harkinian.** Remaining tasks:
original lateral steering/acceleration, environment-dependent jump
impulse and real collision contacts; original animation/rig/audio
and combat dispatch; then integration into the Zelda Player and
Randomizer adapter with executable builds and trace comparison.
