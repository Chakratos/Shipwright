#include "soh/soh/Enhancements/Goemon/OriginalPlayableCharacter.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>

using namespace Goemon::Original;

int main() {
    PlayableOriginalCharacterGate gate{};
    assert(!CanPilotOriginalCharacter(gate));
    gate.renderingEnabled = true;
    gate.pilotOptIn = true;
    gate.originalModelLoaded = true;
    gate.characterActorAlive = true;
    gate.sceneMatches = true;
    gate.vanillaControlAvailable = true;
    gate.noLegacyPilotConflict = true;
    gate.faultFree = true;
    assert(CanPilotOriginalCharacter(gate));
    gate.originalModelLoaded = false; assert(!CanPilotOriginalCharacter(gate));
    gate.originalModelLoaded = true;
    gate.noLegacyPilotConflict = false; assert(!CanPilotOriginalCharacter(gate));
    gate.noLegacyPilotConflict = true;
    gate.vanillaControlAvailable = false; assert(!CanPilotOriginalCharacter(gate));
    gate.vanillaControlAvailable = true;
    gate.faultFree = false; assert(!CanPilotOriginalCharacter(gate));

    // User's in-game test proved lateral axes reversed in the old actor.
    // New character's Ship adapter corrects this WITHOUT changing source
    // original NG5E acceleration or yaw/turn equations.
    const auto right = MapShipInputForOriginalPlayable(85, 0, 0);
    const auto left = MapShipInputForOriginalPlayable(-85, 0, 0);
    const auto forward = MapShipInputForOriginalPlayable(0, 85, 0);
    const auto camera = MapShipInputForOriginalPlayable(0, 85, 0x4000);
    assert(right.kind == ShipPreviewStickKind::Full);
    assert(left.kind == ShipPreviewStickKind::Full);
    assert(right.provisionalOriginalYaw10 == 768);
    assert(left.provisionalOriginalYaw10 == 256);
    assert(forward.provisionalOriginalYaw10 == 0);
    assert(camera.provisionalOriginalYaw10 == 256);
    assert(right.x == -93);
    assert(left.x == 93);

    OriginalLiveFrameState character{};
    auto noCollision = [](float, float, OriginalPlanarStep desired) {
        return desired;
    };
    auto movement = AdvanceOriginalLivePreview(
        character, right, false, false, noCollision);
    assert(movement.measuredTransitionSupported);
    assert(movement.motion.appliedPlanar.x < -0.69f);
    assert(std::fabs(movement.motion.appliedPlanar.z) < 0.001f);

    std::puts("OriginalPlayableCharacter: guarded true Actor control and lateral fix PASS");
}
