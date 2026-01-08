"""
协议命令模块
包含协议命令构建和解析工具
"""

from config.default_params import REGISTER_ADDRESSES


def build_register_command(address: int, value: int, data_length: int = 4) -> bytes:
    """
    构建寄存器设置命令（完整格式）

    Args:
        address: 寄存器地址
        value: 参数值
        data_length: 数据长度（保留参数兼容性，实际固定为4字节）

    Returns:
        bytes: 构建的命令字节数组

    完整命令格式:
    - Head (4字节): 0xAA 0xBB 0xAA 0xBB
    - Length (4字节): 数据长度（大端）0x00 0x00 0x00 0x0C
    - DeviceID (1字节): 0x51
    - reg_addr (2字节): 寄存器地址（大端）
    - Type (1字节): 0x02
    - Data (4字节): 数据值（大端）
    - CRC32 (4字节): 占位符 0xFF 0xFF 0xFF 0xFF
    - Tail (8字节): 0x00 0x00 0x00 0x00 0x0D 0x0A 0x0D 0x0A
    """
    # 构建命令数据部分
    # DeviceID(1) + Addr(2) + Type(1) + Data(4) = 8字节
    command_data = bytearray()

    # DeviceID: 0x51 (1字节)
    command_data.append(0x51)

    # reg_addr: 设置地址（2字节，大端）
    command_data.extend([
        (address >> 8) & 0xFF,
        address & 0xFF
    ])

    # Type: 0x02 (1字节)
    command_data.append(0x02)

    # data4/data3/data2/data1: 设置数据（4字节，高位在前）
    command_data.extend([
        (value >> 24) & 0xFF,
        (value >> 16) & 0xFF,
        (value >> 8) & 0xFF,
        value & 0xFF
    ])

    # 构建完整命令
    command = bytearray()

    # 包头: 0xAA,0xBB,0xAA,0xBB (4字节)
    command.extend([0xAA, 0xBB, 0xAA, 0xBB])

    # Length: 数据长度（4字节，大端）- 固定为0x0C(12字节)
    command.extend([0x00, 0x00, 0x00, 0x0C])

    # 添加命令数据
    command.extend(command_data)

    # CRC32: 占位符 0xFF 0xFF 0xFF 0xFF (4字节)
    command.extend([0xFF, 0xFF, 0xFF, 0xFF])

    # 包尾: 0x00,0x00,0x00,0x00,0x0D,0x0A,0x0D,0x0A (8字节)
    command.extend([0x00, 0x00, 0x00, 0x00, 0x0D, 0x0A, 0x0D, 0x0A])

    return bytes(command)


# 预定义的常用命令
class ProtocolCommands:
    """协议命令常量类"""

    # 新协议寄存器地址（从REGISTER_ADDRESSES引用）
    LIVE = REGISTER_ADDRESSES['live']
    EXIT = REGISTER_ADDRESSES['exit']
    FP_ALL_POINT = REGISTER_ADDRESSES['fp_all_point']
    FP_VALID_POINT = REGISTER_ADDRESSES['fp_valid_point']
    SAMPLE_NUM = REGISTER_ADDRESSES['sample_num']
    ACQ_DELAY_NEW = REGISTER_ADDRESSES['acq_delay']
    X_SWEEP_START_FRE = REGISTER_ADDRESSES['x_sweep_start_fre']
    X_SWEEP_END_FRE = REGISTER_ADDRESSES['x_sweep_end_fre']
    X_SWEEP_FRE_STEP = REGISTER_ADDRESSES['x_sweep_fre_step']
    X_SWEEP_INIT_PHASE = REGISTER_ADDRESSES['x_sweep_init_phase']
    X_SWEEP_FRE_KEEP_NUM = REGISTER_ADDRESSES['x_sweep_fre_keep_num']
    X_MIN = REGISTER_ADDRESSES['x_min']
    X_MAX = REGISTER_ADDRESSES['x_max']
    X_WORK_FRE = REGISTER_ADDRESSES['x_work_fre']
    X_WORK_INIT_PHASE = REGISTER_ADDRESSES['x_work_init_phase']
    Y_SWEEP_START_FRE = REGISTER_ADDRESSES['y_sweep_start_fre']
    Y_SWEEP_END_FRE = REGISTER_ADDRESSES['y_sweep_end_fre']
    Y_SWEEP_FRE_STEP = REGISTER_ADDRESSES['y_sweep_fre_step']
    Y_SWEEP_INIT_PHASE = REGISTER_ADDRESSES['y_sweep_init_phase']
    Y_SWEEP_FRE_KEEP_NUM = REGISTER_ADDRESSES['y_sweep_fre_keep_num']
    Y_MIN = REGISTER_ADDRESSES['y_min']
    Y_MAX = REGISTER_ADDRESSES['y_max']
    Y_WORK_FRE = REGISTER_ADDRESSES['y_work_fre']
    Y_WORK_INIT_PHASE = REGISTER_ADDRESSES['y_work_init_phase']
