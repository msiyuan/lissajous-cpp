#include "DisplayFrameFusion.h"

#include <algorithm>

void DisplayFrameFusion::setEnabled(bool enabled) {
    if (m_enabled == enabled) {
        return;
    }

    m_enabled = enabled;
    clear();
}

void DisplayFrameFusion::setFrameCount(int frameCount) {
    m_frameCount = std::clamp(frameCount, 1, 10);
    trimToWindow();
}

void DisplayFrameFusion::clear() {
    m_frames.clear();
    m_runningSum.clear();
}

std::vector<uint16_t> DisplayFrameFusion::addFrame(const std::vector<uint16_t>& frame) {
    if (frame.empty()) {
        return {};
    }

    if (!m_enabled) {
        return frame;
    }

    initializeForFrame(frame.size());

    m_frames.push_back(frame);
    for (size_t i = 0; i < frame.size(); ++i) {
        m_runningSum[i] += frame[i];
    }

    trimToWindow();

    std::vector<uint16_t> averaged(frame.size(), 0);
    const uint64_t count = static_cast<uint64_t>(m_frames.size());
    for (size_t i = 0; i < averaged.size(); ++i) {
        averaged[i] = static_cast<uint16_t>(m_runningSum[i] / count);
    }

    return averaged;
}

void DisplayFrameFusion::initializeForFrame(size_t pixelCount) {
    if (!m_runningSum.empty() && m_runningSum.size() == pixelCount) {
        return;
    }

    clear();
    m_runningSum.assign(pixelCount, 0);
}

void DisplayFrameFusion::trimToWindow() {
    while (static_cast<int>(m_frames.size()) > m_frameCount) {
        const auto& oldest = m_frames.front();
        for (size_t i = 0; i < oldest.size(); ++i) {
            m_runningSum[i] -= oldest[i];
        }
        m_frames.pop_front();
    }
}
