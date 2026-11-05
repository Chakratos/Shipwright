#pragma once
// Bridge from source-observed full-speed Goemon steering into the
// already isolated Zelda collision/motion boundary. No Link reskin.
// The original 1024-unit target yaw must come from the independent
// original camera/orientation adapter, not from a guessed stick mapping.
#include "OriginalMotionAdapter.hpp"
#include "OriginalSteering.hpp"
#include <cmath>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <utility>

namespace Goemon::Original {

struct OriginalSteeredFullSpeedPose {
    OriginalFlatGroundPose motion;
    OriginalPlanarStep previousDesiredVelocity{0.0f, 0.0f};
    bool hasReferenceVelocity = false;

    // Seed only from a verified full-speed original action.
    void SeedFullSpeedMotion(OriginalPlanarStep measuredOrVerifiedVelocity) {
        const float length = std::hypot(
            measuredOrVerifiedVelocity.x, measuredOrVerifiedVelocity.z);
        if (!std::isfinite(length) ||
            std::fabs(length - kOriginalSteeringFullSpeed) > 0.003f)
            throw std::invalid_argument("cannot seed steering from partial velocity");
        previousDesiredVelocity = measuredOrVerifiedVelocity;
        motion.horizontal.signedSpeed = kOriginalSteeringFullSpeed;
        hasReferenceVelocity = true;
    }
};

// No state mutation occurs if the original transition is unsupported.
// This controls both grounded/airborne directional blending; vertical
// stepping and collision resolution stay in OriginalMotionAdapter.hpp.
// World collision must return APPLIED displacement; a blocked step may
// preserve the original DESIRED velocity for the next update.
template<class Resolve>
[[nodiscard]] inline std::optional<OriginalMotionFrame>
AdvanceVerifiedOriginalSteeredFullSpeed(
    OriginalSteeredFullSpeedPose& state,
    const OriginalSteeringObservation& observation,
    std::int16_t currentOriginalRootYaw,
    bool beginJump,
    bool aButtonHeld,
    float originalJumpImpulse,
    Resolve&& resolve) {
    OriginalSteeringPhase steeringPhase{};
    if (!state.hasReferenceVelocity ||
        !TryClassifyOriginalFullSpeedSteering(observation, steeringPhase))
        return std::nullopt;
    const OriginalPlanarStep desired = SteerOriginalFullSpeed(
        state.previousDesiredVelocity, currentOriginalRootYaw, steeringPhase);
    OriginalMeasuredMotionInput command{};
    command.horizontalPhase = OriginalMeasuredPlanarPhase::Keep;
    command.headingX = desired.x;
    command.headingZ = desired.z;
    command.beginJump = beginJump;
    command.aButtonHeld = aButtonHeld;
    command.jumpImpulse = originalJumpImpulse;

    const OriginalMotionFrame result = AdvanceOriginalFlatGround(
        state.motion, command, std::forward<Resolve>(resolve));
    state.previousDesiredVelocity = result.desiredPlanar;
    return result;
}

} // namespace Goemon::Original
