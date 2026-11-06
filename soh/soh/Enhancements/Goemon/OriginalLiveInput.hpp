#pragma once
// Experimental SHIP INPUT ADAPTER, not recovered Goemon camera/input logic.
// Normalizes full-tilt Ship stick input for the verified original
// action-gated vector core. Only FULL/NONE are accepted. Intermediate
// analog values are explicitly UNSUPPORTED until observed in original NG5E.
// Zelda camera yaw is a temporary target-yaw source; never call it
// source-authentic Goemon camera/turning behavior.
#include "OriginalVectorController.hpp"

#include <cmath>
#include <cstdint>
#include <numbers>
#include <optional>

namespace Goemon::Original {

enum class ShipPreviewStickKind { Neutral, Full, Unsupported };

struct ShipPreviewStick {
    ShipPreviewStickKind kind = ShipPreviewStickKind::Neutral;
    std::int16_t x = 0;
    std::int16_t y = 0;
    std::int16_t provisionalOriginalYaw10 = 0;
};

[[nodiscard]] inline ShipPreviewStick MapShipStickForOriginalPreview(
    int rawX, int rawY, std::int16_t shipCameraYaw) {
    const float length = std::hypot(static_cast<float>(rawX),
                                    static_cast<float>(rawY));
    ShipPreviewStick result{};
    if (!std::isfinite(length) || length > 180.0f) {
        result.kind = ShipPreviewStickKind::Unsupported;
        return result;
    }
    if (length < 15.0f) return result;
    // 75/85 is the explicit preview full-tilt threshold. The original
    // Goemon analog-response curve is NOT inferred from this conversion.
    if (length < 75.0f) {
        result.kind = ShipPreviewStickKind::Unsupported;
        return result;
    }
    result.kind = ShipPreviewStickKind::Full;
    result.x = static_cast<std::int16_t>(std::lround(93.0f * rawX / length));
    result.y = static_cast<std::int16_t>(std::lround(93.0f * rawY / length));
    const int camera10 =
        static_cast<std::uint16_t>(shipCameraYaw) >> 6;
    const float stickAngle = std::atan2(static_cast<float>(rawX),
                                        static_cast<float>(rawY));
    const int direction10 = static_cast<int>(std::lround(
        stickAngle * (1024.0f / (2.0f * std::numbers::pi_v<float>))));
    result.provisionalOriginalYaw10 = static_cast<std::int16_t>(
        (camera10 + direction10) & 1023);
    return result;
}

// This maps only documented numeric ground/air/braking phases to a
// diagnostic input. The action-selection transitions themselves are
// provisional and not asserted as original Goemon action dispatch.
[[nodiscard]] inline std::optional<OriginalVectorInput>
ComposeShipPreviewOriginalInput(
    ShipPreviewStick stick, std::uint8_t previousAction,
    std::int16_t previousX, std::int16_t previousY,
    bool air, bool jumpPressed, bool jumpHeld,
    float priorSpeed) {
    if (stick.kind == ShipPreviewStickKind::Unsupported) return std::nullopt;
    OriginalVectorInput input{};
    input.continuousSameCharacterFrame = true;
    input.previousAction = previousAction;
    input.previousStickX = previousX;
    input.previousStickY = previousY;
    input.stickX = stick.x;
    input.stickY = stick.y;
    input.currentOriginalYaw = stick.provisionalOriginalYaw10;
    input.aButtonHeld = jumpHeld;
    // The runtime begins the isolated jump separately, allowing
    // standing jumps and never double-stepping vertical physics.
    input.beginJump = false;

    if (air) {
        if (stick.kind != ShipPreviewStickKind::Full)
            return std::nullopt;
        input.action = 23;
        return input;
    }
    if (jumpPressed && stick.kind == ShipPreviewStickKind::Full) {
        input.action = 23;
        return input;
    }
    if (stick.kind == ShipPreviewStickKind::Full) {
        input.action = previousAction == 13 || previousAction == 15 ? 15 : 13;
        return input;
    }
    if (previousAction == 15 && std::fabs(priorSpeed - 2.8f) < 0.012f) {
        input.action = 16;
        return input;
    }
    if (previousAction == 16) {
        input.action = 16;
        return input;
    }
    return std::nullopt;
}
} // namespace Goemon::Original
