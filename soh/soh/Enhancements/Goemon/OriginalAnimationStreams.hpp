#pragma once
// GOANIM01 reader: immutable compressed Skeleton animation streams taken
// DIRECTLY from the user's original NG5E ROM. The body-part descriptors
// are 16-bit CHANNEL SELECTORS, not decoded Euler angles or scales.
// In particular 0xB000 and 0xB100 are opaque animation encoding markers.
// No motion is generated or guessed until the MIPS decoder is ported.
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <stdexcept>
#include <utility>
#include <vector>

namespace Goemon::Original {

struct SourceChannelBone {
    std::uint32_t originalLimbPointer=0;
    std::uint32_t graphicsPointer=0;
    std::int16_t parent=-1;
    std::array<std::int16_t,9> encodedChannels{};
};

struct SourceAnimationDescriptor {
    std::uint32_t sourceHeader=0;
    std::uint32_t originalFlags=0;
    std::uint32_t sourceAnimationPtr=0;
    std::uint32_t sourceSkeletonRoot=0;
    std::vector<std::uint8_t> originalCompressedBytes;
    std::vector<SourceChannelBone> limbs;
};

struct SourceAnimationStreamArchive {
    std::uint32_t characterId=0;
    std::vector<SourceAnimationDescriptor> candidates;
};

class SourceAnimationStreamReader {
  public:
    explicit SourceAnimationStreamReader(std::span<const std::uint8_t> bytes)
        : bytes_(bytes) {}
    [[nodiscard]] SourceAnimationStreamArchive Parse() {
        if (bytes_.size() < 16 || bytes_.size() > 48*1024*1024)
            throw std::invalid_argument("original N64 animation file size invalid");
        constexpr std::array<std::uint8_t,8> signature{
            'G','O','A','N','I','M','0','1'
        };
        for (auto value : signature) {
            if (Read8()!=value)
                throw std::invalid_argument("not genuine source animation stream format");
        }
        SourceAnimationStreamArchive archive{};
        archive.characterId=Read32LE();
        const std::uint32_t count=Read32LE();
        if (archive.characterId>2 || !count || count>512)
            throw std::invalid_argument("source animation descriptor count invalid");
        archive.candidates.reserve(count);
        for (std::uint32_t i=0;i<count;++i) {
            SourceAnimationDescriptor item{};
            item.sourceHeader=Read32LE();
            item.originalFlags=Read32LE();
            item.sourceAnimationPtr=Read32LE();
            item.sourceSkeletonRoot=Read32LE();
            const auto streamLength=Read32LE();
            const auto limbCount=Read32LE();
            if (item.sourceHeader>>24!=7 ||
                item.sourceAnimationPtr>>24!=7 ||
                item.sourceSkeletonRoot>>24!=7 ||
                streamLength>1024*1024 ||
                !limbCount || limbCount>128)
                throw std::invalid_argument("source MNSG animation pointer/count invalid");
            if (streamLength>bytes_.size()-pos_ ||
                limbCount>(bytes_.size()-pos_-streamLength)/28)
                throw std::invalid_argument("source N64 animation stream truncated");
            item.originalCompressedBytes.reserve(streamLength);
            for (std::uint32_t j=0;j<streamLength;++j)
                item.originalCompressedBytes.push_back(Read8());
            item.limbs.reserve(limbCount);
            for (std::uint32_t j=0;j<limbCount;++j) {
                SourceChannelBone limb{};
                limb.originalLimbPointer=Read32LE();
                limb.graphicsPointer=Read32LE();
                limb.parent=static_cast<std::int16_t>(Read16LE());
                for (auto& channel : limb.encodedChannels)
                    channel=static_cast<std::int16_t>(Read16LE());
                if (limb.originalLimbPointer>>24!=7 ||
                    limb.parent<-1 || limb.parent>=static_cast<std::int16_t>(j))
                    throw std::invalid_argument("invalid N64 source limb channel hierarchy");
                item.limbs.push_back(limb);
            }
            archive.candidates.push_back(std::move(item));
        }
        if (pos_!=bytes_.size())
            throw std::invalid_argument("trailing original animation payload");
        return archive;
    }
  private:
    std::span<const std::uint8_t> bytes_;
    std::size_t pos_=0;
    [[nodiscard]] std::uint8_t Read8() {
        if(pos_>=bytes_.size())
            throw std::invalid_argument("truncated N64 source animation field");
        return bytes_[pos_++];
    }
    [[nodiscard]] std::uint16_t Read16LE() {
        const auto a=Read8();
        const auto b=Read8();
        return static_cast<std::uint16_t>(
            static_cast<unsigned>(a)|(static_cast<unsigned>(b)<<8));
    }
    [[nodiscard]] std::uint32_t Read32LE() {
        const std::uint32_t a=Read16LE();
        const std::uint32_t b=Read16LE();
        return a|(b<<16);
    }
};

enum class SourceChannelKind : std::uint8_t {
    MarkerB000, MarkerB100, NumericOffset, OtherNegative
};

[[nodiscard]] inline SourceChannelKind ClassifyOriginalEncodedChannel(
    std::int16_t encoded
) {
    const auto bits=static_cast<std::uint16_t>(encoded);
    if ((bits & 0xFF00)==0xB000) return SourceChannelKind::MarkerB000;
    if ((bits & 0xFF00)==0xB100) return SourceChannelKind::MarkerB100;
    return encoded>=0 ? SourceChannelKind::NumericOffset :
                        SourceChannelKind::OtherNegative;
}

struct SourceChannelProfile {
    std::uint32_t markerB000=0;
    std::uint32_t markerB100=0;
    std::uint32_t numericOffsets=0;
    std::uint32_t numericOffsetsInBounds=0;
    std::uint32_t otherNegative=0;
};

[[nodiscard]] inline SourceChannelProfile ProfileOriginalEncodedChannels(
    const SourceAnimationDescriptor& source
) {
    SourceChannelProfile profile{};
    for (const auto& bone : source.limbs) {
        for (const auto raw : bone.encodedChannels) {
            switch(ClassifyOriginalEncodedChannel(raw)) {
                case SourceChannelKind::MarkerB000: ++profile.markerB000; break;
                case SourceChannelKind::MarkerB100: ++profile.markerB100; break;
                case SourceChannelKind::NumericOffset:
                    ++profile.numericOffsets;
                    if (static_cast<std::size_t>(raw)<
                        source.originalCompressedBytes.size())
                        ++profile.numericOffsetsInBounds;
                    break;
                case SourceChannelKind::OtherNegative:
                    ++profile.otherNegative; break;
            }
        }
    }
    return profile;
}

// Encoded channel bytes are safe to inspect but are NOT converted to
// physical rotations until func_800192D0_19ED0's MIPS logic is reconstructed.
// The type system deliberately does not expose "EvaluateAsRotation".
[[nodiscard]] inline std::span<const std::uint8_t> OriginalChannelTail(
    const SourceAnimationDescriptor& source, std::int16_t raw
) {
    if (ClassifyOriginalEncodedChannel(raw)!=SourceChannelKind::NumericOffset ||
        static_cast<std::size_t>(raw)>=source.originalCompressedBytes.size())
        return {};
    return std::span<const std::uint8_t>(
        source.originalCompressedBytes.data()+raw,
        source.originalCompressedBytes.size()-static_cast<std::size_t>(raw));
}

} // namespace Goemon::Original
