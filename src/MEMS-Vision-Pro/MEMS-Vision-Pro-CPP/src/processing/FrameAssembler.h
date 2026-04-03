#ifndef FRAME_ASSEMBLER_H
#define FRAME_ASSEMBLER_H

#include <QThread>
#include <QByteArray>
#include <vector>
#include <memory>
#include <atomic>
#include <chrono>
#include "utils/ThreadSafeQueue.h"
#include "config/Constants.h"

/**
 * 帧数据结构
 */
struct FrameData {
    std::vector<QByteArray> packets;  // 数据包列表
    uint16_t frameId = 0;             // 帧ID
    uint32_t samplePoint = 0;         // 采样点数
    uint32_t phaseX = 0;              // X轴相位原始值
    uint32_t phaseY = 0;              // Y轴相位原始值
    std::chrono::steady_clock::time_point timestamp;  // 时间戳
};

/**
 * 帧组装器
 * 从数据包队列中组装完整的帧
 */
class FrameAssembler : public QThread {
    Q_OBJECT

public:
    explicit FrameAssembler(const QString& channel,
                            std::shared_ptr<ThreadSafeQueue<QByteArray>> inputQueue,
                            QObject* parent = nullptr);
    ~FrameAssembler() override;

    void stop();
    uint64_t framesAssembled() const { return m_framesAssembled.load(); }
    void resetCounters();

signals:
    void frameComplete(std::shared_ptr<FrameData> frame);
    void logMessage(const QString& message);

protected:
    void run() override;

private:
    void processPacket(const QByteArray& packet);
    void finalizeCurrentFrame();
    void startNewFrame(const QByteArray& headerPacket);
    bool isFrameHeader(const QByteArray& packet) const;
    bool isDataPacket(const QByteArray& packet) const;

    QString m_channel;
    std::shared_ptr<ThreadSafeQueue<QByteArray>> m_inputQueue;

    // 当前帧状态
    std::shared_ptr<FrameData> m_currentFrame;
    std::chrono::steady_clock::time_point m_lastPacketTime;

    std::atomic<bool> m_running{false};
    std::atomic<uint64_t> m_framesAssembled{0};
};

#endif  // FRAME_ASSEMBLER_H
