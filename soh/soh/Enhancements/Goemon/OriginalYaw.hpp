#pragma once
// In stable original NG5E movement: root Object.rotation.y is a 10-bit
// heading. 18 independent original samples matched sin/cos direction
// within 0.00002 degrees. This does NOT recover the dynamic turning filter.
#include "OriginalHorizontal.hpp"
#include <cmath>
#include <cstdint>
#include <numbers>

namespace Goemon::Original {
inline constexpr std::uint16_t kOriginalYawMask = 0x03ff;
inline constexpr float kOriginalYawResolution = 1024.0f;

[[nodiscard]] inline OriginalPlanarStep DirectionFromOriginalYaw(
    std::int16_t originalRootYaw) {
    const std::uint16_t yaw =
        static_cast<std::uint16_t>(originalRootYaw) & kOriginalYawMask;
    const float angle = (
        2.0f * std::numbers::pi_v<float> * static_cast<float>(yaw)
    ) / kOriginalYawResolution;
    return {std::sin(angle), std::cos(angle)};
}
} // namespace Goemon::Original
