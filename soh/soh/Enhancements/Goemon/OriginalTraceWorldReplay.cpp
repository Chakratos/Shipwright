// Dry-run genuine Goemon desired-movement vectors against actual Zelda
// wall/floor collision. Read-only with respect to Ship actors, Link, item
// and Randomizer state. This is NOT a playable character controller.
//
// The original capture has its own action/character phases and exact
// PlayerTask X/Z vectors. We replay ONE original sample per Ship player
// update into a private "ghost" pose. No source Goemon assets are loaded.
//
// This bridge intentionally assumes 1 source world unit -> 1 Zelda unit
// only for DIAGNOSTIC contact sampling. It does not establish scale,
// original collision capsule radius, floor snap or physics-tick parity.
#include "OriginalTraceReplay.hpp"
#include "OriginalZeldaWorldProbe.hpp"

#include <cstdint>
#include <exception>
#include <fstream>
#include <iomanip>
#include <locale>
#include <memory>
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

#define CVAR_GOEMON_REPLAY CVAR_SETTING("Goemon.OriginalTraceWorldReplay")

namespace {
using Goemon::Original::OriginalMotionReplay;
using Goemon::Original::OriginalRecordedMovement;
using Goemon::Original::WorldPoint;
using Goemon::Original::OriginalPlanarStep;

std::unique_ptr<OriginalMotionReplay> sReplay;
std::ofstream sLog;
WorldPoint sGhost{};
std::int32_t sScene = -1;
bool sFinished = false;
bool sLoadFailed = false;

void ResetReplay() {
    if (sLog.is_open()) sLog.close();
    sReplay.reset();
    sGhost = {};
    sScene = -1;
    sFinished = false;
    sLoadFailed = false;
}

std::optional<WorldPoint> QueryZeldaWall(WorldPoint from, WorldPoint to) {
    Vec3f a{from.x, from.y + 10.0f, from.z};
    Vec3f b{to.x, to.y + 10.0f, to.z};
    Vec3f intersection{};
    CollisionPoly* poly = nullptr;
    s32 bgId = BGCHECK_SCENE;
    if (BgCheck_EntityLineTest1(
        &gPlayState->colCtx, &a, &b, &intersection, &poly,
        1, 0, 0, 1, &bgId)) {
        return WorldPoint{intersection.x, intersection.y, intersection.z};
    }
    return std::nullopt;
}

std::optional<float> QueryZeldaFloor(WorldPoint projected) {
    Vec3f origin{projected.x, projected.y + 50.0f, projected.z};
    CollisionPoly* poly = nullptr;
    s32 bgId = BGCHECK_SCENE;
    const float floor = BgCheck_EntityRaycastFloor3(
        &gPlayState->colCtx, &poly, &bgId, &origin);
    if (poly != nullptr && floor > BGCHECK_Y_MIN) return floor;
    return std::nullopt;
}

void StepOriginalGhost() {
    if (CVarGetInteger(CVAR_GOEMON_REPLAY, 0) == 0 || gPlayState == nullptr) {
        ResetReplay();
        return;
    }
    if (sFinished || sLoadFailed) return;
    Player* link = GET_PLAYER(gPlayState);
    if (link == nullptr) return;

    if (!sReplay) {
        try {
            std::ifstream original("goemon_original_motion_replay.csv");
            if (!original.is_open()) {
                sLoadFailed = true;
                return; // User must provide an original numeric trace.
            }
            sReplay = std::make_unique<OriginalMotionReplay>(original);
            sLog.open("goemon_original_vs_zelda_world.csv",
                      std::ios::out | std::ios::trunc);
            if (!sLog.is_open()) {
                sLoadFailed = true;
                sReplay.reset();
                return;
            }
            sLog.imbue(std::locale::classic());
            sLog << std::setprecision(9);
            sLog << "sample,goemon_frame,character_id,action_id,"
                    "scene,source_continuous,ghost_x,ghost_y,ghost_z,"
                    "desired_dx,desired_dz,applied_dx,applied_dz,"
                    "wall_hit,floor_found,floor_y\n";
            sScene = -1;
        } catch (const std::exception&) {
            sLoadFailed = true; // Malformed trace never mutates game.
            sReplay.reset();
            return;
        }
    }

    OriginalRecordedMovement frame{};
    if (!sReplay->Next(frame)) {
        sFinished = true;
        if (sLog.is_open()) sLog.close();
        return;
    }
    const auto currentScene = static_cast<std::int32_t>(gPlayState->sceneNum);
    if (sScene != currentScene || !frame.continuousOriginalUpdate) {
        // Reset on original character/frame discontinuity or Zelda room/scene
        // transition. Never carry stale ghost pose across a new geometry.
        sGhost = {
            link->actor.world.pos.x,
            link->actor.world.pos.y,
            link->actor.world.pos.z,
        };
        sScene = currentScene;
    }
    const auto measured = Goemon::Original::ProbeOriginalStepAgainstWorld(
        sGhost, frame.originalDesired, QueryZeldaWall, QueryZeldaFloor);

    // Conservative ghost-only diagnostic: a ray hit blocks the ENTIRE
    // desired planar movement. This is NOT an authentic Goemon collision
    // solver and must never be used to move the actual player Actor.
    OriginalPlanarStep applied = measured.wallHit
        ? OriginalPlanarStep{0.0f, 0.0f}
        : frame.originalDesired;
    sGhost.x += applied.x;
    sGhost.z += applied.z;
    if (!measured.wallHit && measured.floorFound)
        sGhost.y = measured.floorHeight; // Diagnostic only.

    sLog << frame.sample << ',' << frame.gameFrame << ','
         << static_cast<unsigned>(frame.characterId) << ','
         << frame.actionId << ',' << sScene << ','
         << static_cast<int>(frame.continuousOriginalUpdate) << ','
         << sGhost.x << ',' << sGhost.y << ',' << sGhost.z << ','
         << frame.originalDesired.x << ',' << frame.originalDesired.z << ','
         << applied.x << ',' << applied.z << ','
         << static_cast<int>(measured.wallHit) << ','
         << static_cast<int>(measured.floorFound) << ','
         << measured.floorHeight << '\n';
}

void RegisterOriginalWorldReplay() {
    COND_HOOK(OnPlayerUpdate, true, StepOriginalGhost);
}
} // namespace

static RegisterShipInitFunc registerOriginalWorldReplay(RegisterOriginalWorldReplay);
