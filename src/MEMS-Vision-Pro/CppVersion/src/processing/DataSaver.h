#ifndef DATA_SAVER_H
#define DATA_SAVER_H

#include <QString>
#include <QByteArray>
#include <QFile>
#include <QDir>
#include <vector>
#include <cstdint>
#include <memory>

/**
 * 数据保存器
 * 支持数据包、图像和图像堆栈保存
 */
class DataSaver {
public:
    DataSaver();
    ~DataSaver();

    /**
     * 开始保存会话
     */
    bool startSaving(const QString& filename);

    /**
     * 保存单个数据包
     */
    bool savePacket(const QByteArray& packet);

    /**
     * 停止保存会话
     */
    bool stopSaving();

    /**
     * 保存数据包列表到二进制文件
     */
    bool savePacketsToBin(const std::vector<QByteArray>& packets, const QString& filename);

    /**
     * 保存图像数据
     * @param imageData 图像数据 (512x512)
     * @param filename 文件名
     * @param format 格式: "raw", "png", "tiff"
     */
    bool saveImageData(const std::vector<uint16_t>& imageData,
                       int width, int height,
                       const QString& filename,
                       const QString& format = "png");

    /**
     * 保存图像堆栈为多页TIFF
     */
    bool saveStackData(const std::vector<std::vector<uint16_t>>& imageStack,
                       int width, int height,
                       const QString& filename);

    /**
     * 获取默认保存目录
     */
    static QString getDefaultSaveDir();

    /**
     * 确保目录存在
     */
    static bool ensureDirectory(const QString& path);

private:
    QFile* m_currentFile = nullptr;
    QString m_currentFilename;
    bool m_isSaving = false;
};

/**
 * 批量数据保存器
 * 用于会话管理和帧数据保存
 */
class BatchDataSaver {
public:
    BatchDataSaver();
    ~BatchDataSaver();

    /**
     * 开始保存会话
     * @return 会话目录路径
     */
    QString startSession(const QString& sessionName = QString());

    /**
     * 结束保存会话
     */
    void endSession();

    /**
     * 保存帧数据
     */
    bool saveFrameData(const std::vector<QByteArray>& packets,
                       const std::vector<uint16_t>& imageData,
                       int width, int height);

    /**
     * 获取当前帧计数
     */
    int frameCount() const { return m_frameCount; }

    /**
     * 获取会话目录
     */
    QString sessionDir() const { return m_sessionDir; }

private:
    QString m_sessionDir;
    int m_frameCount = 0;
    bool m_isActive = false;
    DataSaver m_dataSaver;
};

#endif  // DATA_SAVER_H
