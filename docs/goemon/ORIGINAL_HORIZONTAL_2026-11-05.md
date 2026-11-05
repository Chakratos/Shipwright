# Goemon: Original horizontal movement / implementation (2026-11-05)

Data source: genuine user-captured NG5E Goemon64Recompiled run
run-20261105-123100.zip (2,375 original updates, four characters).
No original ROM or game assets are committed.

## Independently verified scalar speed transitions

Each of the following observations was checked against the *original*
PlayerTask X/Z movement components at offsets 0x68/0x70.
Tolerances refer to horizontal vector magnitude, not just visual speed.
Original-frame gaps and character switches were excluded.

| Source action phase | Speed rule (world units/update) | Matched / observed |
|---|---|---:|
| Action 13: begin from rest | first step 0.70 | 6 / 6 |
| Action 15: grounded run | +0.54, clamp 2.80 | 48 / 48 |
| Airborne 23/25/26/28 (stable stick direction) | +0.84, clamp 2.80 | 14 / 14 |
| Action 15 → 16: release from full run | 2.80 → 2.00 | 5 / 5 |
| Continue 16 at speeds 2.0/1.4/0.8/0.2 | subtract 0.60 *signed* | 20 / 20 |
| **Total** | | **93 / 93** |

Maximum accepted absolute difference: 0.012 world units per update.
One original ground-start sample was 0.6912 rather than precisely 0.70.

The full-run brake trajectory is signed:
2.8 → 2.0 → 1.4 → 0.8 → 0.2 → **-0.4**.
This brief backwards movement must not be replaced with an
approximate friction model clamped at zero. Four observed runs
subsequently stopped at idle; a fifth retained 0.4 motion while
the world position stayed blocked. Consequently idle reset remains
**explicit**, controlled by the original action machine.

The original task desired movement vector was nonzero while the root
object failed to move in **67 recorded frames**, showing why target
world collision resolution is necessary before applying movement.

## Executable C++20 progress

- OriginalHorizontal.hpp: original-grounded, airborne and braking
  magnitude transitions with explicit sign preservation.
- OriginalJump.hpp: existing recovered jump impulse, gravity,
  variable-height A release and the observed low-impulse variant.
- OriginalMotionAdapter.hpp: flat-floor integration component
  combining horizontal movement, jump arc and game-position stepping.
  It accepts direction externally and REQUIRES a collision callback,
  exposing both the original desired vector and actual applied step.
- test_original_horizontal.cpp and test_original_motion_adapter.cpp:
  standalone GCC 14 C++20 native tests. Both pass strict compiler
  warnings plus AddressSanitizer/UndefinedBehaviorSanitizer.
- horizontal_trace_fit.py validates the complete real recording
  independently of these numeric fixtures, and is registered in
  the recoverable Windows log postprocessor as horizontal_fit.json.
- test_horizontal_trace_fit.py rejects malformed or missing task
  captures, and verifies representative original-ground/air/braking
  phase sequences.

## Remaining fidelity gaps

Camera-relative direction, rotation smoothing, partial analog-stick
magnitude handling, true wall/floor collision responses, action-state
selection, character combat/equipment, original rigs and animation,
and integration into playable Ship of Harkinian remain **unported**.
The prototype must not be described as a playable Goemon character.

Native regression command from Shipwright:

    py -3 tools/goemon/verify.py --native

No GitHub Actions are used. All current changes remain isolated on
feature/goemon-original-controller and leave develop unchanged.
