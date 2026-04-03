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

    // 初始化默认参数（为协议命令x/y work_fre的一半）
    m_currentParams.freqX = 11510.0;  // x_work_fre: 23020 / 2 = 11510 Hz
    m_currentParams.freqY = 2500.0;   // y_work_fre: 5000 / 2 = 2500 Hz
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
    m_freqXInput = new QLineEdit("11510");
    m_freqXInput->setFixedWidth(60);
    controlLayout->addWidget(m_freqXInput);

    controlLayout->addWidget(new QLabel("Y频率:"));
    m_freqYInput = new QLineEdit("2500");
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

    m_saveStackBtn = new QPushButton("录制堆栈");
    m_saveStackBtn->setCheckable(true);
    m_saveStackBtn->setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px; }");
    connect(m_saveStackBtn, &QPushButton::clicked, this, &MainWindow::onSaveStack);
    btnLayout->addWidget(m_saveStackBtn);

    btnLayout->addStretch();
    leftLayout->addLayout(btnLayout);

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
    m_fpsLabel = new QLabel("重建帧率: 0 FPS");
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

void MainWindow::onStartReceiver() {
    QString ip = m_ipInput->text();

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
    m_protocolControl->setEnabled(false);

    onLogMessage("双通道接收已启动");
}

void MainWindow::onStopReceiver() {
    m_statsTimer->stop();

    if (m_processorCh1) {
        m_processorCh1->stop();
        m_processorCh1.reset();
    }

    if (m_processorCh2) {
        m_processorCh2->stop();
        m_processorCh2.reset();
    }

    // 停止录制并保存堆栈
    if (m_isRecordingStack) {
        m_saveStackBtn->setChecked(false);
        onSaveStack();
    }

    // 启用协议控制 (与Python版本一致：停止接收后可以发送命令)
    m_protocolControl->setEnabled(true);

    m_startBtn->setEnabled(true);
    m_stopBtn->setEnabled(false);

    onLogMessage("双通道接收已停止");
}

void MainWindow::onImageReady(std::shared_ptr<ProcessingResult> result) {
    if (!result) return;

    // 记录帧时间用于计算帧率
    auto now = std::chrono::steady_clock::now();
    m_frameTimes.push_back(now);

    // 只保留最近1秒内的帧时间
    while (!m_frameTimes.empty()) {
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            now - m_frameTimes.front()).count();
        if (elapsed > 1) {
            m_frameTimes.pop_front();
        } else {
            break;
        }
    }

    if (result->channel == "ch1") {
        m_displayCh1->setImage(result);
        // 如果正在录制堆栈
        if (m_isRecordingStack && !result->imageData.empty()) {
            m_imageStackCh1.push_back(result->imageData);
        }
    } else if (result->channel == "ch2") {
        m_displayCh2->setImage(result);
        if (m_isRecordingStack && !result->imageData.empty()) {
            m_imageStackCh2.push_back(result->imageData);
        }
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

    onLogMessage(QString("参数已更新: X相位=%.1f° Y相位=%.1f° X频率=%.1f Y频率=%.1f")
                .arg(m_currentParams.deltaPhaseX)
                .arg(m_currentParams.deltaPhaseY)
                .arg(m_currentParams.freqX)
                .arg(m_currentParams.freqY));
}

void MainWindow::updateStats() {
    uint64_t bytes1 = 0, packets1 = 0, frames1 = 0;
    uint64_t bytes2 = 0, packets2 = 0, frames2 = 0;

    if (m_processorCh1) {
        bytes1 = m_processorCh1->bytesReceived();
        packets1 = m_processorCh1->packetsReceived();
        frames1 = m_processorCh1->framesProcessed();
    }

    if (m_processorCh2) {
        bytes2 = m_processorCh2->bytesReceived();
        packets2 = m_processorCh2->packetsReceived();
        frames2 = m_processorCh2->framesProcessed();
    }

    QString stackInfo;
    if (m_isRecordingStack) {
        stackInfo = QString(" | 堆栈: CH1=%1帧 CH2=%2帧")
                    .arg(m_imageStackCh1.size())
                    .arg(m_imageStackCh2.size());
    }

    m_statsLabel->setText(QString("CH1: %1 KB, %2 包, %3 帧 | CH2: %4 KB, %5 包, %6 帧%7")
                         .arg(bytes1 / 1024)
                         .arg(packets1)
                         .arg(frames1)
                         .arg(bytes2 / 1024)
                         .arg(packets2)
                         .arg(frames2)
                         .arg(stackInfo));

    // 更新帧率显示（与Python版本一致）
    int fps = m_frameTimes.size();
    m_fpsLabel->setText(QString("重建帧率: %1 FPS").arg(fps));

    // 根据帧率设置颜色（与Python版本一致）
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

void MainWindow::onSaveImage() {
    QString timestamp = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");

    // 保存通道1图像
    const auto& img1 = m_displayCh1->currentImage();
    if (!img1.empty()) {
        QString filename1 = QString("saved_data/ch1_image_%1.raw").arg(timestamp);
        if (m_dataSaver->saveImageData(img1, 512, 512, filename1, "raw")) {
            onLogMessage(QString("通道1图像已保存: %1").arg(filename1));
        }
    }

    // 保存通道2图像
    const auto& img2 = m_displayCh2->currentImage();
    if (!img2.empty()) {
        QString filename2 = QString("saved_data/ch2_image_%1.raw").arg(timestamp);
        if (m_dataSaver->saveImageData(img2, 512, 512, filename2, "raw")) {
            onLogMessage(QString("通道2图像已保存: %1").arg(filename2));
        }
    }
}

void MainWindow::onSaveStack() {
    if (m_saveStackBtn->isChecked()) {
        // 开始录制
        m_isRecordingStack = true;
        m_imageStackCh1.clear();
        m_imageStackCh2.clear();
        m_saveStackBtn->setText("停止录制");
        m_saveStackBtn->setStyleSheet("QPushButton { background-color: #E91E63; color: white; font-weight: bold; padding: 8px 16px; }");
        onLogMessage("开始录制图像堆栈...");
    } else {
        // 停止录制并保存
        m_isRecordingStack = false;
        m_saveStackBtn->setText("录制堆栈");
        m_saveStackBtn->setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px; }");

        QString timestamp = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");

        // 保存通道1堆栈
        if (!m_imageStackCh1.empty()) {
            QString filename1 = QString("saved_data/ch1_stack_%1.raw").arg(timestamp);
            if (m_dataSaver->saveStackData(m_imageStackCh1, 512, 512, filename1)) {
                onLogMessage(QString("通道1堆栈已保存: %1 (%2帧)").arg(filename1).arg(m_imageStackCh1.size()));
            }
            m_imageStackCh1.clear();
        }

        // 保存通道2堆栈
        if (!m_imageStackCh2.empty()) {
            QString filename2 = QString("saved_data/ch2_stack_%1.raw").arg(timestamp);
            if (m_dataSaver->saveStackData(m_imageStackCh2, 512, 512, filename2)) {
                onLogMessage(QString("通道2堆栈已保存: %1 (%2帧)").arg(filename2).arg(m_imageStackCh2.size()));
            }
            m_imageStackCh2.clear();
        }
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
