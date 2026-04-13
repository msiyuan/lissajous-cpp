#ifndef UDP_RECEIVER_H
#define UDP_RECEIVER_H

#include <QThread>
#include <QUdpSocket>
#include <QByteArray>
#include <atomic>
#include <memory>
#include "utils/ThreadSafeQueue.h"
#include "config/Constants.h"

/**
 * UDP 数据包接收器
 * 独立线程接收 UDP 数据包，放入线程安全队列
 */
class UdpReceiver : public QThread {
    Q_OBJECT

public:
    explicit UdpReceiver(uint16_t port, const QString& channel,
                         std::shared_ptr<ThreadSafeQueue<QByteArray>> queue,
                         QObject* parent = nullptr);
    ~UdpReceiver() override;

    void stop();
    bool isRunning() const { return m_running.load(); }
    uint64_t bytesReceived() const { return m_bytesReceived.load(); }
    uint64_t packetsReceived() const { return m_packetsReceived.load(); }
    void resetCounters();

signals:
    void packetReceived(uint64_t bytes);
    void logMessage(const QString& message);
    void errorOccurred(const QString& error);

protected:
    void run() override;

private:
    uint16_t m_port;
    QString m_channel;
    std::shared_ptr<ThreadSafeQueue<QByteArray>> m_queue;

    std::atomic<bool> m_running{false};
    std::atomic<uint64_t> m_bytesReceived{0};
    std::atomic<uint64_t> m_packetsReceived{0};
};

#endif  // UDP_RECEIVER_H
