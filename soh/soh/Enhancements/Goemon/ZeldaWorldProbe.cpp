// Live Ship of Harkinian geometry diagnostics for future original Goemon
// character world integration. Never mutates Link, player, collision polys,
// save state or a Zelda Actor. Disabled by default via console CVAR.
//
// Enable only to map original desired 2.8-world-unit movement probes against
// real Zelda wall/floor geometry; the diagnostic heading comes from Link's
// shape yaw, not from the still-unported original camera/stick handler.
// This is deliberately not a Link reskin or playable Goemon implementation.
#include "OriginalZeldaWorldProbe.hpp"
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <locale>
#include <numbers>
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

#define CVAR_GOEMON_ZELDA_PROBE CVAR_SETTING("Goemon.ZeldaWorldProbe")

namespace {
using Goemon::Original::OriginalPlanarStep;
using Goemon::Original::WorldPoint;

std::ofstream sProbe;
std::uint64_t sProbeFrame = 0;

void CloseProbe() {
    if (sProbe.is_open()) {
        sProbe.flush();
        sProbe.close();
    }
}

void ProbeZeldaGeometry() {
    if (CVarGetInteger(CVAR_GOEMON_ZELDA_PROBE, 0) == 0 || gPlayState == nullptr) {
        CloseProbe();
        return;
    }
    Player* player = GET_PLAYER(gPlayState);
    if (player == nullptr) {
        CloseProbe();
        return;
    }

    // Link yaw is only a diagnostic direction for the collision query.
    // Never feed it back into original Goemon controller state.
    constexpr float kN64AngleToRadians = std::numbers::pi_v<float> / 32768.0f;
    float angle = static_cast<float>(player->actor.shape.rot.y) * kN64AngleToRadians;
    const float speed = Goemon::Original::kOriginalFullRunSpeed;
    const OriginalPlanarStep desired = {
        speed * std::sin(angle), speed * std::cos(angle)
    };
    const WorldPoint position = {
        player->actor.world.pos.x,
        player->actor.world.pos.y,
        player->actor.world.pos.z
    };
    auto wallQuery = [](WorldPoint origin, WorldPoint destination)
        -> std::optional<WorldPoint> {
        Vec3f from{origin.x, origin.y + 10.0f, origin.z};
        Vec3f to{destination.x, destination.y + 10.0f, destination.z};
        Vec3f hit{};
        CollisionPoly* poly = nullptr;
        s32 bgId = BGCHECK_SCENE;
        const s32 collides = BgCheck_EntityLineTest1(
            &gPlayState->colCtx, &from, &to, &hit, &poly,
            1, 0, 0, 1, &bgId);
        if (collides) {
            return WorldPoint{hit.x, hit.y, hit.z};
        }
        return std::nullopt;
    };
    auto floorQuery = [](WorldPoint destination) -> std::optional<float> {
        // The cast origin and line offset are DIAGNOSTIC. Their height
        // is not the original Goemon actor's proven step or floor radius.
        Vec3f from{destination.x, destination.y + 50.0f, destination.z};
        CollisionPoly* poly = nullptr;
        s32 bgId = BGCHECK_SCENE;
        float ground = BgCheck_EntityRaycastFloor3(
            &gPlayState->colCtx, &poly, &bgId, &from);
        if (poly != nullptr && ground > BGCHECK_Y_MIN) return ground;
        return std::nullopt;
    };
    const auto probe = Goemon::Original::ProbeOriginalStepAgainstWorld(
        position, desired, wallQuery, floorQuery);

    if (!sProbe.is_open()) {
        sProbe.open("goemon_zelda_world_probe.csv", std::ios::out | std::ios::trunc);
        if (!sProbe.is_open()) return;
        sProbe.imbue(std::locale::classic());
        sProbe << std::setprecision(9);
        sProbe << "frame,scene,link_yaw,link_x,link_y,link_z,"
                  "desired_dx,desired_dz,projected_x,projected_z,"
                  "wall_hit,wall_x,wall_y,wall_z,floor_found,floor_y\n";
        sProbeFrame = 0;
    }
    sProbe << sProbeFrame++ << ',' << gPlayState->sceneNum << ','
           << static_cast<int>(player->actor.shape.rot.y) << ','
           << probe.from.x << ',' << probe.from.y << ',' << probe.from.z << ','
           << probe.desired.x << ',' << probe.desired.z << ','
           << probe.to.x << ',' << probe.to.z << ','
           << static_cast<int>(probe.wallHit) << ','
           << probe.wallContact.x << ',' << probe.wallContact.y << ','
           << probe.wallContact.z << ','
           << static_cast<int>(probe.floorFound) << ','
           << probe.floorHeight << '\n';
}

void RegisterGoemonWorldProbe() {
    COND_HOOK(OnPlayerUpdate, true, ProbeZeldaGeometry);
}
} // namespace

static RegisterShipInitFunc registerGoemonWorldProbe(RegisterGoemonWorldProbe);
