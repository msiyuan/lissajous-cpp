"""
协议命令模块
包含协议命令构建和解析工具
"""

import struct
from config.constants import PROTOCOL_HEADER, MEMS_START_CMD, MEMS_STOP_CMD

# 新协议寄存器地址定义
REGISTER_ADDRESSES = {
    'live': 0x801,
    'exit': 0x802,
    'fp_all_point': 0x110,
    'fp_valid_point': 0x111,
    'sample_num': 0x112,
    'acq_delay': 0x113,
    'x_sweep_start_fre': 0x120,
    'x_sweep_end_fre': 0x121,
    'x_sweep_fre_step': 0x122,
    'x_sweep_init_phase': 0x123,
    'x_sweep_fre_keep_num': 0x124,
    'x_min': 0x125,
    'x_max': 0x126,
    'x_work_fre': 0x127,
    'x_work_init_phase': 0x128,
    'y_sweep_start_fre': 0x130,
    'y_sweep_end_fre': 0x131,
    'y_sweep_fre_step': 0x132,
    'y_sweep_init_phase': 0x133,
    'y_sweep_fre_keep_num': 0x134,
    'y_min': 0x135,
    'y_max': 0x136,
    'y_work_fre': 0x137,
    'y_work_init_phase': 0x138,
}

# 新协议寄存器默认值
REGISTER_DEFAULTS = {
    'live': 0,
    'exit': 0,
    'fp_all_point': 1500000,
    'fp_valid_point': 1000000,
    'sample_num': 12,
    'acq_delay': 3000,
    'x_sweep_start_fre': 25000,
    'x_sweep_end_fre': 22000,
    'x_sweep_fre_step': 1000,
    'x_sweep_init_phase': 0,
    'x_sweep_fre_keep_num': 32,
    'x_min': 25000,
    'x_max': 55000,
    'x_work_fre': 22000,
    'x_work_init_phase': 0,
    'y_sweep_start_fre': 8500,
    'y_sweep_end_fre': 6000,
    'y_sweep_fre_step': 100,
    'y_sweep_init_phase': 0,
    'y_sweep_fre_keep_num': 32,
    'y_min': 25000,
    'y_max': 55000,
    'y_work_fre': 6000,
    'y_work_init_phase': 0,
}

def build_register_command(address: int, value: int, data_length: int) -> bytes:
    """
    构建寄存器设置命令（新协议）
    
    Args:
        address: 寄存器地址
        value: 参数值
        data_length: 数据长度（1、2或4字节）
        
    Returns:
        bytes: 构建的命令字节数组
    """
    # 构建命令数据部分（不包括包头、长度、CRC和包尾）
    command_data = bytearray()
    
    # DeviceID: 0x51
    command_data.append(0x51)
    
    # reg_addr: 设置地址（4字节，大端）
    command_data.extend([
        (address >> 24) & 0xFF,
        (address >> 16) & 0xFF,
        (address >> 8) & 0xFF,
        address & 0xFF
    ])
    
    # Type: 0x02
    command_data.append(0x02)
    
    # data4/data3/data2/data1: 设置数据（高位在前）
    if data_length == 1:
        command_data.extend([0x00, 0x00, 0x00, value & 0xFF])
    elif data_length == 2:
        command_data.extend([
            0x00, 0x00,
            (value >> 8) & 0xFF,
            value & 0xFF
        ])
    elif data_length == 4:
        command_data.extend([
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF
        ])
    else:
        raise ValueError(f"不支持的数据长度: {data_length}")
    
    # 计算总长度（固定为12字节，根据规范）
    total_length = 12
    
    # 构建完整命令
    command = bytearray()
    
    # 包头: 0xAA,0xBB,0xAA,0xBB
    command.extend([0xAA, 0xBB, 0xAA, 0xBB])
    
    # Length-4Bytes: 数据长度（大端）
    command.extend([
        (total_length >> 24) & 0xFF,
        (total_length >> 16) & 0xFF,
        (total_length >> 8) & 0xFF,
        total_length & 0xFF
    ])
    
    # 添加命令数据
    command.extend(command_data)
    
    # CRC-32-4Bytes: 简单填充，实际应用中需要计算真实的CRC32值
    command.extend([0xFF, 0xFF, 0xFF, 0xFF])
    
    # 包尾: 0x0D,0x0A,0x0D,0x0A
    command.extend([0x0D, 0x0A, 0x0D, 0x0A])
    
    return bytes(command)

# 预定义的常用命令
class ProtocolCommands:
    """协议命令常量类"""
    
    # 新协议寄存器地址
    LIVE = 0x801
    EXIT = 0x802
    FP_ALL_POINT = 0x110
    FP_VALID_POINT = 0x111
    SAMPLE_NUM = 0x112
    ACQ_DELAY_NEW = 0x113
    X_SWEEP_START_FRE = 0x120
    X_SWEEP_END_FRE = 0x121
    X_SWEEP_FRE_STEP = 0x122
    X_SWEEP_INIT_PHASE = 0x123
    X_SWEEP_FRE_KEEP_NUM = 0x124
    X_MIN = 0x125
    X_MAX = 0x126
    X_WORK_FRE = 0x127
    X_WORK_INIT_PHASE = 0x128
    Y_SWEEP_START_FRE = 0x130
    Y_SWEEP_END_FRE = 0x131
    Y_SWEEP_FRE_STEP = 0x132
    Y_SWEEP_INIT_PHASE = 0x133
    Y_SWEEP_FRE_KEEP_NUM = 0x134
    Y_MIN = 0x135
    Y_MAX = 0x136
    Y_WORK_FRE = 0x137
    Y_WORK_INIT_PHASE = 0x138