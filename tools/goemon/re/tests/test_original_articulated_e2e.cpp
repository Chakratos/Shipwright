#include "soh/soh/Enhancements/Goemon/OriginalArticulatedFrame.hpp"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>

using namespace Goemon::Original;

static std::vector<std::uint8_t> ReadLocal(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary|std::ios::ate);
    if (!file) throw std::runtime_error("missing synthetic rig/matrix file");
    const auto end=file.tellg();
    if (end<=0 || end>1024*1024)
        throw std::runtime_error("synthetic fixture file size invalid");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(end));
    file.seekg(0);
    if (!file.read(reinterpret_cast<char*>(bytes.data()),
                   static_cast<std::streamsize>(bytes.size())))
        throw std::runtime_error("failed reading synthetic fixture");
    return bytes;
}
int main(int argc,char** argv) {
    if (argc!=3) return 2;
    auto sourceBytes=ReadLocal(argv[1]);
    auto sourceFrames=ReadLocal(argv[2]);
    const auto rig=SourceRigReader(sourceBytes).Parse();
    const auto archive=OriginalAnimationArchiveReader(sourceFrames).Parse();

    assert(rig.character==0);
    assert(rig.authoredPoses.size()==1);
    assert(rig.meshes.size()==2);
    assert(archive.frames.size()==1);
    assert(archive.totalBoneMatrices==2);

    const auto animated=BuildExactOriginalArticulatedFrame(
        rig,archive,0,15,123,
        OriginalMatrixMemoryLayout::ColumnMajorColumnVectors);
    assert(animated.character==0 && animated.action==15 &&
           animated.exactOriginalTick==123);
    assert(animated.limbs.size()==2);
    assert(animated.unmatchedSourceMeshes==0);
    assert(animated.limbs[0].sourceBonePointer==0x07000218);
    assert(animated.limbs[1].sourceBonePointer==0x07000230);
    const auto& first=animated.limbs[0].triangleVertices;
    const auto& second=animated.limbs[1].triangleVertices;
    assert(first.size()==3 && second.size()==3);
    assert(first[0].x==11.0f && first[0].y==20.0f &&
           first[0].z==30.0f);
    assert(first[1].x==10.0f && first[1].y==22.0f);
    assert(first[2].z==33.0f);
    assert(second[0].x==-9.0f && second[0].y==20.0f);
    assert(first[1].s==32 && first[1].rgba[1]==255);
    assert(second[2].t==32 && second[2].rgba[2]==255);

    bool missingFrame=false;
    try {
        (void)BuildExactOriginalArticulatedFrame(
            rig,archive,0,15,124,
            OriginalMatrixMemoryLayout::ColumnMajorColumnVectors);
    } catch(const std::invalid_argument&) { missingFrame=true; }
    assert(missingFrame);

    std::puts("Goemon original articulated E2E: Python source file -> C++ exact two-bone world geometry PASS");
}
