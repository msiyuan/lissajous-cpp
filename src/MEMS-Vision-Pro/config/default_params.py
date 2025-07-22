"""
默认参数配置
"""

# MEMS默认参数
DEFAULT_MEMS_PARAMS = {
    # MEMS驱动参数（原组0参数）
    'x0_gain': 300,
    'x0_freq': 11380,
    'x0_phase': 0,
    'y0_gain': 300,
    'y0_freq': 3810,
    'y0_phase': 0,
    
    # 扫频参数
    'sweep_repeat': 1,
    'x_sweep_start_freq': 22780,
    'x_sweep_end_freq': 23500,
    'y_sweep_start_freq': 7580,
    'y_sweep_end_freq': 8500,
    
    # X轴正弦波扫频参数
    'x_sine_step': 2,
    'x_sine_amplitude': 300,
    'x_sine_phase': 0,
    'x_sine_keep': 100,
    
    # Y轴正弦波扫频参数
    'y_sine_step': 2,
    'y_sine_amplitude': 300,
    'y_sine_phase': 0,
    'y_sine_keep': 100,
}

# 图像处理默认参数
DEFAULT_IMAGE_PARAMS = {
    'deltaphasex': 0.0,
    'deltaphasey': 0.0,
    'freqx': 11380,
    'freqy': 3790
}

# 网络默认参数
DEFAULT_NETWORK_PARAMS = {
    'target_ip': '192.168.1.91',
    'recv_port': 8003,
    'send_port': 8003
}

# 图像采集与传输默认参数
DEFAULT_ACQ_PARAMS = {
    'acq_delay': 80000000,
    'ad_rate': 12,
    'trigger_level': 1400,
    'packet_interval': 2500,
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