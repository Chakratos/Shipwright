#pragma once
// Shared deterministic NG5E-measured motion driver for Ship prototypes.
// Ship stick/camera yaw and action dispatch are provisional; only sampled
// original movement phases and the independent jump arc are source-derived.
#include "OriginalLiveInput.hpp"

#include <cmath>
#include <cstdint>
#include <optional>
#include <utility>

namespace Goemon::Original {
struct OriginalLiveFrameState {
    OriginalVectorControllerState controller{};
    std::uint8_t previousAction = 0;
    std::int16_t previousStickX = 0;
    std::int16_t previousStickY = 0;
};
struct OriginalLiveFrameResult {
    OriginalMotionFrame motion{};
    std::uint8_t action = 0;
    bool measuredTransitionSupported = false;
};

// Transactional update: if the collision resolver rejects a frame or
// throws, no source-controller state changes are committed. The owning
// Actor or diagnostic must reset state when entering unsupported gameplay.
template <class Resolve>
[[nodiscard]] inline OriginalLiveFrameResult AdvanceOriginalLivePreview(
    OriginalLiveFrameState& state, const ShipPreviewStick& stick,
    bool jumpPressed, bool jumpHeld, Resolve&& resolve) {
    OriginalLiveFrameState candidate = state;
    const float priorSpeed = std::hypot(
        candidate.controller.previousDesiredVelocity.x,
        candidate.controller.previousDesiredVelocity.z);
    const bool wasAirborne = candidate.controller.motion.jump.airborne;
    const auto input = ComposeShipPreviewOriginalInput(
        stick, candidate.previousAction,
        candidate.previousStickX, candidate.previousStickY,
        wasAirborne, jumpPressed, jumpHeld, priorSpeed);

    if (jumpPressed && !wasAirborne)
        BeginOriginalJump(candidate.controller.motion.jump);

    OriginalLiveFrameResult result{};
    std::optional<OriginalMotionFrame> moved;
    if (input) {
        moved = AdvanceMeasuredOriginalVectorController(
            candidate.controller, *input, resolve);
        result.action = input->action;
    }
    result.measuredTransitionSupported = moved.has_value();
    if (moved) {
        candidate.previousAction = result.action;
    } else {
        // No guessed horizontal motion for unmeasured phases. Still step
        // the separately measured, flat-floor vertical jump model.
        candidate.controller.previousDesiredVelocity = {};
        candidate.controller.hasPrior = false;
        candidate.controller.braking = false;
        candidate.controller.motion.horizontal.ResetForOriginalIdle();
        OriginalMeasuredMotionInput idle{};
        idle.horizontalPhase =
            OriginalMeasuredPlanarPhase::SuppressWhileActionLocked;
        idle.aButtonHeld = jumpHeld;
        moved = AdvanceOriginalFlatGround(
            candidate.controller.motion, idle, resolve);
        candidate.previousAction = 0;
    }
    candidate.previousStickX = stick.x;
    candidate.previousStickY = stick.y;
    result.motion = *moved;
    state = candidate;
    return result;
}
} // namespace Goemon::Original
