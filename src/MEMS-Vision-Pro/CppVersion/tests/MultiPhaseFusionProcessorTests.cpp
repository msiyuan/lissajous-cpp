#include "processing/MultiPhaseFusionProcessor.h"
#include "processing/ImageProcessor.h"
#include "TestSupport.h"
#include <memory>
#include <vector>

namespace {

std::shared_ptr<ProcessingResult> createFrameWithImage(
    const std::vector<uint16_t>& imageData, uint8_t /*phaseIndex*/ = 0) {
    auto frame = std::make_shared<ProcessingResult>();
    frame->imageData = imageData;
    frame->width = 512;
    frame->height = 512;
    return frame;
}

std::vector<uint16_t> createUniformImage(uint16_t value, int startPixel, int count) {
    std::vector<uint16_t> image(512 * 512, 0);
    for (int i = startPixel; i < startPixel + count && i < 512 * 512; ++i) {
        image[i] = value;
    }
    return image;
}

std::vector<uint16_t> createFullUniformImage(uint16_t value) {
    std::vector<uint16_t> image(512 * 512, value);
    return image;
}

void test_fuse_three_non_overlapping_frames() {
    // Three frames with non-overlapping data
    // Frame 0: pixels 0-10000 have value 100
    // Frame 1: pixels 20000-30000 have value 200
    // Frame 2: pixels 40000-50000 have value 300

    auto frame0 = createFrameWithImage(createUniformImage(100, 0, 10000), 0);
    auto frame1 = createFrameWithImage(createUniformImage(200, 20000, 10000), 1);
    auto frame2 = createFrameWithImage(createUniformImage(300, 40000, 10000), 2);

    std::array<std::shared_ptr<ProcessingResult>, 3> frames = {frame0, frame1, frame2};

    MultiPhaseFusionProcessor processor;
    auto fused = processor.fuse(frames);

    // Pixel 5000 should have value 100 (only frame0 has it)
    REQUIRE(fused[5000] == 100);

    // Pixel 25000 should have value 200 (only frame1 has it)
    REQUIRE(fused[25000] == 200);

    // Pixel 45000 should have value 300 (only frame2 has it)
    REQUIRE(fused[45000] == 300);
}

void test_fuse_three_overlapping_frames() {
    // Three frames with same pixel positions having values
    auto frame0 = createFrameWithImage(createFullUniformImage(100), 0);
    auto frame1 = createFrameWithImage(createFullUniformImage(200), 1);
    auto frame2 = createFrameWithImage(createFullUniformImage(300), 2);

    std::array<std::shared_ptr<ProcessingResult>, 3> frames = {frame0, frame1, frame2};

    MultiPhaseFusionProcessor processor;
    auto fused = processor.fuse(frames);

    // Average of 100, 200, 300 = 200
    REQUIRE(fused[100] == 200);
    REQUIRE(fused[500] == 200);
}

void test_fuse_two_overlapping_one_empty() {
    // Two frames have data, one frame is empty
    auto frame0 = createFrameWithImage(createFullUniformImage(100), 0);
    auto frame1 = createFrameWithImage(createFullUniformImage(200), 1);
    auto frame2 = createFrameWithImage(std::vector<uint16_t>(512 * 512, 0), 2);  // empty

    std::array<std::shared_ptr<ProcessingResult>, 3> frames = {frame0, frame1, frame2};

    MultiPhaseFusionProcessor processor;
    auto fused = processor.fuse(frames);

    // Average of 100 and 200 = 150
    REQUIRE(fused[100] == 150);
    REQUIRE(fused[500] == 150);
}

void test_fuse_single_frame_has_data() {
    // Only one frame has data
    auto frame0 = createFrameWithImage(createFullUniformImage(100), 0);
    auto frame1 = createFrameWithImage(std::vector<uint16_t>(512 * 512, 0), 1);
    auto frame2 = createFrameWithImage(std::vector<uint16_t>(512 * 512, 0), 2);

    std::array<std::shared_ptr<ProcessingResult>, 3> frames = {frame0, frame1, frame2};

    MultiPhaseFusionProcessor processor;
    auto fused = processor.fuse(frames);

    // Should use frame0's value
    REQUIRE(fused[100] == 100);
    REQUIRE(fused[500] == 100);
}

void test_fuse_all_frames_empty() {
    auto frame0 = createFrameWithImage(std::vector<uint16_t>(512 * 512, 0), 0);
    auto frame1 = createFrameWithImage(std::vector<uint16_t>(512 * 512, 0), 1);
    auto frame2 = createFrameWithImage(std::vector<uint16_t>(512 * 512, 0), 2);

    std::array<std::shared_ptr<ProcessingResult>, 3> frames = {frame0, frame1, frame2};

    MultiPhaseFusionProcessor processor;
    auto fused = processor.fuse(frames);

    // All pixels should be 0
    REQUIRE(fused[0] == 0);
    REQUIRE(fused[100000] == 0);
    REQUIRE(fused[262143] == 0);  // last pixel (512*512-1)
}

void test_fuse_pixel_value_boundaries() {
    // Test with non-zero values to verify averaging works
    auto frame0 = std::make_shared<ProcessingResult>();
    auto frame1 = std::make_shared<ProcessingResult>();
    auto frame2 = std::make_shared<ProcessingResult>();

    frame0->imageData = std::vector<uint16_t>(512 * 512, 100);
    frame1->imageData = std::vector<uint16_t>(512 * 512, 200);
    frame2->imageData = std::vector<uint16_t>(512 * 512, 300);

    std::array<std::shared_ptr<ProcessingResult>, 3> frames = {frame0, frame1, frame2};

    MultiPhaseFusionProcessor processor;
    auto fused = processor.fuse(frames);

    // Average of 100, 200, 300 = 200
    REQUIRE(fused[100] == 200);
    REQUIRE(fused[5000] == 200);
    REQUIRE(fused[262143] == 200);
}

void test_process_single_frame() {
    auto frame = createFrameWithImage(createFullUniformImage(500), 0);

    MultiPhaseFusionProcessor processor;
    auto result = processor.processSingleFrame(frame);

    REQUIRE(result.size() == 512 * 512);
    REQUIRE(result[0] == 500);
    REQUIRE(result[100000] == 500);
}

void test_process_single_frame_nullptr() {
    MultiPhaseFusionProcessor processor;
    auto result = processor.processSingleFrame(nullptr);

    // Should return empty image filled with zeros
    REQUIRE(result.size() == 512 * 512);
    REQUIRE(result[0] == 0);
}

}  // namespace

void runMultiPhaseFusionProcessorTests() {
    test_fuse_three_non_overlapping_frames();
    test_fuse_three_overlapping_frames();
    test_fuse_two_overlapping_one_empty();
    test_fuse_single_frame_has_data();
    test_fuse_all_frames_empty();
    test_fuse_pixel_value_boundaries();
    test_process_single_frame();
    test_process_single_frame_nullptr();
}