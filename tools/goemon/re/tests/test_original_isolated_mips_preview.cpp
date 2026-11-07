#include "soh/soh/Enhancements/Goemon/OriginalIsolatedMipsPreview.hpp"
#include <cassert>
#include <bit>
#include <cstdint>
#include <cstdio>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace Goemon::Original;

static void U8(std::vector<std::uint8_t>& b,unsigned n){
    b.push_back(static_cast<std::uint8_t>(n));}
static void U16(std::vector<std::uint8_t>& b,unsigned n){
    U8(b,n);U8(b,n>>8);}
static void U32(std::vector<std::uint8_t>& b,std::uint32_t n){
    U16(b,n);U16(b,n>>16);}
static void FloatBits(std::vector<std::uint8_t>& b,float f){
    U32(b,std::bit_cast<std::uint32_t>(f));}
static void Matrix(std::vector<std::uint8_t>& b,float tx){
    const float m[16]={1,0,0,tx,0,1,0,0,0,0,1,0,0,0,0,1};
    for(float v:m)FloatBits(b,v);
}
static void Bone(std::vector<std::uint8_t>& b,std::uint32_t node,
                 std::uint32_t gfx,int parent,unsigned mask,
                 const std::array<std::int16_t,9>& raw,float a,float c) {
    U32(b,node);U32(b,gfx);U16(b,static_cast<unsigned>(parent));U16(b,mask);
    for(auto v:raw)U16(b,static_cast<unsigned>(v));
    Matrix(b,a);Matrix(b,c);
}
static std::vector<std::uint8_t> Fixture(){
    std::vector<std::uint8_t> b{'G','O','M','I','P','S','0','1'};
    U32(b,3);U32(b,0x07000140);U32(b,2);U32(b,2);
    FloatBits(b,0.0f);FloatBits(b,1.0f);
    std::array<std::int16_t,9> a{},c{};
    a.fill(-20480);c.fill(0);c[0]=256;c[1]=256;c[2]=256;
    Bone(b,0x07000100,0,-1,3,a,0,0);
    Bone(b,0x07000118,0x29000100,0,3,c,10,20);
    return b;
}
static SourceRig Rig() {
    SourceRig rig{};
    rig.character=3;
    SourceRigLimbMesh mesh{};
    mesh.sourceGfxPointer=0x09000100;
    mesh.vertices={
        {1,0,0,0,0,0,{255,0,0,255}},
        {0,1,0,0,32,0,{0,255,0,255}},
        {0,0,1,0,0,32,{0,0,255,255}}
    };
    rig.meshes.push_back(mesh);
    SourceRigPose source{};
    source.originalHeader=0x07000140;
    SourceRigBonePose a{},b{};
    a.sourceGfxPointer=0;a.parent=-1;
    a.sourceTransforms.fill(-20480);
    b.sourceGfxPointer=0x29000100;b.parent=0;
    b.sourceTransforms={256,256,256,0,0,0,0,0,0};
    source.bones={a,b};
    rig.authoredPoses.push_back(source);
    return rig;
}
// Live native file check uses ONLY the original source-ROM archives on
// the owner's self-hosted Windows machine. No game code, ROM assets or
// individual matrix/vertex values are uploaded.
static std::vector<std::uint8_t> ReadOwnedAsset(
    const std::filesystem::path& path
) {
    std::ifstream f(path,std::ios::binary|std::ios::ate);
    if(!f) throw std::runtime_error("missing locally staged original rig/MIPS preview file");
    const auto size=f.tellg();
    if(size<=0 || size>24*1024*1024)
        throw std::runtime_error("invalid source file size on private runner");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
    f.seekg(0);
    if(!f.read(reinterpret_cast<char*>(bytes.data()),
               static_cast<std::streamsize>(bytes.size())))
        throw std::runtime_error("unable to read local original N64 source preview");
    return bytes;
}

static int CheckOwnerOriginalPreview(const std::filesystem::path& root) {
    const char* names[]={"Goemon","Ebisumaru","Sasuke","Yae"};
    int readyCharacters=0;
    for(std::size_t slot=0;slot<4;++slot) {
        const auto dir=root/names[slot];
        try {
            auto rigFile=ReadOwnedAsset(dir/"original.goskel");
            auto mipsFile=ReadOwnedAsset(dir/"isolated.gomips");
            const auto rig=SourceRigReader(rigFile).Parse();
            const auto source=IsolatedMipsSourceReader(mipsFile).Parse();
            if(rig.character!=slot || source.sourceCharacterSlot!=slot)
                throw std::runtime_error("original character slot mismatch");
            (void)ValidateIsolatedMipsRig(rig,source);
            bool ready=false;
            for(int mode=0;mode<2;++mode) {
                bool bothSamplesValid=true;
                for(unsigned sample=0;sample<2;++sample) {
                    try {
                        const auto layout=(mode==0
                            ? OriginalMatrixMemoryLayout::RowMajorColumnVectors
                            : OriginalMatrixMemoryLayout::ColumnMajorColumnVectors);
                        const auto frame=BuildIsolatedOriginalMipsPreview(
                            rig,source,sample,layout);
                        std::size_t vertices=0;
                        bool withinRange=true;
                        for(const auto& limb:frame.limbs) {
                            vertices+=limb.triangleVertices.size();
                            for(const auto& v:limb.triangleVertices)
                                if(!std::isfinite(v.x)||!std::isfinite(v.y)||
                                   !std::isfinite(v.z)||
                                   std::fabs(v.x)>32767.0f||
                                   std::fabs(v.y)>32767.0f||
                                   std::fabs(v.z)>32767.0f)
                                    withinRange=false;
                        }
                        const bool sampleReady=withinRange && vertices>0;
                        std::cout<<"GOEMON_NATIVE_SOURCE_RENDER "
                                 <<names[slot]<<" layout="<<mode
                                 <<" sample="<<sample
                                 <<" drawable_limbs="<<frame.limbs.size()
                                 <<" vertices="<<vertices
                                 <<" blocked="<<frame.blockedLimbMatrices
                                 <<" unresolved_geometry="<<frame.unresolvedOriginalMeshes
                                 <<" unknown_gfx_tag="<<frame.unknownGraphicsTags
                                 <<" vtx16_ready="<<(sampleReady?1:0)<<'\n';
                        bothSamplesValid=bothSamplesValid&&sampleReady;
                    } catch(const std::exception& ex) {
                        bothSamplesValid=false;
                        // The private original source matrices are never dumped.
                        std::cout<<"GOEMON_NATIVE_SOURCE_RENDER "
                                 <<names[slot]<<" layout="<<mode
                                 <<" sample="<<sample
                                 <<" ERROR="<<ex.what()<<'\n';
                    }
                }
                ready=ready||bothSamplesValid;
            }
            if(ready) ++readyCharacters;
        } catch(const std::exception& ex) {
            std::cout<<"GOEMON_NATIVE_SOURCE_RENDER "<<names[slot]
                     <<" ASSET_ERROR="<<ex.what()<<'\n';
        }
    }
    std::cout<<"GOEMON_NATIVE_SOURCE_RENDER_SUMMARY characters_ready="
             <<readyCharacters<<"/4\n";
    return readyCharacters==4?0:3;
}

int main(int argc,char** argv) {
    if(argc==2)
        return CheckOwnerOriginalPreview(argv[1]);
    if(argc!=1)
        return 2;
    const auto bytes=Fixture();
    const auto source=IsolatedMipsSourceReader(bytes).Parse();
    const auto rig=Rig();
    assert(source.sourceCharacterSlot==3);
    assert(source.originalAnimatedSkeletonHeader==0x07000140);
    assert(source.bones.size()==2);
    assert(!source.originalActionOrTickVerified);
    assert(!source.originalHierarchyAndMatrixConventionVerified);
    (void)ValidateIsolatedMipsRig(rig,source);
    const auto first=BuildIsolatedOriginalMipsPreview(
        rig,source,0,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    const auto next=BuildIsolatedOriginalMipsPreview(
        rig,source,1,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    assert(first.limbs.size()==1);
    assert(first.limbs[0].sourceBonePointer==0x07000118);
    assert(first.limbs[0].sourceGraphicsPointer==0x29000100);
    assert(first.limbs[0].triangleVertices.size()==3);
    assert(first.limbs[0].triangleVertices[0].x==11.0f);
    assert(next.limbs[0].triangleVertices[0].x==21.0f);
    assert(!first.verifiedOriginalGameFrame);
    bool bad=false;
    try {
        auto invalid=rig;
        invalid.authoredPoses[0].bones[1].sourceTransforms[0]=2;
        (void)ValidateIsolatedMipsRig(invalid,source);
    } catch(const std::invalid_argument&){bad=true;}
    assert(bad);
    bad=false;
    try {
        (void)BuildIsolatedOriginalMipsPreview(
            rig,source,2,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    } catch(const std::invalid_argument&){bad=true;}
    assert(bad);
    auto truncated=bytes;
    truncated.pop_back();
    bad=false;
    try {(void)IsolatedMipsSourceReader(truncated).Parse();}
    catch(const std::invalid_argument&){bad=true;}
    assert(bad);
    // The source skeleton node's unverified graphics tag is not remapped.
    // A missing frame remains unavailable, not silently filled with identity.
    auto missing=bytes;
    const std::size_t secondBone=32+30+2*64;
    missing[secondBone+10]=1; // second sample absent
    const std::size_t secondMatrix=secondBone+30+64;
    for(std::size_t i=0;i<64;++i)missing[secondMatrix+i]=0;
    const auto decoded=IsolatedMipsSourceReader(missing).Parse();
    const auto preview=BuildIsolatedOriginalMipsPreview(
        rig,decoded,0,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    assert(preview.limbs.size()==1);
    bad=false;
    try {
        (void)BuildIsolatedOriginalMipsPreview(
            rig,decoded,1,OriginalMatrixMemoryLayout::RowMajorColumnVectors);
    } catch(const std::invalid_argument&){bad=true;}
    assert(bad);
    std::puts("Original source-ROM isolated MIPS matrices + exact C++ N64 source geometry: PASS");
}
