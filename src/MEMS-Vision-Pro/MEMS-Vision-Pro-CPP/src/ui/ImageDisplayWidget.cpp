#include "ImageDisplayWidget.h"
#include <algorithm>
#include <cmath>

ImageDisplayWidget::ImageDisplayWidget(const QString& title, const QString& channel,
                                         QWidget* parent)
    : QWidget(parent)
    , m_title(title)
    , m_channel(channel) {
    setupUi();
}

ImageDisplayWidget::~ImageDisplayWidget() = default;

void ImageDisplayWidget::setupUi() {
    auto* mainLayout = new QVBoxLayout(this);
    mainLayout->setSpacing(5);

    // 标题
    auto* titleLabel = new QLabel(m_title);
    titleLabel->setStyleSheet("font-weight: bold; font-size: 14px;");
    mainLayout->addWidget(titleLabel);

    // 图像显示区域
    m_imageLabel = new QLabel();
    m_imageLabel->setMinimumSize(512, 512);
    m_imageLabel->setMaximumSize(512, 512);
    m_imageLabel->setStyleSheet("background-color: black; border: 1px solid #ccc;");
    m_imageLabel->setAlignment(Qt::AlignCenter);
    mainLayout->addWidget(m_imageLabel);

    // 控制区域
    auto* controlGroup = new QGroupBox("显示调节");
    auto* controlLayout = new QVBoxLayout(controlGroup);

    // 对比度
    auto* contrastLayout = new QHBoxLayout();
    contrastLayout->addWidget(new QLabel("对比度:"));
    m_contrastSlider = new QSlider(Qt::Horizontal);
    m_contrastSlider->setRange(1, 300);
    m_contrastSlider->setValue(100);
    connect(m_contrastSlider, &QSlider::valueChanged, this, &ImageDisplayWidget::onContrastChanged);
    contrastLayout->addWidget(m_contrastSlider);
    controlLayout->addLayout(contrastLayout);

    // 亮度
    auto* brightnessLayout = new QHBoxLayout();
    brightnessLayout->addWidget(new QLabel("亮度:"));
    m_brightnessSlider = new QSlider(Qt::Horizontal);
    m_brightnessSlider->setRange(-100, 100);
    m_brightnessSlider->setValue(0);
    connect(m_brightnessSlider, &QSlider::valueChanged, this, &ImageDisplayWidget::onBrightnessChanged);
    brightnessLayout->addWidget(m_brightnessSlider);
    controlLayout->addLayout(brightnessLayout);

    // 显示范围
    auto* rangeLayout = new QHBoxLayout();
    rangeLayout->addWidget(new QLabel("范围:"));
    m_minSpinBox = new QSpinBox();
    m_minSpinBox->setRange(0, 65535);
    m_minSpinBox->setValue(0);
    rangeLayout->addWidget(m_minSpinBox);
    rangeLayout->addWidget(new QLabel("-"));
    m_maxSpinBox = new QSpinBox();
    m_maxSpinBox->setRange(0, 65535);
    m_maxSpinBox->setValue(65535);
    rangeLayout->addWidget(m_maxSpinBox);
    m_autoRangeBtn = new QPushButton("自动");
    m_autoRangeBtn->setFixedWidth(50);
    connect(m_autoRangeBtn, &QPushButton::clicked, this, &ImageDisplayWidget::onAutoRange);
    rangeLayout->addWidget(m_autoRangeBtn);
    controlLayout->addLayout(rangeLayout);

    mainLayout->addWidget(controlGroup);

    // 信息标签
    m_infoLabel = new QLabel("等待图像...");
    m_infoLabel->setStyleSheet("color: gray;");
    mainLayout->addWidget(m_infoLabel);
}

void ImageDisplayWidget::setImage(std::shared_ptr<ProcessingResult> result) {
    if (!result || result->imageData.empty()) {
        return;
    }

    m_imageData = result->imageData;
    m_imageWidth = result->width;
    m_imageHeight = result->height;

    m_infoLabel->setText(QString("相位: X=%.2f° Y=%.2f°")
                        .arg(result->phaseX)
                        .arg(result->phaseY));

    updateDisplay();
}

void ImageDisplayWidget::clear() {
    m_imageData.clear();
    m_imageLabel->clear();
    m_infoLabel->setText("等待图像...");
}

void ImageDisplayWidget::onContrastChanged(int value) {
    m_contrast = value / 100.0;
    updateDisplay();
}

void ImageDisplayWidget::onBrightnessChanged(int value) {
    m_brightness = value / 100.0 * 32768;
    updateDisplay();
}

void ImageDisplayWidget::onAutoRange() {
    if (m_imageData.empty()) {
        return;
    }

    // 找到非零像素的最小最大值
    uint16_t minVal = 65535, maxVal = 0;
    for (uint16_t val : m_imageData) {
        if (val > 0) {
            minVal = std::min(minVal, val);
            maxVal = std::max(maxVal, val);
        }
    }

    if (minVal < maxVal) {
        m_minSpinBox->setValue(minVal);
        m_maxSpinBox->setValue(maxVal);
        m_displayMin = minVal;
        m_displayMax = maxVal;
        updateDisplay();
    }
}

void ImageDisplayWidget::updateDisplay() {
    if (m_imageData.empty() || m_imageWidth == 0 || m_imageHeight == 0) {
        return;
    }

    QImage image = convertTo8bit(m_imageData, m_imageWidth, m_imageHeight);
    m_imageLabel->setPixmap(QPixmap::fromImage(image));
}

QImage ImageDisplayWidget::convertTo8bit(const std::vector<uint16_t>& data16,
                                          int width, int height) {
    QImage image(width, height, QImage::Format_Grayscale8);

    m_displayMin = m_minSpinBox->value();
    m_displayMax = m_maxSpinBox->value();
    double range = m_displayMax - m_displayMin;
    if (range <= 0) range = 1;

    for (int y = 0; y < height; ++y) {
        uint8_t* line = image.scanLine(y);
        for (int x = 0; x < width; ++x) {
            int idx = y * width + x;
            double val = data16[idx];

            // 应用范围映射
            val = (val - m_displayMin) / range;

            // 应用对比度和亮度
            val = val * m_contrast + m_brightness / 65535.0;

            // 转换为 8bit
            int val8 = static_cast<int>(val * 255.0);
            val8 = std::clamp(val8, 0, 255);
            line[x] = static_cast<uint8_t>(val8);
        }
    }

    return image;
}
