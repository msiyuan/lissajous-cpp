#include "MainWindow.h"
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QSplitter>
#include <QScrollArea>
#include <QDateTime>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent) {
    setupUi();
    setupConnections();

    // 初始化默认参数（与 msy_code0409 的 DEFAULT_IMAGE_PARAMS 对齐）
    m_currentParams.freqX = Config::DEFAULT_FREQ_X;
    m_currentParams.freqY = Config::DEFAULT_FREQ_Y;
    m_currentParams.deltaPhaseX = 0.0;
    m_currentParams.deltaPhaseY = 0.0;

    // 数据保存器
    m_dataSaver = std::make_unique<DataSaver>();

    // 统计定时器
    m_statsTimer = new QTimer(this);
    connect(m_statsTimer, &QTimer::timeout, this, &MainWindow::updateStats);
}

MainWindow::~MainWindow() {
    onStopReceiver();
}

void MainWindow::setupUi() {
    setWindowTitle("MEMS-Vision-Pro (C++ 版本)");
    resize(1800, 1000);
    setMinimumSize(1600, 900);

    auto* centralWidget = new QWidget();
    auto* mainLayout = new QHBoxLayout(centralWidget);

    // ===== 左侧：图像显示和控制 =====
    auto* leftWidget = new QWidget();
    auto* leftLayout = new QVBoxLayout(leftWidget);

    // 顶部控制区域
    auto* controlGroup = new QGroupBox("参数设置");
    auto* controlLayout = new QHBoxLayout(controlGroup);

    // IP 设置 (默认IP与Python版本保持一致: 192.168.1.91)
    controlLayout->addWidget(new QLabel("目标IP:"));
    m_ipInput = new QLineEdit("192.168.1.91");
    m_ipInput->setFixedWidth(120);
    controlLayout->addWidget(m_ipInput);

    // 相位设置
    controlLayout->addWidget(new QLabel("X相位:"));
    m_phaseXInput = new QLineEdit("0.0");
    m_phaseXInput->setFixedWidth(60);
    controlLayout->addWidget(m_phaseXInput);

    controlLayout->addWidget(new QLabel("Y相位:"));
    m_phaseYInput = new QLineEdit("0.0");
    m_phaseYInput->setFixedWidth(60);
    controlLayout->addWidget(m_phaseYInput);

    // 频率设置（默认值为协议工作频率的一半）
    controlLayout->addWidget(new QLabel("X频率:"));
    m_freqXInput = new QLineEdit(QString::number(Config::DEFAULT_FREQ_X, 'f', 0));
    m_freqXInput->setFixedWidth(60);
    controlLayout->addWidget(m_freqXInput);

    controlLayout->addWidget(new QLabel("Y频率:"));
    m_freqYInput = new QLineEdit(QString::number(Config::DEFAULT_FREQ_Y, 'f', 0));
    m_freqYInput->setFixedWidth(60);
    controlLayout->addWidget(m_freqYInput);

    // 应用参数按钮
    m_applyParamsBtn = new QPushButton("应用参数");
    connect(m_applyParamsBtn, &QPushButton::clicked, this, &MainWindow::onParamsChanged);
    controlLayout->addWidget(m_applyParamsBtn);

    controlLayout->addStretch();
    leftLayout->addWidget(controlGroup);

    // 启动/停止/保存按钮
    auto* btnLayout = new QHBoxLayout();

    m_startBtn = new QPushButton("启动双通道接收");
    m_startBtn->setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px; }");
    connect(m_startBtn, &QPushButton::clicked, this, &MainWindow::onStartReceiver);
    btnLayout->addWidget(m_startBtn);

    m_stopBtn = new QPushButton("停止接收");
    m_stopBtn->setEnabled(false);
    m_stopBtn->setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 8px 16px; }");
    connect(m_stopBtn, &QPushButton::clicked, this, &MainWindow::onStopReceiver);
    btnLayout->addWidget(m_stopBtn);

    m_saveImageBtn = new QPushButton("保存图像");
    m_saveImageBtn->setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px 16px; }");
    connect(m_saveImageBtn, &QPushButton::clicked, this, &MainWindow::onSaveImage);
    btnLayout->addWidget(m_saveImageBtn);

    m_saveRawBtn = new QPushButton("保存原始数据");
    m_saveRawBtn->setStyleSheet("QPushButton { background-color: #607D8B; color: white; font-weight: bold; padding: 8px 16px; }");
    connect(m_saveRawBtn, &QPushButton::clicked, this, &MainWindow::onSaveRawData);
    btnLayout->addWidget(m_saveRawBtn);

    m_saveStackBtn = new QPushButton("录制堆栈");
    m_saveStackBtn->setCheckable(true);
    m_saveStackBtn->setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px; }");
    connect(m_saveStackBtn, &QPushButton::clicked, this, &MainWindow::onSaveStack);
    btnLayout->addWidget(m_saveStackBtn);

    btnLayout->addStretch();
    leftLayout->addLayout(btnLayout);

    auto* fusionLayout = new QHBoxLayout();
    fusionLayout->addStretch();

    m_frameFusionBtn = new QPushButton("多帧融合");
    m_frameFusionBtn->setCheckable(true);
    m_frameFusionBtn->setStyleSheet("QPushButton { background-color: #009688; color: white; font-weight: bold; padding: 8px 16px; }"
                                    "QPushButton:checked { background-color: #00695C; }");
    connect(m_frameFusionBtn, &QPushButton::toggled, this, &MainWindow::onFrameFusionToggled);
    fusionLayout->addWidget(m_frameFusionBtn);

    fusionLayout->addWidget(new QLabel("融合帧数:"));
    m_frameFusionCountSpin = new QSpinBox();
    m_frameFusionCountSpin->setRange(1, 10);
    m_frameFusionCountSpin->setValue(3);
    connect(m_frameFusionCountSpin, qOverload<int>(&QSpinBox::valueChanged),
            this, &MainWindow::onFrameFusionCountChanged);
    fusionLayout->addWidget(m_frameFusionCountSpin);

    leftLayout->addLayout(fusionLayout);

    // 中间图像显示区域
    auto* imageSplitter = new QSplitter(Qt::Horizontal);

    // 通道1
    m_displayCh1 = new ImageDisplayWidget("通道1 (0x8001)", "ch1");
    auto* scroll1 = new QScrollArea();
    scroll1->setWidget(m_displayCh1);
    scroll1->setWidgetResizable(true);
    imageSplitter->addWidget(scroll1);

    // 通道2
    m_displayCh2 = new ImageDisplayWidget("通道2 (0x8000)", "ch2");
    auto* scroll2 = new QScrollArea();
    scroll2->setWidget(m_displayCh2);
    scroll2->setWidgetResizable(true);
    imageSplitter->addWidget(scroll2);

    leftLayout->addWidget(imageSplitter, 1);

    // 状态栏（包含帧率显示）
    auto* statusLayout = new QHBoxLayout();

    m_statsLabel = new QLabel("就绪");
    m_statsLabel->setStyleSheet("color: gray; font-size: 12px;");
    statusLayout->addWidget(m_statsLabel);

    // 帧率显示（与Python版本一致）
    m_fpsLabel = new QLabel("双通道重建帧率: 0 FPS");
    m_fpsLabel->setStyleSheet("font-size: 14px; color: green; font-weight: bold;");
    statusLayout->addWidget(m_fpsLabel);

    statusLayout->addStretch();
    leftLayout->addLayout(statusLayout);

    // 日志区域
    auto* logGroup = new QGroupBox("系统日志");
    auto* logLayout = new QVBoxLayout(logGroup);
    m_logText = new QTextEdit();
    m_logText->setReadOnly(true);
    m_logText->setMaximumHeight(120);
    logLayout->addWidget(m_logText);
    leftLayout->addWidget(logGroup);

    // ===== 右侧：协议控制标签页 =====
    m_controlTabs = new QTabWidget();
    m_controlTabs->setMinimumWidth(450);
    m_controlTabs->setMaximumWidth(550);

    // 协议控制界面
    m_protocolControl = new ProtocolControlWidget();
    connect(m_protocolControl, &ProtocolControlWidget::logMessage,
            this, &MainWindow::onLogMessage);
    m_controlTabs->addTab(m_protocolControl, "协议命令控制");

    // 添加到主布局
    mainLayout->addWidget(leftWidget, 1);
    mainLayout->addWidget(m_controlTabs);

    setCentralWidget(centralWidget);
}

void MainWindow::setupConnections() {
    // IP变化时更新UDP发送器 (与Python版本一致)
    connect(m_ipInput, &QLineEdit::textChanged, this, &MainWindow::updateSenderIp);

    // 初始创建UDP发送器 (与Python版本一致：进入就能发送)
    updateSenderIp();
}

QString MainWindow::makeTimestamp() const {
    return QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
}

void MainWindow::setProtocolControlsEnabled(bool enabled) {
    if (enabled) {
        m_protocolControl->enableControls();
    } else {
        m_protocolControl->disableControls();
    }
}

void MainWindow::resetFpsWindow() {
    m_fpsTracker.reset();
    updateFpsLabel(0);
}

void MainWindow::resetDisplayFusion() {
    m_displayFusionCh1.clear();
    m_displayFusionCh2.clear();
}

void MainWindow::refreshDisplayFromLatestResults() {
    if (m_latestResultCh1) {
        auto displayResult = std::make_shared<ProcessingResult>(*m_latestResultCh1);
        displayResult->imageData = m_displayFusionCh1.addFrame(m_latestResultCh1->imageData);
        m_displayCh1->setImage(displayResult);
    }

    if (m_latestResultCh2) {
        auto displayResult = std::make_shared<ProcessingResult>(*m_latestResultCh2);
        displayResult->imageData = m_displayFusionCh2.addFrame(m_latestResultCh2->imageData);
        m_displayCh2->setImage(displayResult);
    }
}

ChannelCounters MainWindow::currentCountersFor(const std::unique_ptr<ChannelProcessor>& processor) const {
    ChannelCounters counters;
    if (!processor) {
        return counters;
    }

    counters.bytes = processor->bytesReceived();
    counters.packets = processor->packetsReceived();
    counters.frames = processor->framesProcessed();
    return counters;
}

void MainWindow::updateFpsLabel(int fps) {
    m_fpsLabel->setText(QString("双通道重建帧率: %1 FPS").arg(fps));

    QString color;
    if (fps > 10) {
        color = "green";
    } else if (fps > 5) {
        color = "orange";
    } else {
        color = "red";
    }
    m_fpsLabel->setStyleSheet(QString("font-size: 14px; color: %1; font-weight: bold;").arg(color));
}

void MainWindow::onStartReceiver() {
    if (!m_sessionState.startImaging()) {
        onLogMessage("双通道接收已在运行，忽略重复启动");
        return;
    }

    resetFpsWindow();
    m_imageStackCh1.clear();
    m_imageStackCh2.clear();
    resetDisplayFusion();
    m_latestResultCh1.reset();
    m_latestResultCh2.reset();

    // 创建通道处理器
    m_processorCh1 = std::make_unique<ChannelProcessor>("ch1", Config::UDP_PORT_CH1);
    m_processorCh2 = std::make_unique<ChannelProcessor>("ch2", Config::UDP_PORT_CH2);

    // 连接信号
    connect(m_processorCh1.get(), &ChannelProcessor::imageReady,
            this, &MainWindow::onImageReady, Qt::QueuedConnection);
    connect(m_processorCh2.get(), &ChannelProcessor::imageReady,
            this, &MainWindow::onImageReady, Qt::QueuedConnection);
    connect(m_processorCh1.get(), &ChannelProcessor::logMessage,
            this, &MainWindow::onLogMessage, Qt::QueuedConnection);
    connect(m_processorCh2.get(), &ChannelProcessor::logMessage,
            this, &MainWindow::onLogMessage, Qt::QueuedConnection);

    // 设置参数
    onParamsChanged();

    // 启动处理器
    m_processorCh1->start();
    m_processorCh2->start();

    // 启动统计定时器
    m_statsTimer->start(1000);

    // 更新 UI
    m_startBtn->setEnabled(false);
    m_stopBtn->setEnabled(true);

    // 禁用协议控制 (与Python版本一致：接收时不能发送命令)
    setProtocolControlsEnabled(false);

    onLogMessage("双通道接收已启动");
}

void MainWindow::onStopReceiver() {
    if (m_sessionState.stackRecording()) {
        m_saveStackBtn->setChecked(false);
        onSaveStack();
    }
    m_sessionState.stopImaging();
    m_statsTimer->stop();

    if (m_processorCh1) {
        m_processorCh1->stop();
        m_processorCh1.reset();
    }

    if (m_processorCh2) {
        m_processorCh2->stop();
        m_processorCh2.reset();
    }

    // 启用协议控制 (与Python版本一致：停止接收后可以发送命令)
    setProtocolControlsEnabled(true);

    m_startBtn->setEnabled(true);
    m_stopBtn->setEnabled(false);
    resetFpsWindow();
    resetDisplayFusion();
    m_latestResultCh1.reset();
    m_latestResultCh2.reset();

    onLogMessage("双通道接收已停止");
}

void MainWindow::onImageReady(std::shared_ptr<ProcessingResult> result) {
    if (!result) return;

    auto now = std::chrono::steady_clock::now();
    m_fpsTracker.recordFrame(result->channel, now);

    if (result->channel == "ch1") {
        m_latestResultCh1 = result;
        appendToStackIfRecording("ch1", result->imageData);
        auto displayResult = std::make_shared<ProcessingResult>(*result);
        displayResult->imageData = m_displayFusionCh1.addFrame(result->imageData);
        m_displayCh1->setImage(displayResult);
    } else if (result->channel == "ch2") {
        m_latestResultCh2 = result;
        appendToStackIfRecording("ch2", result->imageData);
        auto displayResult = std::make_shared<ProcessingResult>(*result);
        displayResult->imageData = m_displayFusionCh2.addFrame(result->imageData);
        m_displayCh2->setImage(displayResult);
    }
}

void MainWindow::onLogMessage(const QString& message) {
    m_logText->append(QDateTime::currentDateTime().toString("[hh:mm:ss] ") + message);
}

void MainWindow::onParamsChanged() {
    m_currentParams.deltaPhaseX = m_phaseXInput->text().toDouble();
    m_currentParams.deltaPhaseY = m_phaseYInput->text().toDouble();
    m_currentParams.freqX = m_freqXInput->text().toDouble();
    m_currentParams.freqY = m_freqYInput->text().toDouble();

    if (m_processorCh1) {
        m_processorCh1->setParams(m_currentParams);
    }
    if (m_processorCh2) {
        m_processorCh2->setParams(m_currentParams);
    }

    onLogMessage(QString("共享参数已更新: X相位=%1°, Y相位=%2°, X频率=%3, Y频率=%4")
                .arg(m_currentParams.deltaPhaseX)
                .arg(m_currentParams.deltaPhaseY)
                .arg(m_currentParams.freqX)
                .arg(m_currentParams.freqY));
}

void MainWindow::updateStats() {
    const ChannelCounters ch1 = currentCountersFor(m_processorCh1);
    const ChannelCounters ch2 = currentCountersFor(m_processorCh2);
    const auto now = std::chrono::steady_clock::now();

    QString stackInfo;
    if (m_sessionState.stackRecording()) {
        stackInfo = QString(" | 堆栈: CH1=%1帧 CH2=%2帧")
                    .arg(m_imageStackCh1.size())
                    .arg(m_imageStackCh2.size());
    }

    QString fusionInfo;
    if (m_frameFusionBtn->isChecked()) {
        fusionInfo = QString(" | 融合: %1帧平均").arg(m_frameFusionCountSpin->value());
    }

    const int fps = m_fpsTracker.currentFps(now);
    m_statsLabel->setText(m_sessionState.buildStatsText(ch1, ch2, fps) + stackInfo + fusionInfo);

    updateFpsLabel(fps);
}

void MainWindow::onSaveImage() {
    const QString timestamp = makeTimestamp();
    const bool hasCh1 = m_latestResultCh1 && !m_latestResultCh1->imageData.empty();
    const bool hasCh2 = m_latestResultCh2 && !m_latestResultCh2->imageData.empty();
    const auto plan = m_sessionState.buildImageSavePlan("saved_data", timestamp, hasCh1, hasCh2);
    PairedSavePlan completedPlan;
    completedPlan.missingChannels = plan.missingChannels;

    if (plan.pathsByChannel.contains("ch1")) {
        const bool saved = m_dataSaver->saveImageData(
            m_latestResultCh1->imageData,
            m_latestResultCh1->width,
            m_latestResultCh1->height,
            plan.pathsByChannel.value("ch1"),
            "png");
        if (saved) {
            completedPlan.savedChannels << "ch1";
            completedPlan.pathsByChannel.insert("ch1", plan.pathsByChannel.value("ch1"));
        } else {
            onLogMessage(QString("图像保存失败 ch1: %1").arg(plan.pathsByChannel.value("ch1")));
        }
    }
    if (plan.pathsByChannel.contains("ch2")) {
        const bool saved = m_dataSaver->saveImageData(
            m_latestResultCh2->imageData,
            m_latestResultCh2->width,
            m_latestResultCh2->height,
            plan.pathsByChannel.value("ch2"),
            "png");
        if (saved) {
            completedPlan.savedChannels << "ch2";
            completedPlan.pathsByChannel.insert("ch2", plan.pathsByChannel.value("ch2"));
        } else {
            onLogMessage(QString("图像保存失败 ch2: %1").arg(plan.pathsByChannel.value("ch2")));
        }
    }

    logSaveOutcome("图像", completedPlan);
}

void MainWindow::onSaveRawData() {
    const QString timestamp = makeTimestamp();
    const bool hasCh1 = m_latestResultCh1 && !m_latestResultCh1->rawPackets.empty();
    const bool hasCh2 = m_latestResultCh2 && !m_latestResultCh2->rawPackets.empty();
    const auto plan = m_sessionState.buildRawSavePlan("saved_data", timestamp, hasCh1, hasCh2);
    PairedSavePlan completedPlan;
    completedPlan.missingChannels = plan.missingChannels;

    if (plan.pathsByChannel.contains("ch1")) {
        const bool saved = m_dataSaver->savePacketsToBin(
            m_latestResultCh1->rawPackets, plan.pathsByChannel.value("ch1"));
        if (saved) {
            completedPlan.savedChannels << "ch1";
            completedPlan.pathsByChannel.insert("ch1", plan.pathsByChannel.value("ch1"));
        } else {
            onLogMessage(QString("原始数据保存失败 ch1: %1").arg(plan.pathsByChannel.value("ch1")));
        }
    }
    if (plan.pathsByChannel.contains("ch2")) {
        const bool saved = m_dataSaver->savePacketsToBin(
            m_latestResultCh2->rawPackets, plan.pathsByChannel.value("ch2"));
        if (saved) {
            completedPlan.savedChannels << "ch2";
            completedPlan.pathsByChannel.insert("ch2", plan.pathsByChannel.value("ch2"));
        } else {
            onLogMessage(QString("原始数据保存失败 ch2: %1").arg(plan.pathsByChannel.value("ch2")));
        }
    }

    logSaveOutcome("原始数据", completedPlan);
}

void MainWindow::onSaveStack() {
    if (!m_sessionState.stackRecording()) {
        m_sessionState.startStackRecording();
        m_imageStackCh1.clear();
        m_imageStackCh2.clear();
        m_saveStackBtn->setText("停止录制");
        m_saveStackBtn->setStyleSheet("QPushButton { background-color: #E91E63; color: white; font-weight: bold; padding: 8px 16px; }");
        onLogMessage("开始同步录制双通道图像堆栈");
    } else {
        m_sessionState.stopStackRecording();
        m_saveStackBtn->setText("录制堆栈");
        m_saveStackBtn->setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px; }");

        const QString timestamp = makeTimestamp();
        const auto plan = m_sessionState.buildStackSavePlan(
            "saved_data", timestamp, !m_imageStackCh1.empty(), !m_imageStackCh2.empty());
        PairedSavePlan completedPlan;
        completedPlan.missingChannels = plan.missingChannels;

        if (plan.pathsByChannel.contains("ch1")) {
            const bool saved = m_dataSaver->saveStackData(
                m_imageStackCh1, 512, 512, plan.pathsByChannel.value("ch1"));
            if (saved) {
                completedPlan.savedChannels << "ch1";
                completedPlan.pathsByChannel.insert("ch1", plan.pathsByChannel.value("ch1"));
            } else {
                onLogMessage(QString("堆栈保存失败 ch1: %1").arg(plan.pathsByChannel.value("ch1")));
            }
        }
        if (plan.pathsByChannel.contains("ch2")) {
            const bool saved = m_dataSaver->saveStackData(
                m_imageStackCh2, 512, 512, plan.pathsByChannel.value("ch2"));
            if (saved) {
                completedPlan.savedChannels << "ch2";
                completedPlan.pathsByChannel.insert("ch2", plan.pathsByChannel.value("ch2"));
            } else {
                onLogMessage(QString("堆栈保存失败 ch2: %1").arg(plan.pathsByChannel.value("ch2")));
            }
        }

        logSaveOutcome("堆栈", completedPlan);
        m_imageStackCh1.clear();
        m_imageStackCh2.clear();
    }
}

void MainWindow::onFrameFusionToggled(bool enabled) {
    m_displayFusionCh1.setEnabled(enabled);
    m_displayFusionCh2.setEnabled(enabled);
    refreshDisplayFromLatestResults();

    onLogMessage(enabled
        ? QString("已开启多帧融合显示: %1帧平均").arg(m_frameFusionCountSpin->value())
        : "已关闭多帧融合显示");
}

void MainWindow::onFrameFusionCountChanged(int frameCount) {
    m_displayFusionCh1.setFrameCount(frameCount);
    m_displayFusionCh2.setFrameCount(frameCount);

    if (m_frameFusionBtn->isChecked()) {
        resetDisplayFusion();
        refreshDisplayFromLatestResults();
        onLogMessage(QString("多帧融合帧数已更新: %1").arg(frameCount));
    }
}

void MainWindow::appendToStackIfRecording(const QString& channel, const std::vector<uint16_t>& image) {
    if (!m_sessionState.stackRecording() || image.empty()) {
        return;
    }

    if (channel == "ch1") {
        m_imageStackCh1.push_back(image);
    } else if (channel == "ch2") {
        m_imageStackCh2.push_back(image);
    }
}

void MainWindow::logSaveOutcome(const QString& action, const PairedSavePlan& plan) {
    for (const auto& channel : plan.savedChannels) {
        onLogMessage(QString("%1已保存 %2: %3")
            .arg(action)
            .arg(channel)
            .arg(plan.pathsByChannel.value(channel)));
    }

    if (!plan.missingChannels.isEmpty()) {
        onLogMessage(QString("%1缺少通道: %2").arg(action, plan.missingChannels.join(", ")));
    }
}

void MainWindow::updateSenderIp() {
    QString ip = m_ipInput->text().trimmed();
    if (ip.isEmpty()) {
        return;
    }

    // 创建或更新UDP发送器 (端口0x8004与Python版本保持一致)
    m_udpSender = std::make_shared<UdpSender>(ip, 0x8004);
    connect(m_udpSender.get(), &UdpSender::logMessage, this, &MainWindow::onLogMessage);

    // 设置协议控制的发送器
    m_protocolControl->setUdpSender(m_udpSender);

    onLogMessage(QString("UDP发送器已更新: %1:0x8004").arg(ip));
}
