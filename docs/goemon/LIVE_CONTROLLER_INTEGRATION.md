# Goemon × Ship: input-driven original motion in the real Zelda world

## Implemented now: live controller ghost (not playable character yet)

The toggle `gSettings.Goemon.LiveControllerGhost=1` enables
`soh/soh/Enhancements/Goemon/OriginalLiveControllerProbe.cpp` during
actual Ship gameplay. It uses **real Ship controller inputs** to advance a
separate Goemon motion pose on every `OnPlayerUpdate`, using the already
source-measured original NG5E motion kernel.

A **cyan debug ball** shows the separate Goemon ghost position in the scene.
It turns **red on a diagnostic wall-ray hit**. This is a visibility marker,
**not the original character model**. To hide it, set
`gSettings.Goemon.LiveControllerGhostDraw=0` (default: 1 when ghost is enabled).

The CSV `goemon_live_controller_ghost.csv` is written to the **game's
working directory**. Switch the main CVar to `0` to close the recording.
The `action_supported` field is 1 only when the measured original
controller accepts the frame. Unsupported phases use a separate idle
fallback and are marked 0, not falsely reported as verified.

The `preview_floor_snap` field reports the **diagnostic-only** floor
height adjustment. When grounded with no wall hit and a valid Zelda floor,
the ghost updates its base Y to that floor. In-air jumps and blocked wall
steps do not snap. This is not evidence of Goemon's original floor-snapping
behavior or a safe algorithm for moving a real player Actor.

Fields include Ship raw stick axes, provisional numeric Goemon action and
target heading, supported/unsupported original velocity transition, source
desired X/Z motion, Zelda-wall-applied ghost motion, ghost position/Y jump,
Link's actual position, and Zelda wall/floor contact observations.

**Ship player/Link actor, items, saves, animation, camera and Randomizer
are never changed by this diagnostic.** No copyrighted ROM bytes or
original Goemon assets are embedded in Ship or committed to GitHub.

## Exactly which parts are authentic?

| Component | Basis | Status |
|---|---|---|
| Ground start 0.70, ground vector blend, 2.8 cap | Actual NG5E PlayerTask traces | Verified for measured actions and stick states |
| Air start 0.84, steering and turn reset | Actual NG5E PlayerTask traces | Verified for captured states |
| Release 2.0 then 0.6 steps | Actual NG5E action traces | Verified for captured states |
| Jump 6.0, gravity 2/3, early release cap 2.0 | Actual NG5E jump trajectories | Verified on sampled flat-ground conditions |
| Input stick -\> full/neutral classification | Ship input adaptation | **Temporary, not original** |
| Ship camera -\> 10-bit heading | Ship camera adaptation | **Temporary, not original** |
| Action 13/15/16/23 selection from Ship buttons | Diagnostic mapping | **Temporary, not original** |
| Zelda collision ray, full-stop on wall | Ship collision APIs | **Temporary, not original** |
| Flat-ground ghost jump, Zelda floor-height preview and 1:1 world units | Diagnostic only | **Not original floor/collision calibration** |
| Original character models, skeletons, animation | Not converted | **Not implemented** |

The input adapter intentionally **rejects intermediate analog magnitudes**
rather than inventing a response curve. The ghost can stop for unsupported
actions; this is an explicit limitation, not a simulated original behavior.

## Local testing

1. Open the repository's **Actions → goemon-selfhosted → Run workflow**,
   select `feature/goemon-original-controller`, and enable `full_build`
   when a fresh Ship executable is actually required. Ordinary pushes
   only execute Python/C++ regression tests and never compile Ship.
2. Run that build and open **Dev Tools → Goemon** in Ship.
   Enable **Live Goemon Controller Ghost** and **Show Goemon Ghost Marker**.
   Walk, turn, release and press A. The Goemon section also exposes
   separate Zelda geometry, Ship player and original replay recordings.
3. Disable the live ghost. Inspect `goemon_live_controller_ghost.csv`,
   particularly `action_supported` and `preview_floor_snap`.
4. Cross-compare with the original source trace and Zelda geometry trace
   before turning any of the provisional mappings into gameplay rules.

The default is off. The diagnostic never loads the Goemon ROM into Ship.
The **self-hosted CI** uses the user's locally installed Goemon ROM to
verify its exact original SHA-256, decompressed SHA-256 and original resource
tables; it does not upload game data.

## Next stages

1. Recover the original Goemon input-to-camera yaw transform, control
   thresholds, action dispatch and landing transitions from instrumented
   NG5E runtime.
2. Measure collisions, vertical ground snaps and world-scale mapping across
   multiple real geometry cases; replace the conservative ray test with a
   verified source-to-Zelda collision adapter.
3. Apply the validated controller to a player Actor with a proper runtime
   gate and scene transitions (the current diagnostic **does not** do this).
4. Decode original four-character graphics, 3D skeleton/animation resources,
   then integrate character switching, weapons and the agreed Randomizer
   capabilities. No Link re-skin is accepted as the final Goemon port.
