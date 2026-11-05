# Original NG5E animation and heading observations (2026-11-05)

Data: real Goemon64Recompiled v0.3 diagnostic run
run-20261105-123100.zip; original 2,375 captured game updates,
all four original character-ID values. Original ROM/asset bytes
are not committed.

## Native animation-clock evidence

The model Object (not its graphics root) supplies an original
animation-progress value that was recorded on every gameplay update.
For each original (character ID, action ID) pair we compared ONLY
successive measurements with the same character, same action and
a +1 original game-frame counter.

- **68** distinct (character, action) combinations observed.
- **48** have a single dominant **positive progress increment** with
  at least 5 observations, >=95% consistency among positive steps
  and >=60% of consecutive action updates accounted for by that increment.
- Negative animation-progress changes are **reported separately** as
  wrap/reset events, not construed as negative animation speeds.
- Unchanged animation progress is **reported as a hold**, not as
  evidence that an animation is missing.

Important measured positive increments, original progress units
per original game update:

| Character ID | Idle action 0 | Run action 15 | Shared attack action 88 | Attack action 90 |
|---|---:|---:|---:|---:|
| 0 | +0.4 | +1.4 | +0.6 | +0.6 |
| 1 | +0.3 | +1.0 | +0.6 | +0.8 |
| 2 | +0.4 | +1.4 | +1.0 | +1.0 |
| 3 | +0.4 | +1.2 | +1.4 | +1.4 |

Additional individual attack timings:

- Character 0, action 124: +1.4 for 20 consecutive advances.
- Character 1, action 140: +0.6 for 44 consecutive advances.
- Character 1, actions 142 and 143: each +0.8 for 35 advances.
- Character 3, action 162: +0.4 for 40 advances,
  followed by **149 hold measurements** at the terminal progress
  of 16.0; it is **not** a fixed-rate action in our C++ lookup.
- Character 3, action 163: +0.4 for 10 advances with one hold.

Source of truth:
tools/goemon/reference_probe/animation_trace_fit.py
generates animation_fit.json for every future compatible reference trace.

C++20:
soh/soh/Enhancements/Goemon/OriginalAnimationRates.hpp
contains only the 48 stably observed mappings, not fabricated clips,
skeleton/rig assets, weapon identities or frame wraps.
test_original_animation_rates.cpp validates representative entries
and confirms mixed/frozen actions are not blindly advertised as
uniform animation progress.

## Original stable movement orientation

When the root character yaw was constant for at least three
preceding consecutive original game updates, stick direction
was unchanged, action ID was 15, and full running velocity was
>=2.79 world units/update:

- **18/18** eligible measurements matched
  the **1024-step original N64 heading mapping**.
- Maximum absolute orientation error from the original PlayerTask
  desired X/Z movement vector: **0.00000717 degrees**.

Measured original direction:

    yaw10 = root_object.rotation.y & 1023
    worldDirectionX = sin(2 * pi * yaw10 / 1024)
    worldDirectionZ = cos(2 * pi * yaw10 / 1024)

This is a **coordinate convention**, not a reconstruction of the
game's steering filter. Frames with active turning were excluded:
the player's desired movement direction is interpolated separately
from changes in root yaw.

Executable and reproducible sources:

- OriginalYaw.hpp: 10-bit yaw-to-world-direction conversion.
- test_original_yaw.cpp: measured actual yaw index 761 and
  all cardinal 256-step orientations.
- yaw_trace_fit.py: checks eligible original game samples and
  creates yaw_fit.json for postprocessing.
- test_yaw_trace_fit.py: synthetic regression with original Task
  byte layout.

## Work remaining

Mapping original action IDs to 3D skeleton/animation assets, exact
animation clip selection and wraps, intermediate analog values,
turning filter, source-level weapon/equipment state, collision
resolution against Zelda geometry, and runtime integration.
None of these is claimed to be completed merely by a numeric
progress/increment table.
