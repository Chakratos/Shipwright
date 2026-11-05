#pragma once
// Positive model Object.animation_progress increments measured per original
// NG5E game update for 48 stable (character,action) pairs. This table is
// evidence, not a replacement for animation wraps, frame holds, rigs or
// weapon-specific original dispatch.
#include <array>
#include <cstdint>
#include <optional>
namespace Goemon::Original {
struct ObservedOriginalAnimationRate {
    std::uint8_t characterId;
    std::uint8_t actionId;
    float positiveProgressPerUpdate;
};
inline constexpr std::array<ObservedOriginalAnimationRate, 48> kObservedOriginalAnimationRates = {{
    {0, 0, 0.4f},
    {0, 15, 1.4f},
    {0, 17, 0.5f},
    {0, 25, 1.0f},
    {0, 26, 1.44f},
    {0, 28, 2.0f},
    {0, 88, 0.6f},
    {0, 89, 0.6f},
    {0, 90, 0.6f},
    {0, 93, 0.8f},
    {0, 112, 1.0f},
    {0, 114, 0.8f},
    {0, 124, 1.4f},
    {0, 127, 1.4f},
    {1, 0, 0.3f},
    {1, 15, 1.0f},
    {1, 17, 1.0f},
    {1, 26, 1.6f},
    {1, 28, 2.0f},
    {1, 88, 0.6f},
    {1, 89, 0.8f},
    {1, 90, 0.8f},
    {1, 93, 1.0f},
    {1, 140, 0.6f},
    {1, 142, 0.8f},
    {1, 143, 0.8f},
    {2, 0, 0.4f},
    {2, 15, 1.4f},
    {2, 16, 0.8f},
    {2, 25, 1.2f},
    {2, 28, 0.6f},
    {2, 88, 1.0f},
    {2, 89, 1.0f},
    {2, 90, 1.0f},
    {2, 91, 1.6f},
    {2, 93, 1.6f},
    {3, 0, 0.4f},
    {3, 15, 1.2f},
    {3, 17, 1.0f},
    {3, 23, 1.2f},
    {3, 25, 1.0f},
    {3, 26, 1.0f},
    {3, 28, 1.0f},
    {3, 88, 1.4f},
    {3, 89, 0.8f},
    {3, 90, 1.4f},
    {3, 93, 1.4f},
    {3, 163, 0.4f},
}};

[[nodiscard]] inline std::optional<float> LookupObservedOriginalAnimationRate(
    std::uint8_t characterId, std::uint8_t actionId) {
    for (const auto& row : kObservedOriginalAnimationRates)
        if (row.characterId == characterId && row.actionId == actionId)
            return row.positiveProgressPerUpdate;
    return std::nullopt;
}
} // namespace Goemon::Original
