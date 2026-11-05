#pragma once
// Observed action-gated Goemon velocity controller. Exact numeric rules
// for the documented NG5E full-stick ground/air and braking transitions.
// Unknown action/partial-analog/landing/controller-camera states are
// rejected, not filled in with Link movement approximations.
#include "OriginalMotionAdapter.hpp"
#include "OriginalVectorAcceleration.hpp"
#include <cmath>
#include <cstdint>
#include <optional>
#include <utility>

namespace Goemon::Original {

enum class OriginalVectorAction {
    GroundStart, GroundContinue, AirStart, AirContinue,
    AirDirectionReset, BeginBrake, ContinueBrake
};

struct OriginalVectorInput {
    std::uint8_t previousAction = 0;
    std::uint8_t action = 0;
    bool continuousSameCharacterFrame = false;
    std::int16_t previousStickX = 0;
    std::int16_t previousStickY = 0;
    std::int16_t stickX = 0;
    std::int16_t stickY = 0;
    std::int16_t currentOriginalYaw = 0;
    bool beginJump = false;
    bool aButtonHeld = false;
    float jumpImpulse = kOriginalNormalJumpImpulse;
};

// The captured original controller contains only neutral or full-tilt
// stick readings (93 cardinal and 62/62 diagonal ~= 87.7 magnitude).
// Never apply calibrated full-tilt equations to intermediate analog
// magnitudes whose source behavior has not been measured.
[[nodiscard]] inline bool IsVerifiedOriginalFullStick(const OriginalVectorInput& frame) {
    const int x = static_cast<int>(frame.stickX);
    const int y = static_cast<int>(frame.stickY);
    const int lengthSquared = x * x + y * y;
    return lengthSquared >= 85 * 85 && lengthSquared <= 96 * 96;
}
[[nodiscard]] inline bool IsOriginalNeutralStick(const OriginalVectorInput& frame) {
    return std::abs(static_cast<int>(frame.stickX)) < 15 &&
           std::abs(static_cast<int>(frame.stickY)) < 15;
}
[[nodiscard]] inline bool OriginalStickChanged(const OriginalVectorInput& frame) {
    return frame.stickX != frame.previousStickX ||
           frame.stickY != frame.previousStickY;
}

[[nodiscard]] inline std::optional<OriginalVectorAction>
ClassifyOriginalVectorAction(const OriginalVectorInput& frame,
                             float priorDesiredSpeed) {
    if (!frame.continuousSameCharacterFrame ||
        !std::isfinite(priorDesiredSpeed))
        return std::nullopt;
    const bool active = IsVerifiedOriginalFullStick(frame);
    const bool neutral = IsOriginalNeutralStick(frame);
    if (!active && !neutral)
        return std::nullopt; // Unmeasured analog magnitude: never invent input law.
    if (active && frame.action == 13 && priorDesiredSpeed < 0.01f)
        return OriginalVectorAction::GroundStart;
    if (active && frame.action == 15 &&
        (frame.previousAction == 13 || frame.previousAction == 15) &&
        priorDesiredSpeed > 0.30001f)
        return OriginalVectorAction::GroundContinue;
    if (active && frame.action == 23 && priorDesiredSpeed < 0.01f)
        return OriginalVectorAction::AirStart;
    // On identical airborne action with a fresh stick direction, the
    // original reinitializes movement to 0.84 at current yaw.
    if (active && frame.action == frame.previousAction &&
        (frame.action == 23 || frame.action == 25 || frame.action == 26) &&
        OriginalStickChanged(frame))
        return OriginalVectorAction::AirDirectionReset;
    if (active &&
        (frame.action == 23 || frame.action == 25 || frame.action == 26) &&
        (frame.previousAction == 23 || frame.previousAction == 25 ||
         frame.previousAction == 26 || frame.previousAction == 15) &&
        !OriginalStickChanged(frame) && priorDesiredSpeed > 0.00001f)
        return OriginalVectorAction::AirContinue;
    if (neutral && frame.action == 16 && frame.previousAction == 15 &&
        std::fabs(priorDesiredSpeed - kOriginalFullRunSpeed) < 0.012f)
        return OriginalVectorAction::BeginBrake;
    if (neutral && frame.action == 16 && frame.previousAction == 16 &&
        priorDesiredSpeed > 0.00001f)
        return OriginalVectorAction::ContinueBrake;
    return std::nullopt;
}

struct OriginalVectorControllerState {
    OriginalFlatGroundPose motion;
    OriginalPlanarStep previousDesiredVelocity{0.0f,0.0f};
    OriginalPlanarStep brakingHeading{0.0f,0.0f};
    float signedBrakeSpeed = 0.0f;
    bool hasPrior = false;
    bool braking = false;
};

// Called at the original fixed game-update cadence. One unsupported
// transition leaves the state completely unchanged for an external
// original-action handler; it does not silently apply Link-style physics.
template <class Resolve>
[[nodiscard]] inline std::optional<OriginalMotionFrame>
AdvanceMeasuredOriginalVectorController(
    OriginalVectorControllerState& state, const OriginalVectorInput& input,
    Resolve&& resolve) {
    const float priorSpeed = state.hasPrior
        ? std::hypot(state.previousDesiredVelocity.x,
                     state.previousDesiredVelocity.z) : 0.0f;
    const auto phase = ClassifyOriginalVectorAction(input, priorSpeed);
    if (!phase) return std::nullopt;

    OriginalPlanarStep next{0.0f, 0.0f};
    switch (*phase) {
        case OriginalVectorAction::GroundStart:
            next = BeginOriginalGroundMotion(input.currentOriginalYaw);
            state.braking = false;
            break;
        case OriginalVectorAction::GroundContinue:
            next = ContinueOriginalVectorMotion(
                state.previousDesiredVelocity,input.currentOriginalYaw,
                OriginalVectorAccelerationMode::ContinuousGrounded);
            state.braking = false;
            break;
        case OriginalVectorAction::AirStart:
        case OriginalVectorAction::AirDirectionReset:
            next = BeginOriginalAirMotion(input.currentOriginalYaw);
            state.braking = false;
            break;
        case OriginalVectorAction::AirContinue:
            next = ContinueOriginalVectorMotion(
                state.previousDesiredVelocity,input.currentOriginalYaw,
                OriginalVectorAccelerationMode::ContinuousAirborne);
            state.braking = false;
            break;
        case OriginalVectorAction::BeginBrake:
            state.brakingHeading = {
                state.previousDesiredVelocity.x/priorSpeed,
                state.previousDesiredVelocity.z/priorSpeed
            };
            state.signedBrakeSpeed = kOriginalRunReleaseSpeed;
            state.braking = true;
            next = {
                state.brakingHeading.x*state.signedBrakeSpeed,
                state.brakingHeading.z*state.signedBrakeSpeed
            };
            break;
        case OriginalVectorAction::ContinueBrake:
            // Only four successive -0.6 braking steps are evidenced
            // (2.0 -> 1.4 -> 0.8 -> 0.2 -> -0.4).
            // The final negative step may then persist against a wall.
            // Do not invent unlimited backwards acceleration.
            if (!state.braking || state.signedBrakeSpeed < 0.19f)
                return std::nullopt;
            state.signedBrakeSpeed -= kOriginalBrakingStep;
            next = {
                state.brakingHeading.x*state.signedBrakeSpeed,
                state.brakingHeading.z*state.signedBrakeSpeed
            };
            break;
    }

    // OriginalMotionAdapter multiplies signed speed by heading.
    // Here we supply the signed direction explicitly and keep the
    // desired velocity independent from collision-resolved position.
    const float scalar = std::hypot(next.x,next.z);
    const bool negativeBraking =
        state.braking && state.signedBrakeSpeed < 0.0f;
    state.motion.horizontal.signedSpeed =
        negativeBraking ? -scalar : scalar;
    OriginalMeasuredMotionInput command{};
    command.horizontalPhase = OriginalMeasuredPlanarPhase::Keep;
    command.headingX = negativeBraking ? -next.x : next.x;
    command.headingZ = negativeBraking ? -next.z : next.z;
    command.beginJump = input.beginJump;
    command.aButtonHeld = input.aButtonHeld;
    command.jumpImpulse = input.jumpImpulse;

    const OriginalMotionFrame result = AdvanceOriginalFlatGround(
        state.motion,command,std::forward<Resolve>(resolve));
    state.previousDesiredVelocity = result.desiredPlanar;
    state.hasPrior = true;
    return result;
}

} // namespace Goemon::Original
