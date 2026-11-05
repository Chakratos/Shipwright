#pragma once
// Byte-exact views of known original Mystical Ninja Starring Goemon structures.
// No player movement approximation, host pointer casts, or implicit byte swapping.
// Offsets derive from Goemon64Recomp patches/types.h (N64, 32-bit big endian).
#include <bit>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace Goemon::Original {

struct Vec3f {
    float x, y, z;
};

// A view into captured, BIG ENDIAN N64 memory. It never owns or mutates data.
class MemoryView {
  public:
    explicit MemoryView(std::span<const std::uint8_t> bytes) : bytes_(bytes) {}
    [[nodiscard]] std::uint8_t U8(std::size_t offset) const {
        Require(offset, 1);
        return bytes_[offset];
    }
    [[nodiscard]] std::uint16_t U16(std::size_t offset) const {
        Require(offset, 2);
        return (static_cast<std::uint16_t>(bytes_[offset]) << 8) |
               static_cast<std::uint16_t>(bytes_[offset + 1]);
    }
    [[nodiscard]] std::int16_t S16(std::size_t offset) const {
        return std::bit_cast<std::int16_t>(U16(offset));
    }
    [[nodiscard]] std::uint32_t U32(std::size_t offset) const {
        Require(offset, 4);
        return (static_cast<std::uint32_t>(bytes_[offset]) << 24) |
               (static_cast<std::uint32_t>(bytes_[offset + 1]) << 16) |
               (static_cast<std::uint32_t>(bytes_[offset + 2]) << 8) |
               static_cast<std::uint32_t>(bytes_[offset + 3]);
    }
    [[nodiscard]] float F32(std::size_t offset) const {
        static_assert(sizeof(float) == sizeof(std::uint32_t));
        return std::bit_cast<float>(U32(offset));
    }
    [[nodiscard]] Vec3f Vec3(std::size_t offset) const {
        return {F32(offset), F32(offset + 4), F32(offset + 8)};
    }
    [[nodiscard]] std::size_t Size() const { return bytes_.size(); }

  private:
    void Require(std::size_t offset, std::size_t length) const {
        if (offset > bytes_.size() || length > bytes_.size() - offset) {
            throw std::out_of_range("original N64 memory read outside captured buffer");
        }
    }
    std::span<const std::uint8_t> bytes_;
};

class PlayerTaskView final : public MemoryView {
  public:
    static constexpr std::size_t kSize = 0xF0;
    explicit PlayerTaskView(std::span<const std::uint8_t> bytes) : MemoryView(bytes) {
        if (bytes.size() < kSize) throw std::invalid_argument("truncated original PlayerTask");
    }
    [[nodiscard]] std::uint32_t PlayerAddress() const { return U32(0x5C); }
    [[nodiscard]] std::uint8_t CharacterId() const { return U8(0x60); }
    [[nodiscard]] std::uint8_t ActionId() const { return U8(0xCC); }
    [[nodiscard]] std::uint32_t CameraTaskAddress() const { return U32(0x64); }
    // Do not name unknown movement-state bytes until the original is reversed.
};

class PlayerView final : public MemoryView {
  public:
    static constexpr std::size_t kSize = 0x1C0;
    explicit PlayerView(std::span<const std::uint8_t> bytes) : MemoryView(bytes) {
        if (bytes.size() < kSize) throw std::invalid_argument("truncated opaque original Player");
    }
};

class ObjectView final : public MemoryView {
  public:
    static constexpr std::size_t kSize = 0x90;
    explicit ObjectView(std::span<const std::uint8_t> bytes) : MemoryView(bytes) {
        if (bytes.size() < kSize) throw std::invalid_argument("truncated original Object");
    }
    [[nodiscard]] Vec3f Position() const { return Vec3(0x08); }
    [[nodiscard]] std::int16_t RotationX() const { return S16(0x14); }
    [[nodiscard]] std::int16_t RotationY() const { return S16(0x16); }
    [[nodiscard]] std::int16_t RotationZ() const { return S16(0x18); }
    [[nodiscard]] float AnimationProgress() const { return F32(0x28); }
    [[nodiscard]] std::uint32_t GraphicsPointer() const { return U32(0x2C); }
};

} // namespace Goemon::Original
