#include "soh/soh/Enhancements/Goemon/OriginalSourceRig.hpp"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <vector>

using namespace Goemon::Original;

void Put8(std::vector<std::uint8_t>& b,unsigned x){b.push_back(static_cast<std::uint8_t>(x));}
void Put16(std::vector<std::uint8_t>& b,unsigned x){Put8(b,x);Put8(b,x>>8);}
void Put32(std::vector<std::uint8_t>& b,std::uint32_t x){Put16(b,x);Put16(b,x>>16);}
void PutBE16(std::vector<std::uint8_t>& b,unsigned x){Put8(b,x>>8);Put8(b,x);}
void PutVertex(std::vector<std::uint8_t>& b,int x,int y,int z){
    PutBE16(b,static_cast<unsigned>(x));PutBE16(b,static_cast<unsigned>(y));
    PutBE16(b,static_cast<unsigned>(z));PutBE16(b,0);
    PutBE16(b,32);PutBE16(b,64);
    Put8(b,255);Put8(b,192);Put8(b,32);Put8(b,255);
}
void PutBone(std::vector<std::uint8_t>& b,std::uint32_t gfx,int parent,int yaw) {
    Put32(b,gfx);
    Put16(b,static_cast<unsigned>(parent));
    for (int i=0;i<9;++i)Put16(b,i==4?yaw:(i<3?256:0));
}
void PutPose(std::vector<std::uint8_t>& b,std::uint32_t header,int yaw) {
    Put32(b,header);Put32(b,0x80000111);Put32(b,2);
    PutBone(b,0,-1,0);
    PutBone(b,0x09000020,0,yaw);
}
std::vector<std::uint8_t> Fixture(){
    std::vector<std::uint8_t> b{'G','O','S','K','E','L','0','1'};
    Put32(b,0);Put32(b,1);Put32(b,3);
    Put32(b,0x09000020);Put32(b,1);
    PutVertex(b,3,4,5);PutVertex(b,13,14,15);PutVertex(b,23,24,25);
    PutPose(b,0x0700063C,0);
    PutPose(b,0x07000CB8,128);
    PutPose(b,0x07001294,256);
    return b;
}
void Reject(const std::vector<std::uint8_t>& bytes){
    bool caught=false;
    try{(void)SourceRigReader(bytes).Parse();}
    catch(const std::invalid_argument&){caught=true;}
    assert(caught);
}
int main(){
    auto data=Fixture();
    auto rig=SourceRigReader(data).Parse();
    assert(rig.character==0);
    assert(rig.meshes.size()==1);
    assert(rig.authoredPoses.size()==3);
    assert(rig.meshes[0].sourceGfxPointer==0x09000020);
    assert(rig.meshes[0].vertices.size()==3);
    assert(rig.meshes[0].vertices[0].x==3);
    assert(rig.meshes[0].vertices[1].y==14);
    assert(rig.meshes[0].vertices[2].z==25);
    assert(rig.meshes[0].vertices[0].originalRGBA[0]==255);
    assert(rig.authoredPoses[0].bones.size()==2);
    assert(rig.authoredPoses[0].bones[0].parent==-1);
    assert(rig.authoredPoses[1].bones[1].sourceTransforms[4]==128);
    const auto initialGroups=GroupOriginalSourceRigLayouts(rig);
    assert(initialGroups.size()==1);
    assert(initialGroups[0].descriptorIndices.size()==3);
    assert(FindExactOriginalSourceDescriptor(rig,0x07000CB8)
           ==&rig.authoredPoses[1]);
    assert(FindExactOriginalSourceDescriptor(rig,0x07000000)==nullptr);
    // Original descriptor addresses are not timeline frames. The reader
    // does NOT provide fake pose-rate, interpolation or tick loops.
    rig.authoredPoses[2].bones[1].sourceGfxPointer=0x09000050;
    const auto updatedGroups=GroupOriginalSourceRigLayouts(rig);
    assert(updatedGroups.size()==2);
    assert(updatedGroups[0].descriptorIndices.size()==2);
    assert(updatedGroups[1].descriptorIndices.size()==1);
    assert(!HaveMatchingSourceRigLayout(rig.authoredPoses[1],rig.authoredPoses[2]));

    // Yae preserves raw 0x29 source Gfx tags and unresolved 0x0F words.
    // A normalized 0x09 pointer is only used when matching decoded meshes.
    assert(IsOriginalSourceRawGfxWord(0x29000020));
    assert(IsOriginalSourceRawGfxWord(0x0F000120));
    assert(!IsOriginalSourceRawGfxWord(0x30000020));
    assert(OriginalSourceNormalizedGfxWord(0x29000020)==0x09000020);
    assert(OriginalSourceNormalizedGfxWord(0x0F000120)==0x0F000120);
    auto yae=data;
    // GOSKEL01 character slot at byte 8, first authored pose starts after
    // 20-byte header + 8-byte mesh header + 3 16-byte N64 vertices.
    yae[8]=3;
    const std::size_t poseStart=20+8+3*16;
    const std::size_t firstBone=poseStart+12;
    const std::size_t nextBone=firstBone+24;
    yae[firstBone]=0x20;yae[firstBone+1]=0x01;
    yae[firstBone+2]=0x00;yae[firstBone+3]=0x0F;
    yae[nextBone]=0x20;yae[nextBone+1]=0x00;
    yae[nextBone+2]=0x00;yae[nextBone+3]=0x29;
    auto yaeRig=SourceRigReader(yae).Parse();
    assert(yaeRig.character==3);
    assert(yaeRig.authoredPoses[0].bones[0].sourceGfxPointer==0x0F000120);
    assert(yaeRig.authoredPoses[0].bones[1].sourceGfxPointer==0x29000020);

    auto bad=data;bad[0]='X';Reject(bad);
    bad=data;bad.resize(bad.size()-10);Reject(bad);
    bad=data;bad.push_back(0);Reject(bad);
    bad=data;bad[12]=0;bad[13]=0;bad[14]=0;bad[15]=0;Reject(bad);
    bad=data;bad[20]=0;bad[21]=0;bad[22]=0;bad[23]=0;Reject(bad);
    std::puts("OriginalSourceRig: authentic limb mesh, hierarchy and authored poses PASS");
}
