#ifndef PROTOCOL_COMMANDS_H
#define PROTOCOL_COMMANDS_H

#include <QByteArray>
#include <QMap>
#include <QString>
#include <cstdint>

/**
 * 协议命令构建器
 * 用于生成发送到下位机的控制命令
 *
 * 命令格式 (28字节):
 * - Head (4字节): 0xAA 0xBB 0xAA 0xBB
 * - Length (4字节): 0x00 0x00 0x00 0x0C (固定12字节)
 * - DeviceID (1字节): 0x51
 * - reg_addr (2字节): 寄存器地址（大端）
 * - Type (1字节): 0x02
 * - Data (4字节): 数据值（大端）
 * - CRC32 (4字节): 0xFF 0xFF 0xFF 0xFF（占位符）
 * - Tail (8字节): 0x00 0x00 0x00 0x00 0x0D 0x0A 0x0D 0x0A
 */
class ProtocolCommands {
public:
    // 寄存器地址定义 (与 Python 版本 REGISTER_ADDRESSES 完全对应)
    enum RegisterAddress : uint16_t {
        // 控制寄存器
        REG_LIVE = 0x0801,              // 开始成像
        REG_EXIT = 0x0802,              // 停止成像

        // 帧参数
        REG_FP_ALL_POINT = 0x0110,      // 总采样点数
        REG_FP_VALID_POINT = 0x0111,    // 有效采样点数
        REG_SAMPLE_NUM = 0x0112,        // 采样数
        REG_ACQ_DELAY = 0x0113,         // 采集延迟
        REG_MEMS_EN = 0x0114,           // MEMS使能
        REG_MEMS_START = 0x0115,        // MEMS启动
        REG_NORMAL_WORK_START = 0x0116, // 正常工作开始
        REG_SWEEP_STOP = 0x0117,        // 扫频停止
        REG_MANUAL_AD_SAMP = 0x0118,    // 手动AD采集

        // X轴扫频参数
        REG_X_SWEEP_START_FRE = 0x0120,     // X扫频起始频率
        REG_X_SWEEP_END_FRE = 0x0121,       // X扫频结束频率
        REG_X_SWEEP_FRE_STEP = 0x0122,      // X扫频步进
        REG_X_SWEEP_INIT_PHASE = 0x0123,    // X扫频初始相位
        REG_X_SWEEP_FRE_KEEP_NUM = 0x0124,  // X扫频保持数
        REG_X_MIN = 0x0125,                 // X最小值（电压）
        REG_X_MAX = 0x0126,                 // X最大值（电压）
        REG_X_WORK_FRE = 0x0127,            // X工作频率
        REG_X_WORK_INIT_PHASE = 0x0128,     // X工作初始相位

        // Y轴扫频参数
        REG_Y_SWEEP_START_FRE = 0x0130,     // Y扫频起始频率
        REG_Y_SWEEP_END_FRE = 0x0131,       // Y扫频结束频率
        REG_Y_SWEEP_FRE_STEP = 0x0132,      // Y扫频步进
        REG_Y_SWEEP_INIT_PHASE = 0x0133,    // Y扫频初始相位
        REG_Y_SWEEP_FRE_KEEP_NUM = 0x0134,  // Y扫频保持数
        REG_Y_MIN = 0x0135,                 // Y最小值（电压）
        REG_Y_MAX = 0x0136,                 // Y最大值（电压）
        REG_Y_WORK_FRE = 0x0137,            // Y工作频率
        REG_Y_WORK_INIT_PHASE = 0x0138,     // Y工作初始相位

        // 扩展控制参数
        REG_SWEEP_REPEAT_NUM = 0x0140,      // 扫频重复次数
        REG_X_PHASE_ADD_VALUE = 0x0141,     // X相位累加值
        REG_X_AMPLITUDE_GAIN = 0x0142,      // X幅值增益
        REG_X_ZERO_OFFSET = 0x0143,         // X零点偏移
        REG_Y_PHASE_ADD_VALUE = 0x0144,     // Y相位累加值
        REG_Y_AMPLITUDE_GAIN = 0x0145,      // Y幅值增益
        REG_Y_ZERO_OFFSET = 0x0146,         // Y零点偏移
        REG_AD_SAMP_PERIOD = 0x0147,        // AD采样周期
        REG_FF_INTERVAL_PERIOD = 0x0148     // 反馈间隔周期
    };

    /**
     * 构建寄存器命令
     * @param address 寄存器地址
     * @param value 参数值
     * @return 28字节命令
     */
    static QByteArray buildRegisterCommand(uint16_t address, uint32_t value);

    /**
     * 构建开始成像命令 (live = 1)
     */
    static QByteArray buildStartCommand() {
        return buildRegisterCommand(REG_LIVE, 1);
    }

    /**
     * 构建停止成像命令 (exit = 1)
     */
    static QByteArray buildStopCommand() {
        return buildRegisterCommand(REG_EXIT, 1);
    }

    /**
     * 获取寄存器名称
     */
    static QString getRegisterName(uint16_t address);

    /**
     * 获取所有寄存器地址列表
     */
    static QList<uint16_t> getAllRegisterAddresses();

    /**
     * 获取所有寄存器地址和默认值
     */
    static QMap<uint16_t, uint32_t> getDefaultValues();

    /**
     * 将命令转换为十六进制字符串（用于日志显示）
     */
    static QString commandToHexString(const QByteArray& command);

private:
    static const uint8_t DEVICE_ID = 0x51;
    static const uint8_t TYPE_WRITE = 0x02;
};

#endif  // PROTOCOL_COMMANDS_H
