#ifndef PROTOCOL_CONTROL_WORKFLOW_H
#define PROTOCOL_CONTROL_WORKFLOW_H

#include <QList>
#include <QString>
#include <cstdint>

struct ProtocolControlStep {
    uint16_t address = 0;
    uint32_t value = 0;
    QString label;
};

class ProtocolControlWorkflow {
public:
    static QList<ProtocolControlStep> startupSequence();
    static QList<ProtocolControlStep> shutdownSequence();

    static ProtocolControlStep enableMems();
    static ProtocolControlStep disableMems();
    static ProtocolControlStep startMems();
    static ProtocolControlStep stopMems();
};

#endif  // PROTOCOL_CONTROL_WORKFLOW_H
