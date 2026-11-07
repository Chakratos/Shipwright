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
    auto series=LongestAuthoredPoseSeries(rig);
    assert(series.begin==0 && series.count==3);
    assert(PreviewOriginalAuthoredPose(rig,series,0)==&rig.authoredPoses[0]);
    assert(PreviewOriginalAuthoredPose(rig,series,3)==&rig.authoredPoses[1]);
    assert(PreviewOriginalAuthoredPose(rig,series,6)==&rig.authoredPoses[2]);
    assert(PreviewOriginalAuthoredPose(rig,series,9)==&rig.authoredPoses[0]);
    assert(PreviewOriginalAuthoredPose(rig,series,0,0)==nullptr);

    rig.authoredPoses[2].bones[1].sourceGfxPointer=0x09000050;
    series=LongestAuthoredPoseSeries(rig);
    assert(series.begin==0 && series.count==2);
    assert(!HaveMatchingSourceRigLayout(rig.authoredPoses[1],rig.authoredPoses[2]));

    auto bad=data;bad[0]='X';Reject(bad);
    bad=data;bad.resize(bad.size()-10);Reject(bad);
    bad=data;bad.push_back(0);Reject(bad);
    bad=data;bad[12]=0;bad[13]=0;bad[14]=0;bad[15]=0;Reject(bad);
    bad=data;bad[20]=0;bad[21]=0;bad[22]=0;bad[23]=0;Reject(bad);
    std::puts("OriginalSourceRig: authentic limb mesh, hierarchy and authored poses PASS");
}
