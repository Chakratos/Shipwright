#include "soh/soh/Enhancements/Goemon/OriginalVectorAcceleration.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <stdexcept>
using namespace Goemon::Original;
struct VectorCase { float previousX,previousZ;std::int16_t yaw;float nextX,nextZ;OriginalVectorAccelerationMode mode; };
int main() {
    constexpr std::array<VectorCase,10> samples{{
        {-0.743229568f,0.391420275f,848,-1.218604326f,0.647600591f,OriginalVectorAccelerationMode::ContinuousGrounded},
        {-1.218604326f,0.647600591f,850,-1.689588070f,0.911851645f,OriginalVectorAccelerationMode::ContinuousGrounded},
        {-1.689588070f,0.911851645f,852,-2.156455517f,1.183405161f,OriginalVectorAccelerationMode::ContinuousGrounded},
        {0.646715641f,-0.267878383f,321,1.143623590f,-0.479283214f,OriginalVectorAccelerationMode::ContinuousGrounded},
        {-0.089948677f,-0.694196880f,534,-0.164447039f,-1.229042172f,OriginalVectorAccelerationMode::ContinuousGrounded},
        {0.681057990f,0.161740676f,217,1.205239296f,0.291523069f,OriginalVectorAccelerationMode::ContinuousGrounded},
        {-0.500387430f,-0.674694359f,616,-1.000774860f,-1.349388719f,OriginalVectorAccelerationMode::ContinuousAirborne},
        {0.271967828f,-1.657832146f,482,0.425721347f,-2.483640671f,OriginalVectorAccelerationMode::ContinuousAirborne},
        {0.425721347f,-2.483640671f,479,0.495610952f,-2.755788565f,OriginalVectorAccelerationMode::ContinuousAirborne},
        {2.664895296f,0.859263241f,187,2.641933918f,0.927461922f,OriginalVectorAccelerationMode::ContinuousAirborne},
    }};
    for (auto sample:samples) {
        auto predicted = ContinueOriginalVectorMotion(
            {sample.previousX,sample.previousZ},sample.yaw,sample.mode);
        assert(std::hypot(predicted.x-sample.nextX,
                          predicted.z-sample.nextZ)<0.0015f);
    }
    const auto g=BeginOriginalGroundMotion(256);
    assert(std::fabs(g.x-0.7f)<0.00001f);
    const auto a=BeginOriginalAirMotion(0);
    assert(std::fabs(a.z-0.84f)<0.00001f);
    bool rejected=false;
    try { (void)ContinueOriginalVectorMotion(
        {0.2f,0.0f},123,OriginalVectorAccelerationMode::ContinuousGrounded); }
    catch (const std::invalid_argument&) {rejected=true;}
    assert(rejected);
    // Original recording sample 35 -> 36: 122/1024-step target-yaw
    // change. The actual game slows below 2.8 after the raw-vector
    // blend. The old speed-only approximation missed this transition.
    auto sharpTurn = ContinueOriginalVectorMotion(
        {-0.7351038455963135f, 2.7017815113067627f}, 743,
        OriginalVectorAccelerationMode::ContinuousGrounded);
    assert(std::hypot(sharpTurn.x - (-1.4864791631698608f),
                      sharpTurn.z - 2.2839555740356445f) < 0.000002f);
    assert(std::fabs(std::hypot(sharpTurn.x, sharpTurn.z) -
                     2.7250822678786526f) < 0.000002f);
    std::puts("OriginalVectorAcceleration: 11 measured original vectors PASS");
}
