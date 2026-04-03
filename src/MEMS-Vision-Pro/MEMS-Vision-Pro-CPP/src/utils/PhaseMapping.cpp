#include "PhaseMapping.h"

PhaseMapping::PhaseMapping() = default;

PhaseMapping& PhaseMapping::instance() {
    static PhaseMapping instance;
    return instance;
}

double PhaseMapping::mapDeltaPhaseX(double originalPhase) {
    std::lock_guard<std::mutex> lock(m_mutex);

    // 归一化到 0-360
    double phase = std::fmod(originalPhase, 360.0);
    if (phase < 0) phase += 360.0;

    // 首次调用
    if (!m_xInitialized) {
        m_previousXPhase = phase;
        m_xInitialized = true;
        return X_PHASE_COMPENSATION_LOW;
    }

    // 检测相位变化趋势
    double diff = phase - m_previousXPhase;

    // 处理跨越 0/360 边界
    if (diff > 180.0) diff -= 360.0;
    if (diff < -180.0) diff += 360.0;

    // 下降趋势时切换补偿标志
    if (diff < 0) {
        m_xPhaseIncreasing = !m_xPhaseIncreasing;
    }

    m_previousXPhase = phase;

    return m_xPhaseIncreasing ? X_PHASE_COMPENSATION_HIGH : X_PHASE_COMPENSATION_LOW;
}

double PhaseMapping::mapDeltaPhaseY(double originalPhase) {
    std::lock_guard<std::mutex> lock(m_mutex);

    // 归一化到 0-360
    double phase = std::fmod(originalPhase, 360.0);
    if (phase < 0) phase += 360.0;

    // 首次调用
    if (!m_yInitialized) {
        m_previousYPhase = phase;
        m_yInitialized = true;
        return Y_PHASE_COMPENSATION_LOW;
    }

    // 检测相位变化趋势
    double diff = phase - m_previousYPhase;

    // 处理跨越 0/360 边界
    if (diff > 180.0) diff -= 360.0;
    if (diff < -180.0) diff += 360.0;

    // 上升趋势时切换补偿标志
    if (diff > 0) {
        m_yPhaseIncreasing = !m_yPhaseIncreasing;
    }

    m_previousYPhase = phase;

    return m_yPhaseIncreasing ? Y_PHASE_COMPENSATION_HIGH : Y_PHASE_COMPENSATION_LOW;
}

void PhaseMapping::reset() {
    std::lock_guard<std::mutex> lock(m_mutex);
    m_previousXPhase = 0.0;
    m_previousYPhase = 0.0;
    m_xPhaseIncreasing = false;
    m_yPhaseIncreasing = false;
    m_xInitialized = false;
    m_yInitialized = false;
}

PhaseMapping::Status PhaseMapping::getStatus() const {
    std::lock_guard<std::mutex> lock(m_mutex);
    return {
        m_previousXPhase,
        m_previousYPhase,
        m_xPhaseIncreasing,
        m_yPhaseIncreasing,
        m_xInitialized,
        m_yInitialized
    };
}
