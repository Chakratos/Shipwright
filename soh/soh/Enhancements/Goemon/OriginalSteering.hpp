#pragma once
// Measured from real NG5E Goemon64Recompiled trace, 2026-11-05.
// At 2.8 units/update, ground and airborne original turns are exact
// normalized blends with DISTINCT target-yaw factors.
// Applies only to verified consecutive same-character full-speed states.
// Camera-to-target-yaw and partial analog steering remain unresolved.
#include "OriginalYaw.hpp"
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace Goemon::Original {
inline constexpr float kOriginalGroundFullSpeedSteering = 0.336f;
inline constexpr float kOriginalAirFullSpeedSteering = 0.300f;
inline constexpr float kOriginalSteeringFullSpeed = 2.8f;

enum class OriginalSteeringPhase : std::uint8_t { GroundRun, Airborne };

[[nodiscard]] inline OriginalPlanarStep SteerOriginalFullSpeed(
    OriginalPlanarStep previousDesiredVelocity,
    std::int16_t currentOriginalRootYaw,
    OriginalSteeringPhase phase) {
    const float vx = previousDesiredVelocity.x;
    const float vz = previousDesiredVelocity.z;
    if (!std::isfinite(vx) || !std::isfinite(vz))
        throw std::invalid_argument("nonfinite original desired velocity");
    const float magnitude = std::hypot(vx, vz);
    if (std::fabs(magnitude - kOriginalSteeringFullSpeed) > 0.003f)
        throw std::invalid_argument("original steering is only calibrated at full speed");
    float ratio = 0.0f;
    switch (phase) {
        case OriginalSteeringPhase::GroundRun:
            ratio = kOriginalGroundFullSpeedSteering;
            break;
        case OriginalSteeringPhase::Airborne:
            ratio = kOriginalAirFullSpeedSteering;
            break;
        default:
            throw std::invalid_argument("unsupported original steering phase");
    }
    const OriginalPlanarStep yaw = DirectionFromOriginalYaw(currentOriginalRootYaw);
    const float directionX = vx / magnitude + ratio * yaw.x;
    const float directionZ = vz / magnitude + ratio * yaw.z;
    const float length = std::hypot(directionX, directionZ);
    if (length < 0.000001f)
        throw std::invalid_argument("original steering vector cancelled out");
    return {kOriginalSteeringFullSpeed * directionX / length,
            kOriginalSteeringFullSpeed * directionZ / length};
}

struct OriginalSteeringObservation {
    std::uint8_t previousAction = 0;
    std::uint8_t currentAction = 0;
    bool consecutiveGameUpdate = false;
    bool sameCharacter = false;
    bool analogActive = false;
};

[[nodiscard]] inline bool IsOriginalAirborneSteeringAction(std::uint8_t action) {
    return action == 23 || action == 25 || action == 26 || action == 28;
}

[[nodiscard]] inline bool TryClassifyOriginalFullSpeedSteering(
    const OriginalSteeringObservation& observation,
    OriginalSteeringPhase& result) {
    if (!observation.consecutiveGameUpdate || !observation.sameCharacter ||
        !observation.analogActive)
        return false;
    if (observation.previousAction == 15 && observation.currentAction == 15) {
        result = OriginalSteeringPhase::GroundRun;
        return true;
    }
    if (IsOriginalAirborneSteeringAction(observation.previousAction) &&
        IsOriginalAirborneSteeringAction(observation.currentAction)) {
        result = OriginalSteeringPhase::Airborne;
        return true;
    }
    return false;
}
} // namespace Goemon::Original
