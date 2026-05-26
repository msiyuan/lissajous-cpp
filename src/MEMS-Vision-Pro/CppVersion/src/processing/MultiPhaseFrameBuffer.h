#ifndef MULTI_PHASE_FRAME_BUFFER_H
#define MULTI_PHASE_FRAME_BUFFER_H

#include <array>
#include <map>
#include <memory>
#include <cstdint>

class ProcessingResult;

/**
 * 三相位滑动窗口帧缓存
 * 用于缓存最近3个不同 phase_index 的已处理帧结果
 */
class MultiPhaseFrameBuffer {
public:
    // 缓存一帧处理结果
    void pushResult(std::shared_ptr<ProcessingResult> result, uint8_t phaseIndex);

    // 获取缓存状态
    bool isComplete() const;  // 是否已缓存3帧

    // 获取待融合的三帧结果（按phaseIndex=0,1,2排序）
    std::array<std::shared_ptr<ProcessingResult>, 3> getFramesForFusion() const;

    // 清空缓存
    void clear();

    // 检查是否包含指定phaseIndex的帧
    bool hasFrame(uint8_t phaseIndex) const;

    // 获取当前缓存的帧数
    size_t size() const;

private:
    std::map<uint8_t, std::shared_ptr<ProcessingResult>> m_buffer;  // key: phaseIndex (0/1/2)
};

#endif  // MULTI_PHASE_FRAME_BUFFER_H