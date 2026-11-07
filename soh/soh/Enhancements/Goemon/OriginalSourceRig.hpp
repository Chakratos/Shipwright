#pragma once
// GOSKEL01: a user-local authentic source-ROM original Goemon rig.
//
// The file contains ORIGINAL N64 F3DEX vertices (big-endian Vtx) for each
// Skeleton-owned Gfx root and original 24-byte *encoded limb channel selector words*, exported
// without recording or running the original game.
// The raw values MUST NOT be used as literal physical Euler/scale values
// until original MIPS func_800192D0 is ported and validated.
// No bundled copyrighted assets. This loader does not invent action IDs,
// interpolation, animation speed, texture colors, or missing mesh segments.
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>
#include <utility>

namespace Goemon::Original {

struct SourceRigVertex {
    std::int16_t x = 0, y = 0, z = 0;
    std::uint16_t flags = 0;
    std::int16_t s = 0, t = 0;
    std::array<std::uint8_t, 4> originalRGBA{};
};

struct SourceRigLimbMesh {
    std::uint32_t sourceGfxPointer = 0;
    std::vector<SourceRigVertex> vertices;
};

[[nodiscard]] inline bool IsOriginalSourceRawGfxWord(std::uint32_t ptr) {
    return ptr==0 || (ptr>>24)==0x09 ||
           (ptr>>24)==0x29 || (ptr>>24)==0x0F;
}

[[nodiscard]] inline std::uint32_t OriginalSourceNormalizedGfxWord(
    std::uint32_t ptr
) {
    // Original player renderer uses (display_list_vram_addr & 0x8FFFFFFF).
    // 0x0F remains unresolved rather than being forced into source 0x09.
    return ptr & 0x8FFFFFFF;
}

struct SourceRigBonePose {
    std::uint32_t sourceGfxPointer = 0;
    std::int16_t parent = -1;
    // Original raw scale, rotation, translation in Nintendo 64 source units.
    std::array<std::int16_t, 9> sourceTransforms{};
};

struct SourceRigPose {
    std::uint32_t originalHeader = 0;
    std::uint32_t originalFlags = 0;
    std::vector<SourceRigBonePose> bones;
};

struct SourceRig {
    std::uint32_t character = 0;
    std::vector<SourceRigLimbMesh> meshes;
    std::vector<SourceRigPose> authoredPoses;
};

struct SourceRigLayoutGroup {
    // Original Skeleton descriptor indices, never chronological frames.
    std::vector<std::size_t> descriptorIndices;
};

class SourceRigReader {
  public:
    explicit SourceRigReader(std::span<const std::uint8_t> bytes)
        : bytes_(bytes) {}

    [[nodiscard]] SourceRig Parse() {
        if (bytes_.size() > 24 * 1024 * 1024 || bytes_.size() < 20)
            throw std::invalid_argument("original N64 rig package outside size limits");
        constexpr std::array<std::uint8_t,8> magic{
            'G','O','S','K','E','L','0','1'};
        for (auto byte : magic) {
            if (ReadU8() != byte)
                throw std::invalid_argument("invalid source rig magic");
        }
        SourceRig rig{};
        rig.character = ReadU32LE();
        const auto meshCount = ReadU32LE();
        const auto poseCount = ReadU32LE();
        if (rig.character > 3 || !meshCount || meshCount > 2048 ||
            !poseCount || poseCount > 1024)
            throw std::invalid_argument("source ROM character/rig count invalid");
        rig.meshes.reserve(meshCount);
        for (std::uint32_t i=0; i<meshCount; ++i) {
            SourceRigLimbMesh mesh{};
            mesh.sourceGfxPointer = ReadU32LE();
            const auto triCount = ReadU32LE();
            if (mesh.sourceGfxPointer >> 24 != 9 || !triCount ||
                triCount > 30000)
                throw std::invalid_argument("invalid original source limb graphics header");
            for (const auto& prior : rig.meshes) {
                if (prior.sourceGfxPointer == mesh.sourceGfxPointer)
                    throw std::invalid_argument("duplicate original limb gfx pointer");
            }
            const std::size_t vertices = static_cast<std::size_t>(triCount) * 3;
            if (vertices > (bytes_.size() - pos_)/16)
                throw std::invalid_argument("truncated source N64 Vtx records");
            mesh.vertices.reserve(vertices);
            for (std::size_t j=0; j<vertices; ++j) {
                SourceRigVertex v{};
                v.x = static_cast<std::int16_t>(ReadU16BE());
                v.y = static_cast<std::int16_t>(ReadU16BE());
                v.z = static_cast<std::int16_t>(ReadU16BE());
                v.flags = ReadU16BE();
                v.s = static_cast<std::int16_t>(ReadU16BE());
                v.t = static_cast<std::int16_t>(ReadU16BE());
                for (auto& value : v.originalRGBA) value = ReadU8();
                mesh.vertices.push_back(v);
            }
            rig.meshes.push_back(std::move(mesh));
        }
        rig.authoredPoses.reserve(poseCount);
        for (std::uint32_t i=0; i<poseCount; ++i) {
            SourceRigPose pose{};
            pose.originalHeader = ReadU32LE();
            pose.originalFlags = ReadU32LE();
            const auto limbCount = ReadU32LE();
            if ((pose.originalHeader>>24)!=7 ||
                !limbCount || limbCount > 128)
                throw std::invalid_argument("invalid original ROM skeleton pose header");
            pose.bones.reserve(limbCount);
            for (std::uint32_t j=0; j<limbCount; ++j) {
                SourceRigBonePose bone{};
                bone.sourceGfxPointer = ReadU32LE();
                bone.parent = static_cast<std::int16_t>(ReadU16LE());
                for (auto& value : bone.sourceTransforms)
                    value = static_cast<std::int16_t>(ReadU16LE());
                if (bone.parent < -1 || bone.parent >= static_cast<std::int16_t>(j) ||
                    !IsOriginalSourceRawGfxWord(bone.sourceGfxPointer))
                    throw std::invalid_argument("invalid original source Skeleton linkage");
                pose.bones.push_back(bone);
            }
            rig.authoredPoses.push_back(std::move(pose));
        }
        if (pos_ != bytes_.size())
            throw std::invalid_argument("trailing bytes after original N64 Skeleton pose");
        return rig;
    }

  private:
    std::span<const std::uint8_t> bytes_;
    std::size_t pos_ = 0;
    [[nodiscard]] std::uint8_t ReadU8() {
        if (pos_ >= bytes_.size())
            throw std::invalid_argument("truncated original source ROM rig");
        return bytes_[pos_++];
    }
    [[nodiscard]] std::uint16_t ReadU16LE() {
        const auto a = ReadU8();
        const auto b = ReadU8();
        return static_cast<std::uint16_t>(
            static_cast<unsigned>(a) | (static_cast<unsigned>(b)<<8));
    }
    [[nodiscard]] std::uint16_t ReadU16BE() {
        const auto a = ReadU8();
        const auto b = ReadU8();
        return static_cast<std::uint16_t>(
            (static_cast<unsigned>(a)<<8) | static_cast<unsigned>(b));
    }
    [[nodiscard]] std::uint32_t ReadU32LE() {
        const auto a = ReadU16LE();
        const auto b = ReadU16LE();
        return static_cast<std::uint32_t>(a) |
               (static_cast<std::uint32_t>(b)<<16);
    }
};

// Layout grouping is evidence of identical source Skeleton structure,
// NOT evidence of animation sequence, action, frame order or frame rate.
[[nodiscard]] inline bool HaveMatchingSourceRigLayout(
    const SourceRigPose& a, const SourceRigPose& b
) {
    if (a.bones.size()!=b.bones.size()) return false;
    for (std::size_t i=0;i<a.bones.size();++i) {
        if (a.bones[i].parent!=b.bones[i].parent ||
            a.bones[i].sourceGfxPointer!=b.bones[i].sourceGfxPointer)
            return false;
    }
    return true;
}

[[nodiscard]] inline std::vector<SourceRigLayoutGroup> GroupOriginalSourceRigLayouts(
    const SourceRig& rig
) {
    std::vector<SourceRigLayoutGroup> groups;
    for (std::size_t i=0; i<rig.authoredPoses.size(); ++i) {
        bool grouped=false;
        for (auto& group : groups) {
            if (HaveMatchingSourceRigLayout(
                    rig.authoredPoses[group.descriptorIndices.front()],
                    rig.authoredPoses[i])) {
                group.descriptorIndices.push_back(i);
                grouped=true;
                break;
            }
        }
        if (!grouped) groups.push_back({{i}});
    }
    return groups;
}

[[nodiscard]] inline const SourceRigPose* FindExactOriginalSourceDescriptor(
    const SourceRig& rig, std::uint32_t originalSegmentedHeader
) {
    const SourceRigPose* found=nullptr;
    for (const auto& record : rig.authoredPoses) {
        if (record.originalHeader!=originalSegmentedHeader)
            continue;
        if (found!=nullptr)
            throw std::invalid_argument("ambiguous source Skeleton header");
        found=&record;
    }
    return found;
}

// There is deliberately no SourceRig "pose playback" API. Its encoded
// channel words cannot be turned into physical matrices by assigning an
// arbitrary tick rate. Actual animation must come from the original MIPS
// evaluator after source-action ownership and channel decoding are proven.

} // namespace Goemon::Original
