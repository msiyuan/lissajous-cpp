#ifndef CHANNEL_PROCESSOR_H
#define CHANNEL_PROCESSOR_H

#include <QObject>
#include <QThread>
#include <memory>
#include <atomic>
#include <thread>
#include "utils/ThreadSafeQueue.h"
#include "network/UdpReceiver.h"
#include "processing/FrameAssembler.h"
#include "processing/ImageProcessor.h"
#include "processing/MultiPhaseFrameBuffer.h"
#include "processing/MultiPhaseFusionProcessor.h"

/**
 * 通道处理器
 * 管理单个通道的完整处理流水线：UDP接收 -> 帧组装 -> 图像处理 -> 多相位融合
 * 每个阶段使用独立线程，实现真正的并行处理
 */
class ChannelProcessor : public QObject {
    Q_OBJECT

public:
    explicit ChannelProcessor(const QString& channel, uint16_t port,
                              QObject* parent = nullptr);
    ~ChannelProcessor() override;

    void start();
    void stop();
    void resetStats();
    bool isRunning() const { return m_running.load(); }
    QString channel() const { return m_channel; }

    void setParams(const ProcessingParams& params);
    ProcessingParams params() const { return m_params; }

    // 统计信息
    uint64_t bytesReceived() const;
    uint64_t packetsReceived() const;
    uint64_t framesProcessed() const { return m_framesProcessed.load(); }

signals:
    void imageReady(std::shared_ptr<ProcessingResult> result);
    void logMessage(const QString& message);
    void statsUpdated(uint64_t bytes, uint64_t packets, uint64_t frames);

private slots:
    void onFrameComplete(std::shared_ptr<FrameData> frame);

private:
    void processingThreadFunc();
    void handleFusionOutput(std::shared_ptr<ProcessingResult> result);
    bool shouldProcessFrame(std::shared_ptr<FrameData> frame) const;
    void checkPhaseIndexJump(uint8_t newPhaseIndex);

    QString m_channel;
    uint16_t m_port;
    ProcessingParams m_params;

    // 队列
    std::shared_ptr<ThreadSafeQueue<QByteArray>> m_packetQueue;
    std::shared_ptr<ThreadSafeQueue<std::shared_ptr<FrameData>>> m_frameQueue;

    // 工作线程
    std::unique_ptr<UdpReceiver> m_udpReceiver;
    std::unique_ptr<FrameAssembler> m_frameAssembler;
    std::unique_ptr<ImageProcessor> m_imageProcessor;
    std::unique_ptr<std::thread> m_processingThread;

    // 多相位融合组件
    std::unique_ptr<MultiPhaseFrameBuffer> m_frameBuffer;
    std::unique_ptr<MultiPhaseFusionProcessor> m_fusionProcessor;

    std::atomic<bool> m_running{false};
    std::atomic<uint64_t> m_framesProcessed{0};
    std::atomic<uint8_t> m_lastPhaseIndex{0};

    mutable std::mutex m_paramsMutex;
};

#endif  // CHANNEL_PROCESSOR_H
