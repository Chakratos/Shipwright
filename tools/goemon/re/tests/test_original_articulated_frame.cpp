#include "soh/soh/Enhancements/Goemon/OriginalArticulatedFrame.hpp"

#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <functional>
#include <stdexcept>

using namespace Goemon::Original;

static void ExpectInvalid(const std::function<void()>& call) {
    bool rejected=false;
    try { call(); }
    catch (const std::invalid_argument&) { rejected=true; }
    assert(rejected);
}

static SourceRig MakeRealGeometryFixture() {
    SourceRig rig{};
    rig.character=0;
    SourceRigLimbMesh rightArm{};
    rightArm.sourceGfxPointer=0x09000100;
    rightArm.vertices={
        {1,0,0,0,0,0,{255,0,0,255}},
        {0,1,0,0,32,0,{0,255,0,255}},
        {0,0,1,0,0,32,{0,0,255,255}}
    };
    SourceRigLimbMesh leftArm{};
    leftArm.sourceGfxPointer=0x09000200;
    leftArm.vertices={
        {1,0,0,0,0,0,{255,255,0,255}},
        {0,1,0,0,32,0,{255,255,0,255}},
        {0,0,1,0,0,32,{255,255,0,255}}
    };
    rig.meshes={rightArm,leftArm};
    return rig;
}

static OriginalCapturedPose MakeSourceMatrixFrame() {
    OriginalCapturedPose frame{};
    frame.sourceGameFrame=100;
    frame.characterId=0;
    frame.actionId=15;
    OriginalCapturedBone pivot{};
    pivot.originalPointer=0x07000020;  // no gfx in original pivot
    OriginalCapturedBone right{};
    right.originalPointer=0x07000038;
    right.sourceGfxPointer=0x09000100;
    // Column vectors, row-major matrix: rotate Z +90, then x=+10, y=+20
    right.engineMatrix={0,-1,0,10, 1,0,0,20, 0,0,1,30, 0,0,0,1};
    OriginalCapturedBone left{};
    left.originalPointer=0x07000050;
    left.sourceGfxPointer=0x09000200;
    left.engineMatrix={1,0,0,-10, 0,1,0,-20, 0,0,1,-30, 0,0,0,1};
    frame.bones={pivot,right,left};
    return frame;
}

int main() {
    const auto rig=MakeRealGeometryFixture();
    const auto pose=MakeSourceMatrixFrame();
    const auto result=BuildExactOriginalArticulatedFrame(
        rig,pose,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    assert(result.character==0 && result.action==15 &&
           result.exactOriginalTick==100);
    assert(result.limbs.size()==2);
    assert(result.unmatchedSourceMeshes==0);
    assert(result.limbs[0].sourceBonePointer==0x07000038);
    assert(result.limbs[0].triangleVertices.size()==3);
    assert(result.limbs[0].triangleVertices[0].x==10);
    assert(result.limbs[0].triangleVertices[0].y==21);
    assert(result.limbs[0].triangleVertices[0].z==30);
    assert(result.limbs[0].triangleVertices[1].x==9);
    assert(result.limbs[0].triangleVertices[1].y==20);
    assert(result.limbs[0].triangleVertices[0].rgba[0]==255);
    assert(result.limbs[0].triangleVertices[1].s==32);
    assert(result.limbs[1].triangleVertices[0].x==-9);
    assert(result.limbs[1].triangleVertices[0].y==-20);

    // Same exact physical transform, in other memory convention.
    auto col=pose;
    for (auto& bone : col.bones) {
        const auto old=bone.engineMatrix;
        for(int y=0;y<4;++y)for(int x=0;x<4;++x)
            bone.engineMatrix[x*4+y]=old[y*4+x];
    }
    const auto colResult=BuildExactOriginalArticulatedFrame(
        rig,col,OriginalMatrixMemoryLayout::ColumnMajorColumnVectors);
    assert(colResult.limbs[0].triangleVertices[0].x==10);
    assert(colResult.limbs[0].triangleVertices[0].y==21);
    assert(colResult.limbs[0].triangleVertices[0].z==30);

    // Explicit source tick/action: no fallback to generic idle or Link.
    OriginalCapturedAnimation archive{};
    archive.frames.push_back(pose);
    assert(BuildExactOriginalArticulatedFrame(
        rig,archive,0,15,100,
        OriginalMatrixMemoryLayout::RowMajorColumnVectors).limbs.size()==2);
    ExpectInvalid([&]{
        (void)BuildExactOriginalArticulatedFrame(
            rig,archive,0,23,100,
            OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    });
    ExpectInvalid([&]{
        (void)BuildExactOriginalArticulatedFrame(
            rig,archive,0,15,101,
            OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    });

    auto wrongCharacter=rig;
    wrongCharacter.character=2;
    ExpectInvalid([&]{
        (void)BuildExactOriginalArticulatedFrame(
            wrongCharacter,pose,
            OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    });

    auto missing=rig;
    missing.meshes.pop_back();
    ExpectInvalid([&]{
        (void)BuildExactOriginalArticulatedFrame(
            missing,pose,
            OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    });
    const auto partial=BuildExactOriginalArticulatedFrame(
        missing,pose,
        OriginalMatrixMemoryLayout::RowMajorColumnVectors,false);
    assert(partial.limbs.size()==1 && partial.unmatchedSourceMeshes==1);

    auto nanPose=pose;
    nanPose.bones[1].engineMatrix[3]=NAN;
    ExpectInvalid([&]{
        (void)BuildExactOriginalArticulatedFrame(
            rig,nanPose,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    });
    auto badW=pose;
    badW.bones[1].engineMatrix[15]=0;
    ExpectInvalid([&]{
        (void)BuildExactOriginalArticulatedFrame(
            rig,badW,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    });

    std::puts("Original articulated source frame: exact game matrices, 2 limb meshes PASS");
}
