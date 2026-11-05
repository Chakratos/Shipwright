// Exploratory diagnostic source for a SEPARATE local Goemon64Recomp checkout.
//
// NOT linked into Ship of Harkinian. Copy to Goemon64Recomp/patches/ and
// call GoemonReferenceProbe_CaptureRenderFrame() from main_initialize_display_lists.
// This samples render callbacks, NOT necessarily the original physics tick.
// Do not use these rows as authoritative movement parity until tick alignment,
// object-coordinate semantics, and angle units have been verified.
#include "patches.h"

#define GOEMON_PROBE_MAX_SAMPLES 12000

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

    // Prefix allows the converter to ignore unrelated debug output.
    // Position = render root transform, NOT yet verified as physics position.
    // Rotation = raw Goemon object rotation (not an OoT signed 16-bit angle).
    recomp_printf("GOEMON_REF,%u,%d,%u,%u,%u,%u,%f,%f,%f,%d,%d,%d,%f,%u,%d,%d,%f,%f\n",
                  sample++,
                  (s32)D_8008CCC0_8D8C0.frames_elapsed,
                  (u32)task->character_id,
                  (u32)task->action_id,
                  (u32)D_8015C5DC_15D1DC,
                  (u32)input->button_held_down,
                  root->position.x, root->position.y, root->position.z,
                  (s32)root->rotation.x, (s32)root->rotation.y, (s32)root->rotation.z,
                  root->animation_progress,
                  (u32)input->button_pressed,
                  (s32)input->stick_raw_x, (s32)input->stick_raw_y,
                  input->stick_x, input->stick_y);
}
