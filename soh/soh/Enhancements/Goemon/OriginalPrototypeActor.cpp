// First independent Goemon Actor proof inside Ship of Harkinian.
// This is a genuine registered Zelda Actor with its own lifetime and
// source-measured controller state; it does NOT move or disguise Link.
// Until the original graphics are decoded it renders a gold debug marker.
// Stick/camera mapping and Zelda collision response are provisional.
// Enable only with gSettings.Goemon.PrototypeActor = 1.
#include "OriginalLiveFrame.hpp"
#include "OriginalPilotCamera.hpp"
#include "OriginalZeldaActorTerrain.hpp"

#include <cmath>
#include <cstdint>
#include <exception>
#include <fstream>
#include <iomanip>
#include <locale>
#include <optional>

#include <libultraship/bridge/consolevariablebridge.h>
#include "soh/ActorDB.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"

extern "C" {
#include "z64.h"
#include "functions.h"
#include "macros.h"
extern PlayState* gPlayState;
}

#define CVAR_GOEMON_PROTOTYPE_ACTOR CVAR_SETTING("Goemon.PrototypeActor")
#define CVAR_GOEMON_PROTOTYPE_PILOT CVAR_SETTING("Goemon.PrototypePilot")

namespace {
using Goemon::Original::OriginalLiveFrameState;
using Goemon::Original::OriginalPlanarStep;
using Goemon::Original::ZeldaTerrainResult;
using Goemon::Original::ZeldaTerrainReject;
using Goemon::Original::WorldPoint;

int sActorId = -1;
Actor* sActor = nullptr;
OriginalLiveFrameState sLive{};
std::int32_t sScene = -1;
std::int32_t sRoom = -1;
std::uint64_t sFrame = 0;
std::ofstream sLog;
bool sSuspended = false;
bool sFaulted = false; // Clear only when prototype is explicitly disabled.

void CloseLog() {
    if (sLog.is_open()) sLog.close();
}

void ClearRuntime() {
    CloseLog();
    sActor = nullptr;
    sScene = -1;
    sRoom = -1;
    sFrame = 0;
    sLive = {};
    sSuspended = false;
}

void ResetMotionAtActor(Actor* actor) {
    sLive = {};
    sLive.controller.motion.groundX = actor->world.pos.x;
    sLive.controller.motion.groundY = actor->world.pos.y;
    sLive.controller.motion.groundZ = actor->world.pos.z;
}

bool AllowedToStep(PlayState* play, const Player* link) {
    if (link == nullptr || !GameInteractor::IsPlayerInControl() ||
        play->csCtx.state != CS_STATE_IDLE)
        return false;
    constexpr std::uint32_t badStates =
        PLAYER_STATE1_LOADING | PLAYER_STATE1_INPUT_DISABLED |
        PLAYER_STATE1_TALKING | PLAYER_STATE1_DEAD |
        PLAYER_STATE1_HANGING_OFF_LEDGE | PLAYER_STATE1_CLIMBING_LEDGE |
        PLAYER_STATE1_CLIMBING_LADDER | PLAYER_STATE1_ON_HORSE |
        PLAYER_STATE1_IN_WATER | PLAYER_STATE1_IN_CUTSCENE |
        PLAYER_STATE1_GETTING_ITEM;
    return !(link->stateFlags1 & badStates);
}

// Pilot is deliberately separate from spawning. With the Actor enabled
// but Pilot disabled, Link and the research Actor retain independent input.
bool PilotReady(PlayState* play, const Player* link) {
    return Goemon::Original::ShouldRouteInputToGoemon({
        CVarGetInteger(CVAR_GOEMON_PROTOTYPE_PILOT, 0) != 0,
        CVarGetInteger(CVAR_GOEMON_PROTOTYPE_ACTOR, 0) != 0,
        sActor != nullptr && sActor->update != nullptr && !sFaulted,
        play != nullptr && sScene == play->sceneNum,
        play != nullptr && AllowedToStep(play, link)
    });
}

void FollowPrototypeCamera() {
    PlayState* play = gPlayState;
    if (play == nullptr || gDbgCamEnabled ||
        play->pauseCtx.state != 0 || play->csCtx.state != CS_STATE_IDLE)
        return;

    Player* link = GET_PLAYER(play);
    if (!PilotReady(play, link)) return;
    // Read ONLY the already-updated vanilla camera view. This hook runs
    // after Camera_Update but before View matrices are generated.
    // No writes to Camera.player, Link, cutscene data or save state.
    const View& native = play->view;
    try {
        const auto focus = Goemon::Original::TranslatePilotCamera(
            {native.eye.x, native.eye.y, native.eye.z},
            {native.lookAt.x, native.lookAt.y, native.lookAt.z},
            {link->actor.world.pos.x, link->actor.world.pos.y,
             link->actor.world.pos.z},
            {sActor->world.pos.x, sActor->world.pos.y,
             sActor->world.pos.z});
        Vec3f eye{focus.eye.x, focus.eye.y, focus.eye.z};
        Vec3f at{focus.lookAt.x, focus.lookAt.y, focus.lookAt.z};
        Vec3f up = native.up;
        func_800AA358(&play->view, &eye, &at, &up);
    } catch (const std::exception&) {
        // Invalid coordinates must never disrupt the vanilla camera.
    }
}

std::optional<WorldPoint> QueryWall(PlayState* play, WorldPoint from,
                                    WorldPoint to) {
    // Terrain adapter already supplies the exact foot/chest ray height.
    // Adding the legacy +10 offset here would double-count that height.
    Vec3f start{from.x, from.y, from.z};
    Vec3f end{to.x, to.y, to.z};
    Vec3f contact{};
    CollisionPoly* poly = nullptr;
    s32 bgId = BGCHECK_SCENE;
    if (BgCheck_EntityLineTest1(&play->colCtx, &start, &end, &contact,
                                &poly, 1, 0, 0, 1, &bgId))
        return WorldPoint{contact.x, contact.y, contact.z};
    return std::nullopt;
}

std::optional<float> QueryFloor(PlayState* play, WorldPoint to) {
    Vec3f from{to.x, to.y + 50.0f, to.z};
    CollisionPoly* poly = nullptr;
    s32 bgId = BGCHECK_SCENE;
    const float y = BgCheck_EntityRaycastFloor3(
        &play->colCtx, &poly, &bgId, &from);
    if (poly != nullptr && y > BGCHECK_Y_MIN) return y;
    return std::nullopt;
}

void InitActor(Actor* actor, PlayState* play) {
    sActor = actor;
    sScene = play->sceneNum;
    sRoom = play->roomCtx.curRoom.num;
    actor->room = -1; // Continue across rooms in the same Zelda scene.
    sFrame = 0;
    sSuspended = false;
    ResetMotionAtActor(actor);
    CloseLog();
    sLog.open("goemon_prototype_actor.csv", std::ios::out | std::ios::trunc);
    if (sLog.is_open()) {
        sLog.imbue(std::locale::classic());
        sLog << std::setprecision(9);
        sLog << "frame,scene,room,ship_stick_x,ship_stick_y,preview_yaw10,"
                "action,measured_transition,actor_x,actor_y,actor_z,"
                "desired_dx,desired_dz,applied_dx,applied_dz,wall_hit,"
                "floor_found,preview_floor_snap,airborne,terrain_reject_code\n";
    }
}

void DestroyActor(Actor* actor, PlayState*) {
    if (actor == sActor) ClearRuntime();
}

void UpdateActor(Actor* actor, PlayState* play) {
    if (actor != sActor || !CVarGetInteger(CVAR_GOEMON_PROTOTYPE_ACTOR, 0) ||
        sScene != play->sceneNum) {
        Actor_Kill(actor);
        return;
    }
    const Player* link = GET_PLAYER(play);
    if (!AllowedToStep(play, link)) {
        // Do not consume gamepad events while Zelda's real player is in a
        // cutscene/interaction/unsupported traversal state.
        sSuspended = true;
        return;
    }
    if (sRoom != play->roomCtx.curRoom.num) {
        // Same scene, different room: preserve the Actor but reinitialize
        // its motion before sampling a newly active collision mesh.
        sRoom = play->roomCtx.curRoom.num;
        sSuspended = true;
    }
    if (sSuspended) {
        ResetMotionAtActor(actor);
        sSuspended = false;
    }
    const Input& pad = play->state.input[0];
    const auto yaw = Camera_GetInputDirYaw(GET_ACTIVE_CAM(play));
    const auto stick = Goemon::Original::MapShipStickForOriginalPreview(
        static_cast<int>(pad.cur.stick_x),
        static_cast<int>(pad.cur.stick_y), yaw);
    const bool jumpPressed = (pad.press.button & BTN_A) != 0;
    const bool jumpHeld = (pad.cur.button & BTN_A) != 0;

    try {
        ZeldaTerrainResult terrain{};
        auto resolve = [&](float x, float modelY, float z, float groundY,
                           bool airborne, OriginalPlanarStep desired)
            -> OriginalPlanarStep {
            terrain = Goemon::Original::ProbeConservativeZeldaTerrain(
                WorldPoint{x, modelY, z}, groundY, desired, airborne,
                Goemon::Original::ZeldaTerrainEnvelope{},
                [&](WorldPoint a, WorldPoint b) { return QueryWall(play, a, b); },
                [&](WorldPoint to) { return QueryFloor(play, to); });
            return terrain.applied;
        };
        const auto step = Goemon::Original::AdvanceOriginalLivePreview(
            sLive, stick, jumpPressed, jumpHeld, resolve);
        // A floor is only adopted when the provisional Zelda geometry
        // check has explicitly accepted this grounded movement.
        const bool previewFloor = terrain.floorFound &&
                                  terrain.rejection == ZeldaTerrainReject::None &&
                                  !step.motion.airborne;
        if (previewFloor) sLive.controller.motion.groundY = terrain.floorY;

        const auto& pose = sLive.controller.motion;
        actor->prevPos = actor->world.pos;
        actor->world.pos = {pose.groundX, pose.ModelY(), pose.groundZ};
        if (stick.kind == Goemon::Original::ShipPreviewStickKind::Full) {
            // Only an actual directional stick input updates facing.
            // The yaw conversion remains a temporary Ship preview.
            actor->world.rot.y = static_cast<s16>(
                static_cast<std::uint16_t>(stick.provisionalOriginalYaw10) << 6);
            actor->shape.rot.y = actor->world.rot.y;
        }
        Actor_SetFocus(actor, 18.0f);

        // Native debug marker is deliberately not presented as a Goemon mesh.
        DebugDisplay_AddObject(
            actor->world.pos.x, actor->world.pos.y + 18.0f,
            actor->world.pos.z, 0, 0, 0, 2.0f, 2.0f, 2.0f,
            static_cast<std::uint8_t>(255),
            static_cast<std::uint8_t>(terrain.rejection != ZeldaTerrainReject::None ? 50 : 178),
            static_cast<std::uint8_t>(terrain.rejection != ZeldaTerrainReject::None ? 50 : 32),
            static_cast<std::uint8_t>(230), 2, play->state.gfxCtx);

        if (sLog.is_open())
            sLog << sFrame++ << ',' << sScene << ',' << sRoom << ','
                 << static_cast<int>(pad.cur.stick_x) << ','
                 << static_cast<int>(pad.cur.stick_y) << ','
                 << stick.provisionalOriginalYaw10 << ','
                 << static_cast<unsigned>(step.action) << ','
                 << static_cast<int>(step.measuredTransitionSupported) << ','
                 << actor->world.pos.x << ',' << actor->world.pos.y << ','
                 << actor->world.pos.z << ','
                 << step.motion.desiredPlanar.x << ','
                 << step.motion.desiredPlanar.z << ','
                 << step.motion.appliedPlanar.x << ','
                 << step.motion.appliedPlanar.z << ','
                 << static_cast<int>(terrain.wallHit) << ','
                 << static_cast<int>(terrain.floorFound) << ','
                 << static_cast<int>(previewFloor) << ','
                 << static_cast<int>(step.motion.airborne) << ','
                 << static_cast<int>(terrain.rejection) << '\n';
    } catch (const std::exception& error) {
        // Keep the fatal diagnostic and do not auto-respawn every frame.
        // The user can disable then re-enable the prototype to retry.
        std::ofstream failure("goemon_prototype_actor_error.txt",
                              std::ios::out | std::ios::trunc);
        if (failure.is_open()) failure << error.what() << '\n';
        sFaulted = true;
        CloseLog();
        Actor_Kill(actor);
    }
}

void SpawnWhenRequested() {
    if (gPlayState == nullptr || sActorId < 0) return;
    if (!CVarGetInteger(CVAR_GOEMON_PROTOTYPE_ACTOR, 0)) {
        if (sActor != nullptr && sActor->update != nullptr)
            Actor_Kill(sActor);
        sFaulted = false;
        return;
    }
    if (sActor != nullptr || sFaulted) return;
    Player* link = GET_PLAYER(gPlayState);
    if (!AllowedToStep(gPlayState, link) ||
        !(link->actor.bgCheckFlags & BGCHECKFLAG_GROUND)) return;
    const Vec3f& p = link->actor.world.pos;
    // Category PROP is updated independently after the PLAYER category.
    // Only one prototype Actor is spawned at a time.
    Actor* spawned = Actor_Spawn(&gPlayState->actorCtx, gPlayState,
                                static_cast<s16>(sActorId),
                                p.x, p.y, p.z, 0, link->actor.shape.rot.y, 0, 0);
    // Actor initialization may be deferred until its object bank loads.
    // Remember the spawned pointer immediately to prevent duplicate spawns.
    if (spawned != nullptr) sActor = spawned;
}

void RegisterActor() {
    ActorDBInit init{};
    init.name = "GoemonOriginalPrototype";
    init.desc = "Independent NG5E movement research Actor (no model yet)";
    init.category = ACTORCAT_PROP;
    init.objectId = OBJECT_GAMEPLAY_KEEP;
    init.instanceSize = sizeof(Actor);
    init.init = InitActor;
    init.destroy = DestroyActor;
    init.update = UpdateActor;
    // DebugDisplay draws in update; original model draw is a separate stage.
    auto& entry = ActorDB::Instance->AddEntry(init);
    sActorId = entry.entry.id;
    COND_HOOK(OnPlayerUpdate, true, SpawnWhenRequested);
    COND_HOOK(OnPlayDrawBegin, true, FollowPrototypeCamera);
    COND_HOOK(OnPlayDestroy, true, ClearRuntime);
}
} // namespace

// Called only on the local input copy inside Player_Update; original
// play->state.input[] stays untouched so the separate Actor still receives
// the full gamepad. Pilot off -> vanilla behavior without modification.
extern "C" void Goemon_PrototypeFilterLinkInput(
    PlayState* play, Player* link, Input* input) {
    if (input == nullptr || !PilotReady(play, link)) return;
    *input = {};
}

static RegisterShipInitFunc registerPrototypeActor(RegisterActor);
