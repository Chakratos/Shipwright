#include "soh/soh/Enhancements/Goemon/OriginalAnimationStreams.hpp"
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <vector>
using namespace Goemon::Original;
void Push8(std::vector<std::uint8_t>& b,unsigned n){b.push_back(static_cast<std::uint8_t>(n));}
void Push16(std::vector<std::uint8_t>& b,unsigned n){Push8(b,n);Push8(b,n>>8);}
void Push32(std::vector<std::uint8_t>& b,std::uint32_t n){Push16(b,n);Push16(b,n>>16);}
std::vector<std::uint8_t> Fixture(){
    std::vector<std::uint8_t> b{'G','O','A','N','I','M','0','1'};
    Push32(b,0);Push32(b,1);
    Push32(b,0x07000140); // source AnimatedSkeleton header
    Push32(b,0x80000111); // source flags
    Push32(b,0x07000000); // animation bank start
    Push32(b,0x07000100); // source Skeleton root
    Push32(b,256);Push32(b,2);
    for(unsigned i=0;i<256;++i)Push8(b,(i*19+7)&255);
    Push32(b,0x07000100);Push32(b,0);Push16(b,0xffff);
    for(int i=0;i<9;++i)Push16(b,i<3?0xb100:0xb000);
    Push32(b,0x07000118);Push32(b,0x09000020);Push16(b,0);
    for(int i=0;i<9;++i)Push16(b,i<3?0xb100:
                              static_cast<unsigned>(80+(i-3)*23));
    return b;
}
void Reject(const std::vector<std::uint8_t>& bytes){
    bool failed=false;
    try{(void)SourceAnimationStreamReader(bytes).Parse();}
    catch(const std::invalid_argument&){failed=true;}
    assert(failed);
}
int main(){
    auto blob=Fixture();
    auto archive=SourceAnimationStreamReader(blob).Parse();
    assert(archive.characterId==0);
    assert(archive.candidates.size()==1);
    const auto& first=archive.candidates[0];
    assert(first.originalFlags==0x80000111);
    assert(first.sourceAnimationPtr==0x07000000);
    assert(first.sourceHeader==0x07000140);
    assert(first.originalCompressedBytes.size()==256);
    assert(first.originalCompressedBytes[0]==7);
    assert(first.originalCompressedBytes[1]==26);
    assert(first.limbs.size()==2);
    assert(first.limbs[0].parent==-1);
    assert(first.limbs[1].parent==0);
    assert(first.limbs[1].encodedChannels[3]==80);
    assert(first.limbs[1].encodedChannels[4]==103);
    assert(ClassifyOriginalEncodedChannel(-20224)==SourceChannelKind::MarkerB100);
    assert(ClassifyOriginalEncodedChannel(-20480)==SourceChannelKind::MarkerB000);
    assert(ClassifyOriginalEncodedChannel(80)==SourceChannelKind::NumericOffset);
    assert(ClassifyOriginalEncodedChannel(-1000)==SourceChannelKind::OtherNegative);
    const auto profile=ProfileOriginalEncodedChannels(first);
    assert(profile.markerB000==6);
    assert(profile.markerB100==6);
    assert(profile.numericOffsets==6);
    assert(profile.numericOffsetsInBounds==6);
    assert(profile.otherNegative==0);
    const auto tail=OriginalChannelTail(first,80);
    assert(tail.size()==176);
    assert(tail[0]==first.originalCompressedBytes[80]);
    assert(OriginalChannelTail(first,-20224).empty());
    assert(OriginalChannelTail(first,1024).empty());

    auto yae=blob;yae[8]=3;
    auto archiveYae=SourceAnimationStreamReader(yae).Parse();
    assert(archiveYae.characterId==3);
    assert(archiveYae.candidates[0].originalCompressedBytes.size()==256);
    auto invalid=blob;invalid[0]='X';Reject(invalid);
    invalid=blob;invalid.resize(invalid.size()-4);Reject(invalid);
    invalid=blob;invalid.push_back(0);Reject(invalid);
    invalid=blob;invalid[12]=0;invalid[13]=0;
    invalid[14]=0;invalid[15]=0;Reject(invalid);
    std::puts("OriginalAnimationStreams: source raw samples / tagged channels PASS");
}
