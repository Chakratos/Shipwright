# Goemon × Ship: input-driven original motion in the real Zelda world

## Implemented now: live controller ghost (not playable character yet)

The toggle `gSettings.Goemon.LiveControllerGhost=1` enables
`soh/soh/Enhancements/Goemon/OriginalLiveControllerProbe.cpp` during
actual Ship gameplay. It uses **real Ship controller inputs** to advance a
separate Goemon motion pose on every `OnPlayerUpdate`, using the already
source-measured original NG5E motion kernel.

The CSV `goemon_live_controller_ghost.csv` is written to the **game's
working directory**. Switch the CVar to `0` to close the recording.

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
| Flat-ground ghost jump and 1:1 world units | Diagnostic only | **Not scale- or floor-calibrated** |
| Original character models, skeletons, animation | Not converted | **Not implemented** |

The input adapter intentionally **rejects intermediate analog magnitudes**
rather than inventing a response curve. The ghost can stop for unsupported
actions; this is an explicit limitation, not a simulated original behavior.

## Local testing

1. Run a Ship build from the `feature/goemon-original-controller` branch.
   The GitHub `goemon-selfhosted` workflow builds on the user's own
   Windows runner; it does not use GitHub-hosted runner minutes.
2. Set `gSettings.Goemon.LiveControllerGhost` to `1` using Ship CVar
   configuration or console, then walk, turn, release and press A.
3. Set it to `0`. Examine `goemon_live_controller_ghost.csv`.
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
