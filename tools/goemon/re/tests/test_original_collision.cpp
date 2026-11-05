// Native C++20 regressions for two documented original Goemon BSP queries.
// Build without game ROM or Zelda dependencies.
#include "soh/soh/Enhancements/Goemon/OriginalCollision.hpp"
#include <array>
#include <cassert>
#include <bit>
#include <cstdint>
#include <cstdio>
#include <span>
#include <stdexcept>

using namespace Goemon::Original;

template<std::size_t N>
void Set16(std::array<std::uint8_t,N>& b, std::size_t at, std::uint16_t v) {
    b.at(at)=static_cast<std::uint8_t>(v>>8);
    b.at(at+1)=static_cast<std::uint8_t>(v&255);
}
template<std::size_t N>
void Set32(std::array<std::uint8_t,N>& b, std::size_t at, std::uint32_t v) {
    b.at(at)=static_cast<std::uint8_t>(v>>24);
    b.at(at+1)=static_cast<std::uint8_t>(v>>16);
    b.at(at+2)=static_cast<std::uint8_t>(v>>8);
    b.at(at+3)=static_cast<std::uint8_t>(v);
}

int main() {
    // One COL_TREE (three 6-byte nodes) followed by one COL_NODE.
    std::array<std::uint8_t,20> planes{};
    std::array<std::uint8_t,24> nodes{};
    Set32(planes,0,std::bit_cast<std::uint32_t>(1.0f));
    Set16(nodes,0,0xffff); // No next tree.
    Set16(nodes,6,50); Set16(nodes,8,50); Set16(nodes,10,50);
    Set16(nodes,12,static_cast<std::uint16_t>(-50));
    Set16(nodes,14,static_cast<std::uint16_t>(-50));
    Set16(nodes,16,static_cast<std::uint16_t>(-50));
    CollisionMap map(planes,nodes);
    assert(map.Query({-1,0,0},CollisionQuery::ScaledPoint)==0x7fff);
    assert(map.Query({1,0,0},CollisionQuery::ScaledPoint)==0);
    assert(map.Query({100,0,0},CollisionQuery::ScaledPoint)==0);
    assert(map.Query({60,0,0},CollisionQuery::ScaledPoint,2.0f)==0);
    assert(map.Query({-1,0,0},CollisionQuery::ActorWithTenUnitYReach)==0x7fff);

    // The original actor query gives Y an extra 10 units at the lower bound.
    Set16(nodes,14,5);
    CollisionMap ymap(planes,nodes);
    assert(ymap.Query({-1,0,0},CollisionQuery::ScaledPoint)==0);
    assert(ymap.Query({-1,0,0},CollisionQuery::ActorWithTenUnitYReach)==0x7fff);

    bool threw=false;
    try {(void)map.Query({0,0,0},CollisionQuery::ScaledPoint,0.f);}
    catch(std::invalid_argument const&) {threw=true;}
    assert(threw);
    threw=false;
    try {
        [[maybe_unused]] CollisionMap wrong(
            std::span<const std::uint8_t>(nodes).first(18),
            std::span<const std::uint8_t>(planes).first(17));
    } catch(std::invalid_argument const&) {threw=true;}
    assert(threw);

    // Next-tree chaining and plane indexing are part of the original traversal.
    std::array<std::uint8_t,40> p2{};
    std::array<std::uint8_t,48> n2{};
    Set32(p2,0,std::bit_cast<std::uint32_t>(1.f));
    Set32(p2,20,std::bit_cast<std::uint32_t>(-1.f));
    Set16(n2,0,4); // Next COL_TREE starts at 6-byte node index 4.
    Set16(n2,6,10); Set16(n2,8,10); Set16(n2,10,10);
    Set16(n2,12,static_cast<std::uint16_t>(-10));
    Set16(n2,14,static_cast<std::uint16_t>(-10));
    Set16(n2,16,static_cast<std::uint16_t>(-10));
    Set16(n2,24,0xffff);
    Set16(n2,30,50); Set16(n2,32,10); Set16(n2,34,10);
    Set16(n2,36,20);
    Set16(n2,38,static_cast<std::uint16_t>(-10));
    Set16(n2,40,static_cast<std::uint16_t>(-10));
    Set16(n2,42,1); // Original plane index for second tree.
    CollisionMap twoTrees(p2,n2);
    assert(twoTrees.Query({-1,0,0},CollisionQuery::ScaledPoint)==0x7fff);
    assert(twoTrees.Query({30,0,0},CollisionQuery::ScaledPoint)==0x7fff);
    assert(twoTrees.Query({15,0,0},CollisionQuery::ScaledPoint)==0);
    assert(twoTrees.Query({60,0,0},CollisionQuery::ScaledPoint)==0);

    // A corrupt tree cycle must fail rather than spin infinitely.
    Set16(n2,0,0);
    threw=false;
    try {(void)CollisionMap(p2,n2).Query({500,0,0},CollisionQuery::ScaledPoint);}
    catch(std::runtime_error const&) {threw=true;}
    assert(threw);
    std::puts("OriginalCollision: PASS");
}
