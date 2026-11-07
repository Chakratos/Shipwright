#pragma once
// Articulated rendering bridge for *decoded, frame-exact* original Goemon poses.
//
// SourceRig contains original ROM limb geometry; OriginalCapturedAnimation
// contains ORIGINAL matrix values, indexed by actual game tick/action.
// This adapter never treats 0xB000/0xB100 channel words as rotations,
// never chooses an animation by heuristics, and never invents frames.
// Matrix convention is explicitly selected by the caller; it is NOT
// established by the source ROM and must be confirmed against original
// renderer outputs before enabling the in-game preview.
#include "OriginalSourceRig.hpp"
#include "OriginalPoseArchive.hpp"

#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

namespace Goemon::Original {

enum class OriginalMatrixMemoryLayout : std::uint8_t {
    RowMajorColumnVectors,
    ColumnMajorColumnVectors
};

struct OriginalDrawVertex {
    float x = 0.0f, y = 0.0f, z = 0.0f;
    std::int16_t s = 0, t = 0;
    std::array<std::uint8_t, 4> rgba{};
};

struct OriginalDrawLimb {
    std::uint32_t sourceBonePointer = 0;
    std::uint32_t sourceGraphicsPointer = 0;
    std::vector<OriginalDrawVertex> triangleVertices;
};

struct OriginalArticulatedFrame {
    std::uint32_t exactOriginalTick = 0;
    std::uint8_t character = 0;
    std::uint8_t action = 0;
    std::vector<OriginalDrawLimb> limbs;
    std::size_t unmatchedSourceMeshes = 0;
};

[[nodiscard]] inline std::array<float, 3> ApplyOriginalCapturedMatrix(
    const std::array<float, 16>& source,
    OriginalMatrixMemoryLayout layout,
    float x, float y, float z
) {
    for (float v : source) {
        if (!std::isfinite(v))
            throw std::invalid_argument("nonfinite original game bone matrix");
    }
    if (!std::isfinite(x) || !std::isfinite(y) || !std::isfinite(z))
        throw std::invalid_argument("nonfinite original ROM mesh coordinates");
    float tx = 0.0f, ty = 0.0f, tz = 0.0f, w = 1.0f;
    switch (layout) {
        case OriginalMatrixMemoryLayout::RowMajorColumnVectors:
            tx = source[0]*x + source[1]*y + source[2]*z + source[3];
            ty = source[4]*x + source[5]*y + source[6]*z + source[7];
            tz = source[8]*x + source[9]*y + source[10]*z + source[11];
            w = source[12]*x + source[13]*y + source[14]*z + source[15];
            break;
        case OriginalMatrixMemoryLayout::ColumnMajorColumnVectors:
            tx = source[0]*x + source[4]*y + source[8]*z + source[12];
            ty = source[1]*x + source[5]*y + source[9]*z + source[13];
            tz = source[2]*x + source[6]*y + source[10]*z + source[14];
            w = source[3]*x + source[7]*y + source[11]*z + source[15];
            break;
        default:
            throw std::invalid_argument("unsupported original matrix convention");
    }
    // The authentic game matrix must be nonsingular at the chosen source
    // vertex. Do not force a coordinate convention by silently dropping W.
    if (!std::isfinite(w) || std::fabs(w) < 1e-7f ||
        !std::isfinite(tx) || !std::isfinite(ty) || !std::isfinite(tz))
        throw std::invalid_argument("invalid original game vertex transform");
    const std::array<float, 3> result{tx/w, ty/w, tz/w};
    for (float v : result) {
        if (!std::isfinite(v) || std::fabs(v) > 1e8f)
            throw std::invalid_argument("original animation matrix exceeded bounds");
    }
    return result;
}

[[nodiscard]] inline OriginalArticulatedFrame BuildExactOriginalArticulatedFrame(
    const SourceRig& sourceRig,
    const OriginalCapturedPose& original,
    OriginalMatrixMemoryLayout layout,
    bool requireAllMeshes = true
) {
    if (sourceRig.character != original.characterId)
        throw std::invalid_argument("original ROM character/animation mismatch");
    if (sourceRig.meshes.empty() || original.bones.empty())
        throw std::invalid_argument("missing original ROM skeletal geometry or matrices");
    if (sourceRig.meshes.size() > 2048 || original.bones.size() > 128)
        throw std::invalid_argument("original skeletal draw budget exceeded");

    OriginalArticulatedFrame frame{};
    frame.exactOriginalTick = original.sourceGameFrame;
    frame.character = original.characterId;
    frame.action = original.actionId;
    std::size_t triangles = 0;
    for (const auto& bone : original.bones) {
        if (bone.sourceGfxPointer == 0)
            continue;  // Original skeletal parent may be a pure pivot.
        const SourceRigLimbMesh* mesh = nullptr;
        for (const auto& candidate : sourceRig.meshes) {
            if (candidate.sourceGfxPointer == bone.sourceGfxPointer) {
                if (mesh != nullptr)
                    throw std::invalid_argument("duplicate source ROM Gfx mesh");
                mesh = &candidate;
            }
        }
        if (!mesh) {
            ++frame.unmatchedSourceMeshes;
            if (requireAllMeshes)
                throw std::invalid_argument("animation references a missing original limb mesh");
            continue;
        }
        if (mesh->vertices.empty() || mesh->vertices.size()%3 != 0)
            throw std::invalid_argument("invalid source original limb triangle vertices");
        triangles += mesh->vertices.size()/3;
        if (triangles > 300000)
            throw std::invalid_argument("original source renderer triangle budget exceeded");
        OriginalDrawLimb draw{};
        draw.sourceBonePointer = bone.originalPointer;
        draw.sourceGraphicsPointer = bone.sourceGfxPointer;
        draw.triangleVertices.reserve(mesh->vertices.size());
        for (const auto& vertex : mesh->vertices) {
            const auto transformed = ApplyOriginalCapturedMatrix(
                bone.engineMatrix, layout,
                static_cast<float>(vertex.x),
                static_cast<float>(vertex.y),
                static_cast<float>(vertex.z));
            draw.triangleVertices.push_back({
                transformed[0], transformed[1], transformed[2],
                vertex.s, vertex.t, vertex.originalRGBA
            });
        }
        frame.limbs.push_back(std::move(draw));
    }
    if (frame.limbs.empty())
        throw std::invalid_argument("source frame had no renderable original limbs");
    return frame;
}

[[nodiscard]] inline OriginalArticulatedFrame BuildExactOriginalArticulatedFrame(
    const SourceRig& sourceRig,
    const OriginalCapturedAnimation& sourceAnimation,
    std::uint8_t character, std::uint8_t action,
    std::uint32_t originalGameTick, OriginalMatrixMemoryLayout layout,
    bool requireAllMeshes = true
) {
    const auto* pose = FindExactOriginalPose(
        sourceAnimation, character, action, originalGameTick);
    if (pose == nullptr)
        throw std::invalid_argument("original game action/tick has no recorded frame");
    return BuildExactOriginalArticulatedFrame(
        sourceRig, *pose, layout, requireAllMeshes);
}

} // namespace Goemon::Original
