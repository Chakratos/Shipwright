#include "soh/soh/Enhancements/Goemon/OriginalSteeredMotion.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <stdexcept>
using namespace Goemon::Original;
static void Close(float actual,float expected) {
    assert(std::fabs(actual-expected)<0.000002f);
}
int main() {
    OriginalSteeredFullSpeedPose pose{};
    pose.motion.groundX=100.0f;
    pose.motion.groundY=-165.0f;
    // Real character 0 at original reference frames 867 -> 868.
    pose.SeedFullSpeedMotion({1.4979929924f,2.3655900955f});
    OriginalSteeringObservation ground{15,15,true,true,true};
    auto blockAll=[](float,float,OriginalPlanarStep) {
        return OriginalPlanarStep{0,0};
    };
    auto step=AdvanceVerifiedOriginalSteeredFullSpeed(
        pose,ground,988,false,false,6.0f,blockAll);
    assert(step);
    Close(step->desiredPlanar.x,1.0251355171f);
    Close(step->desiredPlanar.z,2.6055896282f);
    Close(step->appliedPlanar.x,0.0f);
    Close(pose.motion.groundX,100.0f);
    Close(pose.previousDesiredVelocity.x,step->desiredPlanar.x);
    auto snapshot=pose.previousDesiredVelocity;
    auto unknown=ground;
    unknown.currentAction=162;
    assert(!AdvanceVerifiedOriginalSteeredFullSpeed(
        pose,unknown,987,false,false,6.0f,blockAll));
    Close(pose.previousDesiredVelocity.x,snapshot.x);
    // World motion and original desired vector are different: a collision
    // never clobbers source velocity. Advance the next original steering.
    auto unblocked=[](float,float,OriginalPlanarStep desired) { return desired; };
    auto second=AdvanceVerifiedOriginalSteeredFullSpeed(
        pose,ground,987,false,false,6.0f,unblocked);
    assert(second);
    Close(pose.motion.groundX,100.0f+second->appliedPlanar.x);
    // Real character 3 airborne sample 568 -> 569.
    OriginalSteeredFullSpeedPose air{};
    air.SeedFullSpeedMotion({2.2966365814f,-1.6017056704f});
    OriginalSteeringObservation airborne{23,23,true,true,true};
    auto firstJump=AdvanceVerifiedOriginalSteeredFullSpeed(
        air,airborne,380,true,true,6.0f,unblocked);
    assert(firstJump);
    Close(firstJump->desiredPlanar.x,2.2391979694f);
    Close(firstJump->desiredPlanar.z,-1.6810685396f);
    Close(firstJump->appliedVertical,6.0f);
    assert(firstJump->airborne);
    auto nextJump=AdvanceVerifiedOriginalSteeredFullSpeed(
        air,airborne,380,false,false,6.0f,unblocked);
    assert(nextJump);
    Close(nextJump->appliedVertical,2.0f);
    // Specialized full-speed adapter must stop once an actual sharp
    // turn drops below 2.8; the generalized vector controller takes over.
    OriginalSteeredFullSpeedPose sharpPose{};
    sharpPose.SeedFullSpeedMotion(
        {-0.7351038455963135f,2.7017815113067627f});
    const auto sharpStep=AdvanceVerifiedOriginalSteeredFullSpeed(
        sharpPose,ground,743,false,false,6.0f,unblocked);
    assert(sharpStep);
    Close(std::hypot(sharpStep->desiredPlanar.x, sharpStep->desiredPlanar.z),
          2.7250822678786526f);
    assert(!sharpPose.hasReferenceVelocity);
    assert(!AdvanceVerifiedOriginalSteeredFullSpeed(
        sharpPose,ground,740,false,false,6.0f,unblocked));
    bool invalid=false;
    try { OriginalSteeredFullSpeedPose bad{};bad.SeedFullSpeedMotion({0.8f,0.0f}); }
    catch (const std::invalid_argument&) {invalid=true;}
    assert(invalid);
    std::puts("OriginalSteeredMotion ground/air/collision/unknown-state: PASS");
}
