// Diagnostic source for a SEPARATE local Goemon64Recomp checkout.
//
// Install with install_probe.py. Never link this code into Ship of Harkinian.
// Samples are taken from a render callback and are not yet synchronized with
// the authoritative Goemon physics tick. Addresses are for the recompilation's
// 32-bit N64 memory layout and must be revalidated after upstream updates.
#include "patches.h"

#define GOEMON_PROBE_MAX_SAMPLES 12000
#define GOEMON_MEMORY_SAMPLE_STRIDE 4
#define GOEMON_MEMORY_MAX_SAMPLES 256

static const char kHexDigits[] = "0123456789abcdef";

// Capture only when the original character or graphics root pointer changes.
// The object_type 0x60000000 pathway is taken directly from patches/anime.c.
static void CaptureOriginalRig(u32 frame, PlayerTask *task, Object *root) {
    static u8 last_character_id = 0xff;
    static u32 last_graphics = 0xffffffff;
    u32 graphics = root->graphics_1;
    if (task->character_id == last_character_id && graphics == last_graphics) {
        return;
    }
    last_character_id = task->character_id;
    last_graphics = graphics;

    if ((graphics & 0x70000000) != 0x60000000) {
        recomp_printf("GOEMON_RIG_UNRESOLVED,%u,%u,%08x\n", frame,
                      (u32)task->character_id, graphics);
        return;
    }

    u32 ptr = graphics & 0x8ffffffe;
    AnimatedSkeleton *rig = (AnimatedSkeleton *)ptr;

    if (ptr == 0) {
        return;
    }

    if ((ptr & 0x80000000) == 0) {
        u32 slot = 0;
        if (ptr >= 0x08000001) {
            u32 segment = (ptr >> 24) & 0x0f;
            if (segment < 8 || segment > 13) {
                return;
            }
            slot = segment - 8;
        }
        if (root->overlay_info[slot].vram_addr == NULL) {
            return;
        }
        rig = (AnimatedSkeleton *)((u32)root->overlay_info[slot].vram_addr +
                                    (graphics & 0x80fffffe));
    }

    // These are original pointer values. No attempt at mapping to ROM offsets
    // is made until the overlay file and load location are both verified.
    recomp_printf("GOEMON_RIG,%u,%u,%u,%08x,%08x,%08x,%08x,%08x,%04x\n",
                  frame, (u32)task->character_id, (u32)task->action_id,
                  graphics, (u32)rig->flags, (u32)rig->animation,
                  (u32)rig->skeletons[0],
                  (u32)root->overlay_info[0].vram_addr,
                  (u32)root->overlay_info[0].file_id);
}

// Capture the opaque 0x1c0-byte original Player record exactly as laid out in
// game memory. This is observational instrumentation, not an interpretation.
static void CaptureOpaquePlayerRecord(u32 trace_frame, PlayerTask *task, Object *root) {
    if (trace_frame % GOEMON_MEMORY_SAMPLE_STRIDE != 0 ||
        trace_frame / GOEMON_MEMORY_SAMPLE_STRIDE >= GOEMON_MEMORY_MAX_SAMPLES ||
        task->player == NULL) {
        return;
    }

    // Keep the buffer static to avoid large MIPS stack allocations.
    static char hex[sizeof(((Player *)0)->a) * 2 + 1];
    const u8 *data = task->player->a;
    u32 i;
    for (i = 0; i < sizeof(((Player *)0)->a); ++i) {
        hex[2 * i] = kHexDigits[data[i] >> 4];
        hex[2 * i + 1] = kHexDigits[data[i] & 0x0f];
    }
    hex[sizeof(hex) - 1] = 0;

    // Root object position is only a visual reference, not verified physics.
    recomp_printf("GOEMON_MEM,%u,%d,%u,%u,%.9f,%.9f,%.9f,%s\n",
                  trace_frame, (s32)D_8008CCC0_8D8C0.frames_elapsed,
                  (u32)task->character_id, (u32)task->action_id,
                  root->position.x, root->position.y, root->position.z, hex);
}

void GoemonReferenceProbe_CaptureRenderFrame(void) {
    static u32 sample = 0;
    if (sample >= GOEMON_PROBE_MAX_SAMPLES) {
        return;
    }

    PlayerTask *task = D_801FC604_5B8514;
    Object *root = D_801FC614_5B8524;
    if (task == NULL || root == NULL) {
        return;
    }

    const CONTROLLER_W *input = &D_8008CCC0_8D8C0.controller[0];
    u32 trace_frame = sample++;

    // Original controller state and render-root transforms.
    recomp_printf("GOEMON_REF,%u,%d,%u,%u,%u,%u,%f,%f,%f,%d,%d,%d,%f,%u,%d,%d,%f,%f\n",
                  trace_frame,
                  (s32)D_8008CCC0_8D8C0.frames_elapsed,
                  (u32)task->character_id,
                  (u32)task->action_id,
                  (u32)D_8015C5DC_15D1DC,
                  (u32)input->button_held_down,
                  root->position.x, root->position.y, root->position.z,
                  (s32)root->rotation.x, (s32)root->rotation.y,
                  (s32)root->rotation.z,
                  root->animation_progress,
                  (u32)input->button_pressed,
                  (s32)input->stick_raw_x, (s32)input->stick_raw_y,
                  input->stick_x, input->stick_y);

    CaptureOpaquePlayerRecord(trace_frame, task, root);
    CaptureOriginalRig(trace_frame, task, root);
}
