#ifndef GOEMON_CAPTURE_GATE_H
#define GOEMON_CAPTURE_GATE_H

// Pure movement-gate logic; compatible with C17/MIPS and host C++20.
typedef struct GoemonTraceMovementGate {
    float previous_x;
    float previous_y;
    float previous_z;
    unsigned char has_previous;
} GoemonTraceMovementGate;

static inline void GoemonTraceMovementGateReset(GoemonTraceMovementGate* gate) {
    gate->has_previous = 0;
}

static inline int GoemonTraceMovementGateTriggered(GoemonTraceMovementGate* gate,
                                                   float x, float y, float z,
                                                   int raw_stick_x, int raw_stick_y) {
    float dx, dy, dz;
    if (!gate->has_previous) {
        gate->previous_x = x;
        gate->previous_y = y;
        gate->previous_z = z;
        gate->has_previous = 1;
        return 0;
    }
    dx = x - gate->previous_x;
    dy = y - gate->previous_y;
    dz = z - gate->previous_z;
    gate->previous_x = x;
    gate->previous_y = y;
    gate->previous_z = z;

    // Stick movement without world motion (e.g. menus) never starts capture.
    if (raw_stick_x < 15 && raw_stick_x > -15 &&
        raw_stick_y < 15 && raw_stick_y > -15) {
        return 0;
    }
    return !(dx < 0.0625f && dx > -0.0625f &&
             dy < 0.0625f && dy > -0.0625f &&
             dz < 0.0625f && dz > -0.0625f);
}

#endif
