#include "ui/DisplayFrameFusion.h"
#include "TestSupport.h"

namespace {

void test_display_frame_fusion_passthrough_when_disabled() {
    DisplayFrameFusion fusion;

    const auto output = fusion.addFrame({10, 20, 30});

    REQUIRE(output.size() == 3);
    REQUIRE(output[0] == 10);
    REQUIRE(output[1] == 20);
    REQUIRE(output[2] == 30);
}

void test_display_frame_fusion_averages_recent_frames() {
    DisplayFrameFusion fusion;
    fusion.setEnabled(true);
    fusion.setFrameCount(2);

    const auto first = fusion.addFrame({10, 20});
    const auto second = fusion.addFrame({30, 40});
    const auto third = fusion.addFrame({50, 60});

    REQUIRE(first[0] == 10);
    REQUIRE(first[1] == 20);
    REQUIRE(second[0] == 20);
    REQUIRE(second[1] == 30);
    REQUIRE(third[0] == 40);
    REQUIRE(third[1] == 50);
}

void test_display_frame_fusion_limits_window_to_ten_frames() {
    DisplayFrameFusion fusion;
    fusion.setEnabled(true);
    fusion.setFrameCount(20);

    std::vector<uint16_t> output;
    for (uint16_t value = 0; value <= 100; value += 10) {
        output = fusion.addFrame({value});
    }

    REQUIRE(output.size() == 1);
    REQUIRE(output[0] == 55);
}

void test_display_frame_fusion_clears_history_when_disabled() {
    DisplayFrameFusion fusion;
    fusion.setEnabled(true);
    fusion.setFrameCount(2);

    fusion.addFrame({10, 20});
    fusion.addFrame({30, 40});
    fusion.setEnabled(false);

    const auto output = fusion.addFrame({70, 90});

    REQUIRE(output.size() == 2);
    REQUIRE(output[0] == 70);
    REQUIRE(output[1] == 90);
}

}  // namespace

void runDisplayFrameFusionTests() {
    test_display_frame_fusion_passthrough_when_disabled();
    test_display_frame_fusion_averages_recent_frames();
    test_display_frame_fusion_limits_window_to_ten_frames();
    test_display_frame_fusion_clears_history_when_disabled();
}
