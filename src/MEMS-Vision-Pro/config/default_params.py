"""
默认参数配置
"""

# MEMS默认参数（新协议）
DEFAULT_MEMS_PARAMS = {
    # 帧参数
    'fp_all_point': 1500000,
    'fp_valid_point': 1000000,
    'sample_num': 12,
    'acq_delay': 3000,
    
    # X轴扫频参数
    'x_sweep_start_fre': 23800,
    'x_sweep_end_fre': 23020,
    'x_sweep_fre_step': 10,
    'x_sweep_init_phase': 0,
    'x_sweep_fre_keep_num': 100,
    'x_min': 25000,
    'x_max': 55000,
    'x_work_fre': 23020,
    'x_work_init_phase': 0,
    
    # Y轴扫频参数
    'y_sweep_start_fre': 6000,
    'y_sweep_end_fre': 5000,
    'y_sweep_fre_step': 10,
    'y_sweep_init_phase': 0,
    'y_sweep_fre_keep_num': 100,
    'y_min': 30000,
    'y_max': 50000, # 电压
    'y_work_fre': 5000,
    'y_work_init_phase': 0,
}

# 图像处理默认参数
DEFAULT_IMAGE_PARAMS = {
    'deltaphasex': 0.0,
    'deltaphasey': 0.0,
    'freqx': 11360,
    'freqy': 3690
}

# 网络默认参数
DEFAULT_NETWORK_PARAMS = {
    'target_ip': '192.168.1.91',
    'recv_port': 8003,
    'send_port': 8003
}

# 图像采集与传输默认参数
DEFAULT_ACQ_PARAMS = {
    'acq_delay': 3000,
    'trigger_level': 1400,
    'packet_interval': 100,
    'selftest_count': 10000
}

# 系统控制默认参数
DEFAULT_SYSTEM_PARAMS = {
    'x_compensation': 350,
    'y_compensation': 480,
    'watchdog_timeout': 20
}

# 界面默认参数
DEFAULT_UI_PARAMS = {
    'frame_buffer_size': 10,
    'max_slider_value': 65535,
    'min_slider_value': 0,
    'contrast_value': 100,
    'brightness_value': 0
}

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
    'mems_en': 0x114,           # MEMS使能
    'mems_start': 0x115,        # 启动
    'normal_work_start': 0x116,    # 正常工作开始
    'sweep_stop': 0x117,           # 扫频停止
    'manual_ad_samp': 0x118,       # 手动AD采集
    'sweep_repeat_num': 0x140,     # 扫频重复次数
    'x_phase_add_value': 0x141,    # X相位累加值
    'x_amplitude_gain': 0x142,     # X幅值增益
    'x_zero_offset': 0x143,        # X零点偏移
    'y_phase_add_value': 0x144,    # Y相位累加值
    'y_amplitude_gain': 0x145,    # Y幅值增益
    'y_zero_offset': 0x146,       # Y零点偏移
    'ad_samp_period': 0x147,       # AD采样周期
    'ff_interval_period': 0x148,   # 反馈间隔周期
}

# 新协议寄存器默认值（合并DEFAULT_MEMS_PARAMS和额外的控制寄存器）
REGISTER_DEFAULTS = {
    **{k: v for k, v in DEFAULT_MEMS_PARAMS.items() if k != 'live' and k != 'exit'},
    'live': 0,
    'exit': 0,
    'mems_en': 0,
    'mems_start': 0,
    'normal_work_start': 0,
    'sweep_stop': 0,
    'manual_ad_samp': 0,
    'sweep_repeat_num': 1,
    'x_phase_add_value': 764369,
    'x_amplitude_gain': 100,
    'x_zero_offset': 0,
    'y_phase_add_value': 251658,
    'y_amplitude_gain': 100,
    'y_zero_offset': 0,
    'ad_samp_period': 12000000,
    'ff_interval_period': 1200000,
}