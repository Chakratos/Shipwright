#include "soh/soh/Enhancements/Goemon/OriginalTraceReplay.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <sstream>
#include <stdexcept>

using Goemon::Original::OriginalMotionReplay;
using Goemon::Original::OriginalRecordedMovement;

std::string Source() {
    return std::string(OriginalMotionReplay::kHeader) + "\n"
        "0,100,2,13,761,-0.7351038455963135,2.7017815113067627,0\n"
        "1,101,2,15,743,-1.4864791631698608,2.2839555740356445,1\n"
        "2,1542,2,23,486,0.129,0.83,0\n"
        "3,1543,3,186,486,0,0,0\n"
        "4,1544,3,0,486,0,0,1\n";
}

static bool Rejected(const std::string& source) {
    try {
        std::istringstream text(source);
        OriginalMotionReplay bad(text);
    } catch (const std::invalid_argument&) { return true; }
    return false;
}

int main() {
    std::istringstream source(Source());
    OriginalMotionReplay capture(source);
    assert(capture.Size() == 5);
    assert(capture.Cursor() == 0);
    OriginalRecordedMovement row{};
    assert(capture.Next(row));
    assert(row.characterId == 2 && row.actionId == 13);
    assert(!row.continuousOriginalUpdate);
    assert(row.targetYaw10 == 761);
    assert(std::fabs(row.originalDesired.x - (-0.73510385f)) < 0.000001f);
    assert(capture.Next(row));
    assert(row.continuousOriginalUpdate);
    assert(row.actionId == 15);
    assert(std::fabs(std::hypot(row.originalDesired.x,row.originalDesired.z)
                     - 2.725082f) < 0.000002f);
    assert(capture.Next(row));
    assert(row.gameFrame == 1542 && !row.continuousOriginalUpdate);
    assert(capture.Next(row));
    assert(row.characterId == 3 && !row.continuousOriginalUpdate);
    assert(capture.Next(row));
    assert(row.continuousOriginalUpdate);
    assert(!capture.Next(row));
    assert(capture.Cursor() == capture.Size());
    capture.Reset();
    assert(capture.Next(row) && row.sample == 0);

    assert(Rejected("wrong header\n" + Source()));
    assert(Rejected(std::string(OriginalMotionReplay::kHeader) + "\n"));
    // Never treat a frame gap or character switch as continuous.
    std::string bad = Source();
    const auto index = bad.find("2,1542,2,23,486,0.129,0.83,0");
    assert(index != std::string::npos);
    bad.replace(index, std::string("2,1542,2,23,486,0.129,0.83,0").size(),
                "2,1542,2,23,486,0.129,0.83,1");
    assert(Rejected(bad));

    bad = Source();
    const auto badIndex = bad.find("4,1544,3,0,486,0,0,1");
    assert(badIndex != std::string::npos);
    bad.replace(badIndex, 20, "8,1544,3,0,486,0,0,1");
    assert(Rejected(bad));

    bad = Source();
    const auto pos = bad.find("0,100,2,13,761,-0.7351038455963135,2.7017815113067627,0");
    assert(pos != std::string::npos);
    bad.replace(pos, std::string("0,100,2,13,761,-0.7351038455963135,2.7017815113067627,0").size(),
                "0,100,2,13,761,99,0,0");
    assert(Rejected(bad));

    std::puts("OriginalTraceReplay: parsed real numeric speeds, gaps, character switches PASS");
}
