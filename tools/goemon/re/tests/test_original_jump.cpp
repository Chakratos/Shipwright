// Native regressions against genuine Goemon Original trace 2026-11-05.
// Synthetic expected numerical trajectories only; no original ROM/assets.
#include "soh/soh/Enhancements/Goemon/OriginalJump.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <stdexcept>

using namespace Goemon::Original;

void CheckJump(float impulse, int heldFrames, int expectedTicks,
               float expectedApex, float expectedFirstDelta,
               bool assertFullTrajectory = false) {
    OriginalJumpState state{};
    BeginOriginalJump(state, impulse);
    float apex = 0.0f;
    for (int tick = 0; tick < expectedTicks; ++tick) {
        assert(state.airborne);
        const float appliedDelta = StepOriginalJump(state, tick < heldFrames);
        if (tick == 0)
            assert(std::fabs(appliedDelta - expectedFirstDelta) < 1e-5f);
        apex = std::fmax(apex, state.heightAboveGround);
        if (assertFullTrajectory) {
            constexpr std::array<float, 19> kExpectedHeights = {
                6.0f, 11.333333f, 16.0f, 20.0f, 23.333333f, 26.0f,
                28.0f, 29.333333f, 30.0f, 30.0f, 29.333333f, 28.0f,
                26.0f, 23.333333f, 20.0f, 16.0f, 11.333333f, 6.0f, 0.0f,
            };
            assert(std::fabs(state.heightAboveGround - kExpectedHeights.at(tick)) < 0.001f);
        }
    }
    assert(!state.airborne);
    assert(state.heightAboveGround == 0.0f);
    assert(state.nextVerticalStep == 0.0f);
    assert(std::fabs(apex - expectedApex) < 0.001f);
    assert(StepOriginalJump(state, false) == 0.0f);
}

int main() {
    // Fully held normal jump (original sample indices 50..68, 680..698).
    CheckJump(6.0f, 19, 19, 30.0f, 6.0f, true);
    // A released after first step (indices 173..182).
    CheckJump(6.0f, 1, 10, 10.0f, 6.0f);
    // A released after third/fourth steps (1584..1598 and 277..292).
    CheckJump(6.0f, 3, 15, 20.0f, 6.0f);
    CheckJump(6.0f, 4, 16, 24.0f, 6.0f);
    // Recorded special low-impulse jump (2081..2087).
    CheckJump(2.0f, 7, 7, 4.0f, 2.0f);
    bool rejected = false;
    OriginalJumpState state{};
    try { BeginOriginalJump(state, 0.0f); }
    catch (std::invalid_argument const&) { rejected = true; }
    assert(rejected);
    BeginOriginalJump(state);
    rejected = false;
    try { BeginOriginalJump(state); }
    catch (std::logic_error const&) { rejected = true; }
    assert(rejected);
    std::puts("OriginalJump (measured real-game trajectories): PASS");
}
