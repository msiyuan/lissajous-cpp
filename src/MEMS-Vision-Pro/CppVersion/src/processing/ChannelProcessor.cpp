#include "ChannelProcessor.h"
#include <QCoreApplication>

ChannelProcessor::ChannelProcessor(const QString& channel, uint16_t port, QObject* parent)
    : QObject(parent)
    , m_channel(channel)
    , m_port(port) {

    // 创建队列
    m_packetQueue = std::make_shared<ThreadSafeQueue<QByteArray>>(Config::QUEUE_MAX_SIZE);
    m_frameQueue = std::make_shared<ThreadSafeQueue<std::shared_ptr<FrameData>>>(100);

    // 创建图像处理器
    m_imageProcessor = std::make_unique<ImageProcessor>();

    // 创建多相位融合组件
    m_frameBuffer = std::make_unique<MultiPhaseFrameBuffer>();
    m_fusionProcessor = std::make_unique<MultiPhaseFusionProcessor>();
}

ChannelProcessor::~ChannelProcessor() {
    stop();
}

void ChannelProcessor::resetStats() {
    m_framesProcessed.store(0);
    if (m_udpReceiver) {
        m_udpReceiver->resetCounters();
    }
}

void ChannelProcessor::start() {
    if (m_running.load()) {
        return;
    }

    m_running.store(true);
    m_packetQueue->start();
    m_frameQueue->start();

    // 创建并启动 UDP 接收器
    m_udpReceiver = std::make_unique<UdpReceiver>(m_port, m_channel, m_packetQueue);
    connect(m_udpReceiver.get(), &UdpReceiver::logMessage,
            this, &ChannelProcessor::logMessage);
    m_udpReceiver->resetCounters();
    m_udpReceiver->start();

    // 创建并启动帧组装器
    m_frameAssembler = std::make_unique<FrameAssembler>(m_channel, m_packetQueue);
    connect(m_frameAssembler.get(), &FrameAssembler::logMessage,
            this, &ChannelProcessor::logMessage);
    connect(m_frameAssembler.get(), &FrameAssembler::frameComplete,
            this, &ChannelProcessor::onFrameComplete);
    m_frameAssembler->start();

    // 重置融合组件
    m_frameBuffer->clear();
    m_lastPhaseIndex.store(0);

    // 启动图像处理线程
    m_framesProcessed.store(0);
    m_processingThread = std::make_unique<std::thread>(&ChannelProcessor::processingThreadFunc, this);

    emit logMessage(QString("[%1] 通道处理器已启动").arg(m_channel));
}

void ChannelProcessor::stop() {
    if (!m_running.load()) {
        return;
    }

    m_running.store(false);

    // 停止队列
    m_packetQueue->stop();
    m_frameQueue->stop();

    // 停止 UDP 接收器
    if (m_udpReceiver) {
        m_udpReceiver->stop();
        m_udpReceiver->wait();
        m_udpReceiver.reset();
    }

    // 停止帧组装器
    if (m_frameAssembler) {
        m_frameAssembler->stop();
        m_frameAssembler->wait();
        m_frameAssembler.reset();
    }

    // 等待处理线程结束
    if (m_processingThread && m_processingThread->joinable()) {
        m_processingThread->join();
        m_processingThread.reset();
    }

    emit logMessage(QString("[%1] 通道处理器已停止").arg(m_channel));
}

void ChannelProcessor::setParams(const ProcessingParams& params) {
    std::lock_guard<std::mutex> lock(m_paramsMutex);
    m_params = params;
}

void ChannelProcessor::onFrameComplete(std::shared_ptr<FrameData> frame) {
    // 过滤掉无效帧
    if (!shouldProcessFrame(frame)) {
        return;
    }

    // 检查 phase_index 跳变 (0→2 is abnormal)
    checkPhaseIndexJump(frame->phaseIndex);

    // 将帧放入处理队列（非阻塞，满则丢弃）
    m_frameQueue->tryPush(frame);
}

bool ChannelProcessor::shouldProcessFrame(std::shared_ptr<FrameData> frame) const {
    if (!frame) {
        return false;
    }

    // frame_status = 0 (idle) 或 2 (transition) 时跳过
    if (frame->frameStatus == 0 || frame->frameStatus == 2) {
        return false;
    }

    // sample_point = 0 时跳过
    if (frame->samplePoint == 0) {
        return false;
    }

    return true;
}

void ChannelProcessor::checkPhaseIndexJump(uint8_t newPhaseIndex) {
    uint8_t lastPhase = m_lastPhaseIndex.load();

    // 检测异常跳变：正常顺序是 0→1→2→0
    // 如果 last=0 且 new=2，或者 last=2 且 new=1（反向），则为异常
    if (lastPhase == 0 && newPhaseIndex == 2) {
        // 异常跳变，清空缓存重新开始
        m_frameBuffer->clear();
        emit logMessage(QString("[%1] 检测到 phase_index 跳变 (0→2)，重置缓存").arg(m_channel));
    }

    m_lastPhaseIndex.store(newPhaseIndex);
}

void ChannelProcessor::processingThreadFunc() {
    while (m_running.load()) {
        // 从帧队列获取帧
        auto frameOpt = m_frameQueue->pop();
        if (!frameOpt.has_value()) {
            continue;
        }

        auto frame = frameOpt.value();

        // 获取当前参数
        ProcessingParams currentParams;
        {
            std::lock_guard<std::mutex> lock(m_paramsMutex);
            currentParams = m_params;
        }

        // 处理帧 (单帧成像，不改变原有逻辑)
        auto result = m_imageProcessor->processFrame(frame, currentParams, m_channel);

        if (!result) {
            continue;
        }

        // 将结果存入帧缓存（使用 frame 的 phaseIndex）
        m_frameBuffer->pushResult(result, frame->phaseIndex);

        // 检查是否需要融合输出
        if (m_frameBuffer->isComplete()) {
            auto frames = m_frameBuffer->getFramesForFusion();
            auto fusedImage = m_fusionProcessor->fuse(frames);

            // 创建融合结果
            auto fusedResult = std::make_shared<ProcessingResult>();
            fusedResult->imageData = std::move(fusedImage);
            fusedResult->channel = m_channel;
            fusedResult->phaseX = result->phaseX;
            fusedResult->phaseY = result->phaseY;
            fusedResult->width = 512;
            fusedResult->height = 512;

            // 使用融合后的结果
            result = fusedResult;
        }

        m_framesProcessed.fetch_add(1);
        emit imageReady(result);
    }
}

void ChannelProcessor::handleFusionOutput(std::shared_ptr<ProcessingResult> result) {
    // This method handles the fusion output when buffer is complete
    // The logic is integrated into processingThreadFunc
}

uint64_t ChannelProcessor::bytesReceived() const {
    return m_udpReceiver ? m_udpReceiver->bytesReceived() : 0;
}

uint64_t ChannelProcessor::packetsReceived() const {
    return m_udpReceiver ? m_udpReceiver->packetsReceived() : 0;
}