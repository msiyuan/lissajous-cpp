#include "DataSaver.h"
#include <QDateTime>
#include <QDataStream>
#include <QImage>
#include <QDebug>
#include <array>
#include <algorithm>

namespace {

void appendUint16LE(QByteArray& data, uint16_t value) {
    data.append(static_cast<char>(value & 0xFF));
    data.append(static_cast<char>((value >> 8) & 0xFF));
}

void appendUint32LE(QByteArray& data, uint32_t value) {
    data.append(static_cast<char>(value & 0xFF));
    data.append(static_cast<char>((value >> 8) & 0xFF));
    data.append(static_cast<char>((value >> 16) & 0xFF));
    data.append(static_cast<char>((value >> 24) & 0xFF));
}

void appendUint32BE(QByteArray& data, uint32_t value) {
    data.append(static_cast<char>((value >> 24) & 0xFF));
    data.append(static_cast<char>((value >> 16) & 0xFF));
    data.append(static_cast<char>((value >> 8) & 0xFF));
    data.append(static_cast<char>(value & 0xFF));
}

uint32_t crc32Bytes(const QByteArray& data) {
    uint32_t crc = 0xFFFFFFFFu;
    for (unsigned char byte : data) {
        crc ^= byte;
        for (int i = 0; i < 8; ++i) {
            const uint32_t mask = -(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return ~crc;
}

uint32_t adler32Bytes(const QByteArray& data) {
    constexpr uint32_t mod = 65521u;
    uint32_t s1 = 1u;
    uint32_t s2 = 0u;

    for (unsigned char byte : data) {
        s1 = (s1 + byte) % mod;
        s2 = (s2 + s1) % mod;
    }

    return (s2 << 16) | s1;
}

void appendPngChunk(QByteArray& output, const char type[4], const QByteArray& payload) {
    appendUint32BE(output, static_cast<uint32_t>(payload.size()));
    output.append(type, 4);
    output.append(payload);

    QByteArray crcInput;
    crcInput.append(type, 4);
    crcInput.append(payload);
    appendUint32BE(output, crc32Bytes(crcInput));
}

QByteArray buildStoredZlibStream(const QByteArray& rawBytes) {
    QByteArray encoded;
    encoded.append(static_cast<char>(0x78));
    encoded.append(static_cast<char>(0x01));

    int offset = 0;
    while (offset < rawBytes.size()) {
        const int chunkSize = std::min<int>(65535, rawBytes.size() - offset);
        const bool isFinalBlock = (offset + chunkSize) == rawBytes.size();

        encoded.append(static_cast<char>(isFinalBlock ? 0x01 : 0x00));
        appendUint16LE(encoded, static_cast<uint16_t>(chunkSize));
        appendUint16LE(encoded, static_cast<uint16_t>(~chunkSize));
        encoded.append(rawBytes.constData() + offset, chunkSize);

        offset += chunkSize;
    }

    appendUint32BE(encoded, adler32Bytes(rawBytes));
    return encoded;
}

bool writeGrayscalePng8(const std::vector<uint16_t>& imageData,
                        int width,
                        int height,
                        const QString& filename) {
    QByteArray encoded;
    encoded.append("\x89PNG\r\n\x1a\n", 8);

    QByteArray ihdr;
    appendUint32BE(ihdr, static_cast<uint32_t>(width));
    appendUint32BE(ihdr, static_cast<uint32_t>(height));
    ihdr.append(static_cast<char>(8));  // bit depth
    ihdr.append(static_cast<char>(0));  // grayscale
    ihdr.append(static_cast<char>(0));  // deflate
    ihdr.append(static_cast<char>(0));  // filter
    ihdr.append(static_cast<char>(0));  // no interlace
    appendPngChunk(encoded, "IHDR", ihdr);

    QByteArray rawScanlines;
    rawScanlines.reserve(height * (width + 1));
    for (int y = 0; y < height; ++y) {
        rawScanlines.append(static_cast<char>(0));  // filter type None
        for (int x = 0; x < width; ++x) {
            const uint16_t value = imageData[static_cast<size_t>(y * width + x)];
            rawScanlines.append(static_cast<char>(value >> 8));
        }
    }

    appendPngChunk(encoded, "IDAT", buildStoredZlibStream(rawScanlines));
    appendPngChunk(encoded, "IEND", QByteArray());

    QFile file(filename);
    if (!file.open(QIODevice::WriteOnly)) {
        return false;
    }

    return file.write(encoded) == encoded.size();
}

void appendTiffTagShort(QByteArray& ifd, uint16_t tag, uint16_t value) {
    appendUint16LE(ifd, tag);
    appendUint16LE(ifd, 3);  // SHORT
    appendUint32LE(ifd, 1);
    appendUint16LE(ifd, value);
    appendUint16LE(ifd, 0);
}

void appendTiffTagLong(QByteArray& ifd, uint16_t tag, uint32_t value) {
    appendUint16LE(ifd, tag);
    appendUint16LE(ifd, 4);  // LONG
    appendUint32LE(ifd, 1);
    appendUint32LE(ifd, value);
}

bool writeTiffStack16(const std::vector<std::vector<uint16_t>>& imageStack,
                      int width,
                      int height,
                      const QString& filename) {
    if (imageStack.empty()) {
        return false;
    }

    const uint32_t bytesPerImage = static_cast<uint32_t>(width * height * sizeof(uint16_t));
    constexpr uint16_t entryCount = 10;
    const uint32_t ifdSize = 2 + static_cast<uint32_t>(entryCount) * 12 + 4;
    const uint32_t firstIfdOffset = 8;
    const uint32_t pixelDataStart = firstIfdOffset + ifdSize * static_cast<uint32_t>(imageStack.size());

    QByteArray output;
    output.reserve(static_cast<int>(pixelDataStart + bytesPerImage * imageStack.size()));

    output.append("II", 2);
    appendUint16LE(output, 42);
    appendUint32LE(output, firstIfdOffset);

    uint32_t currentPixelOffset = pixelDataStart;
    for (size_t index = 0; index < imageStack.size(); ++index) {
        appendUint16LE(output, entryCount);
        appendTiffTagLong(output, 256, static_cast<uint32_t>(width));          // ImageWidth
        appendTiffTagLong(output, 257, static_cast<uint32_t>(height));         // ImageLength
        appendTiffTagShort(output, 258, 16);                                   // BitsPerSample
        appendTiffTagShort(output, 259, 1);                                    // Compression = none
        appendTiffTagShort(output, 262, 1);                                    // PhotometricInterpretation = BlackIsZero
        appendTiffTagLong(output, 273, currentPixelOffset);                    // StripOffsets
        appendTiffTagShort(output, 277, 1);                                    // SamplesPerPixel
        appendTiffTagLong(output, 278, static_cast<uint32_t>(height));         // RowsPerStrip
        appendTiffTagLong(output, 279, bytesPerImage);                         // StripByteCounts
        appendTiffTagShort(output, 339, 1);                                    // SampleFormat = unsigned int

        const bool hasNext = index + 1 < imageStack.size();
        const uint32_t nextIfdOffset = hasNext
            ? firstIfdOffset + ifdSize * static_cast<uint32_t>(index + 1)
            : 0u;
        appendUint32LE(output, nextIfdOffset);

        currentPixelOffset += bytesPerImage;
    }

    for (const auto& image : imageStack) {
        if (image.size() != static_cast<size_t>(width * height)) {
            return false;
        }

        for (uint16_t value : image) {
            appendUint16LE(output, value);
        }
    }

    QFile file(filename);
    if (!file.open(QIODevice::WriteOnly)) {
        return false;
    }

    return file.write(output) == output.size();
}

}  // namespace

// ==================== DataSaver ====================

DataSaver::DataSaver() = default;

DataSaver::~DataSaver() {
    stopSaving();
}

bool DataSaver::startSaving(const QString& filename) {
    if (m_isSaving) {
        stopSaving();
    }

    ensureDirectory(QFileInfo(filename).absolutePath());

    m_currentFile = new QFile(filename);
    if (!m_currentFile->open(QIODevice::WriteOnly)) {
        delete m_currentFile;
        m_currentFile = nullptr;
        return false;
    }

    m_currentFilename = filename;
    m_isSaving = true;
    return true;
}

bool DataSaver::savePacket(const QByteArray& packet) {
    if (!m_isSaving || !m_currentFile) {
        return false;
    }

    // 写入4字节长度前缀 + 数据
    uint32_t length = packet.size();
    m_currentFile->write(reinterpret_cast<const char*>(&length), sizeof(length));
    m_currentFile->write(packet);
    return true;
}

bool DataSaver::stopSaving() {
    if (m_currentFile) {
        m_currentFile->close();
        delete m_currentFile;
        m_currentFile = nullptr;
    }
    m_isSaving = false;
    return true;
}

bool DataSaver::savePacketsToBin(const std::vector<QByteArray>& packets, const QString& filename) {
    ensureDirectory(QFileInfo(filename).absolutePath());

    QFile file(filename);
    if (!file.open(QIODevice::WriteOnly)) {
        return false;
    }

    for (const auto& packet : packets) {
        if (!packet.isEmpty()) {
            uint32_t length = packet.size();
            file.write(reinterpret_cast<const char*>(&length), sizeof(length));
            file.write(packet);
        }
    }

    file.close();
    return true;
}

bool DataSaver::saveImageData(const std::vector<uint16_t>& imageData,
                               int width, int height,
                               const QString& filename,
                               const QString& format) {
    if (imageData.size() != static_cast<size_t>(width * height)) {
        return false;
    }

    ensureDirectory(QFileInfo(filename).absolutePath());

    if (format == "raw") {
        // 保存原始16位数据
        QFile file(filename);
        if (!file.open(QIODevice::WriteOnly)) {
            return false;
        }
        file.write(reinterpret_cast<const char*>(imageData.data()),
                   imageData.size() * sizeof(uint16_t));
        file.close();
        return true;
    }
    else if (format == "png") {
        return writeGrayscalePng8(imageData, width, height, filename);
    }
    else if (format == "tiff") {
        return writeTiffStack16({imageData}, width, height, filename);
    }

    return false;
}

bool DataSaver::saveStackData(const std::vector<std::vector<uint16_t>>& imageStack,
                               int width, int height,
                               const QString& filename) {
    if (imageStack.empty()) {
        return false;
    }

    ensureDirectory(QFileInfo(filename).absolutePath());

    return writeTiffStack16(imageStack, width, height, filename);
}

QString DataSaver::getDefaultSaveDir() {
    return QDir::currentPath() + "/saved_data";
}

bool DataSaver::ensureDirectory(const QString& path) {
    QDir dir(path);
    if (!dir.exists()) {
        return dir.mkpath(".");
    }
    return true;
}

// ==================== BatchDataSaver ====================

BatchDataSaver::BatchDataSaver() = default;

BatchDataSaver::~BatchDataSaver() {
    endSession();
}

QString BatchDataSaver::startSession(const QString& sessionName) {
    if (m_isActive) {
        endSession();
    }

    QString name = sessionName;
    if (name.isEmpty()) {
        name = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
    }

    m_sessionDir = DataSaver::getDefaultSaveDir() + "/session_" + name;
    DataSaver::ensureDirectory(m_sessionDir);

    m_frameCount = 0;
    m_isActive = true;

    return m_sessionDir;
}

void BatchDataSaver::endSession() {
    m_isActive = false;
}

bool BatchDataSaver::saveFrameData(const std::vector<QByteArray>& packets,
                                    const std::vector<uint16_t>& imageData,
                                    int width, int height) {
    if (!m_isActive) {
        return false;
    }

    m_frameCount++;

    // 创建帧目录
    QString frameDir = QString("%1/frame_%2")
                       .arg(m_sessionDir)
                       .arg(m_frameCount, 6, 10, QChar('0'));
    DataSaver::ensureDirectory(frameDir);

    // 保存原始数据
    if (!packets.empty()) {
        m_dataSaver.savePacketsToBin(packets, frameDir + "/raw_data.bin");
    }

    // 保存处理后的图像
    if (!imageData.empty()) {
        m_dataSaver.saveImageData(imageData, width, height,
                                   frameDir + "/processed_image.raw", "raw");
    }

    return true;
}
