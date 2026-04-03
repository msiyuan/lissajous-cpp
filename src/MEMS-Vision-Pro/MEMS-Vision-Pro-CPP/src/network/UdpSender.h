#ifndef UDP_SENDER_H
#define UDP_SENDER_H

#include <QObject>
#include <QUdpSocket>
#include <QHostAddress>
#include <cstdint>

/**
 * UDP 命令发送器
 * 用于向下位机发送控制命令
 */
class UdpSender : public QObject {
    Q_OBJECT

public:
    explicit UdpSender(const QString& targetIp, uint16_t targetPort = 0x8004,
                       QObject* parent = nullptr);
    ~UdpSender() override;

    bool sendCommand(const QByteArray& command);
    void setTargetIp(const QString& ip);
    void setTargetPort(uint16_t port);

    QString targetIp() const { return m_targetIp; }
    uint16_t targetPort() const { return m_targetPort; }

signals:
    void commandSent(const QByteArray& command, bool success);
    void logMessage(const QString& message);

private:
    QString m_targetIp;
    uint16_t m_targetPort;
};

#endif  // UDP_SENDER_H
