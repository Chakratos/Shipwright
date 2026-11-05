# Original Goemon directional steering and vector acceleration

Real reference: original NG5E gameplay on Goemon64Recompiled, Windows,
2026-11-05, capture run-20261105-123100.zip, 2,375 original updates.
Original ROM and PlayerTask memory bytes are never committed to Git.

## Source-observed vector equation

At any supported state, interpret original PlayerTask offsets
+0x68 (desired X velocity), +0x70 (desired Z velocity) as a 2-D
desired world-space movement vector. Root Object rotation Y is a
10-bit target yaw: target=(sin(yaw*2*pi/1024),cos(yaw*2*pi/1024)).
One original game update uses the following experimentally recovered
DIRECTION formulas:

    previousSpeed = hypot(previousVX, previousVZ)

    Grounded:
      rawDirection = (previousSpeed - 0.30)*unit(previousVector)
                     + 0.84*target

    Airborne:
      rawDirection = previousSpeed*unit(previousVector)
                     + 0.84*target

    nextDirection = unit(rawDirection)

The original full-stick SPEED ramp in the tested action states:

    groundSpeed = min(previousSpeed + 0.54, 2.80)
    airSpeed    = min(previousSpeed + 0.84, 2.80)

Thus the grounded 0.54 scalar increment results from the
0.84 directional acceleration and the 0.30 reduction of the
previous heading component (the full original implementation's
ordering and geometry interactions are still being reverse-engineered).

**At the maximum velocity of 2.80**, these formulas simplify exactly to:

    Ground: nextDirection = unit(unit(previousVector) + 0.336*target)
    Air:    nextDirection = unit(unit(previousVector) + 0.300*target)

The constants are not approximations from choosing plausible parameters:
they are independently inferred from the original source velocities
by solving the 2D vector parallelism equation for each turn.

## Full-speed directional validation

- 99/99 grounded action 15 -> 15 original updates reproduced.
- 88/88 airborne action 23/25/26/28 combinations reproduced.
- **187/187** valid full-speed samples agree with the predicted
  original target vectors within 0.000002 world units/update.
- Maximum measured Euclidean velocity error: about
  **0.00000035** units/update.
- Coverage includes all four character IDs.
- Direct inference of the mixing coefficient (ignoring near-collinear
  directions) produced median **0.335999994** grounded
  and **0.300000003** airborne, independently of the constants in C++.

The appropriate ground/air state is determined by observed original
numeric action IDs, not guesses about Link's current animation.

## Extended partial-speed and midair-stick validation

Expanded independent evaluation of ALL eligible first-movement,
continuation and midair-stick-reset states in the same recording:

| Source phase | Original candidate pairs | Direction within 0.001 | Speed within 0.012 |
|---|---:|---:|---:|
| Ground first movement, action 13 | 6 | 6 | 6 |
| Ground continuation, action 13/15 -> 15 | 149 | 149 | 148 |
| Air continuation in actions 23/25/26 | 102 | 102 | 102 |
| Same airborne action + abrupt stick direction change | 4 | 4 | 4 |
| **Total** | **261** | **261** | **260** |

Notes:
- One ground-start direction at sample 146 differed by a tiny
  normalized vector error of 0.000469 (still below 0.001).
- The only scalar-speed failure was sample **36** (character 2):
  observed speed **2.72508** instead of the standard **2.8**
  after a substantial change of target yaw. Both actual and predicted
  DIRECTION vectors still match at better than 0.000001.
  **This is not silently normalized away**; the original
  exception rule still needs investigation.
- Midair stick changes at samples **13, 19, 23, 27** set the
  desired vector to **0.84 * targetYaw** in the same action, with
  negligible numerical discrepancy. All four occur in character
  ID 2 in this specific capture. This observation should be repeated
  with the other original characters when measuring those special cases.
- Landing action 28, unknown actions, camera-to-target-yaw mapping,
  partial analog magnitude and nonflat floor/step collision
  are NOT covered by this recurrence.

## Executable port modules

- OriginalSteering.hpp: exact 2.8-speed ground/air interpolation
  (0.336/0.300), with classifying/unsupported-state guard.
- OriginalSteeredMotion.hpp: uses those full-speed states with the
  existing vertical jump and pluggable collision resolver;
  preserves desired velocity when the target collision blocks motion.
- OriginalVectorAcceleration.hpp: full-stick ground/air directional
  acceleration at any observed supported speed, 0.30 ground
  drag, 0.84 input impulse, and the original 0.54/0.84 speed ramps.
- OriginalVectorController.hpp: action-gated stateful movement
  (ground start, run, air start/continuation, midair turn reset,
  observed braking to -0.4); returns an empty result instead
  of pretending to support unknown original actions.
- The controller steps OriginalMotionAdapter.hpp, which retains
  actual collision-resolved movement independently from
  the original desired velocity and advances the prior
  vertical jump model at the original fixed-update rate.

Native tests:
- test_original_steering.cpp
- test_original_steered_motion.cpp
- test_original_vector_acceleration.cpp
- test_original_vector_controller.cpp

Independent actual-capture Python validators:
- steering_trace_fit.py -> steering_fit.json
- vector_trace_fit.py -> vector_fit.json
- Synthetic regressions in reference_probe/tests.

## Remaining high-priority source work

1. Original camera input -> root target yaw with stick deltas,
   camera orbit/lock-on and partial analog (not identical to
   Link's yaw or Zelda movement smoothing).
2. Source-side action dispatcher including grounded/air transitions,
   special 2.0 jump impulse, weapon/equipment IDs and attack hitboxes.
3. Original collision contact, slopes and step behavior, adapted
   to the Zelda level coordinate system.
4. Authentic four original rigs, texture/animation clips, combat
   and Zelda-world/Randomizer integration, followed by a Ship build.

No playable Goemon is claimed yet. This is numerically measured
and independently testable **controller code**, not a Link reskin.
