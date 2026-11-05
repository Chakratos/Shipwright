// Native regression for the in-game manual recording motion gate.
#include "tools/goemon/diagnostic_mod/src/goemon_capture_gate.h"
#include <cassert>
#include <cstdio>

int main() {
    GoemonTraceMovementGate gate = {};
    GoemonTraceMovementGateReset(&gate);
    // First position sample arms the gate; no recording.
    assert(!GoemonTraceMovementGateTriggered(&gate, 100.f, 200.f, 300.f, 0, 0));
    // Menu navigation or stick movement with an unmoving player is ignored.
    assert(!GoemonTraceMovementGateTriggered(&gate, 100.f, 200.f, 300.f, 80, 0));
    // A moving/cutscene player without analog activity is ignored.
    assert(!GoemonTraceMovementGateTriggered(&gate, 100.5f, 200.f, 300.f, 0, 0));
    // Small root position jitter below the N64 threshold is ignored.
    assert(!GoemonTraceMovementGateTriggered(&gate, 100.52f, 200.f, 300.f, 80, 0));
    assert(GoemonTraceMovementGateTriggered(&gate, 102.f, 200.f, 300.f, 80, 0));
    // Resetting must require another initial sample before the next take.
    GoemonTraceMovementGateReset(&gate);
    assert(!GoemonTraceMovementGateTriggered(&gate, 0.f, 0.f, 0.f, 80, 0));
    assert(GoemonTraceMovementGateTriggered(&gate, -2.f, 0.f, 0.f, -80, 0));
    std::puts("Goemon capture movement gate: PASS");
}
