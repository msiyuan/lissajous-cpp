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
    connect(m_minSpinBox, qOverload<int>(&QSpinBox::valueChanged), this, &ImageDisplayWidget::updateDisplay);
    rangeLayout->addWidget(m_minSpinBox);
    rangeLayout->addWidget(new QLabel("-"));
    m_maxSpinBox = new QSpinBox();
    m_maxSpinBox->setRange(0, 65535);
    m_maxSpinBox->setValue(65535);
    connect(m_maxSpinBox, qOverload<int>(&QSpinBox::valueChanged), this, &ImageDisplayWidget::updateDisplay);
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

    m_infoLabel->setText(QString("相位: X=%1° Y=%2°")
                        .arg(result->phaseX, 0, 'f', 2)
                        .arg(result->phaseY, 0, 'f', 2));

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

    const auto range = ImageDisplayAdjustments::autoAdjustRange(m_imageData);

    if (range.minValue < range.maxValue) {
        m_minSpinBox->setValue(range.minValue);
        m_maxSpinBox->setValue(range.maxValue);
        m_displayMin = range.minValue;
        m_displayMax = range.maxValue;
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
    const auto adjusted = ImageDisplayAdjustments::applyImageAdjustments(
        data16,
        width,
        height,
        m_displayMin,
        m_displayMax,
        static_cast<int>(m_contrast * 100.0),
        m_brightnessSlider->value());

    for (int y = 0; y < height; ++y) {
        uint8_t* line = image.scanLine(y);
        for (int x = 0; x < width; ++x) {
            const int idx = y * width + x;
            line[x] = adjusted[static_cast<size_t>(idx)];
        }
    }

    return image;
}
