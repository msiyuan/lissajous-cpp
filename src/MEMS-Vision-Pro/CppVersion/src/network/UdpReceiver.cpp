#include "UdpReceiver.h"
#include <QNetworkDatagram>
#include <QVariant>

UdpReceiver::UdpReceiver(uint16_t port, const QString& channel,
                         std::shared_ptr<ThreadSafeQueue<QByteArray>> queue,
                         QObject* parent)
    : QThread(parent)
    , m_port(port)
    , m_channel(channel)
    , m_queue(queue) {
}

UdpReceiver::~UdpReceiver() {
    stop();
    wait();
}

void UdpReceiver::stop() {
    m_running.store(false);
}

void UdpReceiver::resetCounters() {
    m_bytesReceived.store(0);
    m_packetsReceived.store(0);
}

void UdpReceiver::run() {
    QUdpSocket socket;

    // 绑定端口（与Python版本一致：绑定所有接口，并启用端口重用）
    // ReuseAddressHint对应Python的SO_REUSEADDR
    if (!socket.bind(QHostAddress::Any, m_port, QAbstractSocket::ReuseAddressHint)) {
        emit errorOccurred(QString("[%1] 绑定端口 0x%2 失败: %3")
                          .arg(m_channel)
                          .arg(m_port, 4, 16, QChar('0'))
                          .arg(socket.errorString()));
        return;
    }

    // 设置接收缓冲区大小（与Python版本SOCKET_RECV_BUFFER一致）
    socket.setSocketOption(QAbstractSocket::ReceiveBufferSizeSocketOption, QVariant(Config::SOCKET_RECV_BUFFER));

    emit logMessage(QString("[%1] UDP 接收器启动，端口 0x%2")
                   .arg(m_channel)
                   .arg(m_port, 4, 16, QChar('0')));

    m_running.store(true);

    while (m_running.load()) {
        // 等待数据，100ms 超时
        if (socket.waitForReadyRead(100)) {
            while (socket.hasPendingDatagrams()) {
                QNetworkDatagram datagram = socket.receiveDatagram();
                QByteArray data = datagram.data();

                if (!data.isEmpty()) {
                    // 尝试放入队列（非阻塞）
                    if (m_queue->tryPush(data)) {
                        m_bytesReceived.fetch_add(data.size());
                        m_packetsReceived.fetch_add(1);
                        emit packetReceived(data.size());
                    }
                    // 队列满则丢弃，避免阻塞
                }
            }
        }
    }

    socket.close();
    emit logMessage(QString("[%1] UDP 接收器已停止").arg(m_channel));
}
