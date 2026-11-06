#include "soh/soh/Enhancements/Goemon/OriginalAnimationRates.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
using namespace Goemon::Original;
static void Rate(std::uint8_t ch,std::uint8_t action,float expected) {
    const auto rate=LookupObservedOriginalAnimationRate(ch,action);
    assert(rate.has_value());assert(std::fabs(*rate-expected)<0.00001f);
}
int main() {
    static_assert(kObservedOriginalAnimationRates.size()==48);
    Rate(0,0,.4f);Rate(1,0,.3f);Rate(2,0,.4f);Rate(3,0,.4f);
    Rate(0,15,1.4f);Rate(1,15,1.f);Rate(2,15,1.4f);Rate(3,15,1.2f);
    Rate(1,140,.6f);Rate(1,142,.8f);Rate(1,143,.8f);
    Rate(0,88,.6f);Rate(1,88,.6f);Rate(2,88,1.0f);Rate(3,88,1.4f);
    Rate(0,90,.6f);Rate(1,90,.8f);Rate(2,90,1.f);Rate(3,90,1.4f);
    // A long action 162 has 149 terminal holds and is NOT a fixed rate.
    assert(!LookupObservedOriginalAnimationRate(3,162).has_value());
    assert(!LookupObservedOriginalAnimationRate(2,23).has_value());
    assert(!LookupObservedOriginalAnimationRate(255,255).has_value());
    std::puts("OriginalAnimationRates (48 measured animation tempos): PASS");
}
