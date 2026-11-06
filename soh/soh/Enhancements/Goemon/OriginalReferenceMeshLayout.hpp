#pragma once
// Source-free layout stage for rendering original-looking Goemon geometry.
// Separates original OBJ coordinates and materials from Ship/N64 Vtx setup.
// Raw static geometry remains a reference pending original ROM rig recovery.
#include "OriginalReferenceMesh.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace Goemon::Original {

enum class ReferenceUpAxis : std::uint8_t { Y = 0, Z = 1 };

struct PreparedReferenceVertex {
    std::int16_t x = 0;
    std::int16_t y = 0;
    std::int16_t z = 0;
    std::int16_t texS = 0;
    std::int16_t texT = 0;
    std::array<std::uint8_t, 4> rgba{};
};

struct PreparedReferenceDrawBatch {
    std::uint32_t material = 0;
    std::vector<PreparedReferenceVertex> vertices;
    // All three vertices per triangle are consecutive. A batch of 30
    // vertices fits the original 32-entry N64 vertex cache.
};

struct PreparedReferenceAppearance {
    std::vector<PreparedReferenceDrawBatch> batches;
    float sourceHeight = 0.0f;
    float appliedScale = 0.0f;
    std::uint32_t triangleCount = 0;
};

[[nodiscard]] inline std::int16_t RoundedReferenceS16(float value) {
    if (!std::isfinite(value) || value < -32768.0f || value > 32767.0f)
        throw std::invalid_argument("source model position/UV exceeds N64 vertex range");
    return static_cast<std::int16_t>(std::lround(value));
}

[[nodiscard]] inline PreparedReferenceAppearance PrepareReferenceAppearance(
    const OriginalStaticReferenceMesh& mesh, float targetHeight = 48.0f,
    ReferenceUpAxis up = ReferenceUpAxis::Y
) {
    if (mesh.vertices.empty() || mesh.triangles.empty() || !mesh.materialCount ||
        !std::isfinite(targetHeight) || targetHeight <= 0.0f)
        throw std::invalid_argument("invalid Goemon original reference layout");
    if (mesh.materialCount > 1024 || mesh.vertices.size() > 300000 ||
        mesh.triangles.size() > 200000)
        throw std::invalid_argument("oversized original reference layout");

    float minX = std::numeric_limits<float>::infinity();
    float maxX = -minX;
    float minY = minX, maxY = -minX;
    float minZ = minX, maxZ = -minX;
    for (const auto& v : mesh.vertices) {
        if (!std::isfinite(v.x) || !std::isfinite(v.y) ||
            !std::isfinite(v.z) || !std::isfinite(v.u) || !std::isfinite(v.v))
            throw std::invalid_argument("nonfinite original reference vertex");
        minX = std::min(minX, v.x); maxX = std::max(maxX, v.x);
        minY = std::min(minY, v.y); maxY = std::max(maxY, v.y);
        minZ = std::min(minZ, v.z); maxZ = std::max(maxZ, v.z);
    }

    const float lo = up == ReferenceUpAxis::Y ? minY : minZ;
    const float hi = up == ReferenceUpAxis::Y ? maxY : maxZ;
    const float sourceHeight = hi - lo;
    if (!std::isfinite(sourceHeight) || sourceHeight < 0.00001f)
        throw std::invalid_argument("degenerate reference character height");
    const float scale = targetHeight / sourceHeight;
    if (!std::isfinite(scale))
        throw std::invalid_argument("nonfinite reference character scale");

    std::vector<std::vector<PreparedReferenceVertex>> byMaterial(mesh.materialCount);
    for (const auto& face : mesh.triangles) {
        if (face.a >= mesh.vertices.size() ||
            face.b >= mesh.vertices.size() ||
            face.c >= mesh.vertices.size() ||
            face.material >= mesh.materialCount)
            throw std::invalid_argument("invalid reference character triangle");
        for (const auto index : {face.a, face.b, face.c}) {
            const auto& v = mesh.vertices[index];
            PreparedReferenceVertex prepared;
            const float height = (up == ReferenceUpAxis::Y ? v.y : v.z) - lo;
            const float forward = up == ReferenceUpAxis::Y ? v.z : -v.y;
            const float centerForward =
                up == ReferenceUpAxis::Y ? (minZ + maxZ) * 0.5f
                                          : -(minY + maxY) * 0.5f;
            prepared.x = RoundedReferenceS16(
                (v.x - (minX + maxX) * 0.5f) * scale);
            prepared.y = RoundedReferenceS16(height * scale);
            prepared.z = RoundedReferenceS16((forward - centerForward) * scale);
            // Preserve source UV repeats up to +/- 16 tiles; local texture
            // loader decides clamp/wrap. N64 texture coordinates are s10.5.
            prepared.texS = RoundedReferenceS16(
                std::clamp(v.u, -16.0f, 16.0f) * 32.0f * 32.0f);
            prepared.texT = RoundedReferenceS16(
                std::clamp(1.0f - v.v, -16.0f, 16.0f) * 32.0f * 32.0f);
            prepared.rgba = v.rgba;
            byMaterial[face.material].push_back(prepared);
        }
    }

    PreparedReferenceAppearance output;
    output.sourceHeight = sourceHeight;
    output.appliedScale = scale;
    output.triangleCount = static_cast<std::uint32_t>(mesh.triangles.size());
    for (std::uint32_t m = 0; m < mesh.materialCount; ++m) {
        const auto& verts = byMaterial[m];
        // Prevent N64 cache overflow and preserve complete triangles.
        for (std::size_t i = 0; i < verts.size(); i += 30) {
            const auto end = std::min(i + 30, verts.size());
            PreparedReferenceDrawBatch batch;
            batch.material = m;
            batch.vertices.assign(verts.begin() + i, verts.begin() + end);
            output.batches.push_back(std::move(batch));
        }
    }
    return output;
}
} // namespace Goemon::Original
