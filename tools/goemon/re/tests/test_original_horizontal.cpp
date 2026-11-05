// Numeric original ground, air and signed-braking speeds from actual NG5E.
#include "soh/soh/Enhancements/Goemon/OriginalHorizontal.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <stdexcept>
using namespace Goemon::Original;
static void Close(float x, float expected) { assert(std::fabs(x - expected) < 1e-5f); }
int main() {
    OriginalHorizontalSpeed ground{};
    ground.StartGroundedMotion();
    std::array<float, 5> grounded{0.70f,1.24f,1.78f,2.32f,2.80f};
    for (std::size_t i=0;i<grounded.size();i++) {
        if (i) ground.ContinueGroundedRun();
        Close(ground.signedSpeed,grounded[i]);
    }
    for (int i=0;i<10;i++)ground.ContinueGroundedRun();
    Close(ground.signedSpeed,2.8f);
    OriginalHorizontalSpeed immediateRun{};
    immediateRun.StartAirborneMotion();
    Close(immediateRun.signedSpeed, 0.84f);
    immediateRun.ContinueGroundedRun();
    Close(immediateRun.signedSpeed, 1.38f);
    immediateRun.ContinueGroundedRun();
    Close(immediateRun.signedSpeed, 1.92f);
    immediateRun.ContinueGroundedRun();
    Close(immediateRun.signedSpeed, 2.46f);
    immediateRun.ContinueGroundedRun();
    Close(immediateRun.signedSpeed, 2.8f);
    OriginalHorizontalSpeed air{};
    air.StartAirborneMotion();
    for (float expected: {1.68f,2.52f,2.80f,2.80f}) {
        air.ContinueAirborneRun();Close(air.signedSpeed,expected);
    }
    ground.BeginFullSpeedRelease();
    Close(ground.signedSpeed,2.0f);
    for (float expected: {1.4f,0.8f,0.2f,-0.4f}) {
        ground.ContinueRelease();Close(ground.signedSpeed,expected);
    }
    auto reversed = ComposeOriginalPlanarStep(ground,0.6f,0.8f);
    Close(reversed.x,-0.24f);Close(reversed.z,-0.32f);
    ground.ResetForOriginalIdle();Close(ground.signedSpeed,0.0f);
    bool rejected=false;
    try { ground.BeginFullSpeedRelease(); }
    catch (const std::invalid_argument&) { rejected=true; }
    assert(rejected);
    rejected=false;
    try { (void)ComposeOriginalPlanarStep(ground,0.0f,0.0f); }
    catch (const std::invalid_argument&) { rejected=true; }
    assert(rejected);
    std::puts("OriginalHorizontal original-speed primitives: PASS");
}
