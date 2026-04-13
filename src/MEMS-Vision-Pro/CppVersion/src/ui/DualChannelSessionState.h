#ifndef DUAL_CHANNEL_SESSION_STATE_H
#define DUAL_CHANNEL_SESSION_STATE_H

#include <QMap>
#include <QString>
#include <QStringList>
#include <cstdint>

struct ChannelCounters {
    uint64_t bytes = 0;
    uint64_t packets = 0;
    uint64_t frames = 0;
};

struct PairedSavePlan {
    QStringList savedChannels;
    QStringList missingChannels;
    QMap<QString, QString> pathsByChannel;
};

class DualChannelSessionState {
public:
    bool startImaging() {
        if (m_imagingActive) {
            return false;
        }
        m_imagingActive = true;
        return true;
    }

    bool stopImaging() {
        const bool shouldFinalizeStacks = m_stackRecording;
        m_imagingActive = false;
        m_stackRecording = false;
        return shouldFinalizeStacks;
    }

    bool startStackRecording() {
        if (m_stackRecording) {
            return false;
        }
        m_stackRecording = true;
        return true;
    }

    bool stopStackRecording() {
        if (!m_stackRecording) {
            return false;
        }
        m_stackRecording = false;
        return true;
    }

    bool imagingActive() const { return m_imagingActive; }
    bool stackRecording() const { return m_stackRecording; }

    QString buildStatsText(const ChannelCounters& ch1,
                           const ChannelCounters& ch2,
                           int fps) const {
        return QString("CH1: %1 KB, %2 包, %3 帧 | CH2: %4 KB, %5 包, %6 帧 | FPS: %7")
            .arg(ch1.bytes / 1024)
            .arg(ch1.packets)
            .arg(ch1.frames)
            .arg(ch2.bytes / 1024)
            .arg(ch2.packets)
            .arg(ch2.frames)
            .arg(fps);
    }

    PairedSavePlan buildImageSavePlan(const QString& baseDir,
                                      const QString& timestamp,
                                      bool hasCh1Image,
                                      bool hasCh2Image) const {
        return buildPlan(baseDir, timestamp, hasCh1Image, hasCh2Image, "image", "raw");
    }

    PairedSavePlan buildStackSavePlan(const QString& baseDir,
                                      const QString& timestamp,
                                      bool hasCh1Stack,
                                      bool hasCh2Stack) const {
        return buildPlan(baseDir, timestamp, hasCh1Stack, hasCh2Stack, "stack", "raw");
    }

private:
    PairedSavePlan buildPlan(const QString& baseDir,
                             const QString& timestamp,
                             bool hasCh1,
                             bool hasCh2,
                             const QString& suffix,
                             const QString& extension) const {
        PairedSavePlan plan;

        if (hasCh1) {
            plan.savedChannels << "ch1";
            plan.pathsByChannel.insert(
                "ch1",
                QString("%1/ch1_%2_%3.%4").arg(baseDir, suffix, timestamp, extension));
        } else {
            plan.missingChannels << "ch1";
        }

        if (hasCh2) {
            plan.savedChannels << "ch2";
            plan.pathsByChannel.insert(
                "ch2",
                QString("%1/ch2_%2_%3.%4").arg(baseDir, suffix, timestamp, extension));
        } else {
            plan.missingChannels << "ch2";
        }

        return plan;
    }

    bool m_imagingActive = false;
    bool m_stackRecording = false;
};

#endif  // DUAL_CHANNEL_SESSION_STATE_H
