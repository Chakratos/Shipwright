// Goemon original-behavior reference capture for MNSGRecompModTemplate.
//
// This mod is OBSERVATIONAL ONLY. It never changes Goemon player state.
// Compile in the official MNSGRecompModTemplate (Clang with MIPS target).
// Event hook follows the working text_printing.c example of the template.
// All data-symbol names are from the Goemon64Recomp pinned source/symbol map.
#include "common.h"
#include "modding.h"
#include "recomputils.h"
#include "recompconfig.h"
#include "goemon_capture_gate.h"

extern void* D_801FC604_5B8514; // PlayerTask* (player one)
extern void* D_801FC614_5B8524; // Object* player-one render root
extern u32 D_8015C5DC_15D1DC; // globally selected character

// No assumed host pointer size: code is compiled to MIPS o32 (32-bit).
typedef char verify_u32_pointer_layout[(sizeof(void*) == 4) ? 1 : -1];

#define GOEMON_TRACE_MAX_FRAMES 2400
#define GOEMON_TRACE_MEM_EVERY 8
#define GOEMON_TRACE_MAX_MEMORY_SAMPLES 128

static u32 trace_frame = 0;
static u32 trace_memory_count = 0;
// State machine: 0 idle, 1 armed, 2 recording, 3 completed.
// A completed capture cannot be restarted without relaunching the game;
// this preserves consecutive sample IDs for the post-processing tools.
static u8 trace_state = 0;
static GoemonTraceMovementGate movement_gate = {0};
static const char k_hex[] = "0123456789abcdef";

static u8* ReadTaskPlayer(u8* task) {
    // Original PlayerTask.player field at +0x5C (as recovered from patches/types.h).
    return *(u8**)(task + 0x5c);
}

static f32 ReadF32(const u8* ptr, u32 off) {
    return *(const f32*)(ptr + off);
}

static s16 ReadS16(const u8* ptr, u32 off) {
    return *(const s16*)(ptr + off);
}

static u32 ReadU32(const u8* ptr, u32 off) {
    return *(const u32*)(ptr + off);
}

static void CapturePlayerMemory(const u8* player, u32 frame, u8 character, u8 action,
                                f32 x, f32 y, f32 z) {
    static char bytes_as_hex[0x1c0 * 2 + 1];
    u32 i;
    if (trace_memory_count >= GOEMON_TRACE_MAX_MEMORY_SAMPLES ||
        frame % GOEMON_TRACE_MEM_EVERY != 0 || player == 0) {
        return;
    }
    for (i = 0; i < 0x1c0; ++i) {
        u8 value = player[i];
        bytes_as_hex[i * 2] = k_hex[value >> 4];
        bytes_as_hex[i * 2 + 1] = k_hex[value & 0x0f];
    }
    bytes_as_hex[sizeof(bytes_as_hex) - 1] = '\0';
    recomp_printf("GOEMON_MEM,%u,%d,%u,%u,%.9f,%.9f,%.9f,%s\n",
                  frame, (s32)D_8008CCC0_8D8C0.frames_elapsed,
                  (u32)character, (u32)action, x, y, z, bytes_as_hex);
    ++trace_memory_count;
}

// In the official mod template this hook is called by the game's game-mode
// handler (func_80002040_2C40); sampling phase is not yet a physics tick.
RECOMP_HOOK_RETURN("func_80002040_2C40") void goemon_capture_mode_handler(void) {
    u8* task;
    u8* root;
    u8* player;
    u32 frame;
    u8 character;
    u8 action;
    const CONTROLLER_W* input;
    f32 x, y, z;

    // The mod's Enum setting is read at every callback. 0 = "Aus"
    // (the manifest's default), 1 = "Aufnahme aktivieren".
    // Crucially, the title screen does not consume any sample budget.
    if (trace_state == 3) return;
    if (recomp_get_config_u32("capture_enabled") == 0) {
        if (trace_state == 2) {
            recomp_printf("GOEMON_TRACE_END,%u,%u,manual_stop\n",
                          trace_frame, trace_memory_count);
            trace_state = 3;
        } else if (trace_state == 1) {
            recomp_printf("GOEMON_TRACE_DISARMED\n");
            trace_state = 0;
            GoemonTraceMovementGateReset(&movement_gate);
        }
        return;
    }

    if (trace_state == 0) {
        GoemonTraceMovementGateReset(&movement_gate);
        trace_state = 1;
        recomp_printf("GOEMON_TRACE_ARMED,wait_for_player_movement\n");
    }

    task = (u8*)D_801FC604_5B8514;
    root = (u8*)D_801FC614_5B8524;
    if (task == 0 || root == 0) return;
    player = ReadTaskPlayer(task);
    if (player == 0) return;

    input = &D_8008CCC0_8D8C0.controller[0];
    x = ReadF32(root, 0x08);
    y = ReadF32(root, 0x0c);
    z = ReadF32(root, 0x10);

    // Merely enabling the option in the mod menu does not start the trace.
    // Require BOTH a real analog-stick deflection and a change in the
    // original player's world position: this excludes menu navigation
    // while the player is stationary or paused.
    if (trace_state == 1) {
        if (!GoemonTraceMovementGateTriggered(&movement_gate, x, y, z,
                                              (int)input->stick_raw_x,
                                              (int)input->stick_raw_y)) {
            return;
        }
        trace_state = 2;
        recomp_printf("GOEMON_TRACE_BEGIN,2,hook=func_80002040_2C40,max_frames=%u,trigger=player_movement\n",
                      (u32)GOEMON_TRACE_MAX_FRAMES);
    }

    frame = trace_frame++;
    character = task[0x60];
    action = task[0xcc];

    // Preserve the exact 18-column GOEMON_REF schema used by the existing
    // log_to_csv.py, action_transitions.py and memory_candidates.py.
    recomp_printf("GOEMON_REF,%u,%d,%u,%u,%u,%u,%f,%f,%f,%d,%d,%d,%f,%u,%d,%d,%f,%f\n",
                  frame, (s32)D_8008CCC0_8D8C0.frames_elapsed,
                  (u32)character, (u32)action,
                  (u32)D_8015C5DC_15D1DC,
                  (u32)input->button_held_down,
                  x, y, z,
                  (s32)ReadS16(root, 0x14), (s32)ReadS16(root, 0x16),
                  (s32)ReadS16(root, 0x18),
                  ReadF32(root, 0x28),
                  (u32)input->button_pressed,
                  (s32)input->stick_raw_x, (s32)input->stick_raw_y,
                  input->stick_x, input->stick_y);

    CapturePlayerMemory(player, frame, character, action, x, y, z);

    recomp_printf("GOEMON_TICK,%u,%d,%d,%u,%u\n",
                  frame, (s32)D_8008CCC0_8D8C0.frames_elapsed,
                  (s32)D_8008CCC0_8D8C0.game_loops_count,
                  (u32)D_8008CCC0_8D8C0.retraces_per_game_step,
                  (u32)D_8008CCC0_8D8C0.retrace_count);

    if (trace_frame >= GOEMON_TRACE_MAX_FRAMES) {
        trace_state = 3;
        recomp_printf("GOEMON_TRACE_END,%u,%u,frame_limit\n", trace_frame,
                      trace_memory_count);
    }
}
