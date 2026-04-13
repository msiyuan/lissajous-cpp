#ifndef IMAGE_DISPLAY_ADJUSTMENTS_H
#define IMAGE_DISPLAY_ADJUSTMENTS_H

#include <cstdint>
#include <vector>

struct DisplayRange {
    int minValue = 0;
    int maxValue = 65535;
};

class ImageDisplayAdjustments {
public:
    static DisplayRange autoAdjustRange(const std::vector<uint16_t>& image);

    static std::vector<uint8_t> applyImageAdjustments(
        const std::vector<uint16_t>& image,
        int width,
        int height,
        int minValue,
        int maxValue,
        int contrast,
        int brightness);

private:
    static double percentile(std::vector<double>& values, double q);
};

#endif  // IMAGE_DISPLAY_ADJUSTMENTS_H
