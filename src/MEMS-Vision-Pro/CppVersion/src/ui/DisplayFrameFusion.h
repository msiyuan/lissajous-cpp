#ifndef DISPLAY_FRAME_FUSION_H
#define DISPLAY_FRAME_FUSION_H

#include <deque>
#include <vector>
#include <cstdint>

class DisplayFrameFusion {
public:
    void setEnabled(bool enabled);
    bool enabled() const { return m_enabled; }

    void setFrameCount(int frameCount);
    int frameCount() const { return m_frameCount; }

    void clear();
    std::vector<uint16_t> addFrame(const std::vector<uint16_t>& frame);

private:
    void initializeForFrame(size_t pixelCount);
    void trimToWindow();

    bool m_enabled = false;
    int m_frameCount = 3;
    std::deque<std::vector<uint16_t>> m_frames;
    std::vector<uint64_t> m_runningSum;
};

#endif  // DISPLAY_FRAME_FUSION_H
