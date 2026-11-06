// First independent Goemon Actor proof inside Ship of Harkinian.
// This is a genuine registered Zelda Actor with its own lifetime and
// source-measured controller state; it does NOT move or disguise Link.
// Until the original graphics are decoded it renders a gold debug marker.
// Stick/camera mapping and Zelda collision response are provisional.
// Enable only with gSettings.Goemon.PrototypeActor = 1.
#include "OriginalLiveFrame.hpp"
#include "OriginalZeldaWorldProbe.hpp"

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

namespace {
using Goemon::Original::OriginalLiveFrameState;
using Goemon::Original::OriginalPlanarStep;
using Goemon::Original::WorldCollisionProbe;
using Goemon::Original::WorldPoint;

int sActorId = -1;
Actor* sActor = nullptr;
OriginalLiveFrameState sLive{};
std::int32_t sScene = -1;
std::uint64_t sFrame = 0;
std::ofstream sLog;
bool sSuspended = false;

void CloseLog() {
    if (sLog.is_open()) sLog.close();
}

void ClearRuntime() {
    CloseLog();
    sActor = nullptr;
    sScene = -1;
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
        play->csCtx.state != CS_STATE_IDLE ||
        !(link->actor.bgCheckFlags & BGCHECKFLAG_GROUND))
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

std::optional<WorldPoint> QueryWall(PlayState* play, WorldPoint from,
                                    WorldPoint to) {
    Vec3f start{from.x, from.y + 10.0f, from.z};
    Vec3f end{to.x, to.y + 10.0f, to.z};
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
    sFrame = 0;
    sSuspended = false;
    ResetMotionAtActor(actor);
    CloseLog();
    sLog.open("goemon_prototype_actor.csv", std::ios::out | std::ios::trunc);
    if (sLog.is_open()) {
        sLog.imbue(std::locale::classic());
        sLog << std::setprecision(9);
        sLog << "frame,scene,action,measured_transition,actor_x,actor_y,actor_z,"
                "desired_dx,desired_dz,applied_dx,applied_dz,wall_hit,"
                "floor_found,preview_floor_snap,airborne\n";
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
        WorldCollisionProbe probe{};
        auto resolve = [&](float x, float z, OriginalPlanarStep desired)
            -> OriginalPlanarStep {
            probe = Goemon::Original::ProbeOriginalStepAgainstWorld(
                WorldPoint{x, sLive.controller.motion.ModelY(), z}, desired,
                [&](WorldPoint a, WorldPoint b) { return QueryWall(play, a, b); },
                [&](WorldPoint to) { return QueryFloor(play, to); });
            // Temporary diagnostic wall-ray block, NOT original Goemon
            // collision. No contact radius or wall-slide has been proven.
            return probe.wallHit ? OriginalPlanarStep{} : desired;
        };
        const auto step = Goemon::Original::AdvanceOriginalLivePreview(
            sLive, stick, jumpPressed, jumpHeld, resolve);
        const auto floor = Goemon::Original::PreviewGhostGroundHeight(
            probe, step.motion.airborne);
        if (floor) sLive.controller.motion.groundY = *floor;

        const auto& pose = sLive.controller.motion;
        actor->prevPos = actor->world.pos;
        actor->world.pos = {pose.groundX, pose.ModelY(), pose.groundZ};
        actor->world.rot.y = static_cast<s16>(
            static_cast<std::uint16_t>(stick.provisionalOriginalYaw10) << 6);
        actor->shape.rot.y = actor->world.rot.y;
        Actor_SetFocus(actor, 18.0f);

        // Native debug marker is deliberately not presented as a Goemon mesh.
        DebugDisplay_AddObject(
            actor->world.pos.x, actor->world.pos.y + 18.0f,
            actor->world.pos.z, 0, 0, 0, 2.0f, 2.0f, 2.0f,
            static_cast<std::uint8_t>(probe.wallHit ? 255 : 255),
            static_cast<std::uint8_t>(probe.wallHit ? 50 : 178),
            static_cast<std::uint8_t>(probe.wallHit ? 50 : 32),
            static_cast<std::uint8_t>(230), 2, play->state.gfxCtx);

        if (sLog.is_open())
            sLog << sFrame++ << ',' << sScene << ','
                 << static_cast<unsigned>(step.action) << ','
                 << static_cast<int>(step.measuredTransitionSupported) << ','
                 << actor->world.pos.x << ',' << actor->world.pos.y << ','
                 << actor->world.pos.z << ','
                 << step.motion.desiredPlanar.x << ','
                 << step.motion.desiredPlanar.z << ','
                 << step.motion.appliedPlanar.x << ','
                 << step.motion.appliedPlanar.z << ','
                 << static_cast<int>(probe.wallHit) << ','
                 << static_cast<int>(probe.floorFound) << ','
                 << static_cast<int>(floor.has_value()) << ','
                 << static_cast<int>(step.motion.airborne) << '\n';
    } catch (const std::exception&) {
        // Isolate failures from vanilla Link: dispose of the prototype.
        Actor_Kill(actor);
    }
}

void SpawnWhenRequested() {
    if (gPlayState == nullptr || sActorId < 0) return;
    if (!CVarGetInteger(CVAR_GOEMON_PROTOTYPE_ACTOR, 0)) {
        if (sActor != nullptr && sActor->update != nullptr)
            Actor_Kill(sActor);
        return;
    }
    if (sActor != nullptr) return;
    Player* link = GET_PLAYER(gPlayState);
    if (!AllowedToStep(gPlayState, link)) return;
    const Vec3f& p = link->actor.world.pos;
    // Category PROP is updated independently after the PLAYER category.
    // Only one prototype Actor is spawned at a time.
    (void)Actor_Spawn(&gPlayState->actorCtx, gPlayState,
                      static_cast<s16>(sActorId),
                      p.x, p.y, p.z, 0, link->actor.shape.rot.y, 0, 0);
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
    COND_HOOK(OnPlayDestroy, true, ClearRuntime);
}
} // namespace

static RegisterShipInitFunc registerPrototypeActor(RegisterActor);
