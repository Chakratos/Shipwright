// Real Mystical Ninja N64 skeletal animation capture, not procedural motion.
//
// Hooked ORIGINAL engine paths (Goemon64Recomp/patches/anime.c):
//   func_80016C44_17844: resolve live animated player root and overlays
//   func_80018CA0_198A0: traverse original player skeleton
//   func_800192D0_19ED0: compose each limb's animation matrix
//
// IMPORTANT: The returned matrix is the ORIGINAL engine's matrix at that
// stage, not a synthesized sine-wave animation or Ship's Link animation.
// The output retains limb display-list pointers so 0x07 Gfx can be matched
// to genuine 0x09 source vertices. No copyrighted image/model bytes are
// logged. The mod is opt-in and runs only in the separate Goemon64Recomp.
#include "common.h"
#include "modding.h"
#include "recompconfig.h"
#include "recomputils.h"

typedef struct GoemonAnimBone {
    u32 display_list_vram_addr;
    s8 offset_right;
    s8 offset_left;
    s16 scale_x, scale_y, scale_z;
    s16 rotation_x, rotation_y, rotation_z;
    s16 translation_x, translation_y, translation_z;
} GoemonAnimBone;
typedef char GoemonAnimBoneMustBe24Bytes[
    sizeof(GoemonAnimBone) == 24 ? 1 : -1
];

extern void *D_801FC604_5B8514; // Original PlayerTask (verified)
extern void *D_801FC614_5B8524; // Original player render root Object
extern void *D_801FC60C_5B851C; // Original player render Object
extern void *D_801684A0_1690A0; // Original current renderer Object
extern void *D_80168520_169120; // Original resolved live animation stream
extern u8 *D_80168530_169130; // Original live MtxF stack destination cursor
extern SYS_W D_8008CCC0_8D8C0;

#define GOEMON_ANIM_CAPTURE_MAX_FRAMES 1800
#define GOEMON_ANIM_MAX_LIMBS_PER_FRAME 96

static u32 g_anim_start_frame;
static u32 g_anim_prior_frame = 0xffffffff;
static u32 g_anim_recorded_frame_count;
static u32 g_anim_bones_in_frame;
static u32 g_anim_active;
static u32 g_anim_stack_depth;
static u32 g_anim_last_root;
static u32 g_anim_last_overlay_signature;
static u32 g_anim_last_graphics;
static u32 g_anim_last_action = 0xffffffff;
static u32 g_anim_pending_matrix_cursor;
static u32 g_anim_emitted_stop;
static u32 g_anim_in_transform;
static GoemonAnimBone *g_anim_pending_bone;
static u8 g_anim_character;
static u8 g_anim_action;
static f32 g_anim_model_progress;

static u8 OriginalCharacterId(void) {
    return ((const u8 *)D_801FC604_5B8514)[0x60];
}

static u8 OriginalActionId(void) {
    return ((const u8 *)D_801FC604_5B8514)[0xCC];
}

static u32 ReadObjectU32(const void *object, u32 at) {
    return *(const u32 *)((const u8 *)object + at);
}

// Mirror the *actual original* 0x60000000 player-graphics and animation
// pointer relocation in Goemon64Recomp patches/anime.c. Do not treat a
// 0x07 structural candidate as proof that it belongs to the live player.
static u32 ResolvePlayerObjectPointer(const void *object, u32 raw) {
    if (raw == 0)
        return 0;
    if ((raw & 0x80000000u) != 0)
        return raw;
    u32 slot = 0;
    if (raw >= 0x08000001u) {
        const u32 segment = (raw >> 24) & 0x0f;
        if (segment < 8 || segment > 13)
            return 0;
        slot = segment - 8;
    }
    const u32 overlay = ReadObjectU32(object, 0x38 + slot * 8);
    if (overlay == 0)
        return 0;
    return overlay + (raw & 0x80ffffffu);
}

static void ResetAnimationCaptureState(void) {
    g_anim_start_frame = 0;
    g_anim_prior_frame = 0xffffffff;
    g_anim_recorded_frame_count = 0;
    g_anim_bones_in_frame = 0;
    g_anim_active = 0;
    g_anim_stack_depth = 0;
    g_anim_last_root = 0;
    g_anim_last_overlay_signature = 0;
    g_anim_last_graphics = 0;
    g_anim_last_action = 0xffffffff;
    g_anim_pending_matrix_cursor = 0;
    g_anim_emitted_stop = 0;
    g_anim_in_transform = 0;
    g_anim_pending_bone = NULL;
}

// The original player render Object identifies the actual animated
// graphics root, per Goemon64Recomp patches/anime.c case 0x60000000.
// All overlay segment IDs and bases come from the live game, NOT guessed
// by treating arbitrary ROM files as 0x08.
RECOMP_HOOK("func_80016C44_17844")
void GoemonAnim_CaptureRoot(void *object) {
    if (!recomp_get_config_u32("capture_animation")) {
        if (g_anim_active || g_anim_recorded_frame_count)
            ResetAnimationCaptureState();
        return;
    }
    if (object == NULL || D_801FC604_5B8514 == NULL ||
        D_801FC614_5B8524 == NULL)
        return;
    // The player model Object and root Object are distinct. The player
    // animated 0x60000000 graphics may be attached to either, so the
    // old root-only gate silently missed valid model render callbacks.
    if (object != D_801FC614_5B8524 &&
        object != D_801FC60C_5B851C)
        return;

    const u32 graphics = ReadObjectU32(object, 0x2C);
    if ((graphics & 0x70000000) != 0x60000000)
        return;
    const u8 character = OriginalCharacterId();
    if (character > 3)
        return;

    // Initialize on first real player stick input. Title/menu cycles
    // never exhaust the limited original-animation capture budget.
    const CONTROLLER_W *pad = &D_8008CCC0_8D8C0.controller[0];
    if (!g_anim_active) {
        if (g_anim_recorded_frame_count >= GOEMON_ANIM_CAPTURE_MAX_FRAMES)
            return;
        if (pad->stick_raw_x < -20 || pad->stick_raw_x > 20 ||
            pad->stick_raw_y < -20 || pad->stick_raw_y > 20) {
            g_anim_active = 1;
            g_anim_start_frame = (u32)D_8008CCC0_8D8C0.frames_elapsed;
            recomp_printf("GOEMON_ANIM_BEGIN,1,%u,source=func_800192D0_19ED0\n",
                          g_anim_start_frame);
        } else return;
    }

    const u32 frame = (u32)D_8008CCC0_8D8C0.frames_elapsed;
    if (frame != g_anim_prior_frame) {
        g_anim_prior_frame = frame;
        g_anim_bones_in_frame = 0;
        ++g_anim_recorded_frame_count;
        if (g_anim_recorded_frame_count > GOEMON_ANIM_CAPTURE_MAX_FRAMES) {
            g_anim_active = 0;
            if (!g_anim_emitted_stop) {
                recomp_printf("GOEMON_ANIM_END,%u,limit\n", frame);
                g_anim_emitted_stop = 1;
            }
            return;
        }
    }

    g_anim_character = character;
    g_anim_action = OriginalActionId();
    g_anim_model_progress =
        *(const f32 *)((const u8 *)object + 0x28);

    // Each overlay is recorded from the *actual active player Object*.
    // Use a simple signature to avoid re-logging identical mappings
    // on every frame.
    u32 signature = graphics;
    u32 n;
    for (n = 0; n < 6; ++n) {
        signature = (signature * 33u) ^
            ReadObjectU32(object, 0x38 + n * 8);
        signature = (signature * 33u) ^
            *(const u16 *)((const u8 *)object + 0x34 + n * 8);
    }
    if ((u32)object != g_anim_last_root ||
        graphics != g_anim_last_graphics ||
        (u32)g_anim_action != g_anim_last_action ||
        signature != g_anim_last_overlay_signature) {
        recomp_printf(
            "GOEMON_ANIM_ROOT,%u,%u,%u,%08x,%08x,%.9f,"
            "%u,%08x,%u,%08x,%u,%08x,%u,%08x,%u,%08x,%u,%08x\n",
            frame, (u32)character, (u32)g_anim_action,
            (u32)object, graphics, g_anim_model_progress,
            (u32)*(u16 *)((u8 *)object+0x34),ReadObjectU32(object,0x38),
            (u32)*(u16 *)((u8 *)object+0x3c),ReadObjectU32(object,0x40),
            (u32)*(u16 *)((u8 *)object+0x44),ReadObjectU32(object,0x48),
            (u32)*(u16 *)((u8 *)object+0x4c),ReadObjectU32(object,0x50),
            (u32)*(u16 *)((u8 *)object+0x54),ReadObjectU32(object,0x58),
            (u32)*(u16 *)((u8 *)object+0x5c),ReadObjectU32(object,0x60));
        // These are **live** source player Object and AnimatedSkeleton
        // pointers. Only dereference after the original 0x60000000
        // render gate, as done by the original renderer itself.
        const u32 encoded = graphics & 0x8ffffffeu;
        const u32 owner = ResolvePlayerObjectPointer(object, encoded);
        if (owner != 0) {
            const u32 flags = *(const u32 *)(owner + 0);
            const u32 raw_animation = *(const u32 *)(owner + 4);
            const u32 root_skeleton = *(const u32 *)(owner + 8);
            const u32 resolved_animation =
                ResolvePlayerObjectPointer(object, raw_animation);
            recomp_printf(
                "GOEMON_ANIM_OWNER,%u,%u,%u,%08x,%08x,%08x,"
                "%08x,%08x,%08x,%08x\n",
                frame,(u32)character,(u32)g_anim_action,
                (u32)object,graphics,owner,flags,
                raw_animation,resolved_animation,root_skeleton);
        }
        g_anim_last_root = (u32)object;
        g_anim_last_graphics = graphics;
        g_anim_last_action = (u32)g_anim_action;
        g_anim_last_overlay_signature = signature;
    }
}

// Scope to the player's genuine animation traversal. The original
// function is recursive; an entry/return pair maintains correct nesting.
// It runs only under the 0x60000000 original player-root render path.
RECOMP_HOOK("func_80018CA0_198A0")
void GoemonAnim_EnterLimb(GoemonAnimBone *skeleton, void *object) {
    if (!g_anim_active || !skeleton || !object)
        return;
    const u32 frame = (u32)D_8008CCC0_8D8C0.frames_elapsed;
    if (frame != g_anim_prior_frame ||
        g_anim_bones_in_frame >= GOEMON_ANIM_MAX_LIMBS_PER_FRAME)
        return;
    if (g_anim_stack_depth == 0) {
        if (D_801684A0_1690A0 != D_801FC614_5B8524 &&
            object != D_801FC614_5B8524 &&
            object != D_801FC60C_5B851C)
            return;
        if (g_anim_bones_in_frame == 0) {
            // At original player-limb entry the source renderer has
            // resolved AnimatedSkeleton.animation into D_80168520.
            recomp_printf(
                "GOEMON_ANIM_ACTIVE,%u,%u,%u,%08x,%08x,%08x,%.9f\n",
                frame,(u32)g_anim_character,(u32)g_anim_action,
                (u32)object,(u32)D_80168520_169120,
                (u32)D_80168530_169130,g_anim_model_progress);
        }
    }
    ++g_anim_stack_depth;
}

RECOMP_HOOK_RETURN("func_80018CA0_198A0")
void GoemonAnim_LeaveLimb(void) {
    if (g_anim_stack_depth > 0)
        --g_anim_stack_depth;
}

// Called by func_80018CA0 on every ORIGINAL player bone. Capture raw
// limb fields at entry, and the actual original MtxF *after* the game's
// animation matrix calculation returns, not an interpolated synthetic pose.
RECOMP_HOOK("func_800192D0_19ED0")
void GoemonAnim_BeforeMatrix(GoemonAnimBone *bone, void *object) {
    (void)object;
    g_anim_in_transform = 0;
    g_anim_pending_bone = NULL;
    if (!g_anim_active || !g_anim_stack_depth || !bone ||
        g_anim_bones_in_frame >= GOEMON_ANIM_MAX_LIMBS_PER_FRAME)
        return;
    if ((u32)D_8008CCC0_8D8C0.frames_elapsed != g_anim_prior_frame)
        return;
    ++g_anim_bones_in_frame;
    g_anim_pending_bone = bone;
    g_anim_pending_matrix_cursor = (u32)D_80168530_169130;
    g_anim_in_transform = 1;
    recomp_printf(
        "GOEMON_ANIM_BONE,%u,%u,%u,%08x,%08x,%d,%d,"
        "%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        g_anim_prior_frame, (u32)g_anim_character, (u32)g_anim_action,
        (u32)bone, bone->display_list_vram_addr,
        (s32)bone->offset_right, (s32)bone->offset_left,
        (s32)bone->scale_x,(s32)bone->scale_y,(s32)bone->scale_z,
        (s32)bone->rotation_x,(s32)bone->rotation_y,(s32)bone->rotation_z,
        (s32)bone->translation_x,(s32)bone->translation_y,
        (s32)bone->translation_z);
}

RECOMP_HOOK_RETURN("func_800192D0_19ED0")
void GoemonAnim_AfterMatrix(void) {
    if (!g_anim_in_transform || g_anim_pending_bone == NULL)
        return;
    const u32 after = (u32)D_80168530_169130;
    if (after < 64 || after < g_anim_pending_matrix_cursor ||
        ((after-g_anim_pending_matrix_cursor) % 64) != 0) {
        g_anim_in_transform = 0;
        g_anim_pending_bone = NULL;
        return;
    }
    recomp_printf(
        "GOEMON_ANIM_MATRIX_CURSOR,%u,%u,%u,%08x,%08x,%08x,%u\n",
        g_anim_prior_frame,(u32)g_anim_character,(u32)g_anim_action,
        (u32)g_anim_pending_bone,g_anim_pending_matrix_cursor,after,
        after-g_anim_pending_matrix_cursor);
    // D_801684B0 is the current/root MtxF, NOT necessarily the
    // transformed limb. The original MIPS function pushes a matrix
    // at D_80168530 (64 bytes, sometimes 128); its final pushed MtxF
    // starts exactly 64 bytes below the advanced destination pointer.
    const f32 *m = (const f32 *)(after-64);
    recomp_printf(
        "GOEMON_ANIM_MATRIX,%u,%u,%u,%08x,%.9f,"
        "%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,"
        "%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f,%.9f\n",
        g_anim_prior_frame,(u32)g_anim_character,(u32)g_anim_action,
        (u32)g_anim_pending_bone,g_anim_model_progress,
        m[0],m[1],m[2],m[3],
        m[4],m[5],m[6],m[7],
        m[8],m[9],m[10],m[11],
        m[12],m[13],m[14],m[15]);
    g_anim_in_transform = 0;
    g_anim_pending_bone = NULL;
}
