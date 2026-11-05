#pragma once
// Reconstructed from the genuine NG5E gameplay trace run-20261105-123100.
// Isolated deterministic, flat-ground VERTICAL jump stepping model.
// Not yet wired to Ship; this does not replace original collision logic.
// Observed PlayerTask float offsets: +0x6C (applied vertical step),
// +0xA4 (next vertical step); model Object.Y - root Object.Y = jump height.

#include <cmath>
#include <stdexcept>

namespace Goemon::Original {

inline constexpr float kOriginalNormalJumpImpulse = 6.0f;
inline constexpr float kOriginalEarlyReleaseVelocityCap = 2.0f;
inline constexpr float kOriginalJumpGravityPerUpdate = 2.0f / 3.0f;

struct OriginalJumpState {
    float heightAboveGround = 0.0f;
    float nextVerticalStep = 0.0f;
    float lastAppliedVerticalStep = 0.0f;
    bool airborne = false;
};

// In another captured area, original jumps also used initial impulse 2.0
// and peaked at height 4.0. The caller must select the initial impulse
// through independently verified environment/state logic.
inline void BeginOriginalJump(OriginalJumpState& state,
                              float measuredInitialImpulse = kOriginalNormalJumpImpulse) {
    if (!std::isfinite(measuredInitialImpulse) || measuredInitialImpulse <= 0.0f)
        throw std::invalid_argument("invalid original measured jump impulse");
    if (state.airborne)
        throw std::logic_error("cannot begin a ground jump while airborne");
    state.heightAboveGround = 0.0f;
    state.nextVerticalStep = measuredInitialImpulse;
    state.lastAppliedVerticalStep = 0.0f;
    state.airborne = true;
}

// One original simulation update; do NOT integrate by variable render delta.
// Early A release caps positive upward speed at 2.0. Gravity is -2/3
// per step. For flat-ground regressions, the final step is truncated
// to remaining height, and velocity is reset at ground contact.
[[nodiscard]] inline float StepOriginalJump(OriginalJumpState& state,
                                            bool aButtonHeld) {
    if (!state.airborne) {
        state.lastAppliedVerticalStep = 0.0f;
        return 0.0f;
    }
    float step = state.nextVerticalStep;
    if (!aButtonHeld && step > kOriginalEarlyReleaseVelocityCap)
        step = kOriginalEarlyReleaseVelocityCap;

    // Float roundoff can leave ~1e-6 height after the measured 19-step
    // arc. The original game resolves ground using geometry/collision;
    // this isolated FLAT-FLOOR regression uses 1e-4 contact tolerance.
    if (state.heightAboveGround + step <= 0.0001f) {
        step = -state.heightAboveGround;
        state.heightAboveGround = 0.0f;
        state.nextVerticalStep = 0.0f;
        state.airborne = false;
    } else {
        state.heightAboveGround += step;
        state.nextVerticalStep = step - kOriginalJumpGravityPerUpdate;
    }
    state.lastAppliedVerticalStep = step;
    return step;
}

} // namespace Goemon::Original
