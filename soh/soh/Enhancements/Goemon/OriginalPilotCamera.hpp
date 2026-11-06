#pragma once
// Camera translation for the independent Goemon Actor pilot.
// SHIP CAMERA ADAPTER ONLY: reuses vanilla Link camera orientation/zoom
// and moves its rendered viewpoint to the independent Actor. This does not
// reproduce the original Goemon camera, collision or animation.
#include "OriginalZeldaWorldProbe.hpp"

#include <stdexcept>

namespace Goemon::Original {

struct PilotCameraView {
    WorldPoint eye{};
    WorldPoint lookAt{};
};

// No global view/actor mutations. The implementation is also usable by
// deterministic tests without linking the full Ship renderer.
[[nodiscard]] inline PilotCameraView TranslatePilotCamera(
    WorldPoint vanillaEye, WorldPoint vanillaAt,
    WorldPoint linkPosition, WorldPoint actorPosition) {
    if (!FiniteWorldPoint(vanillaEye) || !FiniteWorldPoint(vanillaAt) ||
        !FiniteWorldPoint(linkPosition) || !FiniteWorldPoint(actorPosition))
        throw std::invalid_argument("nonfinite prototype camera coordinates");

    const WorldPoint offset{actorPosition.x - linkPosition.x,
                            actorPosition.y - linkPosition.y,
                            actorPosition.z - linkPosition.z};
    PilotCameraView view{
        {vanillaEye.x + offset.x, vanillaEye.y + offset.y,
         vanillaEye.z + offset.z},
        {vanillaAt.x + offset.x, vanillaAt.y + offset.y,
         vanillaAt.z + offset.z}
    };
    if (!FiniteWorldPoint(offset) || !FiniteWorldPoint(view.eye) ||
        !FiniteWorldPoint(view.lookAt))
        throw std::invalid_argument("prototype camera offset overflow");
    return view;
}

struct PilotInputGate {
    bool pilotEnabled = false;
    bool actorEnabled = false;
    bool actorAlive = false;
    bool sceneMatches = false;
    bool vanillaPlayerControllable = false;
};

// Never suppress Link input without a live, matching Actor and an explicit
// user opt-in. A stale CVar alone must not steal the gamepad.
[[nodiscard]] constexpr bool ShouldRouteInputToGoemon(PilotInputGate gate) {
    return gate.pilotEnabled && gate.actorEnabled && gate.actorAlive &&
           gate.sceneMatches && gate.vanillaPlayerControllable;
}
} // namespace Goemon::Original
