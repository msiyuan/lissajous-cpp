#ifndef PROTOCOL_CONTROL_WIDGET_H
#define PROTOCOL_CONTROL_WIDGET_H

#include <QWidget>
#include <QGroupBox>
#include <QLineEdit>
#include <QPushButton>
#include <QGridLayout>
#include <QMap>
#include <memory>
#include "network/UdpSender.h"
#include "network/ProtocolCommands.h"

/**
 * 协议控制界面
 * 用于设置和发送寄存器命令
 */
class ProtocolControlWidget : public QWidget {
    Q_OBJECT

public:
    explicit ProtocolControlWidget(QWidget* parent = nullptr);
    ~ProtocolControlWidget() override;

    void setUdpSender(std::shared_ptr<UdpSender> sender);
    void setEnabled(bool enabled);

signals:
    void logMessage(const QString& message);
    void commandSent(const QByteArray& command);

public slots:
    void sendStartCommand();
    void sendStopCommand();
    void sendAllRegisters();
    void resetToDefaults();

private slots:
    void onSendRegister();

private:
    void setupUi();
    void createRegisterRow(QGridLayout* layout, int row,
                           uint16_t address, const QString& name, uint32_t defaultValue);

    std::shared_ptr<UdpSender> m_udpSender;
    QMap<uint16_t, QLineEdit*> m_registerInputs;
    QMap<uint16_t, QPushButton*> m_sendButtons;

    QPushButton* m_startBtn;
    QPushButton* m_stopBtn;
    QPushButton* m_sendAllBtn;
    QPushButton* m_resetBtn;
};

#endif  // PROTOCOL_CONTROL_WIDGET_H
