#pragma once
// Partial measured action-ID -> original horizontal speed-phase bridge.
// Only action combinations directly seen in genuine original-game
// capture are classified. Anything else is UNKNOWN, not approximated.
#include "OriginalMotionAdapter.hpp"
#include <cmath>
#include <cstdint>
#include <optional>
namespace Goemon::Original {
struct OriginalObservedActionFrame {
    std::uint8_t previousAction = 0;
    std::uint8_t currentAction = 0;
    bool analogActive = false;
    bool sameStickDirection = false;
    bool consecutiveOriginalUpdate = false;
    float previousHorizontalMagnitude = 0.0f;
};

[[nodiscard]] inline std::optional<OriginalMeasuredPlanarPhase>
ClassifyVerifiedOriginalSpeedPhase(const OriginalObservedActionFrame& frame) {
    if (!frame.consecutiveOriginalUpdate ||
        !std::isfinite(frame.previousHorizontalMagnitude))
        return std::nullopt;
    const float speed = frame.previousHorizontalMagnitude;
    const auto action = frame.currentAction;
    if (frame.analogActive && action == 13 && speed < 0.01f)
        return OriginalMeasuredPlanarPhase::GroundBegin;
    if (frame.analogActive && action == 15 &&
        (frame.previousAction == 13 || frame.previousAction == 15) &&
        speed > 0.01f && speed < 2.788f)
        return OriginalMeasuredPlanarPhase::GroundRun;
    if (frame.analogActive && frame.sameStickDirection &&
        (action == 23 || action == 25 || action == 26 || action == 28) &&
        (frame.previousAction == 23 || frame.previousAction == 25 ||
         frame.previousAction == 26 || frame.previousAction == 28) &&
        speed > 0.01f && speed < 2.788f)
        return OriginalMeasuredPlanarPhase::AirRun;
    if (!frame.analogActive && action == 16 && frame.previousAction == 15 &&
        std::abs(speed - kOriginalFullRunSpeed) < 0.012f)
        return OriginalMeasuredPlanarPhase::FullSpeedRelease;
    if (!frame.analogActive && action == 16 && frame.previousAction == 16 &&
        (std::abs(speed - 2.0f) < 0.012f ||
         std::abs(speed - 1.4f) < 0.012f ||
         std::abs(speed - 0.8f) < 0.012f ||
         std::abs(speed - 0.2f) < 0.012f))
        return OriginalMeasuredPlanarPhase::ReleaseNext;
    return std::nullopt;
}
} // namespace Goemon::Original
