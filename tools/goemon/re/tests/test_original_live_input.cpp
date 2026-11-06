// Provisional Ship-input bridge tests. These do NOT claim original Goemon
// camera control or partial-stick behavior; only the original motion core
// is independently measured on genuine NG5E traces.
#include "soh/soh/Enhancements/Goemon/OriginalLiveInput.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>

using namespace Goemon::Original;

int main() {
    const auto neutral = MapShipStickForOriginalPreview(0, 0, 0);
    assert(neutral.kind == ShipPreviewStickKind::Neutral);
    const auto partial = MapShipStickForOriginalPreview(30, 0, 0);
    assert(partial.kind == ShipPreviewStickKind::Unsupported);
    assert(!ComposeShipPreviewOriginalInput(partial, 0, 0, 0, false,
                                            false, false, 0.0f));

    const auto forward = MapShipStickForOriginalPreview(0, 85, 0);
    const auto right = MapShipStickForOriginalPreview(85, 0, 0);
    const auto back = MapShipStickForOriginalPreview(0, -85, 0);
    const auto cameraRight = MapShipStickForOriginalPreview(0, 85, 0x4000);
    assert(forward.kind == ShipPreviewStickKind::Full);
    assert(forward.y == 93 && forward.x == 0);
    assert(forward.provisionalOriginalYaw10 == 0);
    assert(right.provisionalOriginalYaw10 == 256 && right.x == 93);
    assert(back.provisionalOriginalYaw10 == 512);
    assert(cameraRight.provisionalOriginalYaw10 == 256);

    const auto diagonal = MapShipStickForOriginalPreview(62, 62, 0);
    assert(diagonal.kind == ShipPreviewStickKind::Full);
    assert(IsVerifiedOriginalFullStick(OriginalVectorInput{
        .stickX = diagonal.x, .stickY = diagonal.y}));

    OriginalVectorControllerState state{};
    state.motion.groundX = 30.0f;
    state.motion.groundZ = 40.0f;
    auto move = [](float, float, OriginalPlanarStep desired) { return desired; };
    auto input = ComposeShipPreviewOriginalInput(forward, 0, 0, 0,
                                                false, false, false, 0.0f);
    assert(input && input->action == 13);
    auto first = AdvanceMeasuredOriginalVectorController(state, *input, move);
    assert(first && std::fabs(first->desiredPlanar.z - 0.7f) < 0.00001f);
    std::uint8_t previous = 13;
    for (int i = 0; i < 4; ++i) {
        input = ComposeShipPreviewOriginalInput(forward, previous, 0, 93,
                                                false, false, false,
                                                state.motion.horizontal.signedSpeed);
        assert(input && input->action == 15);
        auto next = AdvanceMeasuredOriginalVectorController(state, *input, move);
        assert(next);
        previous = 15;
    }
    assert(std::fabs(state.motion.horizontal.signedSpeed - 2.8f) < 0.0001f);
    input = ComposeShipPreviewOriginalInput(neutral, previous, 0, 93,
                                            false, false, false, 2.8f);
    assert(input && input->action == 16);
    const auto brake = AdvanceMeasuredOriginalVectorController(state, *input, move);
    assert(brake && std::fabs(brake->desiredPlanar.z - 2.0f) < 0.0001f);
    assert(state.motion.groundX == 30.0f);

    // No active airborne direction means no invented horizontal law.
    assert(!ComposeShipPreviewOriginalInput(neutral, 23, 0, 0,
                                            true, false, false, 0.84f));
    std::puts("OriginalLiveInput: Ship adapter boundaries and real motion core PASS");
}
