#include "soh/soh/Enhancements/Goemon/OriginalPilotCamera.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>

using namespace Goemon::Original;
static void Close(float a, float b) { assert(std::fabs(a-b) < 0.00001f); }

int main() {
    const auto view = TranslatePilotCamera(
        {0.0f, 80.0f, -120.0f}, {0.0f, 30.0f, 0.0f},
        {100.0f, 20.0f, 200.0f}, {122.0f, 25.0f, 194.0f});
    Close(view.eye.x, 22.0f);
    Close(view.eye.y, 85.0f);
    Close(view.eye.z, -126.0f);
    Close(view.lookAt.x, 22.0f);
    Close(view.lookAt.y, 35.0f);
    Close(view.lookAt.z, -6.0f);
    // Preserve vanilla distance, angle and relative view orientation.
    Close(view.eye.x-view.lookAt.x, 0.0f);
    Close(view.eye.y-view.lookAt.y, 50.0f);
    Close(view.eye.z-view.lookAt.z, -120.0f);
    const auto same = TranslatePilotCamera(
        {1.0f, 2.0f, 3.0f}, {4.0f, 5.0f, 6.0f},
        {0.0f, 0.0f, 0.0f}, {0.0f, 0.0f, 0.0f});
    Close(same.eye.x, 1.0f);
    Close(same.lookAt.z, 6.0f);

    bool invalid = false;
    try {
        (void)TranslatePilotCamera(
            {NAN, 1.0f, 1.0f}, {}, {}, {});
    } catch (const std::invalid_argument&) { invalid = true; }
    assert(invalid);
    invalid = false;
    try {
        constexpr float kHuge = std::numeric_limits<float>::max();
        (void)TranslatePilotCamera(
            {kHuge, 0, 0}, {}, {-kHuge, 0, 0}, {kHuge, 0, 0});
    } catch (const std::invalid_argument&) { invalid = true; }
    assert(invalid);

    // Camera draw may execute multiple times without a camera update.
    // Repeated pilot draws must NOT accumulate translations.
    PilotCameraHistory history{};
    const PilotCameraView source{
        {0.0f, 80.0f, -120.0f},
        {0.0f, 30.0f, 0.0f}
    };
    const WorldPoint link{100.0f, 20.0f, 200.0f};
    const WorldPoint actor{122.0f, 25.0f, 194.0f};
    const auto first = history.Render(source, link, actor);
    const auto repeat = history.Render(first, link, actor);
    assert(SamePilotView(first, repeat));
    const auto changedActor = history.Render(
        repeat, link, {130.0f, 25.0f, 194.0f});
    Close(changedActor.eye.x, 30.0f); // Not 22+30!
    const auto restored = history.Restore(changedActor);
    assert(restored && SamePilotView(*restored, source));
    const auto fresh = history.Render(source, link, actor);
    assert(SamePilotView(fresh, first));
    const PilotCameraView externallyUpdated{
        {5.0f, 90.0f, -90.0f},
        {5.0f, 40.0f, 30.0f}
    };
    const auto afterCameraUpdate = history.Render(externallyUpdated, link, actor);
    Close(afterCameraUpdate.eye.x, 27.0f);
    Close(afterCameraUpdate.lookAt.z, 24.0f);
    assert(!history.Restore(source)); // Do not clobber an external camera update.
    assert(!history.sourceView && !history.renderedView);

    // Invalid camera input must not poison the last valid render history.
    PilotCameraHistory cameraAfterError{};
    const auto good = cameraAfterError.Render(source, link, actor);
    bool failedRender = false;
    try {
        (void)cameraAfterError.Render(
            good, link, {NAN, 25.0f, 194.0f});
    } catch (const std::invalid_argument&) { failedRender = true; }
    assert(failedRender);
    const auto recovered = cameraAfterError.Render(good, link, actor);
    assert(SamePilotView(recovered, good));

    PilotInputGate gate{};
    assert(!ShouldRouteInputToGoemon(gate));
    gate = {true, true, true, true, true};
    assert(ShouldRouteInputToGoemon(gate));
    gate.actorAlive = false;
    assert(!ShouldRouteInputToGoemon(gate));
    gate.actorAlive = true;
    gate.vanillaPlayerControllable = false;
    assert(!ShouldRouteInputToGoemon(gate));
    gate.vanillaPlayerControllable = true;
    gate.sceneMatches = false;
    assert(!ShouldRouteInputToGoemon(gate));
    gate.sceneMatches = true;
    gate.actorEnabled = false;
    assert(!ShouldRouteInputToGoemon(gate));
    gate.actorEnabled = true;
    gate.pilotEnabled = false;
    assert(!ShouldRouteInputToGoemon(gate));
    std::puts("OriginalPilotCamera: view translation, finite checks, pilot gating PASS");
}
