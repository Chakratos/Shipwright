#include "soh/soh/Enhancements/Goemon/OriginalReferenceMeshLayout.hpp"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <limits>
#include <stdexcept>

using namespace Goemon::Original;

static OriginalStaticReferenceMesh Fixture() {
    OriginalStaticReferenceMesh mesh{};
    mesh.materialCount = 2;
    mesh.vertices = {
        {0, 2, 0, 0, 0, {255, 50, 40, 255}},
        {2, 2, 0, 1, 0, {255, 50, 40, 255}},
        {1, 6, 1, 0.5f, 1, {255, 50, 40, 255}},
        {1, 2, 2, 0.5f, 0.5f, {255, 50, 40, 255}},
    };
    mesh.triangles = {
        {0, 1, 2, 0},
        {0, 2, 3, 1},
    };
    return mesh;
}

int main() {
    const auto mesh = Fixture();
    const auto prepared = PrepareReferenceAppearance(mesh, 48.0f);
    assert(prepared.batches.size() == 2);
    assert(prepared.triangleCount == 2);
    assert(prepared.sourceHeight == 4);
    assert(prepared.appliedScale == 12);
    assert(prepared.batches[0].material == 0);
    assert(prepared.batches[1].material == 1);
    assert(prepared.batches[0].vertices.size() == 3);
    assert(prepared.batches[0].vertices[0].x == -12);
    assert(prepared.batches[0].vertices[0].y == 0);
    assert(prepared.batches[0].vertices[1].x == 12);
    assert(prepared.batches[0].vertices[2].y == 48);
    assert(prepared.batches[0].vertices[2].z == 0);
    assert(prepared.batches[0].vertices[1].texS == 1024);
    assert(prepared.batches[0].vertices[1].texT == 1024);
    assert(prepared.batches[0].vertices[2].texT == 0);
    assert(prepared.batches[0].vertices[2].rgba[1] == 50);

    // Many triangles per original material must be cut at 30 vertices.
    auto many = mesh;
    many.triangles.assign(25, {0, 1, 2, 1});
    const auto batched = PrepareReferenceAppearance(many);
    assert(batched.triangleCount == 25);
    assert(batched.batches.size() == 3);
    assert(batched.batches[0].vertices.size() == 30);
    assert(batched.batches[1].vertices.size() == 30);
    assert(batched.batches[2].vertices.size() == 15);
    for (const auto& batch : batched.batches) {
        assert(batch.vertices.size() <= 30);
        assert(batch.vertices.size() % 3 == 0);
        assert(batch.material == 1);
    }

    // Source OBJ from a Z-up exporter: no guessing; caller selects Z explicitly.
    auto zUp = mesh;
    for (auto& v : zUp.vertices) {
        const float y = v.y;
        v.y = v.z;
        v.z = y;
    }
    const auto turned = PrepareReferenceAppearance(
        zUp, 48.0f, ReferenceUpAxis::Z);
    assert(turned.sourceHeight == 4);
    assert(turned.batches[0].vertices[2].y == 48);

    bool rejected = false;
    try {
        (void)PrepareReferenceAppearance(mesh, 0.0f);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    rejected = false;
    try {
        auto flat = mesh;
        for (auto& v : flat.vertices) v.y = 0;
        (void)PrepareReferenceAppearance(flat);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    rejected = false;
    try {
        auto huge = mesh;
        huge.vertices[0].x = 1000000;
        (void)PrepareReferenceAppearance(huge);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    rejected = false;
    try {
        auto bad = mesh;
        bad.triangles[0].a = 500;
        (void)PrepareReferenceAppearance(bad);
    } catch (const std::invalid_argument&) { rejected = true; }
    assert(rejected);
    std::puts("OriginalReferenceMeshLayout: 30-vertex material batches PASS");
}
