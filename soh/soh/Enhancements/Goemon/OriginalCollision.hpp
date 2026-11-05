#pragma once
// Original MNSG collision BSP queries recovered in mnsg/src/27FE0.c:
// func_80029E58_2AA58 (scaled) and func_8002A168_2AD68 (unscaled actor).
// Values and branch semantics preserved; malformed N64 data is rejected.
// This is not yet the entire original player collision / movement system.

#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>

namespace Goemon::Original {
struct CollisionPoint { float x, y, z; };
enum class CollisionQuery : std::uint8_t { ScaledPoint, ActorWithTenUnitYReach };

class CollisionMap {
public:
    CollisionMap(std::span<const std::uint8_t> planes,
                 std::span<const std::uint8_t> nodes) : planes_(planes), nodes_(nodes) {
        if (planes_.size() % 20 != 0 || nodes_.size() % 6 != 0)
            throw std::invalid_argument("unaligned original collision records");
    }

    // Original result: 0x7fff = solid, 0 = not solid.
    [[nodiscard]] std::uint16_t Query(CollisionPoint p, CollisionQuery mode,
                                      float scale = 1.0f) const {
        if (!std::isfinite(p.x) || !std::isfinite(p.y) || !std::isfinite(p.z) ||
            !std::isfinite(scale) || scale <= 0.0f)
            throw std::invalid_argument("invalid original collision query");
        if (nodes_.size() < 24)
            throw std::invalid_argument("missing original collision tree / plane node");
        std::size_t node = 0;
        std::size_t steps = 0;
        const std::size_t count = nodes_.size() / 6;
        for (;;) {
            CheckStep(++steps, count);
            auto nextTree = U16(nodes_, node * 6);
            while (Outside(p, node, mode, scale)) {
                if (nextTree == 0xffff)
                    return 0;
                node = nextTree;
                CheckStep(++steps, count);
                nextTree = U16(nodes_, node * 6);
            }
            node += 3; // Original COL_TREE header consumes three 6-byte nodes.
            for (;;) {
                CheckStep(++steps, count);
                const std::size_t base = node * 6;
                const auto planeId = U16(nodes_, base);
                const std::size_t at = static_cast<std::size_t>(planeId) * 20;
                if (at + 20 > planes_.size())
                    throw std::out_of_range("original collision plane ID out of range");
                const float nx = F32(planes_, at);
                const float ny = F32(planes_, at + 4);
                const float nz = F32(planes_, at + 8);
                const float dist = F32(planes_, at + 12) *
                    (mode == CollisionQuery::ScaledPoint ? scale : 1.0f);
                const float signedDistance = ((p.x * nx) + (p.y * ny) + (p.z * nz)) + dist;
                if (signedDistance < 0.0f) {
                    const auto back = S16(nodes_, base + 2);
                    if (back == 0)
                        return 0x7fff;
                    if (back < 0)
                        throw std::out_of_range("negative original collision back child");
                    node = static_cast<std::size_t>(back);
                } else {
                    const auto front = S16(nodes_, base + 4);
                    if (front == 0) {
                        if (nextTree == 0xffff)
                            return 0;
                        node = nextTree;
                        break;
                    }
                    if (front < 0)
                        throw std::out_of_range("negative original collision front child");
                    node = static_cast<std::size_t>(front);
                }
            }
        }
    }

private:
    // Exact copy of original outside-box comparisons, including the
    // 10.0f actor Y reach in func_8002A168_2AD68.
    bool Outside(CollisionPoint p, std::size_t node, CollisionQuery mode, float scale) const {
        const auto offset = node * 6;
        if (offset + 18 > nodes_.size())
            throw std::out_of_range("original collision tree outside node buffer");
        const auto maxX = S16(nodes_, offset + 6);
        const auto maxY = S16(nodes_, offset + 8);
        const auto maxZ = S16(nodes_, offset + 10);
        const auto minX = S16(nodes_, offset + 12);
        const auto minY = S16(nodes_, offset + 14);
        const auto minZ = S16(nodes_, offset + 16);
        if (mode == CollisionQuery::ScaledPoint) {
            return (maxX * scale < p.x || p.x < minX * scale ||
                    maxZ * scale < p.z || p.z < minZ * scale ||
                    maxY * scale < p.y || p.y < minY * scale);
        }
        return (maxX < p.x || p.x < minX || maxY < p.y ||
                (p.y + 10.0f) < minY || maxZ < p.z || p.z < minZ);
    }

    static void CheckStep(std::size_t step, std::size_t nodes) {
        if (step > nodes * 8 + 8)
            throw std::runtime_error("malformed original collision tree cycle");
    }
    static std::uint16_t U16(std::span<const std::uint8_t> a, std::size_t at) {
        if (at > a.size() || a.size()-at < 2)
            throw std::out_of_range("truncated N64 collision record");
        return (static_cast<std::uint16_t>(a[at]) << 8) | a[at+1];
    }
    static std::int16_t S16(std::span<const std::uint8_t> a, std::size_t at) {
        return std::bit_cast<std::int16_t>(U16(a,at));
    }
    static float F32(std::span<const std::uint8_t> a, std::size_t at) {
        if (at > a.size() || a.size()-at < 4)
            throw std::out_of_range("truncated N64 collision plane");
        std::uint32_t bits = (static_cast<std::uint32_t>(a[at]) << 24) |
                            (static_cast<std::uint32_t>(a[at+1]) << 16) |
                            (static_cast<std::uint32_t>(a[at+2]) << 8) | a[at+3];
        return std::bit_cast<float>(bits);
    }
    std::span<const std::uint8_t> planes_;
    std::span<const std::uint8_t> nodes_;
};
} // namespace Goemon::Original
