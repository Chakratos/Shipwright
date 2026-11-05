// Read-only Ship of Harkinian movement trace for Goemon controller reverse engineering.
//
// This is deliberately NOT a Goemon player controller. Capturing measured behavior
// before implementing it prevents approximate Link-based replacements from being
// mistaken for the original Mystical Ninja Starring Goemon mechanics.
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <locale>

#include <libultraship/bridge/consolevariablebridge.h>

#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"

extern "C" {
#include "z64.h"
#include "macros.h"
extern PlayState* gPlayState;
}

#define CVAR_GOEMON_SHIP_TRACE CVAR_SETTING("Goemon.ShipTrace")

namespace {
std::ofstream sTrace;
std::uint64_t sFrame = 0;

// Called on the existing player-update hook. It must never change Player state.
void RecordShipPlayerFrame() {
    if (CVarGetInteger(CVAR_GOEMON_SHIP_TRACE, 0) == 0 || gPlayState == nullptr) {
        if (sTrace.is_open()) {
            sTrace.close();
        }
        return;
    }

    Player* player = GET_PLAYER(gPlayState);
    if (player == nullptr) {
        return;
    }

    if (!sTrace.is_open()) {
        // Capture starts a new trace each time the setting is enabled.
        // The file is relative to Ship's current working directory.
        sTrace.open("goemon_ship_trace.csv", std::ios::out | std::ios::trunc);
        if (!sTrace.is_open()) {
            return;
        }
        sTrace.imbue(std::locale::classic());
        sTrace << std::setprecision(9);
        sTrace << "frame,scene,buttons,stick_x,stick_y,pos_x,pos_y,pos_z,"
                  "velocity_x,velocity_y,velocity_z,linear_velocity,yaw,grounded,"
                  "state_flags1,state_flags2\n";
        sFrame = 0;
    }

    const Input& input = gPlayState->state.input[0];
    sTrace << sFrame++ << ',' << gPlayState->sceneNum << ','
           << static_cast<unsigned>(input.cur.button) << ','
           << static_cast<int>(input.cur.stick_x) << ','
           << static_cast<int>(input.cur.stick_y) << ','
           << player->actor.world.pos.x << ','
           << player->actor.world.pos.y << ','
           << player->actor.world.pos.z << ','
           << player->actor.velocity.x << ','
           << player->actor.velocity.y << ','
           << player->actor.velocity.z << ','
           << player->linearVelocity << ','
           << player->actor.shape.rot.y << ','
           << ((player->actor.bgCheckFlags & 1) != 0 ? 1 : 0) << ','
           << player->stateFlags1 << ','
           << player->stateFlags2 << '\n';
}

void RegisterGoemonShipTrace() {
    // Register once. The CVAR is checked at runtime, allowing live toggling.
    COND_HOOK(OnPlayerUpdate, true, RecordShipPlayerFrame);
}
} // namespace

static RegisterShipInitFunc registerGoemonShipTrace(RegisterGoemonShipTrace);
