#ifndef IMAGE_PROCESSOR_H
#define IMAGE_PROCESSOR_H

#include <QObject>
#include <QImage>
#include <vector>
#include <memory>
#include <cstdint>
#include <cmath>
#include "FrameAssembler.h"
#include "config/Constants.h"
#include "utils/PhaseMapping.h"

/**
 * 图像处理参数
 */
struct ProcessingParams {
    double freqX = Config::DEFAULT_FREQ_X;
    double freqY = Config::DEFAULT_FREQ_Y;
    double deltaPhaseX = Config::DEFAULT_PHASE_X;
    double deltaPhaseY = Config::DEFAULT_PHASE_Y;
    double sampleRate = Config::SAMPLE_RATE;
};

/**
 * 图像处理结果
 */
struct ProcessingResult {
    std::vector<uint16_t> imageData;  // 512x512 的 16bit 图像数据
    std::vector<QByteArray> rawPackets;  // 当前帧对应的原始UDP包
    int width = Config::IMAGE_SIZE;
    int height = Config::IMAGE_SIZE;
    double phaseX = 0.0;
    double phaseY = 0.0;
    QString channel;
};

/**
 * 图像处理器
 * 将帧数据处理成图像（纯 CPU 多线程版本）
 */
class ImageProcessor : public QObject {
    Q_OBJECT

public:
    explicit ImageProcessor(QObject* parent = nullptr);
    ~ImageProcessor() override;

    /**
     * 处理帧数据（同步调用，可在任意线程执行）
     */
    std::shared_ptr<ProcessingResult> processFrame(
        std::shared_ptr<FrameData> frame,
        const ProcessingParams& params,
        const QString& channel);

signals:
    void processingComplete(std::shared_ptr<ProcessingResult> result);
    void logMessage(const QString& message);

private:
    PhaseMapping m_phaseMapping;

    // 提取 ADC 数据
    std::vector<uint16_t> extractAdcData(const std::vector<QByteArray>& packets);

    // 计算 Lissajous 轨迹索引
    std::vector<int32_t> calculateTrajectory(size_t numPoints,
                                              double phaseX, double phaseY,
                                              const ProcessingParams& params);

    // 累加像素数据
    void accumulatePixels(const std::vector<uint16_t>& grayValues,
                          const std::vector<int32_t>& trajectoryIndices,
                          std::vector<int64_t>& pixelSum,
                          std::vector<int32_t>& pixelCount);

    // 计算最终图像
    std::vector<uint16_t> computeFinalImage(const std::vector<int64_t>& pixelSum,
                                             const std::vector<int32_t>& pixelCount);

    // 垂直插值填充
    void interpolateColumns(std::vector<uint16_t>& image,
                            const std::vector<int32_t>& pixelCount);
};

#endif  // IMAGE_PROCESSOR_H
