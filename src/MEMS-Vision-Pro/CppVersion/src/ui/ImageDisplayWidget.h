#ifndef IMAGE_DISPLAY_WIDGET_H
#define IMAGE_DISPLAY_WIDGET_H

#include <QWidget>
#include <QLabel>
#include <QSlider>
#include <QSpinBox>
#include <QImage>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGroupBox>
#include <QPushButton>
#include <vector>
#include <memory>
#include "processing/ImageProcessor.h"
#include "ui/ImageDisplayAdjustments.h"

/**
 * 图像显示控件
 * 显示 16bit 图像，支持对比度/亮度调节
 */
class ImageDisplayWidget : public QWidget {
    Q_OBJECT

public:
    explicit ImageDisplayWidget(const QString& title, const QString& channel,
                                 QWidget* parent = nullptr);
    ~ImageDisplayWidget() override;

    void setImage(std::shared_ptr<ProcessingResult> result);
    void clear();

    // 获取当前 16bit 图像数据
    const std::vector<uint16_t>& currentImage() const { return m_imageData; }

signals:
    void logMessage(const QString& message);

private slots:
    void onContrastChanged(int value);
    void onBrightnessChanged(int value);
    void onAutoRange();
    void updateDisplay();

private:
    void setupUi();
    QImage convertTo8bit(const std::vector<uint16_t>& data16, int width, int height);

    QString m_title;
    QString m_channel;

    // UI 控件
    QLabel* m_imageLabel;
    QSlider* m_contrastSlider;
    QSlider* m_brightnessSlider;
    QSpinBox* m_minSpinBox;
    QSpinBox* m_maxSpinBox;
    QPushButton* m_autoRangeBtn;
    QLabel* m_infoLabel;

    // 图像数据
    std::vector<uint16_t> m_imageData;
    int m_imageWidth = 0;
    int m_imageHeight = 0;

    // 显示参数
    double m_contrast = 1.0;
    double m_brightness = 0.0;
    int m_displayMin = 0;
    int m_displayMax = 65535;
};

#endif  // IMAGE_DISPLAY_WIDGET_H
