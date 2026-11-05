// Original source-observed action-gated vector controller, no Zelda build needed.
#include "soh/soh/Enhancements/Goemon/OriginalVectorController.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
using namespace Goemon::Original;
static void Close(float a,float b,float tol=0.0015f) {
    assert(std::fabs(a-b)<tol);
}
int main() {
    OriginalVectorControllerState ground{};
    const auto unblocked=[](float,float,OriginalPlanarStep step) {return step;};
    const auto blocked=[](float,float,OriginalPlanarStep) {
        return OriginalPlanarStep{0.0f,0.0f};
    };
    OriginalVectorInput cmd{};
    cmd.continuousSameCharacterFrame=true;
    cmd.stickX=93;
    cmd.currentOriginalYaw=256;
    cmd.previousAction=0;
    cmd.action=13;
    auto first=AdvanceMeasuredOriginalVectorController(ground,cmd,unblocked);
    assert(first);
    Close(first->desiredPlanar.x,0.70f);
    cmd.previousAction=13;cmd.action=15;cmd.previousStickX=93;
    for(float expected: {1.24f,1.78f,2.32f,2.80f}) {
        auto step=AdvanceMeasuredOriginalVectorController(ground,cmd,unblocked);
        assert(step);
        Close(std::hypot(step->desiredPlanar.x,step->desiredPlanar.z),expected);
    }
    Close(ground.motion.groundX,8.84f);
    // Stable original desired 2.8, while a wall prevents world movement.
    cmd.previousAction=15;cmd.action=15;
    const float x=ground.motion.groundX;
    auto wall=AdvanceMeasuredOriginalVectorController(ground,cmd,blocked);
    assert(wall);
    Close(ground.motion.groundX,x);
    Close(std::hypot(wall->desiredPlanar.x,wall->desiredPlanar.z),2.8f);
    // Real release phases: 2.8 -> 2.0 -> 1.4 -> .8 -> .2 -> -.4.
    cmd.stickX=0;cmd.action=16;cmd.previousAction=15;
    auto release=AdvanceMeasuredOriginalVectorController(ground,cmd,unblocked);
    assert(release);
    Close(ground.previousDesiredVelocity.x,2.0f);
    cmd.previousAction=16;cmd.previousStickX=0;
    for(float expected: {1.4f,0.8f,0.2f,-0.4f}) {
        auto step=AdvanceMeasuredOriginalVectorController(ground,cmd,unblocked);
        assert(step);
        Close(ground.previousDesiredVelocity.x,expected);
    }
    const float priorX=ground.motion.groundX;
    assert(!AdvanceMeasuredOriginalVectorController(ground,cmd,unblocked));
    Close(ground.motion.groundX,priorX);
    // Unknown action 162 must not silently trigger a Link-like state.
    cmd.action=162;
    assert(!AdvanceMeasuredOriginalVectorController(ground,cmd,unblocked));

    OriginalVectorControllerState air{};
    air.motion.groundY=100.0f;
    OriginalVectorInput jump{};
    jump.continuousSameCharacterFrame=true;
    jump.previousAction=0;jump.action=23;
    jump.stickX=62;jump.stickY=62;
    jump.currentOriginalYaw=616;
    jump.beginJump=true;jump.aButtonHeld=true;
    auto start=AdvanceMeasuredOriginalVectorController(air,jump,unblocked);
    assert(start);
    Close(std::hypot(start->desiredPlanar.x,start->desiredPlanar.z),0.84f);
    Close(start->appliedVertical,6.f);
    jump.beginJump=false;
    jump.previousAction=23;
    jump.previousStickX=62;jump.previousStickY=62;
    auto moving=AdvanceMeasuredOriginalVectorController(air,jump,unblocked);
    assert(moving);
    Close(std::hypot(moving->desiredPlanar.x,moving->desiredPlanar.z),1.68f);
    // Genuine original sample 13: stick direction changes mid-air,
    // action remains 23; original movement restarts at 0.84.
    jump.stickX=93;jump.stickY=0;jump.currentOriginalYaw=486;
    auto reset=AdvanceMeasuredOriginalVectorController(air,jump,unblocked);
    assert(reset);
    Close(std::hypot(reset->desiredPlanar.x,reset->desiredPlanar.z),0.84f);
    Close(reset->desiredPlanar.x,0.13344084f);
    assert(reset->airborne);
    // The original trial includes 93/0 and 62/62 (full-tilt) sticks.
    // A previously unmeasured analog magnitude must not be treated
    // as full movement nor misclassified as release.
    auto partial = jump;
    partial.action = 23;
    partial.previousAction = 23;
    partial.stickX = 35;
    partial.stickY = 0;
    const auto snapshot = air.previousDesiredVelocity;
    assert(!AdvanceMeasuredOriginalVectorController(air,partial,unblocked));
    Close(air.previousDesiredVelocity.x, snapshot.x);
    Close(air.previousDesiredVelocity.z, snapshot.z);
    auto diagonal = jump;
    diagonal.action = 23;
    diagonal.previousAction = 23;
    diagonal.stickX = 62;
    diagonal.stickY = 62;
    assert(IsVerifiedOriginalFullStick(diagonal));
    assert(!IsVerifiedOriginalFullStick(partial));
    jump.action=28;jump.previousAction=26;
    assert(!AdvanceMeasuredOriginalVectorController(air,jump,unblocked));
    std::puts("OriginalVectorController source action / jump / brake / collision: PASS");
}
