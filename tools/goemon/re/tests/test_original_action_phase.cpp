#include "soh/soh/Enhancements/Goemon/OriginalActionPhase.hpp"
#include <cassert>
#include <cstdio>
using namespace Goemon::Original;
int main() {
    OriginalObservedActionFrame f{};
    f.previousAction=0;f.currentAction=13;f.analogActive=true;
    f.consecutiveOriginalUpdate=true;
    assert(ClassifyVerifiedOriginalSpeedPhase(f)==OriginalMeasuredPlanarPhase::GroundBegin);
    f.previousAction=13;f.currentAction=15;f.previousHorizontalMagnitude=.7f;
    assert(ClassifyVerifiedOriginalSpeedPhase(f)==OriginalMeasuredPlanarPhase::GroundRun);
    f.currentAction=25;f.previousAction=23;f.previousHorizontalMagnitude=.84f;
    f.sameStickDirection=true;
    assert(ClassifyVerifiedOriginalSpeedPhase(f)==OriginalMeasuredPlanarPhase::AirRun);
    f.currentAction=16;f.previousAction=15;f.analogActive=false;
    f.previousHorizontalMagnitude=2.8f;
    assert(ClassifyVerifiedOriginalSpeedPhase(f)==OriginalMeasuredPlanarPhase::FullSpeedRelease);
    f.previousAction=16;f.previousHorizontalMagnitude=1.4f;
    assert(ClassifyVerifiedOriginalSpeedPhase(f)==OriginalMeasuredPlanarPhase::ReleaseNext);
    f.currentAction=162;
    assert(!ClassifyVerifiedOriginalSpeedPhase(f).has_value());
    f.currentAction=15;f.analogActive=true;f.previousHorizontalMagnitude=2.8f;
    assert(!ClassifyVerifiedOriginalSpeedPhase(f).has_value());
    f.consecutiveOriginalUpdate=false;
    f.previousHorizontalMagnitude=.7f;
    assert(!ClassifyVerifiedOriginalSpeedPhase(f).has_value());
    std::puts("OriginalActionPhase partial original state bridge: PASS");
}
