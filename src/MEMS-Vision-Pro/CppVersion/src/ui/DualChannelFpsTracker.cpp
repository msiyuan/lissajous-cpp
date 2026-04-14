#include "DualChannelFpsTracker.h"

void DualChannelFpsTracker::reset() {
    m_ch1Frames.clear();
    m_ch2Frames.clear();
}

void DualChannelFpsTracker::recordFrame(const QString& channel, TimePoint now) {
    if (channel == "ch1") {
        m_ch1Frames.push_back(now);
    } else if (channel == "ch2") {
        m_ch2Frames.push_back(now);
    }

    prune(now);
}

int DualChannelFpsTracker::currentFps(TimePoint now) {
    prune(now);
    return static_cast<int>(std::min(m_ch1Frames.size(), m_ch2Frames.size()));
}

void DualChannelFpsTracker::prune(TimePoint now) {
    constexpr auto window = std::chrono::seconds(1);

    while (!m_ch1Frames.empty()) {
        if ((now - m_ch1Frames.front()) > window) {
            m_ch1Frames.pop_front();
        } else {
            break;
        }
    }

    while (!m_ch2Frames.empty()) {
        if ((now - m_ch2Frames.front()) > window) {
            m_ch2Frames.pop_front();
        } else {
            break;
        }
    }
}
