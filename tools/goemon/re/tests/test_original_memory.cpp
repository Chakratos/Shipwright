// Native C++20 test for byte-exact original N64 player-state decoding.
// Build directly: c++ -std=c++20 -Wall -Wextra -Werror test_original_memory.cpp -o test
#include "soh/soh/Enhancements/Goemon/OriginalMemory.hpp"
#include <array>
#include <cassert>
#include <bit>
#include <cstdint>
#include <stdexcept>

using namespace Goemon::Original;

template <std::size_t N> void PutU32(std::array<std::uint8_t, N>& b, std::size_t o, std::uint32_t v) {
    b.at(o) = static_cast<std::uint8_t>(v >> 24);
    b.at(o + 1) = static_cast<std::uint8_t>(v >> 16);
    b.at(o + 2) = static_cast<std::uint8_t>(v >> 8);
    b.at(o + 3) = static_cast<std::uint8_t>(v);
}

int main() {
    std::array<std::uint8_t, PlayerTaskView::kSize> task{};
    PutU32(task, 0x5C, 0x80123456);
    PutU32(task, 0x64, 0x80234567);
    PutU32(task, 0x68, std::bit_cast<std::uint32_t>(-2.8f));
    PutU32(task, 0x6C, std::bit_cast<std::uint32_t>(6.0f));
    PutU32(task, 0x70, std::bit_cast<std::uint32_t>(0.0f));
    PutU32(task, 0xA4, std::bit_cast<std::uint32_t>(5.333333f));
    task[0x60] = 3;
    task[0xCC] = 17;
    const PlayerTaskView view(task);
    assert(view.PlayerAddress() == 0x80123456);
    assert(view.CameraTaskAddress() == 0x80234567);
    assert(view.CharacterId() == 3);
    assert(view.ActionId() == 17);
    assert(view.MovementStep().x == -2.8f);
    assert(view.MovementStep().y == 6.0f);
    assert(view.MovementStep().z == 0.0f);
    assert(view.NextVerticalStep() == 5.333333f);

    std::array<std::uint8_t, ObjectView::kSize> bytes{};
    PutU32(bytes, 0x08, std::bit_cast<std::uint32_t>(-3.5f));
    PutU32(bytes, 0x0C, std::bit_cast<std::uint32_t>(27.25f));
    PutU32(bytes, 0x10, std::bit_cast<std::uint32_t>(1.0f));
    bytes[0x16] = 0xFF; bytes[0x17] = 0xFE;
    PutU32(bytes, 0x28, std::bit_cast<std::uint32_t>(0.75f));
    PutU32(bytes, 0x2C, 0x68000300);
    const ObjectView object(bytes);
    assert(object.Position().x == -3.5f);
    assert(object.Position().y == 27.25f);
    assert(object.Position().z == 1.0f);
    assert(object.RotationY() == -2);
    assert(object.AnimationProgress() == 0.75f);
    assert(object.GraphicsPointer() == 0x68000300);

    bool threw = false;
    try { [[maybe_unused]] PlayerTaskView incomplete(std::span{task}.first(32)); }
    catch (const std::invalid_argument&) { threw = true; }
    assert(threw);
    threw = false;
    try { [[maybe_unused]] auto value = view.U32(task.size() - 3); }
    catch (const std::out_of_range&) { threw = true; }
    assert(threw);

    std::array<std::uint8_t, PlayerView::kSize> opaque{};
    const PlayerView originalPlayer(opaque);
    assert(originalPlayer.Size() == 0x1C0);
}
