# First real Ship-world collision integration (2026-11-05)

The original Goemon motion core now has a **real engine collision
observation hook**, not merely a mock callback.

Files:

- `soh/soh/Enhancements/Goemon/OriginalZeldaWorldProbe.hpp`:
  a world-space, callback-based, no-side-effects interface. It keeps
  the **original desired X/Z vector** distinct from a Zelda wall hit,
  wall contact and floor sample. No point radius, step height or
  fictional collision response is introduced.
- `soh/soh/Enhancements/Goemon/ZeldaWorldProbe.cpp`:
  hooks Ship's real `GameInteractor::OnPlayerUpdate`; calls the
  verified engine API `BgCheck_EntityLineTest1` on
  `gPlayState->colCtx` for Zelda wall polygons and
  `BgCheck_EntityRaycastFloor3` for the real collision floor.
  Writes `goemon_zelda_world_probe.csv`.
- `tools/goemon/reference_probe/ship_world_probe_analysis.py`:
  validates the CSV and generates per-scene wall/floor statistics,
  requiring consistent coordinates, angle-to-direction mapping
  and exact Goemon 2.8-unit projected step length.
- Native and Python synthetic regressions:
  `test_original_zelda_world_probe.cpp` and
  `test_ship_world_probe_analysis.py`.

## Activate only in a locally built Ship game

Settings CVar: `gSettings.Goemon.ZeldaWorldProbe` (default **0**, off).

When the existing player update hook is active, probes project a
**2.8 world-unit step** from the current Link position and sample
the Zelda collision context. To test wall directions, the probe
temporarily uses **Link's current shape yaw as a DIAGNOSTIC input**.
This is intentional: the camera-to-target-yaw and partial-stick
logic of the original Goemon game has not yet been integrated.
The source Goemon motion kernel never receives Link's yaw.

The query reports:

- scene / frame; Link's actual position and yaw for reference,
- desired Goemon-length X/Z step and projected destination,
- Zelda wall contact/no contact and intersection point,
- detected Zelda floor height or explicit absence of floor.

It performs **no writes to player position, velocity, actors,
collision geometry, flags, save data or Randomizer state**. The
relative-height and wall-point queries are for evidence gathering;
a 10-unit-high wall ray and 50-unit floor-ray start are not a
claim of original Goemon actor collision dimensions.

## How to inspect a real Ship capture later

After compiling and running the Ship feature branch, enable
`gSettings.Goemon.ZeldaWorldProbe` during normal gameplay, move
across several Zelda surfaces, disable it and inspect the file
`goemon_zelda_world_probe.csv` in the game working directory.

Run the **source-only** analyzer:

```powershell
py -3 tools\goemon\reference_probe\ship_world_probe_analysis.py "C:\Pfad\goemon_zelda_world_probe.csv" --output "C:\Pfad\world_probe_stats.json"
```

The in-game hook has been checked against the original Ship
`functions.h` and `GameInteractor` signatures. The standalone
C++20 geometry-probe interface passed GCC/ASan/UBSan checks.
**The full Windows Ship executable has not yet been built with this
hook**. We are not claiming that original Goemon collision dynamics
are playable; the next stage must link an authoritative collision
resolver to the actual Goemon player.

## Why this improves the port

Previously the motion integrator had only a synthetic `Resolve`
callback. We can now collect *actual Zelda world geometry evidence*
using Ship's own BSP/scene collision structures, without changing
Link or approximating original physics to demonstrate activity.

Once exact original movement states and geometry contact semantics
are verified, this interface can be upgraded from a read-only
measurement adapter to a collision resolver for a real Goemon Actor.
