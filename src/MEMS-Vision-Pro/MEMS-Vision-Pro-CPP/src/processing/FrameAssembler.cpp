#include "FrameAssembler.h"
#include <QDataStream>

FrameAssembler::FrameAssembler(const QString& channel,
                               std::shared_ptr<ThreadSafeQueue<QByteArray>> inputQueue,
                               QObject* parent)
    : QThread(parent)
    , m_channel(channel)
    , m_inputQueue(inputQueue) {
}

FrameAssembler::~FrameAssembler() {
    stop();
    wait();
}

void FrameAssembler::stop() {
    m_running.store(false);
    m_inputQueue->stop();
}

void FrameAssembler::resetCounters() {
    m_framesAssembled.store(0);
}

void FrameAssembler::run() {
    emit logMessage(QString("[%1] 帧组装器启动").arg(m_channel));
    m_running.store(true);
    m_lastPacketTime = std::chrono::steady_clock::now();

    while (m_running.load()) {
        // 批量获取数据包
        auto packets = m_inputQueue->popBatch(1000);

        if (packets.empty()) {
            // 检查帧超时
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                now - m_lastPacketTime).count();

            if (m_currentFrame && elapsed > Config::FRAME_TIMEOUT_MS) {
                finalizeCurrentFrame();
            }

            // 短暂休眠避免空转
            QThread::msleep(1);
            continue;
        }

        m_lastPacketTime = std::chrono::steady_clock::now();

        for (const auto& packet : packets) {
            processPacket(packet);
        }
    }

    // 结束时处理剩余帧
    if (m_currentFrame) {
        finalizeCurrentFrame();
    }

    emit logMessage(QString("[%1] 帧组装器已停止").arg(m_channel));
}

void FrameAssembler::processPacket(const QByteArray& packet) {
    if (packet.size() < 2) {
        return;
    }

    if (isFrameHeader(packet)) {
        // 收到新帧头，先完成当前帧
        if (m_currentFrame && !m_currentFrame->packets.empty()) {
            finalizeCurrentFrame();
        }
        startNewFrame(packet);
    } else if (isDataPacket(packet)) {
        // 数据包添加到当前帧
        if (m_currentFrame) {
            m_currentFrame->packets.push_back(packet);
        }
    }
}

bool FrameAssembler::isFrameHeader(const QByteArray& packet) const {
    if (packet.size() < 2) return false;
    uint16_t magic = (static_cast<uint8_t>(packet[0]) << 8) |
                      static_cast<uint8_t>(packet[1]);
    return magic == Config::FRAME_HEADER_MAGIC;
}

bool FrameAssembler::isDataPacket(const QByteArray& packet) const {
    if (packet.size() < 2) return false;
    uint16_t magic = (static_cast<uint8_t>(packet[0]) << 8) |
                      static_cast<uint8_t>(packet[1]);
    return magic == Config::PACKET_HEADER_MAGIC;
}

void FrameAssembler::startNewFrame(const QByteArray& headerPacket) {
    m_currentFrame = std::make_shared<FrameData>();
    m_currentFrame->timestamp = std::chrono::steady_clock::now();
    m_currentFrame->packets.push_back(headerPacket);

    // 解析帧头
    // 格式: 0x2AFF(2) + FrameCnt(2) + SamplePoint(4) + PhaseX(4) + PhaseY(4)
    if (headerPacket.size() >= 16) {
        const uint8_t* data = reinterpret_cast<const uint8_t*>(headerPacket.constData());

        m_currentFrame->frameId = (data[2] << 8) | data[3];

        m_currentFrame->samplePoint = (data[4] << 24) | (data[5] << 16) |
                                       (data[6] << 8) | data[7];

        m_currentFrame->phaseX = (data[8] << 24) | (data[9] << 16) |
                                  (data[10] << 8) | data[11];

        m_currentFrame->phaseY = (data[12] << 24) | (data[13] << 16) |
                                  (data[14] << 8) | data[15];

        // 限制采样点数
        if (m_currentFrame->samplePoint > 2000000) {
            m_currentFrame->samplePoint = 1000000;
        }
    }
}

void FrameAssembler::finalizeCurrentFrame() {
    if (!m_currentFrame || m_currentFrame->packets.empty()) {
        m_currentFrame.reset();
        return;
    }

    m_framesAssembled.fetch_add(1);
    emit frameComplete(m_currentFrame);
    m_currentFrame.reset();
}
