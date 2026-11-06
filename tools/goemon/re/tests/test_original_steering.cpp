#include "soh/soh/Enhancements/Goemon/OriginalSteering.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <stdexcept>
using namespace Goemon::Original;
struct Case {float px,pz;std::int16_t yaw;float ex,ez;OriginalSteeringPhase phase;};
int main() {
    constexpr std::array<Case,8> samples{{
        { 2.6648952961f, 0.8592632413f, 187, 2.6419339180f,0.9274619222f,OriginalSteeringPhase::Airborne},
        {-0.5238671899f,-2.7505567074f, 558,-0.5833991766f,-2.7385480404f,OriginalSteeringPhase::Airborne},
        { 0.4956109524f,-2.7557885647f, 474, 0.5306819081f,-2.7492501736f,OriginalSteeringPhase::Airborne},
        { 2.2966365814f,-1.6017056704f, 380, 2.2391979694f,-1.6810685396f,OriginalSteeringPhase::Airborne},
        { 1.4979929924f, 2.3655900955f, 988, 1.0251355171f, 2.6055896282f,OriginalSteeringPhase::GroundRun},
        { 1.4385632277f,-2.4021940231f, 452, 1.3338892460f,-2.4618568420f,OriginalSteeringPhase::GroundRun},
        {-2.7749991417f, 0.3733355701f, 616,-2.7817850113f,-0.3188605011f,OriginalSteeringPhase::GroundRun},
        { 2.5338232517f,-1.1915277243f, 341, 2.5087280273f,-1.2434964180f,OriginalSteeringPhase::GroundRun},
    }};
    for (const auto& sample : samples) {
        auto measured = SteerOriginalFullSpeed({sample.px,sample.pz},sample.yaw,sample.phase);
        assert(std::hypot(measured.x-sample.ex,measured.z-sample.ez)<0.000002f);
        assert(std::fabs(std::hypot(measured.x,measured.z)-2.8f)<0.000002f);
    }
    // Real original sharp turn sample 35->36 must retain the drop
    // from 2.8 to 2.725082, rather than forcing 2.8 again.
    const auto sharp = SteerOriginalFullSpeed(
        {-0.7351038455963135f, 2.7017815113067627f},
        743, OriginalSteeringPhase::GroundRun);
    assert(std::hypot(sharp.x - (-1.4864791631698608f),
                      sharp.z - 2.2839555740356445f) < 0.000002f);
    assert(std::fabs(std::hypot(sharp.x,sharp.z) - 2.7250822678786526f)
           < 0.000002f);
    OriginalSteeringPhase phase{};
    OriginalSteeringObservation o{15,15,true,true,true};
    assert(TryClassifyOriginalFullSpeedSteering(o,phase));
    assert(phase==OriginalSteeringPhase::GroundRun);
    o={23,25,true,true,true};
    assert(TryClassifyOriginalFullSpeedSteering(o,phase));
    assert(phase==OriginalSteeringPhase::Airborne);
    o={15,16,true,true,true};
    assert(!TryClassifyOriginalFullSpeedSteering(o,phase));
    o={15,15,true,true,false};
    assert(!TryClassifyOriginalFullSpeedSteering(o,phase));
    o={15,15,true,false,true};
    assert(!TryClassifyOriginalFullSpeedSteering(o,phase));
    bool rejected=false;
    try { (void)SteerOriginalFullSpeed({0.8f,0.0f},123,OriginalSteeringPhase::GroundRun); }
    catch (std::invalid_argument const&) { rejected=true; }
    assert(rejected);
    std::puts("OriginalSteering: 8 original measured vectors and phase gates PASS");
}
