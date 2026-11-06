// Source-measured NG5E motion shared by diagnostic ghost and native Actor.
// Input and camera conversion remain explicitly provisional.
#include "soh/soh/Enhancements/Goemon/OriginalLiveFrame.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <stdexcept>

using namespace Goemon::Original;
static void Near(float actual, float expected) {
    assert(std::fabs(actual - expected) < 0.0001f);
}
int main() {
    auto pass = [](float, float, OriginalPlanarStep desired) { return desired; };
    const auto full = MapShipStickForOriginalPreview(0, 85, 0);
    const auto unsupported = MapShipStickForOriginalPreview(30, 0, 0);
    const auto neutral = MapShipStickForOriginalPreview(0, 0, 0);
    OriginalLiveFrameState state{};
    state.controller.motion.groundX = 12.0f;
    state.controller.motion.groundY = 5.0f;
    state.controller.motion.groundZ = 30.0f;

    auto first = AdvanceOriginalLivePreview(state, full, false, false, pass);
    assert(first.measuredTransitionSupported && first.action == 13);
    Near(first.motion.desiredPlanar.z, 0.7f);
    Near(state.controller.motion.groundZ, 30.7f);

    for (int i = 0; i < 4; ++i) {
        auto move = AdvanceOriginalLivePreview(state, full, false, false, pass);
        assert(move.measuredTransitionSupported && move.action == 15);
    }
    Near(state.controller.motion.horizontal.signedSpeed, 2.8f);
    const auto brake = AdvanceOriginalLivePreview(state, neutral, false, false, pass);
    assert(brake.measuredTransitionSupported && brake.action == 16);
    Near(brake.motion.desiredPlanar.z, 2.0f);

    const auto blocked = AdvanceOriginalLivePreview(state, unsupported, false, false, pass);
    assert(!blocked.measuredTransitionSupported);
    Near(blocked.motion.desiredPlanar.z, 0.0f);
    assert(state.previousAction == 0);
    const auto restarted = AdvanceOriginalLivePreview(state, full, false, false, pass);
    assert(restarted.measuredTransitionSupported && restarted.action == 13);
    Near(restarted.motion.desiredPlanar.z, 0.7f);

    const auto oldZ = state.controller.motion.groundZ;
    const auto oldAction = state.previousAction;
    try {
        (void)AdvanceOriginalLivePreview(
            state, full, false, false,
            [](float, float, OriginalPlanarStep) -> OriginalPlanarStep {
                throw std::runtime_error("synthetic collision resolver failed");
            });
        assert(false);
    } catch (const std::runtime_error&) {
        Near(state.controller.motion.groundZ, oldZ);
        assert(state.previousAction == oldAction);
    }

    OriginalLiveFrameState jumpState{};
    jumpState.controller.motion.groundY = 12.0f;
    float sampledJumpHeight = -1.0f;
    const auto withModelY = [&](float, float modelY, float,
                                OriginalPlanarStep desired) {
        sampledJumpHeight = modelY;
        return desired;
    };
    const auto jumping = AdvanceOriginalLivePreview(
        jumpState, neutral, true, true, withModelY);
    assert(!jumping.measuredTransitionSupported);
    assert(jumping.motion.airborne);
    Near(jumping.motion.modelY, 18.0f);
    Near(sampledJumpHeight, 18.0f);
    const auto rising = AdvanceOriginalLivePreview(jumpState, neutral, false, false, pass);
    assert(rising.motion.airborne);
    assert(rising.motion.modelY > 18.0f);
    std::puts("OriginalLiveFrame: start, run, brake, fallback, rollback, jump PASS");
}
