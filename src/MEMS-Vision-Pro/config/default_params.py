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
    'x_sweep_start_fre': 25000,
    'x_sweep_end_fre': 22000,
    'x_sweep_fre_step': 1000,
    'x_sweep_init_phase': 0,
    'x_sweep_fre_keep_num': 32,
    'x_min': 25000,
    'x_max': 55000,
    'x_work_fre': 22000,
    'x_work_init_phase': 0,
    
    # Y轴扫频参数
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

# 图像处理默认参数
DEFAULT_IMAGE_PARAMS = {
    'deltaphasex': 0.0,
    'deltaphasey': 0.0,
    'freqx': 22000,
    'freqy': 6000
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