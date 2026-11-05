#include "soh/soh/Enhancements/Goemon/OriginalMotionAdapter.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
using namespace Goemon::Original;
static void Close(float a,float b) { assert(std::fabs(a-b)<0.001f); }
int main() {
    OriginalFlatGroundPose p{};
    p.groundY=100.0f;
    OriginalMeasuredMotionInput cmd{};
    cmd.headingX=1.0f;
    const auto unobstructed=[](float,float,OriginalPlanarStep v){return v;};
    for (int k=0;k<5;++k) {
        cmd.horizontalPhase=k==0?OriginalMeasuredPlanarPhase::GroundBegin:
                                  OriginalMeasuredPlanarPhase::GroundRun;
        auto result=AdvanceOriginalFlatGround(p,cmd,unobstructed);
        Close(result.modelY,100.0f);
    }
    Close(p.groundX,8.84f);
    Close(p.horizontal.signedSpeed,2.80f);
    cmd.horizontalPhase=OriginalMeasuredPlanarPhase::Keep;
    auto blocked=[](float,float,OriginalPlanarStep){return OriginalPlanarStep{0,0};};
    auto wall=AdvanceOriginalFlatGround(p,cmd,blocked);
    Close(wall.desiredPlanar.x,2.80f);
    Close(wall.appliedPlanar.x,0.0f);
    Close(p.groundX,8.84f);
    Close(p.horizontal.signedSpeed,2.80f);
    cmd.horizontalPhase=OriginalMeasuredPlanarPhase::FullSpeedRelease;
    (void)AdvanceOriginalFlatGround(p,cmd,unobstructed);
    Close(p.horizontal.signedSpeed,2.0f);
    cmd.horizontalPhase=OriginalMeasuredPlanarPhase::ReleaseNext;
    for (float expected: {1.4f,0.8f,0.2f,-0.4f}) {
        auto result=AdvanceOriginalFlatGround(p,cmd,unobstructed);
        Close(p.horizontal.signedSpeed,expected);
        Close(result.desiredPlanar.x,expected);
    }
    cmd.horizontalPhase=OriginalMeasuredPlanarPhase::Idle;
    (void)AdvanceOriginalFlatGround(p,cmd,unobstructed);
    Close(p.horizontal.signedSpeed,0.0f);
    cmd.horizontalPhase=OriginalMeasuredPlanarPhase::Keep;
    cmd.beginJump=true;cmd.aButtonHeld=true;
    for (int tick=0;tick<19;++tick) {
        if(tick>0)cmd.beginJump=false;
        auto result=AdvanceOriginalFlatGround(p,cmd,unobstructed);
        if(tick==8)Close(result.modelY,130.0f);
        if(tick==18) {
            Close(result.modelY,100.0f);
            assert(!result.airborne);
        }
    }
    Close(p.groundY,100.0f);
    cmd.beginJump=true;cmd.jumpImpulse=2.0f;
    for (int tick=0;tick<7;++tick) {
        if(tick>0)cmd.beginJump=false;
        auto result=AdvanceOriginalFlatGround(p,cmd,unobstructed);
        if(tick==2)Close(result.modelY,104.0f);
        if(tick==6)Close(result.modelY,100.0f);
    }
    p.horizontal.StartGroundedMotion();
    cmd.horizontalPhase=OriginalMeasuredPlanarPhase::SuppressWhileActionLocked;
    auto noMove=AdvanceOriginalFlatGround(p,cmd,unobstructed);
    Close(noMove.desiredPlanar.x,0.0f);
    Close(p.horizontal.signedSpeed,0.70f);
    std::puts("OriginalMotionAdapter measured kinematics boundary: PASS");
}
