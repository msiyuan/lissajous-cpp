#include "PhaseMapping.h"

double PhaseMapping::mapDeltaPhaseX(double originalPhase) {
    std::lock_guard<std::mutex> lock(m_mutex);

    // 归一化到 0-360
    double phase = std::fmod(originalPhase, 360.0);
    if (phase < 0) phase += 360.0;

    // 首次调用
    if (!m_xInitialized) {
        m_previousXPhase = phase;
        m_xPhaseIncreasing = false;
        m_xInitialized = true;
        return X_PHASE_COMPENSATION_LOW;
    }

    // 按 msy_code0409 的当前逻辑：phase < previous 视作 increasing flag
    const bool currentTrendIncreasing = phase < m_previousXPhase;
    if (!currentTrendIncreasing) {
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
        m_yPhaseIncreasing = false;
        m_yInitialized = true;
        return Y_PHASE_COMPENSATION_LOW;
    }

    const bool currentTrendIncreasing = phase > m_previousYPhase;
    if (currentTrendIncreasing) {
        m_yPhaseIncreasing = !m_yPhaseIncreasing;
    }

    m_previousYPhase = phase;
    return m_yPhaseIncreasing ? Y_PHASE_COMPENSATION_HIGH : Y_PHASE_COMPENSATION_LOW;
}

double PhaseMapping::rawPhaseToMappingDegrees(uint32_t rawPhase) {
    return rawPhase * 360.0 / 33554432.0;
}

double PhaseMapping::rawPhaseToDisplayDegrees(uint32_t rawPhase) {
    return rawPhase * 180.0 / 33554432.0;
}

double PhaseMapping::composeFinalPhaseDegrees(uint32_t rawPhase,
                                              double compensation,
                                              double deltaPhase) {
    double phase = std::fmod(rawPhaseToDisplayDegrees(rawPhase) + compensation + deltaPhase, 360.0);
    if (phase < 0) {
        phase += 360.0;
    }
    return phase;
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
