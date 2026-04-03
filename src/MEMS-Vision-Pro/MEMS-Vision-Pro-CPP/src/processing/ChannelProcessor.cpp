#include "ChannelProcessor.h"

ChannelProcessor::ChannelProcessor(const QString& channel, uint16_t port, QObject* parent)
    : QObject(parent)
    , m_channel(channel)
    , m_port(port) {

    // 创建队列
    m_packetQueue = std::make_shared<ThreadSafeQueue<QByteArray>>(Config::QUEUE_MAX_SIZE);
    m_frameQueue = std::make_shared<ThreadSafeQueue<std::shared_ptr<FrameData>>>(100);

    // 创建图像处理器
    m_imageProcessor = std::make_unique<ImageProcessor>();
}

ChannelProcessor::~ChannelProcessor() {
    stop();
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
    m_udpReceiver->start();

    // 创建并启动帧组装器
    m_frameAssembler = std::make_unique<FrameAssembler>(m_channel, m_packetQueue);
    connect(m_frameAssembler.get(), &FrameAssembler::logMessage,
            this, &ChannelProcessor::logMessage);
    connect(m_frameAssembler.get(), &FrameAssembler::frameComplete,
            this, &ChannelProcessor::onFrameComplete);
    m_frameAssembler->start();

    // 启动图像处理线程
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
    // 将帧放入处理队列（非阻塞，满则丢弃）
    m_frameQueue->tryPush(frame);
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

        // 处理帧
        auto result = m_imageProcessor->processFrame(frame, currentParams, m_channel);

        if (result) {
            m_framesProcessed.fetch_add(1);
            emit imageReady(result);
        }
    }
}

uint64_t ChannelProcessor::bytesReceived() const {
    return m_udpReceiver ? m_udpReceiver->bytesReceived() : 0;
}

uint64_t ChannelProcessor::packetsReceived() const {
    return m_udpReceiver ? m_udpReceiver->packetsReceived() : 0;
}
