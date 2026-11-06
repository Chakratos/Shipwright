// First renderer-visible Goemon character integration, independent of the
// discarded diagnostic Actor. Real N64 extracted OBJ geometry, local PNG
// textures, versioned local mesh files. NO built-in copyrighted character art.
// This is a STATIC reference character used to prove actual Ship rendering;
// controls, ROM-accurate skeleton and animation follow in separate milestones.
#include "OriginalReferenceAtlas.hpp"

#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <fstream>
#include <optional>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

#include <stb_image.h>
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

#define CVAR_GOEMON_REFERENCE_RENDER CVAR_SETTING("Goemon.RenderReferenceCharacter")
#define CVAR_GOEMON_REFERENCE_SLOT CVAR_SETTING("Goemon.ReferenceCharacterSlot")

namespace {
namespace fs = std::filesystem;
constexpr int kSlots = 4;
constexpr std::size_t kTextureTileBytes = 32 * 32 * 2;
constexpr float kReferencePi = 3.14159265358979323846f;
const std::array<const char*, kSlots> kNames{
    "Goemon", "Ebisumaru", "Sasuke", "Yae"
};

struct ReferenceDrawBatch {
    std::uint32_t textureTile = 0;
    std::vector<Vtx> vertices;
};

struct ReferenceCharacter {
    bool attempted = false;
    bool valid = false;
    std::vector<ReferenceDrawBatch> batches;
    // Per-material, per-32px-tile big-endian RGBA5551 source bytes.
    std::vector<std::array<std::uint8_t, kTextureTileBytes>> textures;
    std::string failure;
};

std::array<ReferenceCharacter, kSlots> sCharacters{};
int sActorId = -1;
Actor* sCharacterActor = nullptr;
int sScene = -1;

[[nodiscard]] fs::path ModelRoot() {
    if (const char* env = std::getenv("GOEMON_CHARACTER_MODELS")) {
        if (*env != '\0') return fs::path(env);
    }
    const fs::path besideExe = fs::path("character-models");
    if (fs::exists(besideExe)) return besideExe;
#ifdef _WIN32
    return fs::path(R"(C:\actions-runner-goemon\character-models)");
#else
    return fs::path("character-models");
#endif
}

[[nodiscard]] std::vector<std::uint8_t> ReadLocalMesh(const fs::path& fileName) {
    std::ifstream file(fileName, std::ios::binary | std::ios::ate);
    if (!file) throw std::runtime_error("GOMESH01 file not found: " + fileName.string());
    const auto length = file.tellg();
    if (length <= 0 || length > 24 * 1024 * 1024)
        throw std::runtime_error("GOMESH01 local file length outside limits");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(length));
    file.seekg(0, std::ios::beg);
    if (!file.read(reinterpret_cast<char*>(bytes.data()),
                   static_cast<std::streamsize>(bytes.size())))
        throw std::runtime_error("GOMESH01 local file read failed");
    return bytes;
}

void DecodeAtlasMaterial(const fs::path& fileName,
                         ReferenceCharacter& character) {
    int width = 0;
    int height = 0;
    int components = 0;
    const std::string ascii = fileName.string();
    stbi_uc* rgba = stbi_load(ascii.c_str(), &width, &height, &components, 4);
    if (rgba == nullptr)
        throw std::runtime_error("N64 character PNG decode failed: " + ascii);
    try {
        if (width != 128 || height != 128)
            throw std::runtime_error("N64 reference atlas must be exactly 128x128");

        for (int ty = 0; ty < 4; ++ty) {
            for (int tx = 0; tx < 4; ++tx) {
                std::array<std::uint8_t, kTextureTileBytes> tile{};
                for (int y = 0; y < 32; ++y) {
                    for (int x = 0; x < 32; ++x) {
                        const std::size_t source = static_cast<std::size_t>(
                            ((ty * 32 + y) * 128 + tx * 32 + x) * 4
                        );
                        const auto r = static_cast<std::uint16_t>(rgba[source + 0] >> 3);
                        const auto g = static_cast<std::uint16_t>(rgba[source + 1] >> 3);
                        const auto b = static_cast<std::uint16_t>(rgba[source + 2] >> 3);
                        const auto a = static_cast<std::uint16_t>(rgba[source + 3] >= 128);
                        const std::uint16_t pixel = static_cast<std::uint16_t>(
                            (r << 11) | (g << 6) | (b << 1) | a);
                        const std::size_t offset = static_cast<std::size_t>((y * 32 + x) * 2);
                        tile[offset + 0] = static_cast<std::uint8_t>(pixel >> 8);
                        tile[offset + 1] = static_cast<std::uint8_t>(pixel);
                    }
                }
                character.textures.push_back(std::move(tile));
            }
        }
    } catch (...) {
        stbi_image_free(rgba);
        throw;
    }
    stbi_image_free(rgba);
}

void LoadCharacter(int slot) {
    auto& character = sCharacters.at(static_cast<std::size_t>(slot));
    if (character.attempted) return;
    character.attempted = true;
    try {
        const fs::path directory = ModelRoot() / kNames[slot];
        const auto bytes = ReadLocalMesh(directory / "model.gomesh");
        const auto model = Goemon::Original::ParseOriginalReferenceMesh(
            std::span<const std::uint8_t>(bytes.data(), bytes.size()));
        const auto atlas = Goemon::Original::PrepareReferenceAtlas(model);
        for (std::uint32_t material = 0; material < model.materialCount; ++material) {
            char filename[32];
            std::snprintf(filename, sizeof(filename),
                          "texture_%03u.png", material);
            DecodeAtlasMaterial(directory / filename, character);
        }
        if (character.textures.size() != model.materialCount * 16)
            throw std::runtime_error("original reference model texture tile count mismatch");

        for (const auto& group : atlas.batches) {
            if (group.material >= character.textures.size() ||
                group.vertices.size() > 30 || group.vertices.size() % 3 != 0)
                throw std::runtime_error("invalid prepared N64 reference geometry");
            ReferenceDrawBatch batch{};
            batch.textureTile = group.material;
            for (const auto& v : group.vertices) {
                Vtx native{};
                native.n.ob[0] = v.x;
                native.n.ob[1] = v.y;
                native.n.ob[2] = v.z;
                native.n.flag = 0;
                native.n.tc[0] = v.texS;
                native.n.tc[1] = v.texT;
                native.n.cn[0] = v.rgba[0];
                native.n.cn[1] = v.rgba[1];
                native.n.cn[2] = v.rgba[2];
                native.n.cn[3] = v.rgba[3];
                batch.vertices.push_back(native);
            }
            character.batches.push_back(std::move(batch));
        }
        if (character.batches.empty())
            throw std::runtime_error("original N64 static character has no drawable faces");
        character.valid = true;
    } catch (const std::exception& error) {
        character.failure = error.what();
        character.valid = false;
        std::ofstream log("goemon_character_renderer_error.txt",
                          std::ios::out | std::ios::trunc);
        if (log) log << kNames[slot] << ": " << character.failure << '\n';
    }
}

void DrawReferenceCharacter(Actor* actor, PlayState* play) {
    if (!CVarGetInteger(CVAR_GOEMON_REFERENCE_RENDER, 0) ||
        play == nullptr || actor != sCharacterActor) return;
    const int slot = CVarGetInteger(CVAR_GOEMON_REFERENCE_SLOT, 0);
    if (slot < 0 || slot >= kSlots) return;
    LoadCharacter(slot);
    const auto& character = sCharacters[slot];
    if (!character.valid) return;

    OPEN_DISPS(play->state.gfxCtx);
    Gfx_SetupDL_25Opa(play->state.gfxCtx);
    gDPPipeSync(POLY_OPA_DISP++);
    gSPClearGeometryMode(
        POLY_OPA_DISP++,
        G_CULL_BOTH | G_LIGHTING | G_TEXTURE_GEN | G_TEXTURE_GEN_LINEAR);
    gSPSetGeometryMode(POLY_OPA_DISP++,
                       G_ZBUFFER | G_SHADE | G_SHADING_SMOOTH);
    gDPSetCycleType(POLY_OPA_DISP++, G_CYC_1CYCLE);
    gDPSetTextureFilter(POLY_OPA_DISP++, G_TF_POINT);
    gDPSetTextureLUT(POLY_OPA_DISP++, G_TT_NONE);
    gDPSetCombineMode(POLY_OPA_DISP++,
                      G_CC_MODULATEIDECALA, G_CC_MODULATEIDECALA);
    gDPSetRenderMode(POLY_OPA_DISP++,
                     G_RM_AA_ZB_OPA_SURF, G_RM_AA_ZB_OPA_SURF2);
    gSPTexture(POLY_OPA_DISP++,
               0xFFFF, 0xFFFF, 0, G_TX_RENDERTILE, G_ON);

    Matrix_Push();
    Matrix_Translate(actor->world.pos.x, actor->world.pos.y,
                     actor->world.pos.z, MTXMODE_NEW);
    Matrix_RotateY(actor->shape.rot.y * (kReferencePi / 32768.0f),
                   MTXMODE_APPLY);
    gSPMatrix(POLY_OPA_DISP++, MATRIX_NEWMTX(play->state.gfxCtx),
              G_MTX_MODELVIEW | G_MTX_LOAD);

    for (const auto& batch : character.batches) {
        const auto& tile = character.textures[batch.textureTile];
        gDPLoadTextureBlock(
            POLY_OPA_DISP++, tile.data(), G_IM_FMT_RGBA, G_IM_SIZ_16b,
            32, 32, 0,
            G_TX_NOMIRROR | G_TX_CLAMP, G_TX_NOMIRROR | G_TX_CLAMP,
            5, 5, G_TX_NOLOD, G_TX_NOLOD);
        gSPVertex(POLY_OPA_DISP++,
                  reinterpret_cast<uintptr_t>(batch.vertices.data()),
                  static_cast<int>(batch.vertices.size()), 0);
        for (int i = 0; i < static_cast<int>(batch.vertices.size()); i += 3) {
            gSP1Triangle(POLY_OPA_DISP++, i, i + 1, i + 2, 0);
        }
    }
    Matrix_Pop();
    CLOSE_DISPS(play->state.gfxCtx);
}

void InitReferenceActor(Actor* actor, PlayState* play) {
    sCharacterActor = actor;
    sScene = play->sceneNum;
    actor->room = -1;
    Actor_SetScale(actor, 1.0f);
}

void DestroyReferenceActor(Actor* actor, PlayState*) {
    if (actor == sCharacterActor) {
        sCharacterActor = nullptr;
        sScene = -1;
    }
}

void UpdateReferenceActor(Actor* actor, PlayState* play) {
    if (actor != sCharacterActor || sScene != play->sceneNum ||
        !CVarGetInteger(CVAR_GOEMON_REFERENCE_RENDER, 0)) {
        Actor_Kill(actor);
        return;
    }
    const Player* link = GET_PLAYER(play);
    if (link == nullptr) return;
    // For initial visible model inspection, an independent source-model
    // Actor stands approximately 55 world units ahead of Link. It neither
    // replaces Link nor uses the old gold-ball feasibility prototype.
    const float yaw = link->actor.shape.rot.y * (kReferencePi / 32768.0f);
    const float x = link->actor.world.pos.x + std::sin(yaw) * 55.0f;
    const float z = link->actor.world.pos.z + std::cos(yaw) * 55.0f;
    actor->prevPos = actor->world.pos;
    actor->world.pos = {x, link->actor.world.pos.y, z};
    actor->shape.rot.y = link->actor.shape.rot.y;
    actor->world.rot.y = actor->shape.rot.y;
    Actor_SetFocus(actor, 35.0f);
}

void SpawnReferenceActor() {
    if (gPlayState == nullptr || sActorId < 0) return;
    if (!CVarGetInteger(CVAR_GOEMON_REFERENCE_RENDER, 0)) {
        if (sCharacterActor != nullptr && sCharacterActor->update != nullptr)
            Actor_Kill(sCharacterActor);
        return;
    }
    if (sCharacterActor != nullptr && sCharacterActor->update != nullptr)
        return;
    const Player* link = GET_PLAYER(gPlayState);
    if (link == nullptr || gPlayState->csCtx.state != CS_STATE_IDLE ||
        !(link->actor.bgCheckFlags & BGCHECKFLAG_GROUND))
        return;
    const Vec3f& p = link->actor.world.pos;
    Actor* spawned = Actor_Spawn(
        &gPlayState->actorCtx, gPlayState, static_cast<s16>(sActorId),
        p.x, p.y, p.z, 0, link->actor.shape.rot.y, 0, 0
    );
    if (spawned) sCharacterActor = spawned;
}

void RegisterOriginalReferenceActor() {
    ActorDBInit init{};
    init.name = "GoemonOriginalReferenceCharacter";
    init.desc = "Real N64 static character mesh, local assets, no gameplay yet";
    init.category = ACTORCAT_PROP;
    init.objectId = OBJECT_GAMEPLAY_KEEP;
    init.instanceSize = sizeof(Actor);
    init.init = InitReferenceActor;
    init.destroy = DestroyReferenceActor;
    init.update = UpdateReferenceActor;
    init.draw = DrawReferenceCharacter;
    sActorId = ActorDB::Instance->AddEntry(init).entry.id;
    COND_HOOK(OnPlayerUpdate, true, SpawnReferenceActor);
    COND_HOOK(OnPlayDestroy, true, []() {
        sCharacterActor = nullptr;
        sScene = -1;
    });
}
} // namespace

static RegisterShipInitFunc registerOriginalReferenceActor(
    RegisterOriginalReferenceActor);
