#include "soh/soh/Enhancements/Goemon/OriginalZeldaWorldProbe.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <optional>
#include <stdexcept>

using namespace Goemon::Original;

static void Close(float got, float expected) {
    assert(std::fabs(got - expected) < 0.00001f);
}

int main() {
    int walls = 0;
    int floors = 0;
    // Normal Zelda scene: desired 2.8 world units on X, no wall, floor Y 10.
    const auto unobstructed = ProbeOriginalStepAgainstWorld(
        {1.0f, 10.0f, 3.0f}, {2.8f, 0.0f},
        [&](WorldPoint from, WorldPoint to) -> std::optional<WorldPoint> {
            ++walls;
            Close(from.x, 1.0f); Close(to.x, 3.8f);
            return std::nullopt;
        },
        [&](WorldPoint to) -> std::optional<float> {
            ++floors;
            Close(to.z, 3.0f);
            return 10.0f;
        });
    assert(walls == 1 && floors == 1);
    assert(!unobstructed.wallHit && unobstructed.floorFound);
    Close(unobstructed.floorHeight, 10.0f);
    Close(unobstructed.to.x, 3.8f);
    // Even on collision, original desired world movement is unchanged.
    const auto blocked = ProbeOriginalStepAgainstWorld(
        {1.0f, 10.0f, 3.0f}, {2.8f, 0.0f},
        [](WorldPoint from, WorldPoint) -> std::optional<WorldPoint> {
            return WorldPoint{from.x + 0.6f, from.y, from.z};
        },
        [](WorldPoint) -> std::optional<float> { return std::nullopt; });
    assert(blocked.wallHit && !blocked.floorFound);
    Close(blocked.desired.x, 2.8f);
    Close(blocked.wallContact.x, 1.6f);
    // No Zelda floor != fabricated ground height.
    assert(!blocked.floorFound);
    // Reject invalid original or Zelda inputs instead of corrupting game state.
    bool rejected = false;
    try {
        (void)ProbeOriginalStepAgainstWorld(
            {0.0f, 0.0f, 0.0f}, {INFINITY, 0.0f},
            [](auto, auto) -> std::optional<WorldPoint> { return std::nullopt; },
            [](auto) -> std::optional<float> { return 0.0f; });
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    rejected = false;
    try {
        (void)ProbeOriginalStepAgainstWorld(
            {0.0f, 0.0f, 0.0f}, {1.0f, 0.0f},
            [](auto, auto) -> std::optional<WorldPoint> { return std::nullopt; },
            [](auto) -> std::optional<float> { return NAN; });
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    std::puts("OriginalZeldaWorldProbe: desired vs wall/floor and invalid values PASS");
}
