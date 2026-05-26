#include "MultiPhaseFrameBuffer.h"
#include "ImageProcessor.h"

void MultiPhaseFrameBuffer::pushResult(std::shared_ptr<ProcessingResult> result, uint8_t phaseIndex) {
    if (!result) {
        return;
    }

    // Only accept valid phase indices (0, 1, 2)
    if (phaseIndex > 2) {
        return;
    }

    // Store result by phaseIndex
    m_buffer[phaseIndex] = result;
}

bool MultiPhaseFrameBuffer::isComplete() const {
    return m_buffer.size() == 3 &&
           m_buffer.count(0) && m_buffer.count(1) && m_buffer.count(2);
}

std::array<std::shared_ptr<ProcessingResult>, 3> MultiPhaseFrameBuffer::getFramesForFusion() const {
    std::array<std::shared_ptr<ProcessingResult>, 3> result = {nullptr, nullptr, nullptr};

    if (m_buffer.count(0)) {
        result[0] = m_buffer.at(0);
    }
    if (m_buffer.count(1)) {
        result[1] = m_buffer.at(1);
    }
    if (m_buffer.count(2)) {
        result[2] = m_buffer.at(2);
    }

    return result;
}

void MultiPhaseFrameBuffer::clear() {
    m_buffer.clear();
}

bool MultiPhaseFrameBuffer::hasFrame(uint8_t phaseIndex) const {
    return m_buffer.count(phaseIndex) > 0;
}

size_t MultiPhaseFrameBuffer::size() const {
    return m_buffer.size();
}