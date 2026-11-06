# Independent Goemon Actor: first Ship runtime integration (2026-11-06)

## Implemented

Ship's `ActorDB` now registers `GoemonOriginalPrototype`, a genuine
`ACTORCAT_PROP` Actor that owns a separate world position and lifecycle.
The Actor shares `OriginalLiveFrame.hpp` with the earlier live ghost:
source-measured full-stick ground/air acceleration, braking and the
sampled flat-ground jump arc. The original character graphics are **not
yet decoded**. A **gold diagnostic marker** indicates the Actor position;
red indicates a wall-ray contact.

This is a separate Actor, **not a skin, animation or repositioning of
Link**. Original asset data is not compiled into Ship.

## Enable and test

1. Build Ship from `feature/goemon-original-controller` once when a
   testable executable is needed. In GitHub Actions select
   `goemon-selfhosted → Run workflow → full_build=true`. Ordinary pushes
   run native/Python tests only.
2. In Ship open **Dev Tools → Goemon → Spawn Independent Goemon Actor
   (Prototype)**. The toggle defaults to OFF.
3. Stand on normal ground and enable the option. A gold marker spawns at
   Link's current location. By default both Link and the **separate Actor**
   receive the current gamepad for a side-by-side diagnostic.
4. Enable **Pilot Goemon Actor (Freeze Link Input)** to redirect the local
   Link movement input to the independent Actor. Only the Actor receives
   movement/jump commands, while the rendered camera follows its position.
   Press A to try the measured jump arc, use full stick to run and release
   to brake. This does NOT move Link's actor position directly or replace
   Zelda interactions, doors, attacks or items.
5. Disable **Pilot Goemon Actor** to restore normal Link controls and the
   vanilla camera. Disable **Spawn Independent Goemon Actor** to despawn it.
6. Re-enabling the Actor starts a fresh prototype. Inspect
   `goemon_prototype_actor.csv` in Ship's working folder.
   Produce a compact numeric summary, without manual CSV inspection:

   ```powershell
   py -3 tools\goemon\analyze_actor_trace.py "goemon_prototype_actor.csv" --output "goemon_actor_report.json"
   ```

7. If the Actor stops unexpectedly, inspect
   `goemon_prototype_actor_error.txt`. A fatal geometry error is latched;
   **disable and re-enable** the toggle to retry (no infinite respawn loop).

For a clean comparison, turn off **Live Goemon Controller Ghost**. When
Prototype Actor is enabled, that older Ghost automatically suspends its
own updates.

## Architecture

- `OriginalPrototypeActor.cpp` registers a dynamic ActorDB ID after the
  database has initialized, and spawns it through the native `Actor_Spawn`
  API when normal grounded gameplay is active.
- `OriginalLiveFrame.hpp` performs transactional motion updates:
  rejected collision updates do not modify the controller state.
- The native Actor update reads the unmodified Ship gamepad and calls the
  independently measured Goemon motion core. A temporary Ship camera/stick
  adapter chooses numeric Goemon actions; unsupported transitions are
  marked explicitly and **do not acquire fabricated original velocity**.
- The optional `PrototypePilot` flag suppresses **only the local Input
  copy** passed to Link's `Player_UpdateCommon`, never
  `play->state.input[0]`. The separately registered Actor still reads the
  raw current controller. This gate refuses to activate if the Actor is
  absent, faulted, in another scene, or Link is not in normal gameplay.
- `OnPlayDrawBegin` translates the already-updated Zelda camera view
  to the Actor's position while reusing vanilla camera yaw/distance.
  `PilotCameraHistory` guarantees idempotency when high-FPS rendering
  calls Play_Draw multiple times between Camera_Update ticks; it restores
  the vanilla view when pilot mode is turned off.
- Zelda's collision context supplies **six body-sweep wall rays** at two
  heights and three lateral offsets, plus a destination floor query.
  Sample heights and widths are provisional, not original NG5E dimensions.
  The adapter receives actual jumping model Y, the separate ground anchor
  and the independently measured airborne phase.
- When grounded, the provisional adapter rejects missing floor, steps
  higher than 5 Zelda units and drops deeper than 12 units. It rejects
  all planar motion on wall-ray contact. These values do **not** establish
  original Goemon collision radius, stepping or falling mechanics.
- The Actor survives room changes inside one scene, resets its controller
  when a new room is entered, and is discarded on game teardown or scene
  change. Cutscenes, menus, interactions, swimming and other unsupported
  Link states suspend the experimental Actor's motion.
- Debug trace: `frame, scene, room, raw Ship stick X/Y, provisional yaw10,
  action, measured_transition, actor position, desired/applied planar
  deltas, wall contact, floor probe, diagnostic snap, airborne and
  terrain_reject_code`. Input fields allow reproducing a regression from
  a single local capture. The codes are 0=accepted, 1=wall, 2=missing
  floor, 3=step too high, 4=drop too deep.

## Limits / next engineering work

This is a **steerable independent Actor pilot**, not yet a playable Goemon
character or finished player replacement. It has no original mesh,
skeleton, animation, combat or original camera controller. Without pilot,
Link and the Actor read the same gamepad; with pilot, Link's local input
is zeroed while Goemon receives the raw input and the rendered view
follows Goemon. This prototype still has no player collision cylinder,
hitbox, door/scene-exit ownership, item use or Randomizer progression.
It is deliberately not installed in `ACTORCAT_PLAYER`.

The conservative six-ray Zelda envelope, block-on-contact policy, floor
height filters, 1:1 world-unit conversion, provisional analog threshold
and controller camera yaw are **integration probes**, not a reverse
engineered original Goemon collision/scene controller. Falling off
ledges, wall sliding, ceiling collisions and the real capsule radius are
NOT implemented or validated. The code does not claim they match
NG5E's original behavior.

### Required before the first fully playable character

1. Verify the Actor and new C-language Link input hook compile and run
   in Ship using **one** Windows integration build. Test pilot ON/OFF,
   the camera view restoration, a flat surface, a wall, an edge and
   a normal room transition; analyze the Actor's CSV.
2. Replace temporary collision with a tested cylinder + vertical
   ground/ledge/landing integration; calibrate Goemon-to-Zelda world units.
3. Attach genuine model, skeleton and animation data from the local NG5E
   ROM via the private resource conversion pipeline.
4. Implement actual player ownership, camera, combat/interactions and
   scene-exit handling. Preserve the separate original motion controller.
