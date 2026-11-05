#pragma once
// Confirmed write-side effects of two original NG5E player initializers:
// func_801DD5C0_5994D0 and func_801DD654_599564, from original ROM.
// Does not reproduce original call to 0x8003522C or controller logic.
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace Goemon::Original {

enum class CharacterInitVariant : std::uint8_t { A, B };

struct CharacterInitResult {
    std::uint32_t selectedCharacterId;
    std::uint32_t originalUpdateCallback;
    std::uint8_t actionId;
};

inline CharacterInitResult ApplyCharacterInit(
    std::span<std::uint8_t> task, std::span<std::uint8_t> player,
    std::uint8_t characterId, CharacterInitVariant variant) {
    if (task.size() < 0xF0 || player.size() < 0x1C0)
        throw std::invalid_argument("truncated original PlayerTask/Player record");
    const bool a = variant == CharacterInitVariant::A;
    if (!a && variant != CharacterInitVariant::B)
        throw std::invalid_argument("invalid original initializer variant");
    auto clear = [](std::span<std::uint8_t> bytes, std::size_t offset, std::size_t n) {
        for (std::size_t i = 0; i < n; ++i) bytes[offset+i] = 0;
    };
    // The original routines take (PlayerTask* a0, characterId a1).
    task[0x60] = characterId;
    player[0x69] = 1;
    clear(task, 0x80, 2);
    clear(player, 0x30, 2);
    clear(task, 0xE8, 4);
    clear(task, 0x68, 12);
    clear(player, 0x00, 2);
    player[0x01] = 1; // N64 big-endian halfword 0x0001
    task[0x30] = static_cast<std::uint8_t>(task[0x30] & 0xFE);
    if (a) {
        clear(player, 0x86, 2);
        clear(task, 0x48, 4);
        task[0xDB] = 1;
    }
    task[0xCC] = a ? 0xBA : 0xBB;
    // Original JAL 0x8003522C receives one of these a1 callbacks.
    return {characterId, a ? 0x801E0944u : 0x801E0BF8u, task[0xCC]};
}

} // namespace Goemon::Original
