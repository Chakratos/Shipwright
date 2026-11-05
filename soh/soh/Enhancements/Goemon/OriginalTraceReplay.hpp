#pragma once
// Numeric-only original GOEMON_TASK desired vector replay.
// The parser imports no original ROM bytes, models or executable code.
// It is a diagnostic input for applying observed original movement
// against Ship Zelda collision *in a separate, non-player ghost state*.
// It is NOT a Goemon control dispatcher or a playable replacement for Link.
#include "OriginalHorizontal.hpp"
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <istream>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace Goemon::Original {

struct OriginalRecordedMovement {
    std::uint32_t sample = 0;
    std::uint32_t gameFrame = 0;
    std::uint8_t characterId = 0;
    std::uint16_t actionId = 0;
    std::uint16_t targetYaw10 = 0;
    OriginalPlanarStep originalDesired{0.0f, 0.0f};
    bool continuousOriginalUpdate = false;
};

class OriginalMotionReplay {
public:
    static constexpr std::size_t kMaxFrames = 12000;
    static constexpr const char* kHeader =
        "sample,game_frames,character_id,action_id,original_yaw10,"
        "desired_dx,desired_dz,continuous_original_update";

    explicit OriginalMotionReplay(std::istream& stream) {
        std::string header;
        if (!std::getline(stream, header) || header != kHeader)
            throw std::invalid_argument("unexpected original replay CSV header");
        std::string line;
        while (std::getline(stream, line)) {
            if (line.empty()) continue;
            if (frames_.size() >= kMaxFrames)
                throw std::invalid_argument("original replay frame cap exceeded");
            auto values = SplitRow(line);
            OriginalRecordedMovement frame{};
            frame.sample = Number<std::uint32_t>(values[0]);
            frame.gameFrame = Number<std::uint32_t>(values[1]);
            const unsigned ch = Number<unsigned>(values[2]);
            const unsigned action = Number<unsigned>(values[3]);
            const unsigned yaw = Number<unsigned>(values[4]);
            frame.originalDesired.x = Number<float>(values[5]);
            frame.originalDesired.z = Number<float>(values[6]);
            const int continuous = Number<int>(values[7]);
            if (ch > 3 || action > 65535 || yaw > 1023 ||
                (continuous != 0 && continuous != 1))
                throw std::invalid_argument("invalid original replay identifier/flag");
            const float speed = std::hypot(
                frame.originalDesired.x, frame.originalDesired.z);
            if (!std::isfinite(speed) || speed > kOriginalFullRunSpeed + 0.003f)
                throw std::invalid_argument("invalid original replay velocity");
            frame.characterId = static_cast<std::uint8_t>(ch);
            frame.actionId = static_cast<std::uint16_t>(action);
            frame.targetYaw10 = static_cast<std::uint16_t>(yaw);
            frame.continuousOriginalUpdate = continuous != 0;
            if (frame.sample != frames_.size())
                throw std::invalid_argument("nonconsecutive original replay sample");
            bool isContinuous = false;
            if (!frames_.empty()) {
                const auto& prev = frames_.back();
                isContinuous = (
                    frame.gameFrame > prev.gameFrame &&
                    frame.gameFrame - prev.gameFrame == 1 &&
                    frame.characterId == prev.characterId
                );
            }
            if (isContinuous != frame.continuousOriginalUpdate)
                throw std::invalid_argument("incorrect original replay discontinuity");
            frames_.push_back(frame);
        }
        if (frames_.empty())
            throw std::invalid_argument("empty original movement replay");
    }

    [[nodiscard]] bool Next(OriginalRecordedMovement& output) {
        if (position_ >= frames_.size()) return false;
        output = frames_[position_++];
        return true;
    }
    void Reset() noexcept { position_ = 0; }
    [[nodiscard]] std::size_t Size() const noexcept { return frames_.size(); }
    [[nodiscard]] std::size_t Cursor() const noexcept { return position_; }

private:
    template<typename T>
    [[nodiscard]] static T Number(const std::string& value) {
        std::istringstream stream(value);
        stream.imbue(std::locale::classic());
        T output{};
        if (!(stream >> output))
            throw std::invalid_argument("non-numeric original movement field");
        stream >> std::ws;
        if (!stream.eof())
            throw std::invalid_argument("trailing characters in replay field");
        return output;
    }

    [[nodiscard]] static std::array<std::string, 8> SplitRow(
        const std::string& line) {
        std::array<std::string, 8> values{};
        std::istringstream stream(line);
        for (std::size_t i = 0; i < values.size(); ++i) {
            if (!std::getline(stream, values[i], ',') || values[i].empty())
                throw std::invalid_argument("malformed original replay CSV row");
        }
        std::string excess;
        if (std::getline(stream, excess, ','))
            throw std::invalid_argument("unexpected extra replay CSV column");
        return values;
    }

    std::vector<OriginalRecordedMovement> frames_;
    std::size_t position_ = 0;
};

} // namespace Goemon::Original
