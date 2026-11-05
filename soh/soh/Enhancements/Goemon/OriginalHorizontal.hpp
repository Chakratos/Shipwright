#pragma once
// Original horizontal speed magnitudes from real NG5E capture (2,375
// original updates across all 4 characters; 2026-11-05).
// This is NOT a complete steering controller. Direction, action selection,
// and collision response must come from separately verified original logic.
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace Goemon::Original {
inline constexpr float kOriginalFullRunSpeed = 2.8f;
inline constexpr float kOriginalGroundStartSpeed = 0.7f;
inline constexpr float kOriginalAirborneStartSpeed = 0.84f;
inline constexpr float kOriginalGroundRunAcceleration = 0.54f;
inline constexpr float kOriginalAirborneAcceleration = 0.84f;
inline constexpr float kOriginalRunReleaseSpeed = 2.0f;
inline constexpr float kOriginalBrakingStep = 0.6f;

struct OriginalHorizontalSpeed {
    float signedSpeed = 0.0f;

    void StartGroundedMotion() { signedSpeed = kOriginalGroundStartSpeed; }
    void StartAirborneMotion() { signedSpeed = kOriginalAirborneStartSpeed; }

    void ContinueGroundedRun() {
        if (!(signedSpeed >= 0.0f && std::isfinite(signedSpeed)))
            throw std::invalid_argument("expected nonnegative grounded run speed");
        signedSpeed = std::min(signedSpeed + kOriginalGroundRunAcceleration,
                               kOriginalFullRunSpeed);
    }
    void ContinueAirborneRun() {
        if (!(signedSpeed >= 0.0f && std::isfinite(signedSpeed)))
            throw std::invalid_argument("expected nonnegative airborne speed");
        signedSpeed = std::min(signedSpeed + kOriginalAirborneAcceleration,
                               kOriginalFullRunSpeed);
    }
    // All 5 observed transitions of original action 15 -> 16 begin at
    // 2.8 -> 2.0, followed by signed 0.6 decrements. Unlike an invented
    // "friction" law, it permits the observed one-update backward step.
    void BeginFullSpeedRelease() {
        if (std::abs(signedSpeed - kOriginalFullRunSpeed) > 0.012f)
            throw std::invalid_argument("release not observed below full original speed");
        signedSpeed = kOriginalRunReleaseSpeed;
    }
    void ContinueRelease() {
        if (!std::isfinite(signedSpeed))
            throw std::invalid_argument("nonfinite release speed");
        signedSpeed -= kOriginalBrakingStep;
    }
    // The original action/state controller must select idle: in one
    // capture the measured -0.4 motion persisted against geometry.
    void ResetForOriginalIdle() { signedSpeed = 0.0f; }
};

struct OriginalPlanarStep { float x; float z; };

// Unit heading is supplied by an independently established steering
// handler, NOT guessed from camera or raw controller axes.
[[nodiscard]] inline OriginalPlanarStep ComposeOriginalPlanarStep(
    const OriginalHorizontalSpeed& state, float dirX, float dirZ) {
    if (!(std::isfinite(dirX) && std::isfinite(dirZ)))
        throw std::invalid_argument("invalid original movement direction");
    const float length = std::hypot(dirX, dirZ);
    if (length < 1e-6f)
        throw std::invalid_argument("original movement heading is zero");
    return {state.signedSpeed * (dirX / length),
            state.signedSpeed * (dirZ / length)};
}

} // namespace Goemon::Original
