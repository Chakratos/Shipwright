#include "soh/soh/Enhancements/Goemon/OriginalReferenceAtlas.hpp"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <stdexcept>

using namespace Goemon::Original;

static OriginalStaticReferenceMesh WithinOneTile() {
    OriginalStaticReferenceMesh mesh{};
    mesh.materialCount = 1;
    // At PNG x=[8,24] and y=[8,24], entirely inside tile (0,0).
    mesh.vertices = {
        {0, 0, 0, 0.0625f, 0.9375f, {255,255,255,255}},
        {4, 0, 0, 0.1875f, 0.9375f, {255,255,255,255}},
        {0, 8, 0, 0.0625f, 0.8125f, {255,255,255,255}},
    };
    mesh.triangles = {{0, 1, 2, 0}};
    return mesh;
}

int main() {
    const auto mesh = WithinOneTile();
    auto result = PrepareReferenceAtlas(mesh, 48.0f);
    assert(result.batches.size() == 1);
    assert(result.triangleCount == 1);
    assert(result.batches[0].material == 0);
    assert(result.batches[0].vertices.size() == 3);
    assert(result.batches[0].vertices[2].y == 48);
    assert(result.batches[0].vertices[0].texS == 8 * 32);
    assert(result.batches[0].vertices[0].texT == 8 * 32);

    auto crossing = mesh;
    // This triangle crosses the x=32 boundary from left tile to right.
    crossing.vertices[1].u = 0.375f; // 48 pixels
    crossing.vertices[2].u = 0.375f;
    result = PrepareReferenceAtlas(crossing);
    assert(result.triangleCount >= 2);
    bool left = false, right = false;
    for (const auto& b : result.batches) {
        left = left || b.material == 0;
        right = right || b.material == 1;
        assert(b.vertices.size() % 3 == 0);
        assert(b.vertices.size() <= 30);
        for (const auto& v : b.vertices) {
            assert(v.texS >= 0 && v.texS <= 32 * 32);
            assert(v.texT >= 0 && v.texT <= 32 * 32);
        }
    }
    assert(left && right);

    // A separate source material must map into separate atlas tiles.
    auto materials = mesh;
    materials.materialCount = 2;
    materials.triangles.push_back({0,1,2,1});
    result = PrepareReferenceAtlas(materials);
    assert(result.triangleCount == 2);
    assert(result.batches.size() == 2);
    assert(result.batches[0].material == 0);
    assert(result.batches[1].material == 16);

    // Correct behavior at exact x=128 (the outer image border).
    auto outer = mesh;
    for (auto& v : outer.vertices)
        v.u += 0.75f;
    result = PrepareReferenceAtlas(outer);
    assert(result.batches.size() == 1);
    assert(result.batches[0].material == 3);

    bool rejected = false;
    try {
        auto invalid = mesh;
        invalid.vertices[0].u = 4.0f;
        (void)PrepareReferenceAtlas(invalid);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    rejected = false;
    try {
        auto invalid = mesh;
        invalid.vertices[0].y = invalid.vertices[1].y;
        invalid.vertices[2].y = invalid.vertices[1].y;
        (void)PrepareReferenceAtlas(invalid);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);

    std::puts("OriginalReferenceAtlas: exact original PNG tile clipping PASS");
}
