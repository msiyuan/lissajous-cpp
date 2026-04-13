#include "ImageDisplayAdjustments.h"

#include <algorithm>
#include <cmath>

double ImageDisplayAdjustments::percentile(std::vector<double>& values, double q) {
    if (values.empty()) {
        return 0.0;
    }

    std::sort(values.begin(), values.end());

    if (values.size() == 1) {
        return values.front();
    }

    const double position = (q / 100.0) * static_cast<double>(values.size() - 1);
    const auto lowerIndex = static_cast<size_t>(std::floor(position));
    const auto upperIndex = static_cast<size_t>(std::ceil(position));

    if (lowerIndex == upperIndex) {
        return values[lowerIndex];
    }

    const double fraction = position - static_cast<double>(lowerIndex);
    return values[lowerIndex] + (values[upperIndex] - values[lowerIndex]) * fraction;
}

DisplayRange ImageDisplayAdjustments::autoAdjustRange(const std::vector<uint16_t>& image) {
    std::vector<double> validPixels;
    validPixels.reserve(image.size());

    for (const auto value : image) {
        if (value > 0) {
            validPixels.push_back(static_cast<double>(value));
        }
    }

    if (validPixels.empty()) {
        return {};
    }

    auto lowValues = validPixels;
    auto highValues = validPixels;

    DisplayRange range;
    range.minValue = static_cast<int>(percentile(lowValues, 1.0));
    range.maxValue = static_cast<int>(percentile(highValues, 99.0));
    return range;
}

std::vector<uint8_t> ImageDisplayAdjustments::applyImageAdjustments(
    const std::vector<uint16_t>& image,
    int width,
    int height,
    int minValue,
    int maxValue,
    int contrast,
    int brightness) {
    const size_t pixelCount = static_cast<size_t>(width) * static_cast<size_t>(height);
    std::vector<uint8_t> adjusted(pixelCount, 0);

    if (image.size() != pixelCount) {
        return adjusted;
    }

    const int safeMax = std::max(maxValue, minValue + 1);
    const double range = static_cast<double>(safeMax - minValue);
    const double contrastScale = static_cast<double>(contrast) / 100.0;
    const double brightnessOffset = static_cast<double>(brightness) * 65535.0 / 100.0;

    for (size_t i = 0; i < pixelCount; ++i) {
        double value = static_cast<double>(image[i]);
        value = std::clamp(value, static_cast<double>(minValue), static_cast<double>(safeMax));
        value = ((value - static_cast<double>(minValue)) / range) * 65535.0;
        value *= contrastScale;
        value += brightnessOffset;
        value = std::clamp(value, 0.0, 65535.0);
        adjusted[i] = static_cast<uint8_t>((value / 65535.0) * 255.0);
    }

    return adjusted;
}
