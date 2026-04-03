#include "ProtocolCommands.h"

QByteArray ProtocolCommands::buildRegisterCommand(uint16_t address, uint32_t value) {
    QByteArray command;
    command.reserve(28);

    // 包头 (4字节): 0xAA 0xBB 0xAA 0xBB
    command.append(static_cast<char>(0xAA));
    command.append(static_cast<char>(0xBB));
    command.append(static_cast<char>(0xAA));
    command.append(static_cast<char>(0xBB));

    // 长度 (4字节): 0x00 0x00 0x00 0x0C (固定12字节)
    command.append(static_cast<char>(0x00));
    command.append(static_cast<char>(0x00));
    command.append(static_cast<char>(0x00));
    command.append(static_cast<char>(0x0C));

    // 设备ID (1字节): 0x51
    command.append(static_cast<char>(DEVICE_ID));

    // 寄存器地址 (2字节, 大端)
    command.append(static_cast<char>((address >> 8) & 0xFF));
    command.append(static_cast<char>(address & 0xFF));

    // 类型 (1字节): 0x02
    command.append(static_cast<char>(TYPE_WRITE));

    // 数据 (4字节, 大端)
    command.append(static_cast<char>((value >> 24) & 0xFF));
    command.append(static_cast<char>((value >> 16) & 0xFF));
    command.append(static_cast<char>((value >> 8) & 0xFF));
    command.append(static_cast<char>(value & 0xFF));

    // CRC32 占位符 (4字节): 0xFF 0xFF 0xFF 0xFF
    command.append(static_cast<char>(0xFF));
    command.append(static_cast<char>(0xFF));
    command.append(static_cast<char>(0xFF));
    command.append(static_cast<char>(0xFF));

    // 包尾 (8字节): 0x00 0x00 0x00 0x00 0x0D 0x0A 0x0D 0x0A
    command.append(static_cast<char>(0x00));
    command.append(static_cast<char>(0x00));
    command.append(static_cast<char>(0x00));
    command.append(static_cast<char>(0x00));
    command.append(static_cast<char>(0x0D));
    command.append(static_cast<char>(0x0A));
    command.append(static_cast<char>(0x0D));
    command.append(static_cast<char>(0x0A));

    return command;
}

QString ProtocolCommands::getRegisterName(uint16_t address) {
    static QMap<uint16_t, QString> names = {
        {REG_LIVE, "live"},
        {REG_EXIT, "exit"},
        {REG_FP_ALL_POINT, "fp_all_point"},
        {REG_FP_VALID_POINT, "fp_valid_point"},
        {REG_SAMPLE_NUM, "sample_num"},
        {REG_ACQ_DELAY, "acq_delay"},
        {REG_X_SWEEP_START_FRE, "x_sweep_start_fre"},
        {REG_X_SWEEP_END_FRE, "x_sweep_end_fre"},
        {REG_X_SWEEP_FRE_STEP, "x_sweep_fre_step"},
        {REG_X_SWEEP_INIT_PHASE, "x_sweep_init_phase"},
        {REG_X_SWEEP_FRE_KEEP_NUM, "x_sweep_fre_keep_num"},
        {REG_X_MIN, "x_min"},
        {REG_X_MAX, "x_max"},
        {REG_X_WORK_FRE, "x_work_fre"},
        {REG_X_WORK_INIT_PHASE, "x_work_init_phase"},
        {REG_Y_SWEEP_START_FRE, "y_sweep_start_fre"},
        {REG_Y_SWEEP_END_FRE, "y_sweep_end_fre"},
        {REG_Y_SWEEP_FRE_STEP, "y_sweep_fre_step"},
        {REG_Y_SWEEP_INIT_PHASE, "y_sweep_init_phase"},
        {REG_Y_SWEEP_FRE_KEEP_NUM, "y_sweep_fre_keep_num"},
        {REG_Y_MIN, "y_min"},
        {REG_Y_MAX, "y_max"},
        {REG_Y_WORK_FRE, "y_work_fre"},
        {REG_Y_WORK_INIT_PHASE, "y_work_init_phase"}
    };
    return names.value(address, QString("unknown_0x%1").arg(address, 4, 16, QChar('0')));
}

QList<uint16_t> ProtocolCommands::getAllRegisterAddresses() {
    return {
        REG_FP_ALL_POINT,
        REG_FP_VALID_POINT,
        REG_SAMPLE_NUM,
        REG_ACQ_DELAY,
        REG_X_SWEEP_START_FRE,
        REG_X_SWEEP_END_FRE,
        REG_X_SWEEP_FRE_STEP,
        REG_X_SWEEP_INIT_PHASE,
        REG_X_SWEEP_FRE_KEEP_NUM,
        REG_X_MIN,
        REG_X_MAX,
        REG_X_WORK_FRE,
        REG_X_WORK_INIT_PHASE,
        REG_Y_SWEEP_START_FRE,
        REG_Y_SWEEP_END_FRE,
        REG_Y_SWEEP_FRE_STEP,
        REG_Y_SWEEP_INIT_PHASE,
        REG_Y_SWEEP_FRE_KEEP_NUM,
        REG_Y_MIN,
        REG_Y_MAX,
        REG_Y_WORK_FRE,
        REG_Y_WORK_INIT_PHASE
    };
}

QMap<uint16_t, uint32_t> ProtocolCommands::getDefaultValues() {
    // 与 Python 版本 DEFAULT_MEMS_PARAMS 完全对应
    return {
        // 控制寄存器
        {REG_LIVE, 0},
        {REG_EXIT, 0},

        // 帧参数
        {REG_FP_ALL_POINT, 1500000},
        {REG_FP_VALID_POINT, 1000000},
        {REG_SAMPLE_NUM, 12},
        {REG_ACQ_DELAY, 3000},

        // X轴扫频参数 (与Python版本对齐)
        {REG_X_SWEEP_START_FRE, 23800},
        {REG_X_SWEEP_END_FRE, 23020},
        {REG_X_SWEEP_FRE_STEP, 10},
        {REG_X_SWEEP_INIT_PHASE, 0},
        {REG_X_SWEEP_FRE_KEEP_NUM, 100},
        {REG_X_MIN, 25000},
        {REG_X_MAX, 55000},
        {REG_X_WORK_FRE, 23020},
        {REG_X_WORK_INIT_PHASE, 0},

        // Y轴扫频参数 (与Python版本对齐)
        {REG_Y_SWEEP_START_FRE, 6000},
        {REG_Y_SWEEP_END_FRE, 5000},
        {REG_Y_SWEEP_FRE_STEP, 10},
        {REG_Y_SWEEP_INIT_PHASE, 0},
        {REG_Y_SWEEP_FRE_KEEP_NUM, 100},
        {REG_Y_MIN, 30000},
        {REG_Y_MAX, 50000},
        {REG_Y_WORK_FRE, 5000},
        {REG_Y_WORK_INIT_PHASE, 0}
    };
}

QString ProtocolCommands::commandToHexString(const QByteArray& command) {
    QString hexStr;
    for (int i = 0; i < command.size(); ++i) {
        if (i > 0) hexStr += " ";
        hexStr += QString("%1").arg(static_cast<uint8_t>(command[i]), 2, 16, QChar('0')).toUpper();
    }
    return hexStr;
}
