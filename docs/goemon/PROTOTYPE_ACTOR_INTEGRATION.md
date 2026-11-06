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
   Link's current location. Both Link and this **separate Actor** observe
   the current gamepad; their movement diverges because they run different
   movement systems. Full-stick movement, turns, stopping and A jumps
   exercise the prototype.
4. Disable the option to despawn the prototype. Re-enabling starts a new
   Actor. Inspect `goemon_prototype_actor.csv` in Ship's working folder.

For a clean comparison, turn off **Live Goemon Controller Ghost**. When
Prototype Actor is enabled, that older Ghost automatically suspends its
own updates.

## Architecture

- `OriginalPrototypeActor.cpp` registers a dynamic ActorDB ID after the
  database has initialized, and spawns it through the native `Actor_Spawn`
  API when normal grounded gameplay is active.
- `OriginalLiveFrame.hpp` performs transactional motion updates:
  rejected collision updates do not modify the controller state.
- The native Actor update reads Ship input and calls the independently
  measured Goemon motion core. A temporary Ship camera/stick adapter
  chooses numeric Goemon actions; unsupported transitions are marked
  explicitly and **do not acquire fabricated original velocity**.
- Zelda's collision context supplies wall-ray and floor-height observations
  at the actual **jumping model Y**, not the previous grounded Y.
- The Actor survives room changes inside one scene, resets its controller
  when a new room is entered, and is discarded on game teardown or scene
  change. Cutscenes, menus, interactions, swimming and other unsupported
  Link states suspend the experimental Actor's motion.
- Debug trace: `frame, scene, room, raw Ship stick X/Y, provisional yaw10,
  action, measured_transition, actor position, desired/applied planar
  deltas, wall contact, floor probe, diagnostic snap, airborne`. Input
  fields allow reproducing a regression from a single local capture.

## Limits / next engineering work

This is **not yet a playable Goemon character or finished replacement
player**. It has no original mesh, skeleton, animation, combat or camera
controller. Link still moves normally from the same input. It has no
Zelda-player collision cylinder, hitbox, scene-exit ownership, item use or
Randomizer progression. It is deliberately not installed in
`ACTORCAT_PLAYER`.

The single-height Zelda wall ray, block-on-contact policy, floor snap,
1:1 world-unit conversion, provisional analog threshold and controller
camera yaw are **integration probes**, not a reverse engineered original
Goemon collision/scene controller. The code does not claim they match
NG5E's original behavior.

### Required before the first fully playable character

1. Verify the Actor compiles and visibly updates in Ship using **one**
   manually requested full Windows build; review its CSV on a flat surface,
   a wall, an edge and an ordinary room transition.
2. Replace temporary collision with a tested cylinder + vertical
   ground/ledge/landing integration; calibrate Goemon-to-Zelda world units.
3. Attach genuine model, skeleton and animation data from the local NG5E
   ROM via the private resource conversion pipeline.
4. Implement actual player ownership, camera, combat/interactions and
   scene-exit handling. Preserve the separate original motion controller.
