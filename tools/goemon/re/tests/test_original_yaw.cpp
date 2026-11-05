#include "soh/soh/Enhancements/Goemon/OriginalYaw.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
using namespace Goemon::Original;
static void Close(float x,float y) {assert(std::fabs(x-y)<0.00002f);}
int main() {
    auto a=DirectionFromOriginalYaw(0);Close(a.x,0);Close(a.z,1);
    a=DirectionFromOriginalYaw(256);Close(a.x,1);Close(a.z,0);
    a=DirectionFromOriginalYaw(512);Close(a.x,0);Close(a.z,-1);
    a=DirectionFromOriginalYaw(768);Close(a.x,-1);Close(a.z,0);
    // Genuine game sample 106: yaw 761; vx -2.7974; vz -0.1202.
    a=DirectionFromOriginalYaw(761);
    Close(a.x,-2.7974f/2.8f);
    Close(a.z,-0.1202f/2.8f);
    a=DirectionFromOriginalYaw(761+1024);
    Close(a.x,-2.7974f/2.8f);
    Close(a.z,-0.1202f/2.8f);
    std::puts("OriginalYaw original 1024-step direction: PASS");
}
