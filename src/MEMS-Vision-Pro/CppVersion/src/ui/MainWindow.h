#ifndef MAIN_WINDOW_H
#define MAIN_WINDOW_H

#include <QMainWindow>
#include <QTextEdit>
#include <QLineEdit>
#include <QPushButton>
#include <QLabel>
#include <QSpinBox>
#include <QTimer>
#include <QTabWidget>
#include <memory>
#include <chrono>
#include "ui/DualChannelSessionState.h"
#include "ui/DualChannelFpsTracker.h"
#include "ui/DisplayFrameFusion.h"
#include "ui/ImageDisplayWidget.h"
#include "ui/ProtocolControlWidget.h"
#include "processing/ChannelProcessor.h"
#include "processing/DataSaver.h"
#include "network/UdpSender.h"

/**
 * 主窗口
 * 双通道 MEMS 成像系统
 */
class MainWindow : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() override;

private slots:
    void onStartReceiver();
    void onStopReceiver();
    void onImageReady(std::shared_ptr<ProcessingResult> result);
    void onLogMessage(const QString& message);
    void onParamsChanged();
    void updateStats();
    void onSaveImage();
    void onSaveRawData();
    void onSaveStack();
    void onFrameFusionToggled(bool enabled);
    void onFrameFusionCountChanged(int frameCount);
    void updateSenderIp();

private:
    void setupUi();
    void setupConnections();
    QString makeTimestamp() const;
    void setProtocolControlsEnabled(bool enabled);
    void resetFpsWindow();
    void resetDisplayFusion();
    void refreshDisplayFromLatestResults();
    ChannelCounters currentCountersFor(const std::unique_ptr<ChannelProcessor>& processor) const;
    void updateFpsLabel(int fps);
    void appendToStackIfRecording(const QString& channel, const std::vector<uint16_t>& image);
    void logSaveOutcome(const QString& action, const PairedSavePlan& plan);

    // UI 控件
    QLineEdit* m_ipInput;
    QLineEdit* m_phaseXInput;
    QLineEdit* m_phaseYInput;
    QLineEdit* m_freqXInput;
    QLineEdit* m_freqYInput;
    QPushButton* m_startBtn;
    QPushButton* m_stopBtn;
    QPushButton* m_applyParamsBtn;
    QPushButton* m_saveImageBtn;
    QPushButton* m_saveRawBtn;
    QPushButton* m_saveStackBtn;
    QPushButton* m_frameFusionBtn;
    QSpinBox* m_frameFusionCountSpin;
    QTextEdit* m_logText;
    QLabel* m_statsLabel;
    QLabel* m_fpsLabel;  // 帧率显示标签
    QTabWidget* m_controlTabs;

    // 图像显示
    ImageDisplayWidget* m_displayCh1;
    ImageDisplayWidget* m_displayCh2;

    // 协议控制
    ProtocolControlWidget* m_protocolControl;

    // 通道处理器
    std::unique_ptr<ChannelProcessor> m_processorCh1;
    std::unique_ptr<ChannelProcessor> m_processorCh2;

    // UDP 发送器
    std::shared_ptr<UdpSender> m_udpSender;

    // 数据保存
    std::unique_ptr<DataSaver> m_dataSaver;
    std::vector<std::vector<uint16_t>> m_imageStackCh1;
    std::vector<std::vector<uint16_t>> m_imageStackCh2;
    DisplayFrameFusion m_displayFusionCh1;
    DisplayFrameFusion m_displayFusionCh2;
    std::shared_ptr<ProcessingResult> m_latestResultCh1;
    std::shared_ptr<ProcessingResult> m_latestResultCh2;
    DualChannelSessionState m_sessionState;

    // 定时器
    QTimer* m_statsTimer;
    DualChannelFpsTracker m_fpsTracker;

    // 当前参数
    ProcessingParams m_currentParams;

    // 帧率统计
    std::chrono::steady_clock::time_point m_lastFrameTime;
};

#endif  // MAIN_WINDOW_H
