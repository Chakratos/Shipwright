// Standalone native tests for original Goemon player initialization writes.
// These records contain no copyrighted assets or original game code.
#include "soh/soh/Enhancements/Goemon/OriginalCharacterInit.hpp"
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <span>
#include <stdexcept>

using namespace Goemon::Original;

int main() {
    std::array<std::uint8_t, 0xF0> task{};
    std::array<std::uint8_t, 0x1C0> player{};
    task.fill(0xFF);
    player.fill(0xFF);

    auto a = ApplyCharacterInit(task, player, 2, CharacterInitVariant::A);
    assert(a.selectedCharacterId == 2 && a.originalUpdateCallback == 0x801E0944);
    assert(a.actionId == 0xBA && task[0xCC] == 0xBA && task[0x60] == 2);
    assert(player[0] == 0 && player[1] == 1 && player[0x69] == 1);
    assert(task[0x68] == 0 && task[0x6F] == 0 && task[0x70] == 0 && task[0x73] == 0);
    assert(task[0xE8] == 0 && task[0xEB] == 0 && task[0x80] == 0 && task[0x81] == 0);
    assert(task[0x30] == 0xFE && task[0x48] == 0 && task[0x4B] == 0 && task[0xDB] == 1);
    assert(player[0x86] == 0 && player[0x87] == 0);
    assert(player[0x30] == 0 && player[0x31] == 0);

    task.fill(0xFF);
    player.fill(0xFF);
    auto b = ApplyCharacterInit(task, player, 3, CharacterInitVariant::B);
    assert(b.selectedCharacterId == 3 && b.originalUpdateCallback == 0x801E0BF8);
    assert(b.actionId == 0xBB && task[0xCC] == 0xBB);
    assert(player[0x86] == 0xFF && player[0x87] == 0xFF);
    assert(task[0x48] == 0xFF && task[0x4B] == 0xFF && task[0xDB] == 0xFF);
    assert(player[0] == 0 && player[1] == 1 && task[0x30] == 0xFE);

    bool threw = false;
    try {
        (void)ApplyCharacterInit(std::span(task).first(4), player, 2, CharacterInitVariant::A);
    } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);

    std::puts("OriginalCharacterInit: PASS");
}
