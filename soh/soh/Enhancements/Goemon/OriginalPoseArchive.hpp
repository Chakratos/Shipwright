#pragma once
// Decoder for GOPA0001 snapshots captured by Goemon64Recomp's ORIGINAL
// skeletal traversal/animation-matrix routines. No synthetic animation
// or heuristic pose retargeting is performed here.
//
// This loader is independent of the Ship engine and can be tested natively.
// Play-ready skeleton-bone coordinate spaces and texture binding still
// require verification against actual GOEMON_ANIM_MATRIX capture samples.
#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <stdexcept>
#include <utility>
#include <vector>

namespace Goemon::Original {

struct OriginalCapturedBone {
    std::uint32_t originalPointer = 0;
    std::uint32_t sourceGfxPointer = 0;
    std::int8_t childOffset = 0;
    std::int8_t siblingOffset = 0;
    std::array<std::int16_t, 9> rawTransform{};
    std::array<float, 16> engineMatrix{};
};

struct OriginalCapturedPose {
    std::uint32_t sourceGameFrame = 0;
    std::uint8_t characterId = 0;
    std::uint8_t actionId = 0;
    std::vector<OriginalCapturedBone> bones;
};

struct OriginalCapturedAnimation {
    std::vector<OriginalCapturedPose> frames;
    std::uint32_t totalBoneMatrices = 0;
};

class OriginalAnimationArchiveReader {
  public:
    explicit OriginalAnimationArchiveReader(std::span<const std::uint8_t> data)
        : data_(data) {}

    [[nodiscard]] OriginalCapturedAnimation Parse() {
        if (data_.size() < 16)
            throw std::invalid_argument("truncated original Goemon animation archive");
        constexpr std::array<std::uint8_t, 8> magic{
            'G','O','P','A','0','0','0','1'
        };
        for (auto letter : magic) {
            if (ReadU8() != letter)
                throw std::invalid_argument("unknown original animation archive magic");
        }
        const std::uint32_t frameCount = ReadU32();
        const std::uint32_t boneCount = ReadU32();
        if (frameCount < 1 || frameCount > 7200 ||
            boneCount < 1 || boneCount > 300000)
            throw std::invalid_argument("original animation archive exceeds limits");

        OriginalCapturedAnimation archive;
        archive.frames.reserve(frameCount);
        std::uint32_t lastFrame = 0;
        std::uint64_t total = 0;
        for (std::uint32_t index = 0; index < frameCount; ++index) {
            OriginalCapturedPose frame{};
            frame.sourceGameFrame = ReadU32();
            frame.characterId = ReadU8();
            frame.actionId = ReadU8();
            const auto limbCount = ReadU16();
            if (frame.characterId > 3 || limbCount < 1 || limbCount > 96 ||
                (index != 0 && frame.sourceGameFrame < lastFrame))
                throw std::invalid_argument("invalid original game animation frame");
            lastFrame = frame.sourceGameFrame;
            frame.bones.reserve(limbCount);
            for (unsigned i = 0; i < limbCount; ++i) {
                OriginalCapturedBone bone{};
                bone.originalPointer = ReadU32();
                bone.sourceGfxPointer = ReadU32();
                bone.childOffset = static_cast<std::int8_t>(ReadU8());
                bone.siblingOffset = static_cast<std::int8_t>(ReadU8());
                if (!bone.originalPointer)
                    throw std::invalid_argument("null source skeleton pointer");
                for (auto& value : bone.rawTransform)
                    value = static_cast<std::int16_t>(ReadU16());
                for (auto& value : bone.engineMatrix) {
                    const std::uint32_t bits = ReadU32();
                    value = std::bit_cast<float>(bits);
                    if (!std::isfinite(value) || std::fabs(value) > 1e8f)
                        throw std::invalid_argument("invalid source animation matrix");
                }
                for (const auto& previous : frame.bones) {
                    if (previous.originalPointer == bone.originalPointer)
                        throw std::invalid_argument(
                            "source limb repeated within same original game frame");
                }
                frame.bones.push_back(bone);
                ++total;
                if (total > boneCount)
                    throw std::invalid_argument("too many bone records");
            }
            archive.frames.push_back(std::move(frame));
        }
        if (offset_ != data_.size() || total != boneCount)
            throw std::invalid_argument("original animation archive length/count mismatch");
        archive.totalBoneMatrices = boneCount;
        return archive;
    }

  private:
    std::span<const std::uint8_t> data_;
    std::size_t offset_ = 0;

    [[nodiscard]] std::uint8_t ReadU8() {
        if (offset_ >= data_.size())
            throw std::invalid_argument("truncated source animation field");
        return data_[offset_++];
    }
    [[nodiscard]] std::uint16_t ReadU16() {
        const auto a = ReadU8();
        const auto b = ReadU8();
        return static_cast<std::uint16_t>(a | (static_cast<unsigned>(b) << 8));
    }
    [[nodiscard]] std::uint32_t ReadU32() {
        const std::uint32_t a = ReadU16();
        const std::uint32_t b = ReadU16();
        return a | (b << 16);
    }
};

// Exact original game tick, character and action only. A player action
// change or missing source frame never silently borrows a different
// animation or manufactures a keyframe.
[[nodiscard]] inline const OriginalCapturedPose* FindExactOriginalPose(
    const OriginalCapturedAnimation& source, std::uint8_t character,
    std::uint8_t action, std::uint32_t originalGameTick
) {
    for (const auto& pose : source.frames) {
        if (pose.sourceGameFrame == originalGameTick &&
            pose.characterId == character && pose.actionId == action)
            return &pose;
    }
    return nullptr;
}

} // namespace Goemon::Original
