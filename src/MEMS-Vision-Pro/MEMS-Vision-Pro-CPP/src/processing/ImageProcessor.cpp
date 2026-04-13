#include "ImageProcessor.h"
#include "utils/PhaseMapping.h"
#include <algorithm>
#include <cstring>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

ImageProcessor::ImageProcessor(QObject* parent)
    : QObject(parent) {
}

ImageProcessor::~ImageProcessor() = default;

std::shared_ptr<ProcessingResult> ImageProcessor::processFrame(
    std::shared_ptr<FrameData> frame,
    const ProcessingParams& params,
    const QString& channel) {

    if (!frame || frame->packets.empty()) {
        return nullptr;
    }

    auto result = std::make_shared<ProcessingResult>();
    result->channel = channel;

    // 1. 计算相位（添加相位映射补偿 - 与Python版本一致）
    const double phaseXForMapping = PhaseMapping::rawPhaseToMappingDegrees(frame->phaseX);
    const double phaseYForMapping = PhaseMapping::rawPhaseToMappingDegrees(frame->phaseY);

    // 使用相位映射补偿（与Python版本的map_delta_phasex/y一致）
    const double phaseXCompensation = m_phaseMapping.mapDeltaPhaseX(phaseXForMapping);
    const double phaseYCompensation = m_phaseMapping.mapDeltaPhaseY(phaseYForMapping);

    result->phaseX = PhaseMapping::composeFinalPhaseDegrees(
        frame->phaseX, phaseXCompensation, params.deltaPhaseX);
    result->phaseY = PhaseMapping::composeFinalPhaseDegrees(
        frame->phaseY, phaseYCompensation, params.deltaPhaseY);

    double phaseXRad = result->phaseX * M_PI / 180.0;
    double phaseYRad = result->phaseY * M_PI / 180.0;

    // 2. 提取 ADC 数据
    std::vector<uint16_t> grayValues = extractAdcData(frame->packets);
    if (grayValues.empty()) {
        return nullptr;
    }

    // 3. 计算轨迹
    size_t numPoints = std::min(grayValues.size(), static_cast<size_t>(Config::NUM_FRAME));
    std::vector<int32_t> trajectoryIndices = calculateTrajectory(
        numPoints, phaseXRad, phaseYRad, params);

    // 4. 累加像素
    const int imagePixels = Config::IMAGE_SIZE * Config::IMAGE_SIZE;
    std::vector<int64_t> pixelSum(imagePixels, 0);
    std::vector<int32_t> pixelCount(imagePixels, 0);

    accumulatePixels(grayValues, trajectoryIndices, pixelSum, pixelCount);

    // 5. 计算最终图像
    result->imageData = computeFinalImage(pixelSum, pixelCount);

    // 6. 插值填充
    interpolateColumns(result->imageData, pixelCount);

    return result;
}

std::vector<uint16_t> ImageProcessor::extractAdcData(const std::vector<QByteArray>& packets) {
    std::vector<uint16_t> result;
    result.reserve(Config::NUM_FRAME);

    for (size_t i = 0; i < packets.size(); ++i) {
        const QByteArray& packet = packets[i];
        const uint8_t* data = reinterpret_cast<const uint8_t*>(packet.constData());
        int size = packet.size();

        int offset = 0;
        if (i == 0) {
            // 第一个包是帧头，跳过16字节头
            offset = 16;
        } else {
            // 数据包跳过4字节头 (0x2CFF + PacketCnt)
            offset = 4;
        }

        // 提取 16bit ADC 数据 (小端序 - 与Python版本一致)
        for (int j = offset; j + 1 < size; j += 2) {
            // 小端序：低位在前，高位在后
            uint16_t value = static_cast<uint16_t>(data[j]) |
                              (static_cast<uint16_t>(data[j + 1]) << 8);
            result.push_back(value);
        }
    }

    return result;
}

std::vector<int32_t> ImageProcessor::calculateTrajectory(
    size_t numPoints,
    double phaseX, double phaseY,
    const ProcessingParams& params) {

    std::vector<int32_t> indices(numPoints);

    const double deltaT = 1.0 / params.sampleRate;
    const double xFreq = M_PI * deltaT * 2.0 * params.freqX;
    const double yFreq = M_PI * deltaT * 2.0 * params.freqY;
    const double xAmp = Config::IMAGE_SIZE / 2.0;
    const double yAmp = Config::IMAGE_SIZE / 2.0;
    const double offset = 256.0;

    // 并行计算轨迹（可用 OpenMP 加速）
    #pragma omp parallel for
    for (size_t i = 0; i < numPoints; ++i) {
        double xVal = xAmp * std::sin(xFreq * i + phaseX) + offset;
        double yVal = yAmp * std::sin(yFreq * i + phaseY) + offset;

        int x = static_cast<int>(std::floor(xVal));
        int y = static_cast<int>(std::floor(yVal));

        // 边界检查
        x = std::clamp(x, 0, Config::IMAGE_SIZE - 1);
        y = std::clamp(y, 0, Config::IMAGE_SIZE - 1);

        indices[i] = x * Config::IMAGE_SIZE + y;
    }

    return indices;
}

void ImageProcessor::accumulatePixels(
    const std::vector<uint16_t>& grayValues,
    const std::vector<int32_t>& trajectoryIndices,
    std::vector<int64_t>& pixelSum,
    std::vector<int32_t>& pixelCount) {

    size_t numPoints = std::min(grayValues.size(), trajectoryIndices.size());

    for (size_t i = 0; i < numPoints; ++i) {
        int32_t idx = trajectoryIndices[i];
        pixelSum[idx] += grayValues[i];
        pixelCount[idx] += 1;
    }
}

std::vector<uint16_t> ImageProcessor::computeFinalImage(
    const std::vector<int64_t>& pixelSum,
    const std::vector<int32_t>& pixelCount) {

    const int imagePixels = Config::IMAGE_SIZE * Config::IMAGE_SIZE;
    std::vector<uint16_t> image(imagePixels, 0);

    #pragma omp parallel for
    for (int i = 0; i < imagePixels; ++i) {
        if (pixelCount[i] > 0) {
            image[i] = static_cast<uint16_t>(pixelSum[i] / pixelCount[i]);
        }
    }

    return image;
}

void ImageProcessor::interpolateColumns(
    std::vector<uint16_t>& image,
    const std::vector<int32_t>& pixelCount) {

    const int size = Config::IMAGE_SIZE;

    // 逐列插值
    #pragma omp parallel for
    for (int col = 0; col < size; ++col) {
        // 找到有效点
        std::vector<int> validRows;
        std::vector<uint16_t> validValues;

        for (int row = 0; row < size; ++row) {
            int idx = row * size + col;
            if (pixelCount[idx] > 0) {
                validRows.push_back(row);
                validValues.push_back(image[idx]);
            }
        }

        if (validRows.size() < 2) {
            continue;  // 不够插值
        }

        // 对未扫描的点进行线性插值
        for (int row = 0; row < size; ++row) {
            int idx = row * size + col;
            if (pixelCount[idx] > 0) {
                continue;  // 已有值
            }

            // 找到最近的上下有效点
            int lowerIdx = -1, upperIdx = -1;
            for (size_t i = 0; i < validRows.size(); ++i) {
                if (validRows[i] <= row) {
                    lowerIdx = i;
                }
                if (validRows[i] >= row && upperIdx < 0) {
                    upperIdx = i;
                    break;
                }
            }

            if (lowerIdx >= 0 && upperIdx >= 0 && lowerIdx != upperIdx) {
                // 线性插值
                int r0 = validRows[lowerIdx];
                int r1 = validRows[upperIdx];
                uint16_t v0 = validValues[lowerIdx];
                uint16_t v1 = validValues[upperIdx];

                double t = static_cast<double>(row - r0) / (r1 - r0);
                image[idx] = static_cast<uint16_t>(v0 + t * (v1 - v0));
            } else if (lowerIdx >= 0) {
                image[idx] = validValues[lowerIdx];
            } else if (upperIdx >= 0) {
                image[idx] = validValues[upperIdx];
            }
        }
    }
}
