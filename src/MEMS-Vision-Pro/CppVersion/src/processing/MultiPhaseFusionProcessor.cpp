#include "MultiPhaseFusionProcessor.h"
#include "ImageProcessor.h"
#include <algorithm>

std::vector<uint16_t> MultiPhaseFusionProcessor::fuse(
    const std::array<std::shared_ptr<ProcessingResult>, 3>& frames) {

    const int imageSize = 512;
    const int pixelCount = imageSize * imageSize;
    std::vector<uint16_t> fusedImage(pixelCount, 0);

    // Get image data from each frame
    const std::vector<uint16_t>* img1 = nullptr;
    const std::vector<uint16_t>* img2 = nullptr;
    const std::vector<uint16_t>* img3 = nullptr;

    if (frames[0] && !frames[0]->imageData.empty()) {
        img1 = &frames[0]->imageData;
    }
    if (frames[1] && !frames[1]->imageData.empty()) {
        img2 = &frames[1]->imageData;
    }
    if (frames[2] && !frames[2]->imageData.empty()) {
        img3 = &frames[2]->imageData;
    }

    // Fuse each pixel
    for (int i = 0; i < pixelCount; ++i) {
        uint16_t v1 = (img1 && i < static_cast<int>(img1->size())) ? (*img1)[i] : 0;
        uint16_t v2 = (img2 && i < static_cast<int>(img2->size())) ? (*img2)[i] : 0;
        uint16_t v3 = (img3 && i < static_cast<int>(img3->size())) ? (*img3)[i] : 0;

        fusedImage[i] = fusePixelValue(v1, v2, v3);
    }

    return fusedImage;
}

uint16_t MultiPhaseFusionProcessor::fusePixelValue(uint16_t v1, uint16_t v2, uint16_t v3) {
    // Count non-zero values
    int count = (v1 > 0 ? 1 : 0) + (v2 > 0 ? 1 : 0) + (v3 > 0 ? 1 : 0);

    if (count == 3) {
        // All three frames have values - average
        return static_cast<uint16_t>((static_cast<uint32_t>(v1) + v2 + v3) / 3);
    } else if (count == 2) {
        // Two frames have values - average of the two
        uint32_t sum = 0;
        if (v1 > 0) sum += v1;
        if (v2 > 0) sum += v2;
        if (v3 > 0) sum += v3;
        return static_cast<uint16_t>(sum / 2);
    } else if (count == 1) {
        // Only one frame has value - use that value
        if (v1 > 0) return v1;
        if (v2 > 0) return v2;
        if (v3 > 0) return v3;
        return 0;
    } else {
        // No frames have values - return 0
        return 0;
    }
}

std::vector<uint16_t> MultiPhaseFusionProcessor::processSingleFrame(
    std::shared_ptr<ProcessingResult> frame) {

    if (!frame || frame->imageData.empty()) {
        return std::vector<uint16_t>(512 * 512, 0);
    }

    return frame->imageData;
}