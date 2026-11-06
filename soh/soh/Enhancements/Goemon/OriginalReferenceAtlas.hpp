#pragma once
// Piecewise rendering of an original N64 character OBJ 128x128 texture atlas.
// RGBA16 N64 TMEM holds 32x32 atlas tiles (2048 bytes), not a whole 128x128
// source PNG. Clip each UV triangle to its tile; retain positions by linear
// interpolation. This gives an unmodified atlas at native resolution instead
// of uploading or baking copyrighted game graphics.
#include "OriginalReferenceMeshLayout.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <utility>
#include <vector>

namespace Goemon::Original {
constexpr std::uint32_t kReferenceAtlasSize = 128;
constexpr std::uint32_t kReferenceTileSize = 32;
constexpr std::uint32_t kReferenceTilesPerSide = 4;
constexpr std::uint32_t kReferenceTilesPerMaterial = 16;

struct AtlasClippingVertex {
    float x, y, z;
    float u, v; // PNG pixel coordinates, origin at top-left.
    std::array<std::uint8_t, 4> rgba{};
};

enum class AtlasClipSide : std::uint8_t {
    MinimumU, MaximumU, MinimumV, MaximumV
};

[[nodiscard]] inline float AtlasCoordinate(const AtlasClippingVertex& p,
                                           AtlasClipSide side) {
    return side == AtlasClipSide::MinimumU ||
                   side == AtlasClipSide::MaximumU ? p.u : p.v;
}

[[nodiscard]] inline AtlasClippingVertex InterpolateAtlasVertex(
    const AtlasClippingVertex& a, const AtlasClippingVertex& b, float t
) {
    const auto mix = [t](float x, float y) { return x + (y - x) * t; };
    AtlasClippingVertex out{
        mix(a.x, b.x), mix(a.y, b.y), mix(a.z, b.z),
        mix(a.u, b.u), mix(a.v, b.v), a.rgba
    };
    return out;
}

[[nodiscard]] inline std::vector<AtlasClippingVertex> ClipAtlasPolygon(
    const std::vector<AtlasClippingVertex>& polygon,
    AtlasClipSide side, float border
) {
    if (polygon.empty()) return {};
    const bool lower = side == AtlasClipSide::MinimumU ||
                       side == AtlasClipSide::MinimumV;
    const auto inside = [&](const AtlasClippingVertex& p) {
        return lower ? AtlasCoordinate(p, side) >= border :
                       AtlasCoordinate(p, side) <= border;
    };
    std::vector<AtlasClippingVertex> result;
    result.reserve(polygon.size() + 2);
    AtlasClippingVertex previous = polygon.back();
    bool lastInside = inside(previous);
    for (const auto& current : polygon) {
        const bool nowInside = inside(current);
        if (lastInside != nowInside) {
            const float from = AtlasCoordinate(previous, side);
            const float to = AtlasCoordinate(current, side);
            const float delta = to - from;
            if (delta == 0.0f)
                throw std::invalid_argument("degenerate original UV clipping edge");
            const float t = std::clamp((border - from) / delta, 0.0f, 1.0f);
            auto inter = InterpolateAtlasVertex(previous, current, t);
            if (side == AtlasClipSide::MinimumU ||
                side == AtlasClipSide::MaximumU) inter.u = border;
            else inter.v = border;
            result.push_back(inter);
        }
        if (nowInside) result.push_back(current);
        previous = current;
        lastInside = nowInside;
    }
    return result;
}

[[nodiscard]] inline PreparedReferenceAppearance PrepareReferenceAtlas(
    const OriginalStaticReferenceMesh& mesh, float targetHeight = 48.0f,
    ReferenceUpAxis up = ReferenceUpAxis::Y
) {
    if (mesh.vertices.empty() || mesh.triangles.empty() || !mesh.materialCount ||
        !std::isfinite(targetHeight) || targetHeight <= 0.0f ||
        mesh.vertices.size() > 300000 || mesh.triangles.size() > 200000 ||
        mesh.materialCount > 32)
        throw std::invalid_argument("invalid original static reference atlas input");

    std::array<float, 3> minimum{
        std::numeric_limits<float>::infinity(),
        std::numeric_limits<float>::infinity(),
        std::numeric_limits<float>::infinity()
    };
    std::array<float, 3> maximum{-minimum[0], -minimum[1], -minimum[2]};
    for (const auto& v : mesh.vertices) {
        const std::array<float, 5> values{v.x,v.y,v.z,v.u,v.v};
        for (float x : values)
            if (!std::isfinite(x))
                throw std::invalid_argument("nonfinite original model vertex");
        const std::array<float,3> xyz{v.x,v.y,v.z};
        for (std::size_t n = 0; n < 3; ++n) {
            minimum[n] = std::min(minimum[n], xyz[n]);
            maximum[n] = std::max(maximum[n], xyz[n]);
        }
        if (v.u < -0.001f || v.u > 1.001f ||
            v.v < -0.001f || v.v > 1.001f)
            throw std::invalid_argument("source atlas UV outside 0..1");
    }
    const std::size_t heightAxis = up == ReferenceUpAxis::Y ? 1 : 2;
    const float sourceHeight = maximum[heightAxis] - minimum[heightAxis];
    if (!std::isfinite(sourceHeight) || sourceHeight < 0.00001f)
        throw std::invalid_argument("degenerate original character height");
    const float scale = targetHeight / sourceHeight;
    if (!std::isfinite(scale))
        throw std::invalid_argument("invalid original character scale");

    constexpr std::uint32_t tiles = kReferenceTilesPerMaterial;
    std::vector<std::vector<PreparedReferenceVertex>> groups(
        mesh.materialCount * tiles);

    for (const auto& face : mesh.triangles) {
        if (face.a >= mesh.vertices.size() || face.b >= mesh.vertices.size() ||
            face.c >= mesh.vertices.size() || face.material >= mesh.materialCount)
            throw std::invalid_argument("invalid original atlas face");
        const auto transform = [](const StaticMeshVertex& v) {
            return AtlasClippingVertex{
                v.x, v.y, v.z,
                std::clamp(v.u, 0.0f, 1.0f) * 128.0f,
                (1.0f - std::clamp(v.v, 0.0f, 1.0f)) * 128.0f,
                v.rgba
            };
        };
        const std::array<AtlasClippingVertex,3> triangle{
            transform(mesh.vertices[face.a]),
            transform(mesh.vertices[face.b]),
            transform(mesh.vertices[face.c])
        };
        float loU = 128, hiU = 0, loV = 128, hiV = 0;
        for (const auto& p : triangle) {
            loU = std::min(loU, p.u); hiU = std::max(hiU, p.u);
            loV = std::min(loV, p.v); hiV = std::max(hiV, p.v);
        }
        const auto tileMin = [](float v) {
            return std::clamp(static_cast<int>(std::floor(v / 32.0f)), 0, 3);
        };
        const auto tileMax = [](float v) {
            return std::clamp(static_cast<int>(std::ceil(v / 32.0f)) - 1, 0, 3);
        };
        for (int ty = tileMin(loV); ty <= tileMax(hiV); ++ty) {
            for (int tx = tileMin(loU); tx <= tileMax(hiU); ++tx) {
                std::vector<AtlasClippingVertex> clipped{
                    triangle.begin(), triangle.end()
                };
                clipped = ClipAtlasPolygon(
                    clipped, AtlasClipSide::MinimumU, tx * 32.0f);
                clipped = ClipAtlasPolygon(
                    clipped, AtlasClipSide::MaximumU, (tx + 1) * 32.0f);
                clipped = ClipAtlasPolygon(
                    clipped, AtlasClipSide::MinimumV, ty * 32.0f);
                clipped = ClipAtlasPolygon(
                    clipped, AtlasClipSide::MaximumV, (ty + 1) * 32.0f);
                if (clipped.size() < 3) continue;

                const std::uint32_t materialTile =
                    face.material * tiles + ty * 4 + tx;
                auto& vertices = groups[materialTile];
                for (std::size_t i = 1; i + 1 < clipped.size(); ++i) {
                    const std::array<AtlasClippingVertex,3> subtriangle{
                        clipped[0], clipped[i], clipped[i + 1]
                    };
                    const float determinant =
                        (subtriangle[1].u - subtriangle[0].u) *
                        (subtriangle[2].v - subtriangle[0].v) -
                        (subtriangle[2].u - subtriangle[0].u) *
                        (subtriangle[1].v - subtriangle[0].v);
                    if (std::fabs(determinant) < 0.000001f) continue;
                    for (const auto& p : subtriangle) {
                        const float height = (&p.x)[heightAxis] -
                                             minimum[heightAxis];
                        const float centerX =
                            (minimum[0] + maximum[0]) * 0.5f;
                        const float centerForward =
                            up == ReferenceUpAxis::Y ?
                              (minimum[2] + maximum[2]) * 0.5f :
                             -(minimum[1] + maximum[1]) * 0.5f;
                        const float forward =
                            up == ReferenceUpAxis::Y ? p.z : -p.y;
                        PreparedReferenceVertex v{};
                        v.x = RoundedReferenceS16((p.x - centerX) * scale);
                        v.y = RoundedReferenceS16(height * scale);
                        v.z = RoundedReferenceS16(
                            (forward - centerForward) * scale);
                        v.texS = RoundedReferenceS16(
                            std::clamp(p.u - tx * 32.0f, 0.0f, 32.0f) * 32.0f);
                        v.texT = RoundedReferenceS16(
                            std::clamp(p.v - ty * 32.0f, 0.0f, 32.0f) * 32.0f);
                        v.rgba = p.rgba;
                        vertices.push_back(v);
                    }
                }
            }
        }
    }

    PreparedReferenceAppearance result;
    result.sourceHeight = sourceHeight;
    result.appliedScale = scale;
    for (std::uint32_t tile = 0; tile < groups.size(); ++tile) {
        const auto& verts = groups[tile];
        for (std::size_t i = 0; i < verts.size(); i += 30) {
            const auto last = std::min(i + 30, verts.size());
            PreparedReferenceDrawBatch batch{};
            batch.material = tile;
            batch.vertices.assign(verts.begin() + i, verts.begin() + last);
            if (batch.vertices.size() % 3)
                throw std::invalid_argument("partial original atlas triangle");
            result.triangleCount +=
                static_cast<std::uint32_t>(batch.vertices.size() / 3);
            result.batches.push_back(std::move(batch));
        }
    }
    if (result.batches.empty())
        throw std::invalid_argument("all original character atlas faces degenerate");
    return result;
}
} // namespace Goemon::Original
