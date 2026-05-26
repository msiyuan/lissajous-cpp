#ifndef MULTI_PHASE_FUSION_PROCESSOR_H
#define MULTI_PHASE_FUSION_PROCESSOR_H

#include <array>
#include <memory>
#include <vector>
#include <cstdint>

class ProcessingResult;

/**
 * 多相位帧融合处理器
 * 将三帧图像数据按像素位置融合
 */
class MultiPhaseFusionProcessor {
public:
    // 融合三帧图像
    // 输入: 三帧 ProcessingResult（含 imageData）
    // 输出: 融合后的 imageData (512x512)
    std::vector<uint16_t> fuse(const std::array<std::shared_ptr<ProcessingResult>, 3>& frames);

    // 单帧处理接口（当三相位融合未启用时使用）
    std::vector<uint16_t> processSingleFrame(std::shared_ptr<ProcessingResult> frame);

private:
    // 融合算法核心
    uint16_t fusePixelValue(uint16_t v1, uint16_t v2, uint16_t v3);
};

#endif  // MULTI_PHASE_FUSION_PROCESSOR_H