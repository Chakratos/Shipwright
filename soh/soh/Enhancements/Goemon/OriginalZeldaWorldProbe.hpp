#pragma once
// Strictly observational integration boundary between original Goemon
// desired motion and Ship of Harkinian's collision queries.
// NO guessed wall radius, step-up, floor tolerance, or Link physics.
// Source frame and current target heading are supplied by the caller.
#include "OriginalHorizontal.hpp"
#include <cmath>
#include <optional>
#include <stdexcept>
#include <utility>

namespace Goemon::Original {

struct WorldPoint {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
};
struct WorldCollisionProbe {
    WorldPoint from;
    WorldPoint to;
    OriginalPlanarStep desired;
    bool wallHit = false;
    WorldPoint wallContact{};
    bool floorFound = false;
    float floorHeight = 0.0f;
};
[[nodiscard]] inline bool FiniteWorldPoint(WorldPoint p) {
    return std::isfinite(p.x) && std::isfinite(p.y) && std::isfinite(p.z);
}

// WallQuery(from, to) returns optional<WorldPoint> of hit intersection.
// FloorQuery(to) returns optional<float> of floor Y.
// Both queries are delegated to the LIVE Zelda CollisionContext.
// Returned desired movement is never silently treated as applied motion.
template <class WallQuery, class FloorQuery>
[[nodiscard]] WorldCollisionProbe ProbeOriginalStepAgainstWorld(
    WorldPoint current, OriginalPlanarStep desired,
    WallQuery&& wallQuery, FloorQuery&& floorQuery) {
    if (!FiniteWorldPoint(current) ||
        !std::isfinite(desired.x) || !std::isfinite(desired.z))
        throw std::invalid_argument("nonfinite Goemon-to-Ship world probe");
    WorldCollisionProbe sample{};
    sample.from = current;
    sample.desired = desired;
    sample.to = {current.x + desired.x, current.y, current.z + desired.z};
    if (!FiniteWorldPoint(sample.to))
        throw std::invalid_argument("Goemon projected position overflow");
    std::optional<WorldPoint> hit =
        std::forward<WallQuery>(wallQuery)(sample.from, sample.to);
    if (hit) {
        if (!FiniteWorldPoint(*hit))
            throw std::invalid_argument("Zelda collision returned invalid wall contact");
        sample.wallHit = true;
        sample.wallContact = *hit;
    }
    std::optional<float> floor =
        std::forward<FloorQuery>(floorQuery)(sample.to);
    if (floor) {
        if (!std::isfinite(*floor))
            throw std::invalid_argument("Zelda collision returned invalid floor");
        sample.floorFound = true;
        sample.floorHeight = *floor;
    }
    return sample;
}

} // namespace Goemon::Original
