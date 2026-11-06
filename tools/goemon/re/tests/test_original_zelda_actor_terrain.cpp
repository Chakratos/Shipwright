// Zelda Actor six-ray diagnostic collision. Not original Goemon hull.
#include "soh/soh/Enhancements/Goemon/OriginalZeldaActorTerrain.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
#include <optional>
#include <stdexcept>
using namespace Goemon::Original;
static void Near(float x, float y) { assert(std::fabs(x-y) < 0.0001f); }
int main() {
    ZeldaTerrainEnvelope env{};
    const WorldPoint at{1.0f, 10.0f, 2.0f};
    const OriginalPlanarStep right{2.8f, 0.0f};
    int walls = 0;
    auto clear = [&](WorldPoint from, WorldPoint to) -> std::optional<WorldPoint> {
        assert(from.y == to.y);
        ++walls;
        return std::nullopt;
    };
    auto floor = [](WorldPoint projected) -> std::optional<float> {
        Near(projected.x, 3.8f);
        return 10.0f;
    };
    const auto free = ProbeConservativeZeldaTerrain(
        at, 10.0f, right, false, env, clear, floor);
    assert(walls == 6);
    assert(free.rejection == ZeldaTerrainReject::None);
    assert(free.floorFound && free.sampledFloorAtDestination);
    Near(free.applied.x, 2.8f);

    // The outer side ray detects a wall missed by the old central ray.
    int count = 0;
    const auto sideWall = ProbeConservativeZeldaTerrain(
        at, 10.0f, right, false, env,
        [&](WorldPoint from, WorldPoint) -> std::optional<WorldPoint> {
            ++count;
            if (std::fabs(from.z - (at.z - env.halfWidth)) < 0.001f)
                return WorldPoint{at.x+0.3f, from.y, from.z};
            return std::nullopt;
        }, floor);
    assert(count == 1);
    assert(sideWall.wallHit && sideWall.rejection == ZeldaTerrainReject::Wall);
    Near(sideWall.applied.x, 0.0f);
    Near(sideWall.desired.x, 2.8f);

    // Height-specific ray: obstruction at chest height only.
    const auto upperWall = ProbeConservativeZeldaTerrain(
        at, 10.0f, right, true, env,
        [](WorldPoint from, WorldPoint) -> std::optional<WorldPoint> {
            if (from.y > 30.0f) return from;
            return std::nullopt;
        }, floor);
    assert(upperWall.wallHit);
    assert(upperWall.rejection == ZeldaTerrainReject::Wall);

    auto floorAt = [&](std::optional<float> y, bool air) {
        return ProbeConservativeZeldaTerrain(
            at, 10.0f, right, air, env, clear,
            [&](WorldPoint) -> std::optional<float> { return y; });
    };
    const auto gap = floorAt(std::nullopt, false);
    assert(gap.rejection == ZeldaTerrainReject::MissingFloor);
    assert(!gap.floorFound);
    Near(gap.applied.x, 0.0f);
    assert(floorAt(16.0f, false).rejection == ZeldaTerrainReject::StepTooHigh);
    assert(floorAt(-3.0f, false).rejection == ZeldaTerrainReject::DropTooDeep);
    const auto climb = floorAt(15.0f, false);
    assert(climb.rejection == ZeldaTerrainReject::None);
    Near(climb.applied.x, 2.8f);
    const auto airGap = floorAt(std::nullopt, true);
    assert(airGap.rejection == ZeldaTerrainReject::None);
    Near(airGap.applied.x, 2.8f);

    // Still probe floor while stationary; never report invented wall contact.
    const auto stand = ProbeConservativeZeldaTerrain(
        at, 10.0f, {0.0f, 0.0f}, false, env, clear,
        [](WorldPoint) -> std::optional<float> { return 10.0f; });
    assert(!stand.wallHit);
    assert(stand.rejection == ZeldaTerrainReject::None);

    bool rejected = false;
    try {
        ZeldaTerrainEnvelope bad{};
        bad.halfWidth = -1.0f;
        (void)ProbeConservativeZeldaTerrain(at, 10.0f, right,
                                            false, bad, clear, floor);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    rejected = false;
    try {
        (void)ProbeConservativeZeldaTerrain(
            at, 10.0f, right, false, env,
            [](WorldPoint, WorldPoint) -> std::optional<WorldPoint> {
                return WorldPoint{NAN, 0.0f, 0.0f};
            }, floor);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    rejected = false;
    try {
        (void)floorAt(std::numeric_limits<float>::infinity(), false);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    std::puts("OriginalZeldaActorTerrain: 6 sweeps, floor gates, air and validation PASS");
}
