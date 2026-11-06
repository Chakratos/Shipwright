#pragma once
// Camera translation for the independent Goemon Actor pilot.
// SHIP CAMERA ADAPTER ONLY: reuses vanilla Link camera orientation/zoom
// and moves its rendered viewpoint to the independent Actor. This does not
// reproduce the original Goemon camera, collision or animation.
#include "OriginalZeldaWorldProbe.hpp"

#include <optional>
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

// At high render rates there can be multiple Play_Draw calls for one
// Camera_Update. Never add the Actor translation on top of our own
// previously translated View: that would make the camera drift away.
[[nodiscard]] inline bool SamePilotView(const PilotCameraView& a,
                                       const PilotCameraView& b) {
    return a.eye.x == b.eye.x && a.eye.y == b.eye.y &&
           a.eye.z == b.eye.z && a.lookAt.x == b.lookAt.x &&
           a.lookAt.y == b.lookAt.y && a.lookAt.z == b.lookAt.z;
}

struct PilotCameraHistory {
    std::optional<PilotCameraView> sourceView;
    std::optional<PilotCameraView> renderedView;

    [[nodiscard]] PilotCameraView Render(PilotCameraView observed,
                                        WorldPoint link, WorldPoint actor) {
        const PilotCameraView source =
            renderedView && sourceView && SamePilotView(observed, *renderedView)
                ? *sourceView : observed;
        const PilotCameraView output =
            TranslatePilotCamera(source.eye, source.lookAt, link, actor);
        sourceView = source;
        renderedView = output;
        return output;
    }

    // Restore the last known vanilla view only when nobody else has
    // overwritten it since our last render. Avoid touching debug cam.
    [[nodiscard]] std::optional<PilotCameraView> Restore(
        PilotCameraView observed) {
        std::optional<PilotCameraView> restored;
        if (renderedView && sourceView && SamePilotView(observed, *renderedView))
            restored = sourceView;
        sourceView.reset();
        renderedView.reset();
        return restored;
    }

    void Reset() {
        sourceView.reset();
        renderedView.reset();
    }
};

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
