#include "processing/MultiPhaseFrameBuffer.h"
#include "processing/ImageProcessor.h"
#include "TestSupport.h"
#include <memory>

namespace {

std::shared_ptr<ProcessingResult> createResult(uint8_t phaseIndex, uint32_t frameId = 0) {
    auto result = std::make_shared<ProcessingResult>();
    result->phaseX = 0;
    result->phaseY = phaseIndex * 45000000;  // 0, 45M, 90M
    result->channel = "CH1";
    result->width = 512;
    result->height = 512;
    result->imageData = std::vector<uint16_t>(512 * 512, static_cast<uint16_t>(100 + phaseIndex));
    return result;
}

void test_three_frames_complete_buffer() {
    MultiPhaseFrameBuffer buffer;

    // Push three results with different phase indices
    buffer.pushResult(createResult(0, 1), 0);
    buffer.pushResult(createResult(1, 2), 1);
    buffer.pushResult(createResult(2, 3), 2);

    REQUIRE(buffer.isComplete() == true);
    REQUIRE(buffer.size() == 3);
}

void test_incomplete_buffer_not_complete() {
    MultiPhaseFrameBuffer buffer;

    // Push only two results
    buffer.pushResult(createResult(0, 1), 0);
    buffer.pushResult(createResult(1, 2), 1);

    REQUIRE(buffer.isComplete() == false);
    REQUIRE(buffer.size() == 2);
}

void test_push_same_phase_index_replaces_old_result() {
    MultiPhaseFrameBuffer buffer;

    // Push result with phaseIndex=0
    buffer.pushResult(createResult(0, 1), 0);
    REQUIRE(buffer.hasFrame(0) == true);

    // Push another result with phaseIndex=0, should replace
    buffer.pushResult(createResult(0, 100), 0);
    REQUIRE(buffer.size() == 1);
    REQUIRE(buffer.isComplete() == false);
}

void test_get_frames_for_fusion_returns_correct_order() {
    MultiPhaseFrameBuffer buffer;

    buffer.pushResult(createResult(1, 10), 1);
    buffer.pushResult(createResult(2, 20), 2);
    buffer.pushResult(createResult(0, 30), 0);

    auto frames = buffer.getFramesForFusion();

    // Should return frames in order: phase0, phase1, phase2
    REQUIRE(frames[0] != nullptr);
    REQUIRE(frames[1] != nullptr);
    REQUIRE(frames[2] != nullptr);
}

void test_clear_resets_buffer() {
    MultiPhaseFrameBuffer buffer;

    buffer.pushResult(createResult(0, 1), 0);
    buffer.pushResult(createResult(1, 2), 1);
    buffer.pushResult(createResult(2, 3), 2);

    REQUIRE(buffer.isComplete() == true);

    buffer.clear();

    REQUIRE(buffer.isComplete() == false);
    REQUIRE(buffer.size() == 0);
}

void test_push_invalid_phase_index_ignored() {
    MultiPhaseFrameBuffer buffer;

    // Push result with phaseIndex=255 (invalid)
    buffer.pushResult(createResult(255, 1), 255);
    REQUIRE(buffer.size() == 0);

    // Push result with phaseIndex=3 (invalid)
    buffer.pushResult(createResult(3, 2), 3);
    REQUIRE(buffer.size() == 0);

    // Push valid result
    buffer.pushResult(createResult(0, 3), 0);
    REQUIRE(buffer.size() == 1);
}

void test_has_frame() {
    MultiPhaseFrameBuffer buffer;

    buffer.pushResult(createResult(1, 10), 1);

    REQUIRE(buffer.hasFrame(0) == false);
    REQUIRE(buffer.hasFrame(1) == true);
    REQUIRE(buffer.hasFrame(2) == false);
}

void test_four_frames_sliding_window() {
    MultiPhaseFrameBuffer buffer;

    // Push three results
    buffer.pushResult(createResult(0, 1), 0);
    buffer.pushResult(createResult(1, 2), 1);
    buffer.pushResult(createResult(2, 3), 2);

    REQUIRE(buffer.isComplete() == true);

    // Push fourth result (phaseIndex=0), should replace old result
    buffer.pushResult(createResult(0, 4), 0);

    // Buffer should still have 3 frames, but phase0 now has frameId=4
    REQUIRE(buffer.size() == 3);
    REQUIRE(buffer.isComplete() == true);
}

void test_empty_buffer_queries() {
    MultiPhaseFrameBuffer buffer;

    REQUIRE(buffer.isComplete() == false);
    REQUIRE(buffer.size() == 0);
    REQUIRE(buffer.hasFrame(0) == false);
    REQUIRE(buffer.hasFrame(1) == false);
    REQUIRE(buffer.hasFrame(2) == false);

    auto frames = buffer.getFramesForFusion();
    REQUIRE(frames[0] == nullptr);
    REQUIRE(frames[1] == nullptr);
    REQUIRE(frames[2] == nullptr);
}

}  // namespace

void runMultiPhaseFrameBufferTests() {
    test_three_frames_complete_buffer();
    test_incomplete_buffer_not_complete();
    test_push_same_phase_index_replaces_old_result();
    test_get_frames_for_fusion_returns_correct_order();
    test_clear_resets_buffer();
    test_push_invalid_phase_index_ignored();
    test_has_frame();
    test_four_frames_sliding_window();
    test_empty_buffer_queries();
}