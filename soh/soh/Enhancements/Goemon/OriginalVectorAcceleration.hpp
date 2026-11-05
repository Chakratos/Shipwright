#pragma once
// Original N64 Goemon acceleration also determines steering direction.
// Empirical NG5E, all four characters, 2026-11-05 genuine PlayerTask
// desired X/Z vectors (not collision-resolved world displacement).
// For continuous full-stick motion:
// ground: previous heading*(previousSpeed-0.30) + yawHeading*0.84;
// air:    previous heading* previousSpeed      + yawHeading*0.84.
// Normalize, then apply separately observed scalar acceleration/cap.
// Airborne abrupt stick turns can RESET to speed 0.84; landing and
// partial stick magnitudes require separate original-state handling.
#include "OriginalYaw.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>

namespace Goemon::Original {
inline constexpr float kOriginalVectorInputAcceleration = 0.84f;
inline constexpr float kOriginalGroundDirectionalDrag = 0.30f;

enum class OriginalVectorAccelerationMode : std::uint8_t {
    ContinuousGrounded, ContinuousAirborne
};

[[nodiscard]] inline OriginalPlanarStep BeginOriginalGroundMotion(
    std::int16_t targetYaw) {
    const auto direction = DirectionFromOriginalYaw(targetYaw);
    return {kOriginalGroundStartSpeed * direction.x,
            kOriginalGroundStartSpeed * direction.z};
}

[[nodiscard]] inline OriginalPlanarStep BeginOriginalAirMotion(
    std::int16_t targetYaw) {
    const auto direction = DirectionFromOriginalYaw(targetYaw);
    return {kOriginalAirborneStartSpeed * direction.x,
            kOriginalAirborneStartSpeed * direction.z};
}

// Precondition: this is a continuous original action with unchanged
// full-tilt stick direction, not the abrupt airborne reinitialization.
[[nodiscard]] inline OriginalPlanarStep ContinueOriginalVectorMotion(
    OriginalPlanarStep previousDesiredVelocity,
    std::int16_t currentTargetYaw,
    OriginalVectorAccelerationMode mode) {
    const float prevSpeed = std::hypot(
        previousDesiredVelocity.x, previousDesiredVelocity.z);
    if (!std::isfinite(prevSpeed) || prevSpeed > kOriginalFullRunSpeed + 0.003f)
        throw std::invalid_argument("original vector speed outside measured range");
    float remainingSpeed, nextSpeed;
    switch (mode) {
        case OriginalVectorAccelerationMode::ContinuousGrounded:
            if (prevSpeed <= kOriginalGroundDirectionalDrag + 0.00001f)
                throw std::invalid_argument("original ground continuation below drag threshold");
            remainingSpeed = prevSpeed - kOriginalGroundDirectionalDrag;
            nextSpeed = std::min(kOriginalFullRunSpeed,
                                 prevSpeed + kOriginalGroundRunAcceleration);
            break;
        case OriginalVectorAccelerationMode::ContinuousAirborne:
            if (prevSpeed <= 0.00001f)
                throw std::invalid_argument("original air continuation begins from rest");
            remainingSpeed = prevSpeed;
            nextSpeed = std::min(kOriginalFullRunSpeed,
                                 prevSpeed + kOriginalAirborneAcceleration);
            break;
        default:
            throw std::invalid_argument("unknown original acceleration mode");
    }
    const auto target = DirectionFromOriginalYaw(currentTargetYaw);
    const float combinedX =
        remainingSpeed * previousDesiredVelocity.x / prevSpeed
        + kOriginalVectorInputAcceleration * target.x;
    const float combinedZ =
        remainingSpeed * previousDesiredVelocity.z / prevSpeed
        + kOriginalVectorInputAcceleration * target.z;
    const float combinedLength = std::hypot(combinedX, combinedZ);
    if (combinedLength <= 0.000001f)
        throw std::invalid_argument("original target cancels previous heading");
    return {nextSpeed * combinedX / combinedLength,
            nextSpeed * combinedZ / combinedLength};
}

} // namespace Goemon::Original
