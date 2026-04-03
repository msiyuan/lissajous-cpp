#include "DataSaver.h"
#include <QDateTime>
#include <QDataStream>
#include <QImage>
#include <QDebug>

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
        // 转换为8位PNG
        QImage image(width, height, QImage::Format_Grayscale8);
        for (int y = 0; y < height; ++y) {
            uint8_t* line = image.scanLine(y);
            for (int x = 0; x < width; ++x) {
                uint16_t val = imageData[y * width + x];
                line[x] = static_cast<uint8_t>(val >> 8);  // 取高8位
            }
        }
        return image.save(filename, "PNG");
    }
    else if (format == "tiff") {
        // 保存为16位TIFF (使用原始格式，因为Qt不直接支持16位TIFF)
        // 这里保存为raw格式，文件扩展名为.tiff
        QFile file(filename);
        if (!file.open(QIODevice::WriteOnly)) {
            return false;
        }

        // 简单的TIFF头 (这是一个简化版本)
        // 实际项目中建议使用libtiff库
        file.write(reinterpret_cast<const char*>(imageData.data()),
                   imageData.size() * sizeof(uint16_t));
        file.close();
        return true;
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

    // 保存为原始堆栈格式
    QFile file(filename);
    if (!file.open(QIODevice::WriteOnly)) {
        return false;
    }

    // 写入头信息
    uint32_t numImages = imageStack.size();
    uint32_t w = width;
    uint32_t h = height;
    file.write(reinterpret_cast<const char*>(&numImages), sizeof(numImages));
    file.write(reinterpret_cast<const char*>(&w), sizeof(w));
    file.write(reinterpret_cast<const char*>(&h), sizeof(h));

    // 写入每帧数据
    for (const auto& image : imageStack) {
        if (image.size() == static_cast<size_t>(width * height)) {
            file.write(reinterpret_cast<const char*>(image.data()),
                       image.size() * sizeof(uint16_t));
        }
    }

    file.close();
    return true;
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
