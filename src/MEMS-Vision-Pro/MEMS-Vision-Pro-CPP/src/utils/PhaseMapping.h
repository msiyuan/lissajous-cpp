#ifndef PHASE_MAPPING_H
#define PHASE_MAPPING_H

#include <cmath>
#include <mutex>

/**
 * 相位映射模块
 * 用于 X/Y 方向的相位补偿计算
 */
class PhaseMapping {
public:
    // 补偿常量
    static constexpr double X_PHASE_COMPENSATION_LOW = 6.0;
    static constexpr double X_PHASE_COMPENSATION_HIGH = 186.0;
    static constexpr double Y_PHASE_COMPENSATION_LOW = 35.0;
    static constexpr double Y_PHASE_COMPENSATION_HIGH = 215.0;

    /**
     * 获取单例实例
     */
    static PhaseMapping& instance();

    /**
     * X方向相位映射
     * @param originalPhase 原始相位值 (0-360度)
     * @return 补偿相位值
     */
    double mapDeltaPhaseX(double originalPhase);

    /**
     * Y方向相位映射
     * @param originalPhase 原始相位值 (0-360度)
     * @return 补偿相位值
     */
    double mapDeltaPhaseY(double originalPhase);

    /**
     * 重置所有状态
     */
    void reset();

    /**
     * 获取当前状态
     */
    struct Status {
        double previousXPhase;
        double previousYPhase;
        bool xPhaseIncreasing;
        bool yPhaseIncreasing;
        bool xInitialized;
        bool yInitialized;
    };
    Status getStatus() const;

private:
    PhaseMapping();
    ~PhaseMapping() = default;
    PhaseMapping(const PhaseMapping&) = delete;
    PhaseMapping& operator=(const PhaseMapping&) = delete;

    mutable std::mutex m_mutex;

    // X方向状态
    double m_previousXPhase = 0.0;
    bool m_xPhaseIncreasing = false;
    bool m_xInitialized = false;

    // Y方向状态
    double m_previousYPhase = 0.0;
    bool m_yPhaseIncreasing = false;
    bool m_yInitialized = false;
};

#endif  // PHASE_MAPPING_H
