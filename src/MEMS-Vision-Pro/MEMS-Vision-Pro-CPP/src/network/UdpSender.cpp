#include "UdpSender.h"

UdpSender::UdpSender(const QString& targetIp, uint16_t targetPort, QObject* parent)
    : QObject(parent)
    , m_targetIp(targetIp)
    , m_targetPort(targetPort) {
}

UdpSender::~UdpSender() {
    // 不再需要关闭socket，因为使用临时socket
}

bool UdpSender::sendCommand(const QByteArray& command) {
    // 每次发送都创建新的临时socket（与Python版本一致）
    QUdpSocket socket;
    QHostAddress address(m_targetIp);

    // 发送数据
    qint64 bytesSent = socket.writeDatagram(command, address, m_targetPort);

    bool success = (bytesSent == command.size());

    if (success) {
        emit logMessage(QString("发送命令成功: %1 字节 -> %2:0x%3")
                       .arg(bytesSent)
                       .arg(m_targetIp)
                       .arg(m_targetPort, 4, 16, QChar('0')));
    } else {
        emit logMessage(QString("发送命令失败: %1").arg(socket.errorString()));
    }

    emit commandSent(command, success);

    // socket会在函数结束时自动销毁（与Python版本sock.close()一致）
    return success;
}

void UdpSender::setTargetIp(const QString& ip) {
    m_targetIp = ip;
}

void UdpSender::setTargetPort(uint16_t port) {
    m_targetPort = port;
}
