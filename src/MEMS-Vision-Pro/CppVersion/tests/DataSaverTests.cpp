#include "processing/DataSaver.h"
#include "processing/ImageProcessor.h"
#include "ui/ImageDisplayWidget.h"
#include "TestSupport.h"

#include <QFile>
#include <QFileInfo>
#include <QDir>
#include <QLabel>
#include <cmath>

namespace {

QString prepareTestDir(const QString& name) {
    const QString path = QDir::current().filePath(QString("test-output/%1").arg(name));
    QDir dir(path);
    if (dir.exists()) {
        dir.removeRecursively();
    }
    QDir().mkpath(path);
    return path;
}

double normalizeDegrees(double value) {
    double normalized = std::fmod(value, 360.0);
    if (normalized < 0.0) {
        normalized += 360.0;
    }
    return normalized;
}

std::shared_ptr<FrameData> makeFrameWithPackets() {
    auto frame = std::make_shared<FrameData>();
    frame->phaseX = 0;
    frame->phaseY = 0;
    frame->samplePoint = 2;

    QByteArray headerPacket;
    headerPacket.append(static_cast<char>(0x2A));
    headerPacket.append(static_cast<char>(0xFF));
    headerPacket.append(14, '\0');
    headerPacket.append(static_cast<char>(0x12));
    headerPacket.append(static_cast<char>(0x34));

    QByteArray dataPacket;
    dataPacket.append(static_cast<char>(0x2C));
    dataPacket.append(static_cast<char>(0xFF));
    dataPacket.append(static_cast<char>(0x00));
    dataPacket.append(static_cast<char>(0x01));
    dataPacket.append(static_cast<char>(0xAB));
    dataPacket.append(static_cast<char>(0xCD));

    frame->packets.push_back(headerPacket);
    frame->packets.push_back(dataPacket);
    return frame;
}

void test_save_image_data_writes_png() {
    DataSaver saver;
    const std::vector<uint16_t> image = {
        0, 65535,
        32768, 16384
    };
    const QString path = QDir(prepareTestDir("png")).filePath("image.png");

    REQUIRE(saver.saveImageData(image, 2, 2, path, "png"));
    REQUIRE(QFileInfo::exists(path));

    QFile file(path);
    REQUIRE(file.open(QIODevice::ReadOnly));
    const QByteArray bytes = file.read(8);
    REQUIRE(bytes == QByteArray("\x89PNG\r\n\x1a\n", 8));
}

void test_save_stack_data_writes_tiff() {
    DataSaver saver;
    const std::vector<std::vector<uint16_t>> stack = {
        std::vector<uint16_t>{1, 2, 3, 4},
        std::vector<uint16_t>{5, 6, 7, 8}
    };
    const QString path = QDir(prepareTestDir("tiff")).filePath("stack.tiff");

    REQUIRE(saver.saveStackData(stack, 2, 2, path));
    REQUIRE(QFileInfo::exists(path));

    QFile file(path);
    REQUIRE(file.open(QIODevice::ReadOnly));
    const QByteArray bytes = file.readAll();
    REQUIRE(bytes.size() > 8);
    REQUIRE(bytes[0] == 'I');
    REQUIRE(bytes[1] == 'I');
    REQUIRE(static_cast<unsigned char>(bytes[2]) == 42);

    const int firstIfdOffset = static_cast<unsigned char>(bytes[4])
        | (static_cast<unsigned char>(bytes[5]) << 8)
        | (static_cast<unsigned char>(bytes[6]) << 16)
        | (static_cast<unsigned char>(bytes[7]) << 24);
    REQUIRE(firstIfdOffset == 8);

    const int nextIfdFieldOffset = firstIfdOffset + 2 + 10 * 12;
    const int nextIfdOffset = static_cast<unsigned char>(bytes[nextIfdFieldOffset])
        | (static_cast<unsigned char>(bytes[nextIfdFieldOffset + 1]) << 8)
        | (static_cast<unsigned char>(bytes[nextIfdFieldOffset + 2]) << 16)
        | (static_cast<unsigned char>(bytes[nextIfdFieldOffset + 3]) << 24);
    REQUIRE(nextIfdOffset > 0);
}

void test_save_packets_to_bin_writes_data() {
    DataSaver saver;
    const std::vector<QByteArray> packets = {QByteArray("abc", 3), QByteArray("de", 2)};
    const QString path = QDir(prepareTestDir("bin")).filePath("raw.bin");

    REQUIRE(saver.savePacketsToBin(packets, path));
    REQUIRE(QFileInfo::exists(path));

    QFile file(path);
    REQUIRE(file.open(QIODevice::ReadOnly));
    const QByteArray payload = file.readAll();
    REQUIRE(payload.size() == static_cast<int>((sizeof(uint32_t) + 3) + (sizeof(uint32_t) + 2)));
}

void test_processing_result_retains_raw_packets() {
    ImageProcessor processor;
    ProcessingParams params;

    const auto result = processor.processFrame(makeFrameWithPackets(), params, "ch1");

    REQUIRE(result != nullptr);
    REQUIRE(result->rawPackets.size() == 2);
    REQUIRE(result->rawPackets[0].size() == 18);
    REQUIRE(result->rawPackets[1].size() == 6);
}

void test_processing_result_applies_delta_phase_offsets() {
    ProcessingParams paramsBase;
    ProcessingParams paramsShifted;
    paramsShifted.deltaPhaseX = 45.0;
    paramsShifted.deltaPhaseY = -30.0;

    ImageProcessor baseProcessor;
    ImageProcessor shiftedProcessor;

    const auto base = baseProcessor.processFrame(makeFrameWithPackets(), paramsBase, "ch1");
    const auto shifted = shiftedProcessor.processFrame(makeFrameWithPackets(), paramsShifted, "ch1");

    REQUIRE(base != nullptr);
    REQUIRE(shifted != nullptr);
    REQUIRE(std::abs(normalizeDegrees(shifted->phaseX - base->phaseX) - 45.0) < 0.001);
    REQUIRE(std::abs(normalizeDegrees(shifted->phaseY - base->phaseY) - 330.0) < 0.001);
}

void test_image_display_widget_shows_current_phase_values() {
    ImageDisplayWidget widget("test", "ch1");

    auto result = std::make_shared<ProcessingResult>();
    result->imageData = {123};
    result->width = 1;
    result->height = 1;
    result->phaseX = 12.5;
    result->phaseY = 34.75;

    widget.setImage(result);

    const auto labels = widget.findChildren<QLabel*>();
    bool foundPhaseLabel = false;
    for (QLabel* label : labels) {
        const QString text = label->text();
        if (text.contains("相位:")) {
            foundPhaseLabel = true;
            REQUIRE(text.contains("12.50"));
            REQUIRE(text.contains("34.75"));
            break;
        }
    }

    REQUIRE(foundPhaseLabel);
}

}  // namespace

void runDataSaverTests() {
    test_save_image_data_writes_png();
    test_save_stack_data_writes_tiff();
    test_save_packets_to_bin_writes_data();
    test_processing_result_retains_raw_packets();
    test_processing_result_applies_delta_phase_offsets();
    test_image_display_widget_shows_current_phase_values();
}
