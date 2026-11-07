#pragma once
// Native reader for source-ROM MIPS-evaluated, ISOLATED Skeleton transforms.
//
// GOMIPS01 is deliberately NOT GOPA0001. It has no authentic action ID,
// gameplay tick, hierarchical matrix stack or verified N64 matrix layout.
// Samples correspond to original animation_progress = 0 and 1 with a
// controlled identity parent; raw CPU matrix bits were obtained by executing
// original ROM MIPS instructions. The asset lives only on the owner's PC.
//
// The consumer refuses mismatching GOSKEL01 rigs, unknown source S/R/T
// selectors, malformed matrices and attempts to claim sample chronology.
#include "OriginalArticulatedFrame.hpp"

#include <array>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <utility>
#include <vector>

namespace Goemon::Original {

struct IsolatedMipsBone {
    std::uint32_t originalPointer=0;
    std::uint32_t originalGraphicsPointer=0;
    std::int16_t sourceParent=-1;
    std::array<std::int16_t,9> originalEncodedChannels{};
    std::array<bool,2> available{};
    std::array<std::array<float,16>,2> sourceMipsMatrix{};
};

struct IsolatedMipsSourceArchive {
    std::uint32_t sourceCharacterSlot=0;
    std::uint32_t originalAnimatedSkeletonHeader=0;
    std::array<float,2> controlledProgress{};
    std::vector<IsolatedMipsBone> bones;
    // Sample progress is not the original game's clock or action identity.
    bool originalActionOrTickVerified=false;
    bool originalHierarchyAndMatrixConventionVerified=false;
};

class IsolatedMipsSourceReader {
  public:
    explicit IsolatedMipsSourceReader(std::span<const std::uint8_t> bytes)
        : bytes_(bytes) {}
    [[nodiscard]] IsolatedMipsSourceArchive Parse() {
        constexpr std::array<std::uint8_t,8> magic{
            'G','O','M','I','P','S','0','1'};
        if (bytes_.size()<32 || bytes_.size()>1024*1024)
            throw std::invalid_argument("invalid source MIPS package size");
        for (auto byte:magic) {
            if (Read8()!=byte)
                throw std::invalid_argument("invalid original source MIPS signature");
        }
        IsolatedMipsSourceArchive result{};
        result.sourceCharacterSlot=Read32();
        result.originalAnimatedSkeletonHeader=Read32();
        const auto count=Read32();
        const auto samples=Read32();
        for(auto& progress:result.controlledProgress)
            progress=std::bit_cast<float>(Read32());
        if (result.sourceCharacterSlot>3 ||
            result.originalAnimatedSkeletonHeader>>24!=7 ||
            !count || count>128 || samples!=2 ||
            result.controlledProgress[0]!=0.0f ||
            result.controlledProgress[1]!=1.0f ||
            bytes_.size()!=32+static_cast<std::size_t>(count)*(30+2*16*4))
            throw std::invalid_argument("inconsistent isolated original MIPS asset");
        result.bones.reserve(count);
        for(std::uint32_t i=0;i<count;++i) {
            IsolatedMipsBone bone{};
            bone.originalPointer=Read32();
            bone.originalGraphicsPointer=Read32();
            bone.sourceParent=static_cast<std::int16_t>(Read16());
            const auto validBits=Read16();
            if (bone.originalPointer>>24!=7 ||
                bone.sourceParent<-1 ||
                bone.sourceParent>=static_cast<std::int16_t>(i) ||
                (validBits&~3U)!=0 ||
                !IsOriginalSourceRawGfxWord(bone.originalGraphicsPointer))
                throw std::invalid_argument("invalid original MIPS source limb metadata");
            for (const auto& previous:result.bones) {
                if (previous.originalPointer==bone.originalPointer)
                    throw std::invalid_argument("duplicate original source MIPS limb");
            }
            for (auto& channel:bone.originalEncodedChannels)
                channel=static_cast<std::int16_t>(Read16());
            for (unsigned sample=0;sample<2;++sample) {
                bone.available[sample]=(validBits & (1U<<sample))!=0;
                for(auto& cell:bone.sourceMipsMatrix[sample]) {
                    const auto bits=Read32();
                    if (!bone.available[sample]) {
                        if (bits!=0)
                            throw std::invalid_argument(
                                "missing original MIPS sample has nonzero fake matrix");
                        cell=0.0f;
                        continue;
                    }
                    cell=std::bit_cast<float>(bits);
                    if (!std::isfinite(cell) || std::fabs(cell)>1.0e8f)
                        throw std::invalid_argument(
                            "invalid original MIPS source matrix value");
                }
            }
            result.bones.push_back(std::move(bone));
        }
        if(pos_!=bytes_.size())
            throw std::invalid_argument("trailing original source MIPS bytes");
        return result;
    }
  private:
    std::span<const std::uint8_t> bytes_;
    std::size_t pos_=0;
    [[nodiscard]] std::uint8_t Read8(){
        if(pos_>=bytes_.size())
            throw std::invalid_argument("truncated original source MIPS archive");
        return bytes_[pos_++];
    }
    [[nodiscard]] std::uint16_t Read16(){
        const std::uint16_t a=Read8(),b=Read8();
        return static_cast<std::uint16_t>(a|(b<<8));
    }
    [[nodiscard]] std::uint32_t Read32(){
        const std::uint32_t lo=Read16(),hi=Read16();
        return lo|(hi<<16);
    }
};

[[nodiscard]] inline const SourceRigPose& ValidateIsolatedMipsRig(
    const SourceRig& rig,const IsolatedMipsSourceArchive& samples
) {
    if(rig.character!=samples.sourceCharacterSlot)
        throw std::invalid_argument("source character/rigger mismatch");
    const auto* pose=FindExactOriginalSourceDescriptor(
        rig,samples.originalAnimatedSkeletonHeader);
    if(!pose || pose->bones.size()!=samples.bones.size())
        throw std::invalid_argument("source MIPS matrices do not belong to this original rig");
    for(std::size_t i=0;i<samples.bones.size();++i) {
        const auto& fromRom=pose->bones[i];
        const auto& fromCPU=samples.bones[i];
        if(fromRom.sourceGfxPointer!=fromCPU.originalGraphicsPointer ||
           fromRom.parent!=fromCPU.sourceParent ||
           fromRom.sourceTransforms!=fromCPU.originalEncodedChannels)
            throw std::invalid_argument(
                "original ROM rig and native MIPS matrix sources disagree");
    }
    return *pose;
}

struct IsolatedOriginalMipsPreview {
    std::uint32_t sourceCharacter=0;
    float controlledSourceProgress=0.0f;
    std::vector<OriginalDrawLimb> limbs;
    std::size_t blockedLimbMatrices=0;
    std::size_t unknownGraphicsTags=0;
    std::size_t unresolvedOriginalMeshes=0;
    // Never promote these samples into gameplay frames implicitly.
    bool verifiedOriginalGameFrame=false;
};

[[nodiscard]] inline IsolatedOriginalMipsPreview BuildIsolatedOriginalMipsPreview(
    const SourceRig& rig,
    const IsolatedMipsSourceArchive& samples,
    unsigned sampleIndex,
    OriginalMatrixMemoryLayout explicitUnverifiedLayout
) {
    if(sampleIndex>=2)
        throw std::invalid_argument("only recorded source MIPS sample indices 0/1 exist");
    (void)ValidateIsolatedMipsRig(rig,samples);
    IsolatedOriginalMipsPreview frame{};
    frame.sourceCharacter=rig.character;
    frame.controlledSourceProgress=samples.controlledProgress[sampleIndex];
    std::size_t triangles=0;
    for(const auto& bone:samples.bones) {
        if(!bone.available[sampleIndex]) {
            ++frame.blockedLimbMatrices;
            continue;
        }
        if(!bone.originalGraphicsPointer)
            continue;
        const auto normalized=OriginalSourceNormalizedGfxWord(
            bone.originalGraphicsPointer);
        if(normalized>>24!=9) {
            ++frame.unknownGraphicsTags;
            continue;
        }
        const SourceRigLimbMesh* mesh=nullptr;
        for(const auto& candidate:rig.meshes) {
            if(candidate.sourceGfxPointer==normalized) {
                if(mesh)
                    throw std::invalid_argument("duplicate original source preview mesh");
                mesh=&candidate;
            }
        }
        if(!mesh) {
            ++frame.unresolvedOriginalMeshes;
            continue;
        }
        if(mesh->vertices.empty() || mesh->vertices.size()%3)
            throw std::invalid_argument("invalid original N64 source triangle batch");
        triangles+=mesh->vertices.size()/3;
        if(triangles>300000)
            throw std::invalid_argument("excessive original MIPS preview triangles");
        OriginalDrawLimb draw{};
        draw.sourceBonePointer=bone.originalPointer;
        draw.sourceGraphicsPointer=bone.originalGraphicsPointer;
        draw.triangleVertices.reserve(mesh->vertices.size());
        for(const auto& vertex:mesh->vertices) {
            const auto transformed=ApplyOriginalCapturedMatrix(
                bone.sourceMipsMatrix[sampleIndex],explicitUnverifiedLayout,
                static_cast<float>(vertex.x),static_cast<float>(vertex.y),
                static_cast<float>(vertex.z));
            draw.triangleVertices.push_back({
                transformed[0],transformed[1],transformed[2],
                vertex.s,vertex.t,vertex.originalRGBA
            });
        }
        frame.limbs.push_back(std::move(draw));
    }
    if(frame.limbs.empty())
        throw std::invalid_argument("isolated source MIPS preview has no drawable parts");
    return frame;
}

} // namespace Goemon::Original
