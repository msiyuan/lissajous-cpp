#include "ProtocolControlWidget.h"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QScrollArea>
#include <QTabWidget>
#include <QFrame>

ProtocolControlWidget::ProtocolControlWidget(QWidget* parent)
    : QWidget(parent) {
    setupUi();
    resetToDefaults();
}

ProtocolControlWidget::~ProtocolControlWidget() = default;

void ProtocolControlWidget::setupUi() {
    auto* mainLayout = new QVBoxLayout(this);

    auto* tabWidget = new QTabWidget();

    // ===== 寄存器设置页 =====
    auto* registerPage = new QWidget();
    auto* registerLayout = new QVBoxLayout(registerPage);

    auto* scrollArea = new QScrollArea();
    scrollArea->setWidgetResizable(true);

    auto* scrollWidget = new QWidget();
    auto* gridLayout = new QGridLayout(scrollWidget);
    gridLayout->setSpacing(5);

    // 添加寄存器行
    auto defaults = ProtocolCommands::getDefaultValues();
    int row = 0;

    // 帧参数
    gridLayout->addWidget(new QLabel("<b>帧参数</b>"), row++, 0, 1, 4);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_FP_ALL_POINT, "fp_all_point", defaults[ProtocolCommands::REG_FP_ALL_POINT]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_FP_VALID_POINT, "fp_valid_point", defaults[ProtocolCommands::REG_FP_VALID_POINT]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_SAMPLE_NUM, "sample_num", defaults[ProtocolCommands::REG_SAMPLE_NUM]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_ACQ_DELAY, "acq_delay", defaults[ProtocolCommands::REG_ACQ_DELAY]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_MEMS_EN, "mems_en", defaults[ProtocolCommands::REG_MEMS_EN]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_MEMS_START, "mems_start", defaults[ProtocolCommands::REG_MEMS_START]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_NORMAL_WORK_START, "normal_work_start", defaults[ProtocolCommands::REG_NORMAL_WORK_START]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_SWEEP_STOP, "sweep_stop", defaults[ProtocolCommands::REG_SWEEP_STOP]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_MANUAL_AD_SAMP, "manual_ad_samp", defaults[ProtocolCommands::REG_MANUAL_AD_SAMP]);

    // X轴扫频参数
    gridLayout->addWidget(new QLabel("<b>X轴扫频参数</b>"), row++, 0, 1, 4);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_SWEEP_START_FRE, "x_sweep_start_fre", defaults[ProtocolCommands::REG_X_SWEEP_START_FRE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_SWEEP_END_FRE, "x_sweep_end_fre", defaults[ProtocolCommands::REG_X_SWEEP_END_FRE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_SWEEP_FRE_STEP, "x_sweep_fre_step", defaults[ProtocolCommands::REG_X_SWEEP_FRE_STEP]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_SWEEP_INIT_PHASE, "x_sweep_init_phase", defaults[ProtocolCommands::REG_X_SWEEP_INIT_PHASE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_SWEEP_FRE_KEEP_NUM, "x_sweep_fre_keep_num", defaults[ProtocolCommands::REG_X_SWEEP_FRE_KEEP_NUM]);

    // X轴工作参数
    gridLayout->addWidget(new QLabel("<b>X轴工作参数</b>"), row++, 0, 1, 4);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_MIN, "x_min", defaults[ProtocolCommands::REG_X_MIN]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_MAX, "x_max", defaults[ProtocolCommands::REG_X_MAX]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_WORK_FRE, "x_work_fre", defaults[ProtocolCommands::REG_X_WORK_FRE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_WORK_INIT_PHASE, "x_work_init_phase", defaults[ProtocolCommands::REG_X_WORK_INIT_PHASE]);

    // Y轴扫频参数
    gridLayout->addWidget(new QLabel("<b>Y轴扫频参数</b>"), row++, 0, 1, 4);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_SWEEP_START_FRE, "y_sweep_start_fre", defaults[ProtocolCommands::REG_Y_SWEEP_START_FRE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_SWEEP_END_FRE, "y_sweep_end_fre", defaults[ProtocolCommands::REG_Y_SWEEP_END_FRE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_SWEEP_FRE_STEP, "y_sweep_fre_step", defaults[ProtocolCommands::REG_Y_SWEEP_FRE_STEP]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_SWEEP_INIT_PHASE, "y_sweep_init_phase", defaults[ProtocolCommands::REG_Y_SWEEP_INIT_PHASE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_SWEEP_FRE_KEEP_NUM, "y_sweep_fre_keep_num", defaults[ProtocolCommands::REG_Y_SWEEP_FRE_KEEP_NUM]);

    // Y轴工作参数
    gridLayout->addWidget(new QLabel("<b>Y轴工作参数</b>"), row++, 0, 1, 4);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_MIN, "y_min", defaults[ProtocolCommands::REG_Y_MIN]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_MAX, "y_max", defaults[ProtocolCommands::REG_Y_MAX]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_WORK_FRE, "y_work_fre", defaults[ProtocolCommands::REG_Y_WORK_FRE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_WORK_INIT_PHASE, "y_work_init_phase", defaults[ProtocolCommands::REG_Y_WORK_INIT_PHASE]);

    // 扩展控制参数
    gridLayout->addWidget(new QLabel("<b>扩展控制参数</b>"), row++, 0, 1, 4);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_SWEEP_REPEAT_NUM, "sweep_repeat_num", defaults[ProtocolCommands::REG_SWEEP_REPEAT_NUM]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_PHASE_ADD_VALUE, "x_phase_add_value", defaults[ProtocolCommands::REG_X_PHASE_ADD_VALUE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_AMPLITUDE_GAIN, "x_amplitude_gain", defaults[ProtocolCommands::REG_X_AMPLITUDE_GAIN]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_X_ZERO_OFFSET, "x_zero_offset", defaults[ProtocolCommands::REG_X_ZERO_OFFSET]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_PHASE_ADD_VALUE, "y_phase_add_value", defaults[ProtocolCommands::REG_Y_PHASE_ADD_VALUE]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_AMPLITUDE_GAIN, "y_amplitude_gain", defaults[ProtocolCommands::REG_Y_AMPLITUDE_GAIN]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_Y_ZERO_OFFSET, "y_zero_offset", defaults[ProtocolCommands::REG_Y_ZERO_OFFSET]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_AD_SAMP_PERIOD, "ad_samp_period", defaults[ProtocolCommands::REG_AD_SAMP_PERIOD]);
    createRegisterRow(gridLayout, row++, ProtocolCommands::REG_FF_INTERVAL_PERIOD, "ff_interval_period", defaults[ProtocolCommands::REG_FF_INTERVAL_PERIOD]);

    gridLayout->setRowStretch(row, 1);
    scrollArea->setWidget(scrollWidget);
    registerLayout->addWidget(scrollArea);

    // 全局按钮
    auto* globalBtnLayout = new QHBoxLayout();
    m_sendAllBtn = new QPushButton("发送所有");
    m_resetBtn = new QPushButton("重置默认");
    connect(m_sendAllBtn, &QPushButton::clicked, this, &ProtocolControlWidget::sendAllRegisters);
    connect(m_resetBtn, &QPushButton::clicked, this, &ProtocolControlWidget::resetToDefaults);
    globalBtnLayout->addWidget(m_sendAllBtn);
    globalBtnLayout->addWidget(m_resetBtn);
    globalBtnLayout->addStretch();
    registerLayout->addLayout(globalBtnLayout);

    tabWidget->addTab(registerPage, "寄存器设置");

    // ===== 控制启停页 =====
    auto* controlPage = new QWidget();
    auto* controlLayout = new QVBoxLayout(controlPage);
    controlLayout->addStretch();

    auto makeToggleButton = [](const QString& label,
                               const QString& style,
                               bool checkable) {
        auto* button = new QPushButton(label);
        button->setCheckable(checkable);
        button->setStyleSheet(style);
        button->setMinimumHeight(44);
        button->setMinimumWidth(110);
        return button;
    };

    m_startImagingBtn = makeToggleButton(
        "开始成像",
        "QPushButton { background-color: #4CAF50; color: white; font-size: 16px; font-weight: bold; padding: 12px; }",
        false);
    connect(m_startImagingBtn, &QPushButton::clicked, this, &ProtocolControlWidget::sendStartCommand);
    controlLayout->addWidget(m_startImagingBtn);

    m_stopImagingBtn = makeToggleButton(
        "结束成像",
        "QPushButton { background-color: #f44336; color: white; font-size: 16px; font-weight: bold; padding: 12px; }",
        false);
    connect(m_stopImagingBtn, &QPushButton::clicked, this, &ProtocolControlWidget::sendStopCommand);
    controlLayout->addWidget(m_stopImagingBtn);

    auto* separator = new QFrame();
    separator->setFrameShape(QFrame::VLine);
    controlLayout->addWidget(separator);

    m_memsEnBtn = makeToggleButton(
        "MEMS使能",
        "QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 12px; }"
        "QPushButton:checked { background-color: #0D47A1; }",
        true);
    connect(m_memsEnBtn, &QPushButton::toggled, this, &ProtocolControlWidget::toggleMemsEn);
    controlLayout->addWidget(m_memsEnBtn);

    m_memsStartBtn = makeToggleButton(
        "启动",
        "QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 12px; }"
        "QPushButton:checked { background-color: #E65100; }",
        true);
    connect(m_memsStartBtn, &QPushButton::toggled, this, &ProtocolControlWidget::toggleMemsStart);
    controlLayout->addWidget(m_memsStartBtn);

    m_normalWorkStartBtn = makeToggleButton(
        "正常工作",
        "QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 12px; }"
        "QPushButton:checked { background-color: #4A148C; }",
        true);
    connect(m_normalWorkStartBtn, &QPushButton::toggled, this, &ProtocolControlWidget::toggleNormalWorkStart);
    controlLayout->addWidget(m_normalWorkStartBtn);

    m_sweepStopBtn = makeToggleButton(
        "扫频停止",
        "QPushButton { background-color: #795548; color: white; font-weight: bold; padding: 12px; }"
        "QPushButton:checked { background-color: #3E2723; }",
        true);
    connect(m_sweepStopBtn, &QPushButton::toggled, this, &ProtocolControlWidget::toggleSweepStop);
    controlLayout->addWidget(m_sweepStopBtn);

    m_manualAdSampBtn = makeToggleButton(
        "AD采集",
        "QPushButton { background-color: #607D8B; color: white; font-weight: bold; padding: 12px; }"
        "QPushButton:checked { background-color: #263238; }",
        true);
    connect(m_manualAdSampBtn, &QPushButton::toggled, this, &ProtocolControlWidget::toggleManualAdSamp);
    controlLayout->addWidget(m_manualAdSampBtn);

    controlLayout->addStretch();

    tabWidget->addTab(controlPage, "控制启停");

    mainLayout->addWidget(tabWidget);
}

void ProtocolControlWidget::createRegisterRow(QGridLayout* layout, int row,
                                               uint16_t address, const QString& name,
                                               uint32_t defaultValue) {
    auto* label = new QLabel(name + ":");
    label->setToolTip(QString("地址: 0x%1").arg(address, 4, 16, QChar('0')).toUpper());
    auto* input = new QLineEdit(QString::number(defaultValue));
    input->setFixedWidth(100);
    auto* sendBtn = new QPushButton("发送");
    sendBtn->setFixedWidth(50);
    sendBtn->setProperty("address", address);

    connect(sendBtn, &QPushButton::clicked, this, &ProtocolControlWidget::onSendRegister);

    layout->addWidget(label, row, 0);
    layout->addWidget(input, row, 1);
    layout->addWidget(sendBtn, row, 2);

    m_registerInputs[address] = input;
    m_sendButtons[address] = sendBtn;
}

void ProtocolControlWidget::setUdpSender(std::shared_ptr<UdpSender> sender) {
    m_udpSender = sender;
}

void ProtocolControlWidget::setEnabled(bool enabled) {
    QWidget::setEnabled(enabled);
}

void ProtocolControlWidget::disableControls() {
    for (auto* input : m_registerInputs) {
        input->setEnabled(false);
    }
    for (auto* btn : findChildren<QPushButton*>()) {
        btn->setEnabled(false);
    }
}

void ProtocolControlWidget::enableControls() {
    for (auto* input : m_registerInputs) {
        input->setEnabled(true);
    }
    for (auto* btn : findChildren<QPushButton*>()) {
        btn->setEnabled(true);
    }
}

void ProtocolControlWidget::onSendRegister() {
    auto* btn = qobject_cast<QPushButton*>(sender());
    if (!btn || !m_udpSender) {
        emit logMessage("错误: UDP发送器未设置");
        return;
    }

    uint16_t address = btn->property("address").toUInt();
    auto* input = m_registerInputs.value(address);
    if (!input) return;

    uint32_t value = input->text().toUInt();
    QByteArray cmd = ProtocolCommands::buildRegisterCommand(address, value);

    if (m_udpSender->sendCommand(cmd)) {
        QString regName = ProtocolCommands::getRegisterName(address);
        QString hexStr = ProtocolCommands::commandToHexString(cmd);
        emit logMessage(QString("[发送成功] %1 (0x%2) = %3 -> 目标端口: 0x%4")
                       .arg(regName)
                       .arg(QString("%1").arg(address, 4, 16, QChar('0')).toUpper())
                       .arg(value)
                       .arg(QString("%1").arg(m_udpSender->targetPort(), 4, 16, QChar('0')).toUpper()));
        emit logMessage(QString("  命令: %1 (%2字节)").arg(hexStr).arg(cmd.size()));
        emit commandSent(cmd);
    } else {
        emit logMessage(QString("[发送失败] %1 - 请检查网络连接").arg(ProtocolCommands::getRegisterName(address)));
    }
}

void ProtocolControlWidget::sendStartCommand() {
    if (!m_udpSender) {
        emit logMessage("错误: UDP发送器未设置，请先启动接收");
        return;
    }

    QByteArray cmd = ProtocolCommands::buildStartCommand();
    if (m_udpSender->sendCommand(cmd)) {
        QString hexStr = ProtocolCommands::commandToHexString(cmd);
        emit logMessage(QString("[发送成功] 开始成像命令 (live=1, 地址=0x0801)"));
        emit logMessage(QString("  命令: %1").arg(hexStr));
        emit commandSent(cmd);
    } else {
        emit logMessage("[发送失败] 开始成像命令");
    }
}

bool ProtocolControlWidget::quickSetRegister(uint16_t address, uint32_t value) {
    if (!m_udpSender) {
        emit logMessage("错误: UDP发送器未设置，请先启动接收");
        return false;
    }

    const QByteArray cmd = ProtocolCommands::buildRegisterCommand(address, value);
    if (m_udpSender->sendCommand(cmd)) {
        emit logMessage(QString("快捷设置 %1 = %2")
            .arg(ProtocolCommands::getRegisterName(address))
            .arg(value));
        emit commandSent(cmd);
        return true;
    }

    emit logMessage(QString("快捷设置 %1 失败").arg(ProtocolCommands::getRegisterName(address)));
    return false;
}

void ProtocolControlWidget::toggleMemsEn(bool checked) {
    if (quickSetRegister(ProtocolCommands::REG_MEMS_EN, checked ? 1 : 0)) {
        emit logMessage(QString("[MEMS使能] %1").arg(checked ? "开启" : "关闭"));
    } else {
        m_memsEnBtn->setChecked(!checked);
    }
}

void ProtocolControlWidget::toggleMemsStart(bool checked) {
    if (quickSetRegister(ProtocolCommands::REG_MEMS_START, checked ? 1 : 0)) {
        emit logMessage(QString("[启动] %1").arg(checked ? "开启" : "关闭"));
    } else {
        m_memsStartBtn->setChecked(!checked);
    }
}

void ProtocolControlWidget::toggleNormalWorkStart(bool checked) {
    if (quickSetRegister(ProtocolCommands::REG_NORMAL_WORK_START, checked ? 1 : 0)) {
        emit logMessage(QString("[正常工作] %1").arg(checked ? "开启" : "关闭"));
    } else {
        m_normalWorkStartBtn->setChecked(!checked);
    }
}

void ProtocolControlWidget::toggleSweepStop(bool checked) {
    if (quickSetRegister(ProtocolCommands::REG_SWEEP_STOP, checked ? 1 : 0)) {
        emit logMessage(QString("[扫频停止] %1").arg(checked ? "开启" : "关闭"));
    } else {
        m_sweepStopBtn->setChecked(!checked);
    }
}

void ProtocolControlWidget::toggleManualAdSamp(bool checked) {
    if (quickSetRegister(ProtocolCommands::REG_MANUAL_AD_SAMP, checked ? 1 : 0)) {
        emit logMessage(QString("[AD采集] %1").arg(checked ? "开启" : "关闭"));
    } else {
        m_manualAdSampBtn->setChecked(!checked);
    }
}

void ProtocolControlWidget::sendStopCommand() {
    if (!m_udpSender) {
        emit logMessage("错误: UDP发送器未设置，请先启动接收");
        return;
    }

    QByteArray cmd = ProtocolCommands::buildStopCommand();
    if (m_udpSender->sendCommand(cmd)) {
        QString hexStr = ProtocolCommands::commandToHexString(cmd);
        emit logMessage(QString("[发送成功] 停止成像命令 (exit=1, 地址=0x0802)"));
        emit logMessage(QString("  命令: %1").arg(hexStr));
        emit commandSent(cmd);
    } else {
        emit logMessage("[发送失败] 停止成像命令");
    }
}

void ProtocolControlWidget::sendAllRegisters() {
    if (!m_udpSender) {
        emit logMessage("错误: UDP发送器未设置，请先启动接收");
        return;
    }

    // 按照Python版本的顺序发送寄存器，确保依赖关系正确
    QList<uint16_t> registerOrder = {
        ProtocolCommands::REG_FP_ALL_POINT,
        ProtocolCommands::REG_FP_VALID_POINT,
        ProtocolCommands::REG_SAMPLE_NUM,
        ProtocolCommands::REG_ACQ_DELAY,
        ProtocolCommands::REG_X_SWEEP_START_FRE,
        ProtocolCommands::REG_X_SWEEP_END_FRE,
        ProtocolCommands::REG_X_SWEEP_FRE_STEP,
        ProtocolCommands::REG_X_SWEEP_INIT_PHASE,
        ProtocolCommands::REG_X_SWEEP_FRE_KEEP_NUM,
        ProtocolCommands::REG_X_MIN,
        ProtocolCommands::REG_X_MAX,
        ProtocolCommands::REG_X_WORK_FRE,
        ProtocolCommands::REG_X_WORK_INIT_PHASE,
        ProtocolCommands::REG_Y_SWEEP_START_FRE,
        ProtocolCommands::REG_Y_SWEEP_END_FRE,
        ProtocolCommands::REG_Y_SWEEP_FRE_STEP,
        ProtocolCommands::REG_Y_SWEEP_INIT_PHASE,
        ProtocolCommands::REG_Y_SWEEP_FRE_KEEP_NUM,
        ProtocolCommands::REG_Y_MIN,
        ProtocolCommands::REG_Y_MAX,
        ProtocolCommands::REG_Y_WORK_FRE,
        ProtocolCommands::REG_Y_WORK_INIT_PHASE,
        ProtocolCommands::REG_SWEEP_REPEAT_NUM,
        ProtocolCommands::REG_X_PHASE_ADD_VALUE,
        ProtocolCommands::REG_X_AMPLITUDE_GAIN,
        ProtocolCommands::REG_X_ZERO_OFFSET,
        ProtocolCommands::REG_Y_PHASE_ADD_VALUE,
        ProtocolCommands::REG_Y_AMPLITUDE_GAIN,
        ProtocolCommands::REG_Y_ZERO_OFFSET,
        ProtocolCommands::REG_AD_SAMP_PERIOD,
        ProtocolCommands::REG_FF_INTERVAL_PERIOD
    };

    int successCount = 0;
    int totalCount = registerOrder.size();

    emit logMessage(QString("开始发送所有寄存器 (共%1个) -> 目标端口: 0x%2...")
                   .arg(totalCount)
                   .arg(QString("%1").arg(m_udpSender->targetPort(), 4, 16, QChar('0')).toUpper()));

    for (uint16_t address : registerOrder) {
        if (!m_registerInputs.contains(address)) {
            continue;
        }

        uint32_t value = m_registerInputs[address]->text().toUInt();
        QByteArray cmd = ProtocolCommands::buildRegisterCommand(address, value);
        QString regName = ProtocolCommands::getRegisterName(address);
        QString hexStr = ProtocolCommands::commandToHexString(cmd);

        if (m_udpSender->sendCommand(cmd)) {
            successCount++;
            emit logMessage(QString("  [OK] %1 (0x%2) = %3")
                           .arg(regName)
                           .arg(QString("%1").arg(address, 4, 16, QChar('0')).toUpper())
                           .arg(value));
            emit logMessage(QString("       命令: %1").arg(hexStr));
        } else {
            emit logMessage(QString("  [失败] %1 - 请检查网络连接")
                           .arg(regName));
        }
    }

    emit logMessage(QString("寄存器设置完成: 成功 %1/%2").arg(successCount).arg(totalCount));
}

void ProtocolControlWidget::resetToDefaults() {
    auto defaults = ProtocolCommands::getDefaultValues();
    for (auto it = defaults.begin(); it != defaults.end(); ++it) {
        if (m_registerInputs.contains(it.key())) {
            m_registerInputs[it.key()]->setText(QString::number(it.value()));
        }
    }
    emit logMessage("已重置所有寄存器为默认值");
}
