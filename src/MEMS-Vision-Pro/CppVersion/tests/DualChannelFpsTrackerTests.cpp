#include "ui/DualChannelFpsTracker.h"
#include "TestSupport.h"

namespace {

void test_dual_channel_fps_requires_both_channels_for_one_frame() {
    DualChannelFpsTracker tracker;
    const auto base = DualChannelFpsTracker::Clock::time_point{};

    tracker.recordFrame("ch1", base);
    REQUIRE(tracker.currentFps(base) == 0);

    tracker.recordFrame("ch2", base);
    REQUIRE(tracker.currentFps(base) == 1);
}

void test_dual_channel_fps_uses_matching_pair_count_not_total_frames() {
    DualChannelFpsTracker tracker;
    const auto base = DualChannelFpsTracker::Clock::time_point{};

    tracker.recordFrame("ch1", base);
    tracker.recordFrame("ch1", base + std::chrono::milliseconds(100));
    tracker.recordFrame("ch2", base + std::chrono::milliseconds(150));
    REQUIRE(tracker.currentFps(base + std::chrono::milliseconds(150)) == 1);

    tracker.recordFrame("ch2", base + std::chrono::milliseconds(200));
    REQUIRE(tracker.currentFps(base + std::chrono::milliseconds(200)) == 2);
}

void test_dual_channel_fps_expires_old_pairs_after_one_second() {
    DualChannelFpsTracker tracker;
    const auto base = DualChannelFpsTracker::Clock::time_point{};

    tracker.recordFrame("ch1", base);
    tracker.recordFrame("ch2", base);
    REQUIRE(tracker.currentFps(base) == 1);

    const auto later = base + std::chrono::milliseconds(1500);
    tracker.recordFrame("ch1", later);
    REQUIRE(tracker.currentFps(later) == 0);

    tracker.recordFrame("ch2", later);
    REQUIRE(tracker.currentFps(later) == 1);
}

}  // namespace

void runDualChannelFpsTrackerTests() {
    test_dual_channel_fps_requires_both_channels_for_one_frame();
    test_dual_channel_fps_uses_matching_pair_count_not_total_frames();
    test_dual_channel_fps_expires_old_pairs_after_one_second();
}
