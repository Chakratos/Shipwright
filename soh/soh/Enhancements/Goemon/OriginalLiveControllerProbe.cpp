// Input-driven Goemon motion GHOST in the real Zelda collision world.
// Uses independently measured NG5E horizontal/vertical motion, but Ship
// stick->target yaw, Goemon action selection, wall/floor response and unit
// scale are currently PROVISIONAL, explicitly separated from the original
// controller. This module NEVER changes Link's Actor or game state.
//
// Enable: gSettings.Goemon.LiveControllerGhost = 1
// Logs: goemon_live_controller_ghost.csv in Ship's working directory.
// No Goemon ROM/assets are loaded into Ship and no synthetic trace is
// presented as original runtime evidence.
#include "OriginalLiveInput.hpp"
#include "OriginalZeldaWorldProbe.hpp"

#include <cmath>
#include <cstdint>
#include <exception>
#include <fstream>
#include <iomanip>
#include <locale>
#include <optional>

#include <libultraship/bridge/consolevariablebridge.h>
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"

extern "C" {
#include "z64.h"
#include "functions.h"
#include "macros.h"
extern PlayState* gPlayState;
}

#define CVAR_GOEMON_LIVE_GHOST CVAR_SETTING("Goemon.LiveControllerGhost")
#define CVAR_GOEMON_LIVE_GHOST_DRAW CVAR_SETTING("Goemon.LiveControllerGhostDraw")

namespace {
using Goemon::Original::OriginalPlanarStep;
using Goemon::Original::WorldPoint;
using Goemon::Original::WorldCollisionProbe;
using Goemon::Original::OriginalVectorControllerState;
using Goemon::Original::OriginalMeasuredMotionInput;
using Goemon::Original::OriginalMeasuredPlanarPhase;
using Goemon::Original::ShipPreviewStickKind;

OriginalVectorControllerState sController;
std::ofstream sLog;
std::int32_t sScene = -1;
std::uint64_t sFrame = 0;
std::uint8_t sPreviousAction = 0;
std::int16_t sPreviousStickX = 0;
std::int16_t sPreviousStickY = 0;
bool sInitialized = false;

void ResetPreview() {
    if (sLog.is_open()) sLog.close();
    sController = {};
    sScene = -1;
    sFrame = 0;
    sPreviousAction = 0;
    sPreviousStickX = 0;
    sPreviousStickY = 0;
    sInitialized = false;
}

std::optional<WorldPoint> WallQuery(WorldPoint from, WorldPoint to) {
    // Diagnostic intersection ray, not the source Goemon collision hull.
    Vec3f a{from.x, from.y + 10.0f, from.z};
    Vec3f b{to.x, to.y + 10.0f, to.z};
    Vec3f intersection{};
    CollisionPoly* poly = nullptr;
    s32 bgId = BGCHECK_SCENE;
    if (BgCheck_EntityLineTest1(&gPlayState->colCtx, &a, &b, &intersection,
                                &poly, 1, 0, 0, 1, &bgId)) {
        return WorldPoint{intersection.x, intersection.y, intersection.z};
    }
    return std::nullopt;
}

std::optional<float> FloorQuery(WorldPoint projected) {
    // Query Zelda geometry but do not invent original floor snapping.
    Vec3f cast{projected.x, projected.y + 50.0f, projected.z};
    CollisionPoly* poly = nullptr;
    s32 bgId = BGCHECK_SCENE;
    const float y = BgCheck_EntityRaycastFloor3(
        &gPlayState->colCtx, &poly, &bgId, &cast);
    if (poly != nullptr && y > BGCHECK_Y_MIN) return y;
    return std::nullopt;
}

void RecordLiveControllerGhost() {
    if (CVarGetInteger(CVAR_GOEMON_LIVE_GHOST, 0) == 0 ||
        gPlayState == nullptr) {
        ResetPreview();
        return;
    }
    Player* link = GET_PLAYER(gPlayState);
    if (link == nullptr || gPlayState->csCtx.state != CS_STATE_IDLE ||
        (link->stateFlags1 & (PLAYER_STATE1_DEAD | PLAYER_STATE1_IN_CUTSCENE |
                              PLAYER_STATE1_INPUT_DISABLED))) {
        ResetPreview();
        return;
    }

    if (!sInitialized || sScene != gPlayState->sceneNum) {
        sController = {};
        sController.motion.groundX = link->actor.world.pos.x;
        sController.motion.groundY = link->actor.world.pos.y;
        sController.motion.groundZ = link->actor.world.pos.z;
        sScene = gPlayState->sceneNum;
        sPreviousAction = 0;
        sPreviousStickX = 0;
        sPreviousStickY = 0;
        sInitialized = true;
        if (sLog.is_open()) sLog.close();
        sLog.open("goemon_live_controller_ghost.csv",
                  std::ios::out | std::ios::trunc);
        if (sLog.is_open()) {
            sLog.imbue(std::locale::classic());
            sLog << std::setprecision(9);
            sLog << "frame,scene,ship_stick_x,ship_stick_y,"
                    "preview_stick_kind,preview_action,action_supported,"
                    "provisional_target_yaw10,desired_dx,desired_dz,"
                    "applied_dx,applied_dz,ghost_x,ghost_y,ghost_z,"
                    "link_x,link_y,link_z,ghost_airborne,wall_hit,"
                    "floor_found,zelda_floor_y\n";
        }
    }

    const Input& pad = gPlayState->state.input[0];
    // Use Ship's current camera heading only as a temporary interactive
    // target. Recover the genuine Goemon camera filter separately.
    const auto shipCameraYaw = Camera_GetInputDirYaw(GET_ACTIVE_CAM(gPlayState));
    const auto stick = Goemon::Original::MapShipStickForOriginalPreview(
        static_cast<int>(pad.cur.stick_x),
        static_cast<int>(pad.cur.stick_y), shipCameraYaw);
    const bool jumpPressed = (pad.press.button & BTN_A) != 0;
    const bool jumpHeld = (pad.cur.button & BTN_A) != 0;
    const float priorSpeed = std::hypot(
        sController.previousDesiredVelocity.x,
        sController.previousDesiredVelocity.z);
    const bool previouslyAirborne = sController.motion.jump.airborne;
    const auto proposed = Goemon::Original::ComposeShipPreviewOriginalInput(
        stick, sPreviousAction, sPreviousStickX, sPreviousStickY,
        previouslyAirborne, jumpPressed, jumpHeld, priorSpeed);

    try {
        if (jumpPressed && !previouslyAirborne)
            Goemon::Original::BeginOriginalJump(sController.motion.jump);

        WorldCollisionProbe probe{};
        auto resolve = [&](float x, float z, OriginalPlanarStep desired)
            -> OriginalPlanarStep {
            probe = Goemon::Original::ProbeOriginalStepAgainstWorld(
                WorldPoint{x, sController.motion.ModelY(), z}, desired,
                WallQuery, FloorQuery);
            // Conservative ghost-only block; NOT the original Goemon
            // collision response. Desired velocity remains unchanged.
            return probe.wallHit ? OriginalPlanarStep{0.0f, 0.0f} : desired;
        };

        std::optional<Goemon::Original::OriginalMotionFrame> step;
        std::uint8_t numericAction = 0;
        if (proposed) {
            numericAction = proposed->action;
            step = Goemon::Original::AdvanceMeasuredOriginalVectorController(
                sController, *proposed, resolve);
        }
        if (step) {
            sPreviousAction = numericAction;
        } else {
            // Unsupported input phases freeze horizontal motion. Vertical
            // Goemon jump integrates independently, including idle jump.
            sController.previousDesiredVelocity = {0.0f, 0.0f};
            sController.hasPrior = false;
            sController.braking = false;
            sController.motion.horizontal.ResetForOriginalIdle();
            OriginalMeasuredMotionInput idle{};
            idle.horizontalPhase =
                OriginalMeasuredPlanarPhase::SuppressWhileActionLocked;
            idle.aButtonHeld = jumpHeld;
            step = Goemon::Original::AdvanceOriginalFlatGround(
                sController.motion, idle, resolve);
            sPreviousAction = 0;
        }
        sPreviousStickX = stick.x;
        sPreviousStickY = stick.y;

        // Native Zelda debug ball: display our private source-driven
        // ghost pose in the scene without spawning or modifying an Actor.
        // Red = the diagnostic Zelda wall ray blocked this update.
        // Cyan = otherwise. This is NOT an original Goemon 3D model.
        if (CVarGetInteger(CVAR_GOEMON_LIVE_GHOST_DRAW, 1) != 0) {
            DebugDisplay_AddObject(
                sController.motion.groundX, step->modelY + 18.0f,
                sController.motion.groundZ,
                0, 0, 0, 1.4f, 1.4f, 1.4f,
                static_cast<std::uint8_t>(probe.wallHit ? 255 : 32),
                static_cast<std::uint8_t>(probe.wallHit ? 56 : 208),
                static_cast<std::uint8_t>(probe.wallHit ? 56 : 255),
                static_cast<std::uint8_t>(220), 2,
                gPlayState->state.gfxCtx);
        }

        if (sLog.is_open()) {
            sLog << sFrame++ << ',' << sScene << ','
                 << static_cast<int>(pad.cur.stick_x) << ','
                 << static_cast<int>(pad.cur.stick_y) << ','
                 << static_cast<int>(stick.kind) << ','
                 << static_cast<unsigned>(numericAction) << ','
                 << static_cast<int>(numericAction != 0 &&
                                     sPreviousAction == numericAction) << ','
                 << stick.provisionalOriginalYaw10 << ','
                 << step->desiredPlanar.x << ',' << step->desiredPlanar.z << ','
                 << step->appliedPlanar.x << ',' << step->appliedPlanar.z << ','
                 << sController.motion.groundX << ','
                 << step->modelY << ','
                 << sController.motion.groundZ << ','
                 << link->actor.world.pos.x << ','
                 << link->actor.world.pos.y << ','
                 << link->actor.world.pos.z << ','
                 << static_cast<int>(step->airborne) << ','
                 << static_cast<int>(probe.wallHit) << ','
                 << static_cast<int>(probe.floorFound) << ','
                 << probe.floorHeight << '\n';
        }
    } catch (const std::exception&) {
        // Never permit unsupported world geometry to mutate Ship or
        // propagate an exception into the game update loop.
        ResetPreview();
    }
}

void RegisterOriginalLiveControllerGhost() {
    COND_HOOK(OnPlayerUpdate, true, RecordLiveControllerGhost);
}
} // namespace

static RegisterShipInitFunc registerLiveControllerGhost(
    RegisterOriginalLiveControllerGhost);
