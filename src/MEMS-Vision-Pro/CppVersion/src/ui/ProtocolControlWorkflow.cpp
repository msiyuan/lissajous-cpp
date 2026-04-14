#include "ProtocolControlWorkflow.h"

#include "network/ProtocolCommands.h"

QList<ProtocolControlStep> ProtocolControlWorkflow::startupSequence() {
    return {
        enableMems(),
        startMems(),
        {ProtocolCommands::REG_LIVE, 1, "开始成像"},
    };
}

QList<ProtocolControlStep> ProtocolControlWorkflow::shutdownSequence() {
    return {
        {ProtocolCommands::REG_EXIT, 1, "结束成像"},
        stopMems(),
        disableMems(),
    };
}

ProtocolControlStep ProtocolControlWorkflow::enableMems() {
    return {ProtocolCommands::REG_MEMS_EN, 1, "使能MEMS"};
}

ProtocolControlStep ProtocolControlWorkflow::disableMems() {
    return {ProtocolCommands::REG_MEMS_EN, 0, "关闭MEMS"};
}

ProtocolControlStep ProtocolControlWorkflow::startMems() {
    return {ProtocolCommands::REG_MEMS_START, 1, "启动MEMS"};
}

ProtocolControlStep ProtocolControlWorkflow::stopMems() {
    return {ProtocolCommands::REG_MEMS_START, 0, "停止MEMS"};
}
