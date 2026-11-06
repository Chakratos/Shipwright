#pragma once
// Ship-side loader for locally generated Goemon reference geometry.
// Source file: tools/goemon/re/import_reference_models.py
// No proprietary model data, game ROM bytes or textures are compiled here.
//
// GOMESH01 contains STATIC geometry only. This is NOT the original
// NG5E skeleton/skin/animation or a replacement for the playable actor.
#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <vector>

namespace Goemon::Original {

struct StaticMeshVertex {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    float u = 0.0f;
    float v = 0.0f;
    std::array<std::uint8_t, 4> rgba{};
};

struct StaticMeshTriangle {
    std::uint32_t a = 0;
    std::uint32_t b = 0;
    std::uint32_t c = 0;
    std::uint32_t material = 0;
};

struct OriginalStaticReferenceMesh {
    std::vector<StaticMeshVertex> vertices;
    std::vector<StaticMeshTriangle> triangles;
    std::uint32_t materialCount = 0;
};

class OriginalMeshReader {
  public:
    explicit OriginalMeshReader(std::span<const std::uint8_t> bytes) : bytes_(bytes) {}

    std::uint32_t U32(std::size_t at) const {
        if (at > bytes_.size() || bytes_.size() - at < 4)
            throw std::invalid_argument("truncated GOMESH01 input");
        return static_cast<std::uint32_t>(bytes_[at]) |
               (static_cast<std::uint32_t>(bytes_[at + 1]) << 8) |
               (static_cast<std::uint32_t>(bytes_[at + 2]) << 16) |
               (static_cast<std::uint32_t>(bytes_[at + 3]) << 24);
    }

    float F32(std::size_t at) const {
        const float value = std::bit_cast<float>(U32(at));
        if (!std::isfinite(value))
            throw std::invalid_argument("nonfinite GOMESH01 vertex attribute");
        return value;
    }

    std::uint8_t U8(std::size_t at) const {
        if (at >= bytes_.size())
            throw std::invalid_argument("truncated GOMESH01 vertex color");
        return bytes_[at];
    }

  private:
    std::span<const std::uint8_t> bytes_;
};

[[nodiscard]] inline OriginalStaticReferenceMesh ParseOriginalReferenceMesh(
    std::span<const std::uint8_t> bytes) {
    constexpr std::size_t headerSize = 20;
    constexpr std::size_t vertexSize = 24;
    constexpr std::size_t triangleSize = 16;
    if (bytes.size() < headerSize)
        throw std::invalid_argument("truncated GOMESH01 header");
    constexpr std::array<std::uint8_t, 8> magic{'G','O','M','E','S','H','0','1'};
    for (std::size_t i = 0; i < magic.size(); ++i) {
        if (bytes[i] != magic[i])
            throw std::invalid_argument("unsupported GOMESH01 magic/version");
    }

    OriginalMeshReader reader(bytes);
    const std::uint32_t vertexCount = reader.U32(8);
    const std::uint32_t triangleCount = reader.U32(12);
    const std::uint32_t materialCount = reader.U32(16);
    if (vertexCount == 0 || triangleCount == 0 ||
        vertexCount > 300000 || triangleCount > 200000 ||
        materialCount == 0 || materialCount > 1024)
        throw std::invalid_argument("invalid original static mesh counts");
    const std::size_t expectedSize =
        headerSize + static_cast<std::size_t>(vertexCount) * vertexSize +
        static_cast<std::size_t>(triangleCount) * triangleSize;
    if (bytes.size() != expectedSize)
        throw std::invalid_argument("GOMESH01 payload size mismatch");

    OriginalStaticReferenceMesh mesh;
    mesh.materialCount = materialCount;
    mesh.vertices.reserve(vertexCount);
    mesh.triangles.reserve(triangleCount);
    std::size_t at = headerSize;
    for (std::uint32_t i = 0; i < vertexCount; ++i) {
        StaticMeshVertex vertex;
        vertex.x = reader.F32(at);
        vertex.y = reader.F32(at + 4);
        vertex.z = reader.F32(at + 8);
        vertex.u = reader.F32(at + 12);
        vertex.v = reader.F32(at + 16);
        for (std::size_t c = 0; c < 4; ++c)
            vertex.rgba[c] = reader.U8(at + 20 + c);
        mesh.vertices.push_back(vertex);
        at += vertexSize;
    }
    for (std::uint32_t i = 0; i < triangleCount; ++i) {
        StaticMeshTriangle face{
            reader.U32(at), reader.U32(at + 4),
            reader.U32(at + 8), reader.U32(at + 12)
        };
        if (face.a >= vertexCount || face.b >= vertexCount ||
            face.c >= vertexCount || face.material >= materialCount)
            throw std::invalid_argument("out-of-range original static mesh face");
        mesh.triangles.push_back(face);
        at += triangleSize;
    }
    return mesh;
}
} // namespace Goemon::Original
