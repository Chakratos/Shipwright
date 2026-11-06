#pragma once
// Original physics measurement -> Zelda world boundary, FLAT-GROUND
// prototype. Requires a real collision resolver; does not substitute
// Link steering, camera logic or an unverified original action machine.
#include "OriginalHorizontal.hpp"
#include "OriginalJump.hpp"
#include <cmath>
#include <stdexcept>
#include <type_traits>

namespace Goemon::Original {

enum class OriginalMeasuredPlanarPhase {
    Keep, GroundBegin, AirBegin, GroundRun, AirRun,
    FullSpeedRelease, ReleaseNext, Idle, SuppressWhileActionLocked
};
struct OriginalMeasuredMotionInput {
    OriginalMeasuredPlanarPhase horizontalPhase = OriginalMeasuredPlanarPhase::Keep;
    float headingX = 0.0f;
    float headingZ = 0.0f;
    bool beginJump = false;
    bool aButtonHeld = false;
    float jumpImpulse = kOriginalNormalJumpImpulse;
};
struct OriginalFlatGroundPose {
    float groundX = 0.0f;
    float groundY = 0.0f;
    float groundZ = 0.0f;
    OriginalHorizontalSpeed horizontal;
    OriginalJumpState jump;
    [[nodiscard]] float ModelY() const { return groundY + jump.heightAboveGround; }
};
struct OriginalMotionFrame {
    OriginalPlanarStep desiredPlanar;
    OriginalPlanarStep appliedPlanar;
    float appliedVertical = 0.0f;
    float modelY = 0.0f;
    bool airborne = false;
};

// Resolver must return actual applied (X,Z) displacement after querying
// target geometry. In the original trace, desired Task motion often remains
// nonzero during collision with a blocking wall.
// Resolve(float x, float z, OriginalPlanarStep desired) -> OriginalPlanarStep
template<class Resolve>
[[nodiscard]] OriginalMotionFrame AdvanceOriginalFlatGround(
    OriginalFlatGroundPose& pose, const OriginalMeasuredMotionInput& input,
    Resolve&& resolve) {
    switch (input.horizontalPhase) {
        case OriginalMeasuredPlanarPhase::GroundBegin: pose.horizontal.StartGroundedMotion(); break;
        case OriginalMeasuredPlanarPhase::AirBegin: pose.horizontal.StartAirborneMotion(); break;
        case OriginalMeasuredPlanarPhase::GroundRun: pose.horizontal.ContinueGroundedRun(); break;
        case OriginalMeasuredPlanarPhase::AirRun: pose.horizontal.ContinueAirborneRun(); break;
        case OriginalMeasuredPlanarPhase::FullSpeedRelease: pose.horizontal.BeginFullSpeedRelease(); break;
        case OriginalMeasuredPlanarPhase::ReleaseNext: pose.horizontal.ContinueRelease(); break;
        case OriginalMeasuredPlanarPhase::Idle: pose.horizontal.ResetForOriginalIdle(); break;
        case OriginalMeasuredPlanarPhase::Keep:
        case OriginalMeasuredPlanarPhase::SuppressWhileActionLocked: break;
    }
    if (input.beginJump) BeginOriginalJump(pose.jump,input.jumpImpulse);
    const float dy = StepOriginalJump(pose.jump,input.aButtonHeld);
    OriginalPlanarStep desired{0.0f,0.0f};
    const bool locked = input.horizontalPhase ==
        OriginalMeasuredPlanarPhase::SuppressWhileActionLocked;
    if (!locked && std::abs(pose.horizontal.signedSpeed) > 1e-6f)
        desired = ComposeOriginalPlanarStep(pose.horizontal,input.headingX,input.headingZ);
    // New Zelda-Actor boundary may also request the original model's
    // current Y. Retain the existing 3-argument resolver contract for
    // source-only and previously validated native regression tests.
    OriginalPlanarStep actual{};
    if constexpr (std::is_invocable_v<Resolve&, float, float, float,
                                      OriginalPlanarStep>) {
        actual = resolve(pose.groundX,pose.ModelY(),pose.groundZ,desired);
    } else {
        actual = resolve(pose.groundX,pose.groundZ,desired);
    }
    if (!std::isfinite(actual.x) || !std::isfinite(actual.z))
        throw std::invalid_argument("collision returned nonfinite original position step");
    pose.groundX += actual.x;
    pose.groundZ += actual.z;
    return {desired,actual,dy,pose.ModelY(),pose.jump.airborne};
}

} // namespace Goemon::Original
