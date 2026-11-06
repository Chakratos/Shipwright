#pragma once
// CONSERVATIVE Zelda-world terrain adapter for the independent Goemon Actor.
// This is a provisional integration envelope, NOT original NG5E collision.
// The independently measured original velocity is never modified by this
// resolver: wall, missing floor and large height differences block position
// only. Original source capsule, wall slide and fall logic remain unknown.
#include "OriginalZeldaWorldProbe.hpp"

#include <initializer_list>
#include <cmath>
#include <optional>
#include <stdexcept>

namespace Goemon::Original {

enum class ZeldaTerrainReject {
    None, Wall, MissingFloor, StepTooHigh, DropTooDeep
};
struct ZeldaTerrainEnvelope {
    // Explicitly provisional Zelda-sized sample geometry, not NG5E data.
    float halfWidth = 5.0f;
    float footHeight = 5.0f;
    float chestHeight = 25.0f;
    float maxStepUp = 5.0f;
    float maxGroundDrop = 12.0f;
};
struct ZeldaTerrainResult {
    OriginalPlanarStep desired{};
    OriginalPlanarStep applied{};
    ZeldaTerrainReject rejection = ZeldaTerrainReject::None;
    bool wallHit = false;
    WorldPoint wallContact{};
    bool floorFound = false;
    float floorY = 0.0f;
    bool sampledFloorAtDestination = false;
};

// The "groundY" parameter is the current motion anchor: when jumping,
// modelY is higher but the decision about a floor step is against groundY.
// WallQuery(from,to) -> optional<WorldPoint>.
// FloorQuery(projected) -> optional<float>.
template <class WallQuery, class FloorQuery>
[[nodiscard]] inline ZeldaTerrainResult ProbeConservativeZeldaTerrain(
    WorldPoint modelPosition, float groundY, OriginalPlanarStep desired,
    bool airborne, const ZeldaTerrainEnvelope& envelope,
    WallQuery&& wallQuery, FloorQuery&& floorQuery) {
    if (!FiniteWorldPoint(modelPosition) || !std::isfinite(groundY) ||
        !std::isfinite(desired.x) || !std::isfinite(desired.z) ||
        !std::isfinite(envelope.halfWidth) ||
        !std::isfinite(envelope.footHeight) ||
        !std::isfinite(envelope.chestHeight) ||
        !std::isfinite(envelope.maxStepUp) ||
        !std::isfinite(envelope.maxGroundDrop) ||
        envelope.halfWidth < 0.0f || envelope.footHeight < 0.0f ||
        envelope.chestHeight <= envelope.footHeight ||
        envelope.maxStepUp < 0.0f || envelope.maxGroundDrop < 0.0f)
        throw std::invalid_argument("invalid Zelda prototype collision envelope");

    const WorldPoint target{modelPosition.x + desired.x, modelPosition.y,
                            modelPosition.z + desired.z};
    if (!FiniteWorldPoint(target))
        throw std::invalid_argument("Zelda prototype displacement overflow");

    ZeldaTerrainResult result{};
    result.desired = desired;
    const float len = std::hypot(desired.x, desired.z);
    if (!std::isfinite(len))
        throw std::invalid_argument("invalid Zelda prototype displacement norm");
    if (len > 0.000001f) {
        // Three parallel sweeps at two body heights. This is intentionally
        // more conservative than the old single center ray, but does not
        // pretend to reproduce a continuous cylinder collider.
        const float sideX = -desired.z / len * envelope.halfWidth;
        const float sideZ = desired.x / len * envelope.halfWidth;
        for (const float vertical : {envelope.footHeight, envelope.chestHeight}) {
            for (const float lateral : {-1.0f, 0.0f, 1.0f}) {
                const WorldPoint from{
                    modelPosition.x + sideX * lateral,
                    modelPosition.y + vertical,
                    modelPosition.z + sideZ * lateral
                };
                const WorldPoint to{
                    target.x + sideX * lateral,
                    target.y + vertical,
                    target.z + sideZ * lateral
                };
                if (!FiniteWorldPoint(from) || !FiniteWorldPoint(to))
                    throw std::invalid_argument("Zelda prototype envelope overflow");
                const std::optional<WorldPoint> contact =
                    wallQuery(from, to);
                if (contact) {
                    if (!FiniteWorldPoint(*contact))
                        throw std::invalid_argument("invalid Zelda wall contact");
                    result.wallHit = true;
                    result.wallContact = *contact;
                    result.rejection = ZeldaTerrainReject::Wall;
                    return result;
                }
            }
        }
    }

    const std::optional<float> floor =
        floorQuery(target);
    result.sampledFloorAtDestination = true;
    if (floor) {
        if (!std::isfinite(*floor))
            throw std::invalid_argument("invalid Zelda destination floor");
        result.floorFound = true;
        result.floorY = *floor;
    }

    // Airborne source motion is retained. Full jump-to-floor/ledge support
    // remains pending; never silently give it fabricated grounded status.
    if (!airborne) {
        if (!result.floorFound) {
            result.rejection = ZeldaTerrainReject::MissingFloor;
            return result;
        }
        if (result.floorY > groundY + envelope.maxStepUp) {
            result.rejection = ZeldaTerrainReject::StepTooHigh;
            return result;
        }
        if (result.floorY < groundY - envelope.maxGroundDrop) {
            result.rejection = ZeldaTerrainReject::DropTooDeep;
            return result;
        }
    }

    result.applied = desired;
    return result;
}
} // namespace Goemon::Original
