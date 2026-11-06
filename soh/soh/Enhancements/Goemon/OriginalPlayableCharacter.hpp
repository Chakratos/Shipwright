#pragma once
// New source-measured, selectable playable character bridge.
// This is NOT the previous debug-ball Actor and does not alter the
// independently verified Goemon motion equations. Input direction and
// Zelda-world collision remain explicit integration adapters.
#include "OriginalLiveFrame.hpp"

namespace Goemon::Original {
struct PlayableOriginalCharacterGate {
    bool renderingEnabled = false;
    bool pilotOptIn = false;
    bool originalModelLoaded = false;
    bool characterActorAlive = false;
    bool sceneMatches = false;
    bool vanillaControlAvailable = false;
    bool noLegacyPilotConflict = false;
    bool faultFree = true;
};

// Never steal Link's controls unless a real rendered actor and valid model
// exist in the same scene and the user has opted in.
[[nodiscard]] constexpr bool CanPilotOriginalCharacter(
    PlayableOriginalCharacterGate gate
) {
    return gate.renderingEnabled && gate.pilotOptIn &&
           gate.originalModelLoaded && gate.characterActorAlive &&
           gate.sceneMatches && gate.vanillaControlAvailable &&
           gate.noLegacyPilotConflict && gate.faultFree;
}

[[nodiscard]] inline ShipPreviewStick MapShipInputForOriginalPlayable(
    int stickX, int stickY, std::int16_t cameraYaw
) {
    // First in-game Goemon actor test observed Ship lateral handness
    // reversed. This is the FINAL actor's Ship input adapter only;
    // the source-measured original yaw/physics core is unchanged.
    // We preserve camera heading and swap just lateral stick sign.
    return MapShipStickForOriginalPreview(-stickX, stickY, cameraYaw);
}
} // namespace Goemon::Original
