#include "soh/soh/Enhancements/Goemon/OriginalReferenceMesh.hpp"

#include <cassert>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>

using namespace Goemon::Original;

static void AppendU32(std::vector<std::uint8_t>& out, std::uint32_t n) {
    out.push_back(static_cast<std::uint8_t>(n));
    out.push_back(static_cast<std::uint8_t>(n >> 8));
    out.push_back(static_cast<std::uint8_t>(n >> 16));
    out.push_back(static_cast<std::uint8_t>(n >> 24));
}
static void AppendF32(std::vector<std::uint8_t>& out, float f) {
    AppendU32(out, std::bit_cast<std::uint32_t>(f));
}
static std::vector<std::uint8_t> Fixture() {
    std::vector<std::uint8_t> out{'G','O','M','E','S','H','0','1'};
    AppendU32(out, 3);
    AppendU32(out, 1);
    AppendU32(out, 1);
    for (std::uint32_t i = 0; i < 3; ++i) {
        AppendF32(out, static_cast<float>(i));
        AppendF32(out, static_cast<float>(i * 10));
        AppendF32(out, -3.0f);
        AppendF32(out, static_cast<float>(i) / 2.0f);
        AppendF32(out, 0.5f);
        out.insert(out.end(), {255, 128, 64, 255});
    }
    AppendU32(out, 0);
    AppendU32(out, 1);
    AppendU32(out, 2);
    AppendU32(out, 0);
    return out;
}
static bool Fails(std::span<const std::uint8_t> bytes) {
    try {
        (void)ParseOriginalReferenceMesh(bytes);
    } catch (const std::invalid_argument&) {
        return true;
    }
    return false;
}
int main() {
    auto source = Fixture();
    auto data = std::span<const std::uint8_t>(source);
    const auto mesh = ParseOriginalReferenceMesh(data);
    assert(mesh.vertices.size() == 3);
    assert(mesh.triangles.size() == 1);
    assert(mesh.materialCount == 1);
    assert(mesh.vertices[1].y == 10.0f);
    assert(mesh.vertices[2].u == 1.0f);
    assert(mesh.vertices[2].z == -3.0f);
    assert(mesh.vertices[0].rgba[1] == 128);
    assert(mesh.triangles[0].a == 0);
    assert(mesh.triangles[0].b == 1);
    assert(mesh.triangles[0].c == 2);
    assert(mesh.triangles[0].material == 0);
    assert(source.size() == 20 + 3 * 24 + 16);

    auto modified = source;
    modified[0] = 'B';
    assert(Fails(modified));
    modified = source;
    modified.pop_back();
    assert(Fails(modified));
    modified = source;
    modified.push_back(0);
    assert(Fails(modified));
    modified = source;
    modified[8] = 0;
    assert(Fails(modified));
    modified = source;
    modified[16] = 0;
    assert(Fails(modified));
    modified = source;
    modified[20 + 3*24 + 8] = 3; // Invalid triangle index
    assert(Fails(modified));
    modified = source;
    modified[20 + 3*24 + 12] = 1; // Invalid material index
    assert(Fails(modified));
    modified = source;
    // Set x of first vertex to positive infinity, IEEE 754 little endian.
    modified[20 + 0] = 0;
    modified[20 + 1] = 0;
    modified[20 + 2] = 0x80;
    modified[20 + 3] = 0x7F;
    assert(Fails(modified));
    assert(Fails({source.data(), 4}));

    std::puts("OriginalReferenceMesh: geometry loading and data guards PASS");
}
