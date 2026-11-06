#include "soh/soh/Enhancements/Goemon/OriginalPoseArchive.hpp"

#include <bit>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <vector>

using namespace Goemon::Original;

static void Add8(std::vector<std::uint8_t>& b, unsigned n) {
    b.push_back(static_cast<std::uint8_t>(n));
}
static void Add16(std::vector<std::uint8_t>& b, unsigned n) {
    Add8(b, n & 255);
    Add8(b, (n >> 8) & 255);
}
static void Add32(std::vector<std::uint8_t>& b, std::uint32_t n) {
    Add16(b, n & 65535);
    Add16(b, n >> 16);
}
static void AddBone(std::vector<std::uint8_t>& b, std::uint32_t ptr,
                    std::uint32_t gfx, float translation) {
    Add32(b, ptr);
    Add32(b, gfx);
    Add8(b, 1);
    Add8(b, 0);
    for (int i = 0; i < 9; ++i)
        Add16(b, static_cast<unsigned>(i + 3));
    for (int i = 0; i < 16; ++i) {
        const float value = (i % 5 == 0) ? 1.0f :
                            (i == 12) ? translation : 0.0f;
        Add32(b, std::bit_cast<std::uint32_t>(value));
    }
}
static void AddFrame(std::vector<std::uint8_t>& b,
                     std::uint32_t tick, unsigned charSlot,
                     unsigned action, std::uint32_t ptr, float x) {
    Add32(b,tick);
    Add8(b,charSlot);
    Add8(b,action);
    Add16(b,1);
    AddBone(b,ptr,0x070024A8,x);
}
static std::vector<std::uint8_t> Fixture() {
    std::vector<std::uint8_t> bytes = {'G','O','P','A','0','0','0','1'};
    Add32(bytes,2);
    Add32(bytes,2);
    AddFrame(bytes,100,0,15,0x80123480,2.5f);
    AddFrame(bytes,101,0,23,0x80123480,3.5f);
    return bytes;
}
static void MustReject(const std::vector<std::uint8_t>& bytes) {
    bool rejected=false;
    try { (void)OriginalAnimationArchiveReader(bytes).Parse(); }
    catch (const std::invalid_argument&) { rejected=true; }
    assert(rejected);
}
int main() {
    const auto fixture=Fixture();
    const auto data=OriginalAnimationArchiveReader(fixture).Parse();
    assert(data.frames.size()==2);
    assert(data.totalBoneMatrices==2);
    const auto* run=FindExactOriginalPose(data,0,15,100);
    assert(run);
    assert(run->bones.size()==1);
    assert(run->bones[0].originalPointer==0x80123480);
    assert(run->bones[0].sourceGfxPointer==0x070024A8);
    assert(run->bones[0].rawTransform[0]==3);
    assert(run->bones[0].rawTransform[8]==11);
    assert(run->bones[0].engineMatrix[0]==1);
    assert(run->bones[0].engineMatrix[12]==2.5f);
    const auto* jump=FindExactOriginalPose(data,0,23,101);
    assert(jump && jump->bones[0].engineMatrix[12]==3.5f);
    assert(!FindExactOriginalPose(data,0,15,101));
    assert(!FindExactOriginalPose(data,1,15,100));
    assert(!FindExactOriginalPose(data,0,15,102));

    auto malformed=fixture;
    malformed[0]='X'; MustReject(malformed);
    malformed=fixture; malformed.resize(malformed.size()-3); MustReject(malformed);
    malformed=fixture; malformed.push_back(1); MustReject(malformed);
    malformed=fixture; malformed[12]=3; MustReject(malformed); // wrong header bone count
    malformed=fixture;
    // Frame count=2, original frame #2 starts at 16+8+92=116.
    malformed[116]=90; // 90 < 100, game tick out of order
    MustReject(malformed);
    malformed=fixture;
    // First bone pointer starts at frame header + file header = 16+8
    malformed[24]=0;
    malformed[25]=0;
    malformed[26]=0;
    malformed[27]=0;
    MustReject(malformed);

    std::puts("OriginalPoseArchive: exact original tick/action and matrices PASS");
}
