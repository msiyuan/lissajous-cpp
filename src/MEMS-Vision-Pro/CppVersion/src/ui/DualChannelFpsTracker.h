#ifndef DUAL_CHANNEL_FPS_TRACKER_H
#define DUAL_CHANNEL_FPS_TRACKER_H

#include <QString>
#include <chrono>
#include <deque>

class DualChannelFpsTracker {
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    void reset();
    void recordFrame(const QString& channel, TimePoint now);
    int currentFps(TimePoint now);

private:
    void prune(TimePoint now);

    std::deque<TimePoint> m_ch1Frames;
    std::deque<TimePoint> m_ch2Frames;
};

#endif  // DUAL_CHANNEL_FPS_TRACKER_H
