"""
协议命令模块
包含协议命令构建和解析工具
"""

from config.constants import PROTOCOL_HEADER, MEMS_START_CMD, MEMS_STOP_CMD

def build_mems_command(cmd_code: int, value: int, data_length: int) -> bytes:
    """
    构建MEMS控制命令
    
    Args:
        cmd_code: 命令代码
        value: 参数值
        data_length: 数据长度（1、2或4字节）
        
    Returns:
        bytes: 构建的命令字节数组
    """
    command = bytearray([PROTOCOL_HEADER, cmd_code, data_length])
    
    if data_length == 1:
        command.append(value & 0xFF)
    elif data_length == 2:
        command.extend([(value >> 8) & 0xFF, value & 0xFF])
    elif data_length == 4:
        command.extend([
            (value >> 24) & 0xFF,
            (value >> 16) & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF
        ])
    else:
        raise ValueError(f"不支持的数据长度: {data_length}")
    
    return bytes(command)

def build_sweep_command(wave_type: int, repeat_count: int) -> bytes:
    """
    构建扫频命令
    
    Args:
        wave_type: 波形类型 (0x01=正弦波, 0x22=方波)
        repeat_count: 重复次数
        
    Returns:
        bytes: 扫频命令
    """
    return bytes([PROTOCOL_HEADER, 0x50, 0x02, wave_type, repeat_count])

def build_sweep_control_command(start: bool) -> bytes:
    """
    构建扫频启停命令
    
    Args:
        start: True为启动，False为停止
        
    Returns:
        bytes: 扫频控制命令
    """
    action = MEMS_START_CMD if start else MEMS_STOP_CMD
    return bytes([PROTOCOL_HEADER, 0x51, 0x01, action])

def build_freq_range_command(cmd_code: int, start_freq: int, end_freq: int) -> bytes:
    """
    构建频率范围设置命令
    
    Args:
        cmd_code: 命令代码
        start_freq: 起始频率
        end_freq: 结束频率
        
    Returns:
        bytes: 频率范围命令
    """
    command = bytearray([PROTOCOL_HEADER, cmd_code, 0x08])
    # 起始频率（4字节，大端格式）
    command.extend([
        (start_freq >> 24) & 0xFF,
        (start_freq >> 16) & 0xFF,
        (start_freq >> 8) & 0xFF,
        start_freq & 0xFF
    ])
    # 结束频率（4字节，大端格式）
    command.extend([
        (end_freq >> 24) & 0xFF,
        (end_freq >> 16) & 0xFF,
        (end_freq >> 8) & 0xFF,
        end_freq & 0xFF
    ])
    return bytes(command)

def build_sine_sweep_params_command(cmd_code: int, step: int, amplitude: int, 
                                  phase: int, keep_cycles: int) -> bytes:
    """
    构建正弦波扫频参数命令
    
    Args:
        cmd_code: 命令代码
        step: 步进值
        amplitude: 幅值
        phase: 初相位
        keep_cycles: 维持周期数
        
    Returns:
        bytes: 正弦波扫频参数命令
    """
    command = bytearray([PROTOCOL_HEADER, cmd_code, 0x08])
    # 步进（2字节）
    command.extend([(step >> 8) & 0xFF, step & 0xFF])
    # 幅值（2字节）
    command.extend([(amplitude >> 8) & 0xFF, amplitude & 0xFF])
    # 初相位（2字节）
    command.extend([(phase >> 8) & 0xFF, phase & 0xFF])
    # 维持周期数（2字节）
    command.extend([(keep_cycles >> 8) & 0xFF, keep_cycles & 0xFF])
    return bytes(command)

def build_square_sweep_params_command(cmd_code: int, step: int, duty: int, delay: int) -> bytes:
    """
    构建方波扫频参数命令
    
    Args:
        cmd_code: 命令代码
        step: 步进值
        duty: 占空比（百分比）
        delay: 相位延时
        
    Returns:
        bytes: 方波扫频参数命令
    """
    command = bytearray([PROTOCOL_HEADER, cmd_code, 0x06])
    # 步进（2字节）
    command.extend([(step >> 8) & 0xFF, step & 0xFF])
    # 占空比（2字节，需要转换为0-1000范围）
    duty_value = duty * 10  # 将百分比转换为千分比
    command.extend([(duty_value >> 8) & 0xFF, duty_value & 0xFF])
    # 相位延时（2字节）
    command.extend([(delay >> 8) & 0xFF, delay & 0xFF])
    return bytes(command)

def build_compensation_command(x_comp: int, y_comp: int) -> bytes:
    """
    构建硬件补偿命令
    
    Args:
        x_comp: X轴补偿值（有符号16位）
        y_comp: Y轴补偿值（有符号16位）
        
    Returns:
        bytes: 硬件补偿命令
    """
    # 处理负数（16位有符号整数）
    if x_comp < 0:
        x_comp = 65536 + x_comp
    if y_comp < 0:
        y_comp = 65536 + y_comp
        
    command = bytearray([PROTOCOL_HEADER, 0x47, 0x04])
    # X补偿值（2字节）
    command.extend([(x_comp >> 8) & 0xFF, x_comp & 0xFF])
    # Y补偿值（2字节）
    command.extend([(y_comp >> 8) & 0xFF, y_comp & 0xFF])
    return bytes(command)

def build_read_command(cmd_code: int) -> bytes:
    """
    构建读取命令
    
    Args:
        cmd_code: 命令代码
        
    Returns:
        bytes: 读取命令
    """
    return bytes([PROTOCOL_HEADER, cmd_code, 0x01, MEMS_START_CMD])

def build_simple_command(cmd_code: int, action: int = MEMS_START_CMD) -> bytes:
    """
    构建简单命令
    
    Args:
        cmd_code: 命令代码
        action: 动作代码（默认为启动）
        
    Returns:
        bytes: 简单命令
    """
    return bytes([PROTOCOL_HEADER, cmd_code, 0x01, action])

# 预定义的常用命令
class ProtocolCommands:
    """协议命令常量类"""
    
    # MEMS控制命令代码
    MEMS_CONTROL = 0x31
    AD_CONTROL = 0x34
    SELFTEST_CONTROL = 0x35
    WATCHDOG_CONTROL = 0x43
    FEED_DOG = 0x45
    
    # 参数设置命令代码
    X0_GAIN = 0x20
    X0_FREQ = 0x21
    X0_PHASE = 0x22
    X1_GAIN = 0x23
    X1_FREQ = 0x24
    X1_PHASE = 0x25
    
    Y0_GAIN = 0x26
    Y0_FREQ = 0x27
    Y0_PHASE = 0x28
    Y1_GAIN = 0x29
    Y1_FREQ = 0x2A
    Y1_PHASE = 0x2B
    
    # 采集参数命令代码
    ACQ_DELAY = 0x30
    AD_RATE = 0x32
    TRIGGER_LEVEL = 0x33
    PACKET_INTERVAL = 0x36
    SELFTEST_COUNT = 0x37
    DUAL_PARAM_MODE = 0x38
    
    # 读取命令代码
    READ_MEMS_PHASE = 0x40
    READ_DDR3_STATUS = 0x48
    
    # 补偿命令代码
    HARDWARE_COMPENSATION = 0x47
    
    # 看门狗命令代码
    WATCHDOG_TIMEOUT = 0x44
    
    # 扫频命令代码
    SWEEP_TYPE = 0x50
    SWEEP_CONTROL = 0x51
    X_SINE_FREQ_RANGE = 0x52
    X_SINE_PARAMS = 0x53
    X_SQUARE_FREQ_RANGE = 0x54
    X_SQUARE_PARAMS = 0x55
    Y_SINE_FREQ_RANGE = 0x56
    Y_SINE_PARAMS = 0x57
    Y_SQUARE_FREQ_RANGE = 0x58
    Y_SQUARE_PARAMS = 0x59