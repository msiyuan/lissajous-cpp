"""
协议控制界面模块
包含MEMS控制、扫频设置、系统控制等功能界面
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QSpinBox, QComboBox, QLineEdit
)
from PyQt5.QtCore import pyqtSignal

from config.default_params import DEFAULT_MEMS_PARAMS, DEFAULT_ACQ_PARAMS, DEFAULT_SYSTEM_PARAMS
from network.udp_sender import UDPSender
from network.protocol_commands import (
    build_mems_command, build_sweep_command, build_sweep_control_command,
    build_freq_range_command, build_sine_sweep_params_command,
    build_square_sweep_params_command, build_compensation_command,
    build_read_command, build_simple_command, ProtocolCommands
)
from config.constants import MEMS_START_CMD, MEMS_STOP_CMD

class ProtocolControlWidget(QWidget):
    """协议命令控制界面"""
    
    # 信号定义
    log_message = pyqtSignal(str)
    command_sent = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """
        初始化协议控制组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        self.udp_sender = None
        self.setup_ui()
        self.load_default_values()
    
    def setup_ui(self):
        """设置界面布局"""
        main_layout = QVBoxLayout()

        # 添加协议命令的说明标签
        title_label = QLabel("通讯协议命令控制")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2E8B57;")
        main_layout.addWidget(title_label)

        # 创建主要控制区域，使用QGridLayout实现两列布局
        control_layout = QGridLayout()
        
        # 1. MEMS驱动信号参数配置
        mems_group = self.create_mems_control_section()
        
        # 2. 图像采集与传输控制
        image_group = self.create_image_control_section()
        
        # 3. 系统控制
        system_group = self.create_system_control_section()
        
        # 4. 看门狗与诊断
        watchdog_group = self.create_watchdog_control_section()

        # 将控件添加到网格布局中
        # MEMS组占据左侧一整列 (第0列)，并跨越3行
        control_layout.addWidget(mems_group, 0, 0, 3, 1)
        
        # 其他组垂直排列在右侧列 (第1列)
        control_layout.addWidget(image_group, 0, 1)
        control_layout.addWidget(system_group, 1, 1)
        control_layout.addWidget(watchdog_group, 2, 1)

        # 设置列的拉伸因子
        control_layout.setColumnStretch(0, 1)
        control_layout.setColumnStretch(1, 1)
        
        # 添加一个空的行拉伸
        control_layout.setRowStretch(3, 1)

        main_layout.addLayout(control_layout)
        self.setLayout(main_layout)
    
    def create_mems_control_section(self):
        """创建MEMS驱动信号参数配置区域"""
        group = QGroupBox("MEMS驱动信号参数配置")
        layout = QVBoxLayout()

        # 波形模式和双参数模式
        mode_layout = QHBoxLayout()
        
        # 波形模式切换按钮
        self.wave_mode_button = QPushButton("正弦波")
        self.wave_mode_button.setCheckable(True)
        self.wave_mode_button.setChecked(False)
        self.wave_mode_button.clicked.connect(self.toggle_wave_mode)
        self.wave_mode_button.setMinimumWidth(80)
        self.wave_mode_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        mode_layout.addWidget(QLabel("波形模式:"))
        mode_layout.addWidget(self.wave_mode_button)
        
        # 双参数模式切换按钮
        self.dual_param_button = QPushButton("单组参数")
        self.dual_param_button.setCheckable(True)
        self.dual_param_button.setChecked(False)
        self.dual_param_button.clicked.connect(self.toggle_dual_param_mode)
        self.dual_param_button.setMinimumWidth(100)
        self.dual_param_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        mode_layout.addWidget(QLabel("参数模式:"))
        mode_layout.addWidget(self.dual_param_button)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # 组0参数设置
        group0_box = self.create_group_params_section("组0参数", 0)
        layout.addWidget(group0_box)

        # 组1参数设置
        group1_box = self.create_group_params_section("组1参数", 1)
        layout.addWidget(group1_box)

        # 扫频参数设置
        sweep_box = self.create_sweep_control_section()
        layout.addWidget(sweep_box)

        # 全局操作
        global_layout = QHBoxLayout()
        all_params_btn = QPushButton("发送所有参数")
        all_params_btn.clicked.connect(self.send_all_mems_params)
        global_layout.addWidget(all_params_btn)
        
        reset_params_btn = QPushButton("重置为默认值")
        reset_params_btn.clicked.connect(self.reset_mems_params)
        global_layout.addWidget(reset_params_btn)
        global_layout.addStretch()
        
        layout.addLayout(global_layout)
        group.setLayout(layout)
        return group
    
    def create_group_params_section(self, title: str, group_index: int):
        """创建组参数设置区域"""
        group_box = QGroupBox(title)
        layout = QGridLayout()
        
        # 根据组索引设置参数名前缀
        prefix = f"{'x' if group_index == 0 else 'x'}{group_index}"
        y_prefix = f"{'y' if group_index == 0 else 'y'}{group_index}"
        
        # X轴参数
        layout.addWidget(QLabel("X轴增益:"), 0, 0)
        x_gain_input = QSpinBox()
        x_gain_input.setRange(0, 300)
        x_gain_input.setMinimumWidth(120)
        setattr(self, f"x{group_index}_gain_input", x_gain_input)
        layout.addWidget(x_gain_input, 0, 1)
        
        layout.addWidget(QLabel("X轴频率:"), 0, 2)
        x_freq_input = QSpinBox()
        x_freq_input.setRange(0, 1000000)
        x_freq_input.setMinimumWidth(120)
        setattr(self, f"x{group_index}_freq_input", x_freq_input)
        layout.addWidget(x_freq_input, 0, 3)
        
        layout.addWidget(QLabel("X轴相位:"), 0, 4)
        x_phase_input = QSpinBox()
        x_phase_input.setRange(0, 3600)
        x_phase_input.setMinimumWidth(120)
        setattr(self, f"x{group_index}_phase_input", x_phase_input)
        layout.addWidget(x_phase_input, 0, 5)
        
        # Y轴参数
        layout.addWidget(QLabel("Y轴增益:"), 1, 0)
        y_gain_input = QSpinBox()
        y_gain_input.setRange(0, 300)
        y_gain_input.setMinimumWidth(120)
        setattr(self, f"y{group_index}_gain_input", y_gain_input)
        layout.addWidget(y_gain_input, 1, 1)
        
        layout.addWidget(QLabel("Y轴频率:"), 1, 2)
        y_freq_input = QSpinBox()
        y_freq_input.setRange(0, 1000000)
        y_freq_input.setMinimumWidth(120)
        setattr(self, f"y{group_index}_freq_input", y_freq_input)
        layout.addWidget(y_freq_input, 1, 3)
        
        layout.addWidget(QLabel("Y轴相位:"), 1, 4)
        y_phase_input = QSpinBox()
        y_phase_input.setRange(0, 3600)
        y_phase_input.setMinimumWidth(120)
        setattr(self, f"y{group_index}_phase_input", y_phase_input)
        layout.addWidget(y_phase_input, 1, 5)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        send_btn = QPushButton(f"发送{title}")
        send_btn.clicked.connect(lambda: self.send_group_params(group_index))
        btn_layout.addWidget(send_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout, 2, 0, 1, 6)
        group_box.setLayout(layout)
        return group_box
    
    def create_sweep_control_section(self):
        """创建扫频控制区域"""
        sweep_box = QGroupBox("扫频参数设置")
        layout = QVBoxLayout()
        
        # 扫频基本控制
        basic_layout = QHBoxLayout()
        
        # 扫频重复次数
        basic_layout.addWidget(QLabel("重复次数:"))
        self.sweep_repeat_input = QSpinBox()
        self.sweep_repeat_input.setRange(1, 255)
        self.sweep_repeat_input.setMinimumWidth(80)
        basic_layout.addWidget(self.sweep_repeat_input)
        
        # 设置扫频类型按钮
        set_sweep_type_btn = QPushButton("设置扫频类型")
        set_sweep_type_btn.clicked.connect(self.send_sweep_type_command)
        basic_layout.addWidget(set_sweep_type_btn)
        
        # 扫频启停按钮
        self.sweep_control_button = QPushButton("开始扫频")
        self.sweep_control_button.setCheckable(True)
        self.sweep_control_button.setChecked(False)
        self.sweep_control_button.clicked.connect(self.toggle_sweep_control)
        self.sweep_control_button.setStyleSheet("QPushButton:checked { background-color: #FF5722; color: white; }")
        basic_layout.addWidget(self.sweep_control_button)
        
        basic_layout.addStretch()
        layout.addLayout(basic_layout)
        
        # X轴和Y轴扫频参数
        axes_layout = QHBoxLayout()
        
        # X轴扫频参数
        x_sweep_group = self.create_axis_sweep_section("X轴扫频参数", "x")
        axes_layout.addWidget(x_sweep_group)
        
        # Y轴扫频参数  
        y_sweep_group = self.create_axis_sweep_section("Y轴扫频参数", "y")
        axes_layout.addWidget(y_sweep_group)
        
        layout.addLayout(axes_layout)
        sweep_box.setLayout(layout)
        return sweep_box
    
    def create_axis_sweep_section(self, title: str, axis: str):
        """创建轴扫频参数区域"""
        group = QGroupBox(title)
        layout = QGridLayout()
        
        # 起始/终止频率
        layout.addWidget(QLabel("起始频率:"), 0, 0)
        start_freq_input = QSpinBox()
        start_freq_input.setRange(0, 25000 if axis == 'x' else 10000)
        start_freq_input.setMinimumWidth(100)
        setattr(self, f"{axis}_sweep_start_freq_input", start_freq_input)
        layout.addWidget(start_freq_input, 0, 1)
        
        layout.addWidget(QLabel("终止频率:"), 0, 2)
        end_freq_input = QSpinBox()
        end_freq_input.setRange(0, 25000 if axis == 'x' else 10000)
        end_freq_input.setMinimumWidth(100)
        setattr(self, f"{axis}_sweep_end_freq_input", end_freq_input)
        layout.addWidget(end_freq_input, 0, 3)
        
        # 正弦波参数
        layout.addWidget(QLabel("步进(Hz):"), 1, 0)
        sine_step_input = QSpinBox()
        sine_step_input.setRange(1, 100)
        sine_step_input.setMinimumWidth(100)
        setattr(self, f"{axis}_sine_step_input", sine_step_input)
        layout.addWidget(sine_step_input, 1, 1)
        
        layout.addWidget(QLabel("幅值:"), 1, 2)
        sine_amplitude_input = QSpinBox()
        sine_amplitude_input.setRange(0, 65535)
        sine_amplitude_input.setMinimumWidth(100)
        setattr(self, f"{axis}_sine_amplitude_input", sine_amplitude_input)
        layout.addWidget(sine_amplitude_input, 1, 3)
        
        layout.addWidget(QLabel("初相位:"), 2, 0)
        sine_phase_input = QSpinBox()
        sine_phase_input.setRange(0, 3600)
        sine_phase_input.setMinimumWidth(100)
        setattr(self, f"{axis}_sine_phase_input", sine_phase_input)
        layout.addWidget(sine_phase_input, 2, 1)
        
        layout.addWidget(QLabel("维持周期:"), 2, 2)
        sine_keep_input = QSpinBox()
        sine_keep_input.setRange(1, 65535)
        sine_keep_input.setMinimumWidth(100)
        setattr(self, f"{axis}_sine_keep_input", sine_keep_input)
        layout.addWidget(sine_keep_input, 2, 3)
        
        # 方波参数
        layout.addWidget(QLabel("方波步进:"), 3, 0)
        square_step_input = QSpinBox()
        square_step_input.setRange(1, 65535)
        square_step_input.setMinimumWidth(100)
        setattr(self, f"{axis}_square_step_input", square_step_input)
        layout.addWidget(square_step_input, 3, 1)
        
        layout.addWidget(QLabel("占空比:"), 3, 2)
        square_duty_input = QSpinBox()
        square_duty_input.setRange(0, 100)
        square_duty_input.setSuffix(" %")
        square_duty_input.setMinimumWidth(100)
        setattr(self, f"{axis}_square_duty_input", square_duty_input)
        layout.addWidget(square_duty_input, 3, 3)
        
        layout.addWidget(QLabel("相位延时:"), 4, 0)
        square_delay_input = QSpinBox()
        square_delay_input.setRange(0, 65535)
        square_delay_input.setMinimumWidth(100)
        setattr(self, f"{axis}_square_delay_input", square_delay_input)
        layout.addWidget(square_delay_input, 4, 1)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        freq_btn = QPushButton(f"设置{axis.upper()}轴频率范围")
        freq_btn.clicked.connect(lambda: self.send_axis_sweep_freq_range(axis))
        btn_layout.addWidget(freq_btn)
        
        sine_btn = QPushButton(f"设置{axis.upper()}轴正弦波参数")
        sine_btn.clicked.connect(lambda: self.send_axis_sine_sweep_params(axis))
        btn_layout.addWidget(sine_btn)
        
        square_btn = QPushButton(f"设置{axis.upper()}轴方波参数")
        square_btn.clicked.connect(lambda: self.send_axis_square_sweep_params(axis))
        btn_layout.addWidget(square_btn)
        
        layout.addLayout(btn_layout, 5, 0, 1, 4)
        group.setLayout(layout)
        return group
    
    def create_image_control_section(self):
        """创建图像采集与传输控制区域"""
        group = QGroupBox("图像采集与传输控制")
        layout = QVBoxLayout()

        # 第一行：延时和MEMS控制
        row1_layout = QHBoxLayout()
        
        row1_layout.addWidget(QLabel("采集延时:"))
        self.acq_delay_input = QSpinBox()
        self.acq_delay_input.setRange(0, 1000000000)
        self.acq_delay_input.setMinimumWidth(120)
        row1_layout.addWidget(self.acq_delay_input)
        
        acq_delay_btn = QPushButton("设置")
        acq_delay_btn.setFixedWidth(60)
        acq_delay_btn.clicked.connect(lambda: self.send_command_with_log(
            ProtocolCommands.ACQ_DELAY, self.acq_delay_input.value(), 4))
        row1_layout.addWidget(acq_delay_btn)
        
        row1_layout.addWidget(QLabel("MEMS:"))
        self.mems_control_button = QPushButton("已停止")
        self.mems_control_button.setCheckable(True)
        self.mems_control_button.setChecked(False)
        self.mems_control_button.clicked.connect(self.toggle_mems_control)
        self.mems_control_button.setMinimumWidth(80)
        self.mems_control_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        row1_layout.addWidget(self.mems_control_button)
        
        row1_layout.addStretch()
        layout.addLayout(row1_layout)

        # 第二行：AD采样率和控制
        row2_layout = QHBoxLayout()
        
        row2_layout.addWidget(QLabel("AD采样率:"))
        self.ad_rate_input = QSpinBox()
        self.ad_rate_input.setRange(1, 255)
        self.ad_rate_input.setSuffix(" 分频")
        self.ad_rate_input.setMinimumWidth(120)
        row2_layout.addWidget(self.ad_rate_input)
        
        ad_rate_btn = QPushButton("设置")
        ad_rate_btn.setFixedWidth(60)
        ad_rate_btn.clicked.connect(lambda: self.send_command_with_log(
            ProtocolCommands.AD_RATE, self.ad_rate_input.value(), 1))
        row2_layout.addWidget(ad_rate_btn)
        
        row2_layout.addWidget(QLabel("AD采集:"))
        self.ad_control_button = QPushButton("已停止")
        self.ad_control_button.setCheckable(True)
        self.ad_control_button.setChecked(False)
        self.ad_control_button.clicked.connect(self.toggle_ad_control)
        self.ad_control_button.setMinimumWidth(80)
        self.ad_control_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        row2_layout.addWidget(self.ad_control_button)
        
        row2_layout.addStretch()
        layout.addLayout(row2_layout)

        # 第三行：网络传输参数
        row3_layout = QHBoxLayout()
        
        row3_layout.addWidget(QLabel("触发水平:"))
        self.trigger_level_input = QSpinBox()
        self.trigger_level_input.setRange(0, 65535)
        self.trigger_level_input.setSuffix(" 字节")
        self.trigger_level_input.setMinimumWidth(120)
        row3_layout.addWidget(self.trigger_level_input)
        
        trigger_btn = QPushButton("设置")
        trigger_btn.setFixedWidth(60)
        trigger_btn.clicked.connect(lambda: self.send_command_with_log(
            ProtocolCommands.TRIGGER_LEVEL, self.trigger_level_input.value(), 2))
        row3_layout.addWidget(trigger_btn)
        
        row3_layout.addWidget(QLabel("包间隔:"))
        self.packet_interval_input = QSpinBox()
        self.packet_interval_input.setRange(0, 65535)
        self.packet_interval_input.setSuffix("clk")
        self.packet_interval_input.setMinimumWidth(120)
        row3_layout.addWidget(self.packet_interval_input)
        
        interval_btn = QPushButton("设置")
        interval_btn.setFixedWidth(60)
        interval_btn.clicked.connect(lambda: self.send_command_with_log(
            ProtocolCommands.PACKET_INTERVAL, self.packet_interval_input.value(), 2))
        row3_layout.addWidget(interval_btn)
        row3_layout.addStretch()
        
        layout.addLayout(row3_layout)
        group.setLayout(layout)
        return group
    
    def create_system_control_section(self):
        """创建系统控制区域"""
        group = QGroupBox("系统控制与状态监控")
        layout = QVBoxLayout()

        # 第一行：网口自检控制
        row1_layout = QHBoxLayout()
        
        row1_layout.addWidget(QLabel("网口自检:"))
        self.selftest_combo = QComboBox()
        self.selftest_combo.addItems(["使能", "禁止"])
        self.selftest_combo.setMinimumWidth(80)
        row1_layout.addWidget(self.selftest_combo)
        
        selftest_btn = QPushButton("设置")
        selftest_btn.setFixedWidth(60)
        selftest_btn.clicked.connect(self.send_selftest_command)
        row1_layout.addWidget(selftest_btn)
        
        row1_layout.addWidget(QLabel("自检包数:"))
        self.selftest_count_input = QSpinBox()
        self.selftest_count_input.setRange(0, 100000)
        self.selftest_count_input.setMinimumWidth(120)
        row1_layout.addWidget(self.selftest_count_input)
        
        count_btn = QPushButton("设置")
        count_btn.setFixedWidth(60)
        count_btn.clicked.connect(lambda: self.send_command_with_log(
            ProtocolCommands.SELFTEST_COUNT, self.selftest_count_input.value(), 4))
        row1_layout.addWidget(count_btn)
        row1_layout.addStretch()
        
        layout.addLayout(row1_layout)

        # 第二行：状态监控
        row2_layout = QHBoxLayout()
        
        read_phase_btn = QPushButton("读取MEMS相位")
        read_phase_btn.clicked.connect(self.read_mems_phase)
        row2_layout.addWidget(read_phase_btn)
        
        read_ddr3_btn = QPushButton("读取DDR3状态")
        read_ddr3_btn.clicked.connect(self.read_ddr3_status)
        row2_layout.addWidget(read_ddr3_btn)
        
        row2_layout.addStretch()
        layout.addLayout(row2_layout)

        # 第三行：硬件补偿
        row3_layout = QHBoxLayout()
        
        row3_layout.addWidget(QLabel("X轴零偏:"))
        self.x_compensation_input = QSpinBox()
        self.x_compensation_input.setRange(-32768, 32767)
        self.x_compensation_input.setMinimumWidth(120)
        row3_layout.addWidget(self.x_compensation_input)
        
        row3_layout.addWidget(QLabel("Y轴零偏:"))
        self.y_compensation_input = QSpinBox()
        self.y_compensation_input.setRange(-32768, 32767)
        self.y_compensation_input.setMinimumWidth(120)
        row3_layout.addWidget(self.y_compensation_input)
        
        comp_btn = QPushButton("设置补偿")
        comp_btn.clicked.connect(self.send_compensation_command)
        row3_layout.addWidget(comp_btn)
        row3_layout.addStretch()
        
        layout.addLayout(row3_layout)
        group.setLayout(layout)
        return group
    
    def create_watchdog_control_section(self):
        """创建看门狗与诊断区域"""
        group = QGroupBox("看门狗控制")
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("看门狗:"))
        self.watchdog_combo = QComboBox()
        self.watchdog_combo.addItems(["使能", "禁止"])
        self.watchdog_combo.setMinimumWidth(80)
        layout.addWidget(self.watchdog_combo)
        
        wd_enable_btn = QPushButton("设置")
        wd_enable_btn.setFixedWidth(60)
        wd_enable_btn.clicked.connect(self.send_watchdog_enable_command)
        layout.addWidget(wd_enable_btn)
        
        layout.addWidget(QLabel("超时时间:"))
        self.watchdog_timeout_input = QSpinBox()
        self.watchdog_timeout_input.setRange(1, 255)
        self.watchdog_timeout_input.setSuffix(" 秒")
        self.watchdog_timeout_input.setMinimumWidth(120)
        layout.addWidget(self.watchdog_timeout_input)
        
        wd_timeout_btn = QPushButton("设置")
        wd_timeout_btn.setFixedWidth(60)
        wd_timeout_btn.clicked.connect(lambda: self.send_command_with_log(
            ProtocolCommands.WATCHDOG_TIMEOUT, self.watchdog_timeout_input.value(), 1))
        layout.addWidget(wd_timeout_btn)
        
        feed_dog_btn = QPushButton("喂狗")
        feed_dog_btn.clicked.connect(self.send_feed_dog_command)
        layout.addWidget(feed_dog_btn)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
    
    def load_default_values(self):
        """加载默认值"""
        # MEMS参数
        self.x0_gain_input.setValue(DEFAULT_MEMS_PARAMS['x0_gain'])
        self.x0_freq_input.setValue(DEFAULT_MEMS_PARAMS['x0_freq'])
        self.x0_phase_input.setValue(DEFAULT_MEMS_PARAMS['x0_phase'])
        self.y0_gain_input.setValue(DEFAULT_MEMS_PARAMS['y0_gain'])
        self.y0_freq_input.setValue(DEFAULT_MEMS_PARAMS['y0_freq'])
        self.y0_phase_input.setValue(DEFAULT_MEMS_PARAMS['y0_phase'])
        
        self.x1_gain_input.setValue(DEFAULT_MEMS_PARAMS['x1_gain'])
        self.x1_freq_input.setValue(DEFAULT_MEMS_PARAMS['x1_freq'])
        self.x1_phase_input.setValue(DEFAULT_MEMS_PARAMS['x1_phase'])
        self.y1_gain_input.setValue(DEFAULT_MEMS_PARAMS['y1_gain'])
        self.y1_freq_input.setValue(DEFAULT_MEMS_PARAMS['y1_freq'])
        self.y1_phase_input.setValue(DEFAULT_MEMS_PARAMS['y1_phase'])
        
        # 扫频参数
        self.sweep_repeat_input.setValue(DEFAULT_MEMS_PARAMS['sweep_repeat'])
        self.x_sweep_start_freq_input.setValue(DEFAULT_MEMS_PARAMS['x_sweep_start_freq'])
        self.x_sweep_end_freq_input.setValue(DEFAULT_MEMS_PARAMS['x_sweep_end_freq'])
        self.y_sweep_start_freq_input.setValue(DEFAULT_MEMS_PARAMS['y_sweep_start_freq'])
        self.y_sweep_end_freq_input.setValue(DEFAULT_MEMS_PARAMS['y_sweep_end_freq'])
        
        # 正弦波扫频参数
        self.x_sine_step_input.setValue(DEFAULT_MEMS_PARAMS['x_sine_step'])
        self.x_sine_amplitude_input.setValue(DEFAULT_MEMS_PARAMS['x_sine_amplitude'])
        self.x_sine_phase_input.setValue(DEFAULT_MEMS_PARAMS['x_sine_phase'])
        self.x_sine_keep_input.setValue(DEFAULT_MEMS_PARAMS['x_sine_keep'])
        
        self.y_sine_step_input.setValue(DEFAULT_MEMS_PARAMS['y_sine_step'])
        self.y_sine_amplitude_input.setValue(DEFAULT_MEMS_PARAMS['y_sine_amplitude'])
        self.y_sine_phase_input.setValue(DEFAULT_MEMS_PARAMS['y_sine_phase'])
        self.y_sine_keep_input.setValue(DEFAULT_MEMS_PARAMS['y_sine_keep'])
        
        # 方波扫频参数
        self.x_square_step_input.setValue(DEFAULT_MEMS_PARAMS['x_square_step'])
        self.x_square_duty_input.setValue(DEFAULT_MEMS_PARAMS['x_square_duty'])
        self.x_square_delay_input.setValue(DEFAULT_MEMS_PARAMS['x_square_delay'])
        
        self.y_square_step_input.setValue(DEFAULT_MEMS_PARAMS['y_square_step'])
        self.y_square_duty_input.setValue(DEFAULT_MEMS_PARAMS['y_square_duty'])
        self.y_square_delay_input.setValue(DEFAULT_MEMS_PARAMS['y_square_delay'])
        
        # 采集参数
        self.acq_delay_input.setValue(DEFAULT_ACQ_PARAMS['acq_delay'])
        self.ad_rate_input.setValue(DEFAULT_ACQ_PARAMS['ad_rate'])
        self.trigger_level_input.setValue(DEFAULT_ACQ_PARAMS['trigger_level'])
        self.packet_interval_input.setValue(DEFAULT_ACQ_PARAMS['packet_interval'])
        self.selftest_count_input.setValue(DEFAULT_ACQ_PARAMS['selftest_count'])
        
        # 系统参数
        self.x_compensation_input.setValue(DEFAULT_SYSTEM_PARAMS['x_compensation'])
        self.y_compensation_input.setValue(DEFAULT_SYSTEM_PARAMS['y_compensation'])
        self.watchdog_timeout_input.setValue(DEFAULT_SYSTEM_PARAMS['watchdog_timeout'])
    
    def set_udp_sender(self, udp_sender: UDPSender):
        """设置UDP发送器"""
        self.udp_sender = udp_sender
    
    def send_command_with_log(self, cmd_code: int, value: int, data_length: int):
        """发送命令并记录日志"""
        if not self.udp_sender:
            self.log_message.emit("错误：UDP发送器未设置")
            return False
        
        try:
            command = build_mems_command(cmd_code, value, data_length)
            success, bytes_sent = self.udp_sender.send_command(command)
            
            if success:
                self.log_message.emit(f"发送命令0x{cmd_code:02X}，值={value}，数据长度={data_length}")
                self.command_sent.emit(command.hex().upper())
            else:
                self.log_message.emit(f"发送命令0x{cmd_code:02X}失败")
            
            return success
        except Exception as e:
            self.log_message.emit(f"发送命令0x{cmd_code:02X}出错：{str(e)}")
            return False
    
    def send_group_params(self, group_index: int):
        """发送组参数"""
        try:
            if group_index == 0:
                # 发送组0参数
                self.send_command_with_log(ProtocolCommands.X0_GAIN, self.x0_gain_input.value(), 2)
                self.send_command_with_log(ProtocolCommands.X0_FREQ, self.x0_freq_input.value(), 4)
                self.send_command_with_log(ProtocolCommands.X0_PHASE, self.x0_phase_input.value(), 2)
                self.send_command_with_log(ProtocolCommands.Y0_GAIN, self.y0_gain_input.value(), 2)
                self.send_command_with_log(ProtocolCommands.Y0_FREQ, self.y0_freq_input.value(), 4)
                self.send_command_with_log(ProtocolCommands.Y0_PHASE, self.y0_phase_input.value(), 2)
                self.log_message.emit("已发送组0所有参数")
            else:
                # 发送组1参数
                self.send_command_with_log(ProtocolCommands.X1_GAIN, self.x1_gain_input.value(), 2)
                self.send_command_with_log(ProtocolCommands.X1_FREQ, self.x1_freq_input.value(), 4)
                self.send_command_with_log(ProtocolCommands.X1_PHASE, self.x1_phase_input.value(), 2)
                self.send_command_with_log(ProtocolCommands.Y1_GAIN, self.y1_gain_input.value(), 2)
                self.send_command_with_log(ProtocolCommands.Y1_FREQ, self.y1_freq_input.value(), 4)
                self.send_command_with_log(ProtocolCommands.Y1_PHASE, self.y1_phase_input.value(), 2)
                self.log_message.emit("已发送组1所有参数")
        except Exception as e:
            self.log_message.emit(f"发送组{group_index}参数出错：{str(e)}")
    
    def send_all_mems_params(self):
        """发送所有MEMS参数"""
        try:
            self.send_group_params(0)
            self.send_group_params(1)
            self.log_message.emit("已发送所有MEMS参数")
        except Exception as e:
            self.log_message.emit(f"发送所有MEMS参数出错：{str(e)}")
    
    def reset_mems_params(self):
        """重置MEMS参数为默认值"""
        try:
            self.load_default_values()
            
            # 重置模式按钮
            self.wave_mode_button.setChecked(False)
            self.dual_param_button.setChecked(False)
            self.sweep_control_button.setChecked(False)
            self.toggle_wave_mode()
            self.toggle_dual_param_mode()
            
            self.log_message.emit("已重置所有参数为默认值")
        except Exception as e:
            self.log_message.emit(f"重置参数出错：{str(e)}")
    
    def toggle_wave_mode(self):
        """切换波形模式"""
        if self.wave_mode_button.isChecked():
            self.wave_mode_button.setText("方波")
            self.wave_mode_button.setStyleSheet("QPushButton:checked { background-color: #FF9800; color: white; }")
        else:
            self.wave_mode_button.setText("正弦波")
            self.wave_mode_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
    
    def toggle_dual_param_mode(self):
        """切换双参数模式"""
        if self.dual_param_button.isChecked():
            self.dual_param_button.setText("双组交替")
            self.send_command_with_log(ProtocolCommands.DUAL_PARAM_MODE, MEMS_STOP_CMD, 1)  # 启用双组交替
        else:
            self.dual_param_button.setText("单组参数")
            self.send_command_with_log(ProtocolCommands.DUAL_PARAM_MODE, MEMS_START_CMD, 1)  # 使用单组
    
    def toggle_mems_control(self):
        """切换MEMS启停状态"""
        if self.mems_control_button.isChecked():
            self.mems_control_button.setText("已启动")
            action = MEMS_START_CMD
            action_text = "启动"
        else:
            self.mems_control_button.setText("已停止")
            action = MEMS_STOP_CMD
            action_text = "停止"
        
        success = self.send_command_with_log(ProtocolCommands.MEMS_CONTROL, action, 1)
        if success:
            self.log_message.emit(f"已{action_text}MEMS驱动")
        else:
            self.log_message.emit(f"{action_text}MEMS驱动命令发送失败")
    
    def toggle_ad_control(self):
        """切换AD采集启停状态"""
        if self.ad_control_button.isChecked():
            self.ad_control_button.setText("已启动")
            action = MEMS_START_CMD
            action_text = "启动"
        else:
            self.ad_control_button.setText("已停止")
            action = MEMS_STOP_CMD
            action_text = "停止"
        
        success = self.send_command_with_log(ProtocolCommands.AD_CONTROL, action, 1)
        if success:
            self.log_message.emit(f"已{action_text}AD采集")
        else:
            self.log_message.emit(f"{action_text}AD采集命令发送失败")
    
    def send_sweep_type_command(self):
        """发送扫频波形类型与重复次数设置"""
        try:
            wave_type = MEMS_STOP_CMD if self.wave_mode_button.isChecked() else 0x01  # 方波=0x22, 正弦波=0x01
            repeat_count = self.sweep_repeat_input.value()
            
            command = build_sweep_command(wave_type, repeat_count)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    wave_str = "方波" if wave_type == MEMS_STOP_CMD else "正弦波"
                    self.log_message.emit(f"已设置扫频类型：{wave_str}，重复次数：{repeat_count}")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit("设置扫频类型失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
                
        except Exception as e:
            self.log_message.emit(f"发送扫频类型命令出错：{str(e)}")
    
    def toggle_sweep_control(self):
        """切换扫频启停状态"""
        start_sweep = self.sweep_control_button.isChecked()
        
        if start_sweep:
            self.sweep_control_button.setText("停止扫频")
            action_text = "启动"
        else:
            self.sweep_control_button.setText("开始扫频")
            action_text = "停止"
        
        try:
            command = build_sweep_control_command(start_sweep)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    self.log_message.emit(f"已{action_text}扫频")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit(f"{action_text}扫频命令发送失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
        except Exception as e:
            self.log_message.emit(f"{action_text}扫频命令出错：{str(e)}")
    
    def send_axis_sweep_freq_range(self, axis: str):
        """设置轴扫频起始/结束频率"""
        try:
            start_freq_input = getattr(self, f"{axis}_sweep_start_freq_input")
            end_freq_input = getattr(self, f"{axis}_sweep_end_freq_input")
            
            start_freq = start_freq_input.value()
            end_freq = end_freq_input.value()
            
            # 根据轴和波形模式确定命令代码
            if axis == 'x':
                cmd_code = ProtocolCommands.X_SQUARE_FREQ_RANGE if self.wave_mode_button.isChecked() else ProtocolCommands.X_SINE_FREQ_RANGE
            else:
                cmd_code = ProtocolCommands.Y_SQUARE_FREQ_RANGE if self.wave_mode_button.isChecked() else ProtocolCommands.Y_SINE_FREQ_RANGE
            
            command = build_freq_range_command(cmd_code, start_freq, end_freq)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    wave_type = "方波" if self.wave_mode_button.isChecked() else "正弦波"
                    self.log_message.emit(f"已设置{axis.upper()}轴{wave_type}扫频频率范围：{start_freq}Hz → {end_freq}Hz")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit(f"设置{axis.upper()}轴扫频频率范围失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
                
        except Exception as e:
            self.log_message.emit(f"发送{axis.upper()}轴扫频频率范围命令出错：{str(e)}")
    
    def send_axis_sine_sweep_params(self, axis: str):
        """设置轴正弦波扫频参数"""
        try:
            step_input = getattr(self, f"{axis}_sine_step_input")
            amplitude_input = getattr(self, f"{axis}_sine_amplitude_input")
            phase_input = getattr(self, f"{axis}_sine_phase_input")
            keep_input = getattr(self, f"{axis}_sine_keep_input")
            
            step = step_input.value()
            amplitude = amplitude_input.value()
            phase = phase_input.value()
            keep_cycles = keep_input.value()
            
            cmd_code = ProtocolCommands.X_SINE_PARAMS if axis == 'x' else ProtocolCommands.Y_SINE_PARAMS
            command = build_sine_sweep_params_command(cmd_code, step, amplitude, phase, keep_cycles)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    self.log_message.emit(f"已设置{axis.upper()}轴正弦波扫频参数：步进{step}Hz，幅值{amplitude}，相位{phase/10}°，维持{keep_cycles}周期")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit(f"设置{axis.upper()}轴正弦波扫频参数失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
                
        except Exception as e:
            self.log_message.emit(f"发送{axis.upper()}轴正弦波扫频参数命令出错：{str(e)}")
    
    def send_axis_square_sweep_params(self, axis: str):
        """设置轴方波扫频参数"""
        try:
            if not self.wave_mode_button.isChecked():
                self.log_message.emit("当前不是方波模式，无法设置方波参数")
                return
                
            step_input = getattr(self, f"{axis}_square_step_input")
            duty_input = getattr(self, f"{axis}_square_duty_input")
            delay_input = getattr(self, f"{axis}_square_delay_input")
            
            step = step_input.value()
            duty = duty_input.value()
            delay = delay_input.value()
            
            cmd_code = ProtocolCommands.X_SQUARE_PARAMS if axis == 'x' else ProtocolCommands.Y_SQUARE_PARAMS
            command = build_square_sweep_params_command(cmd_code, step, duty, delay)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    self.log_message.emit(f"已设置{axis.upper()}轴方波扫频参数：步进{step}Hz，占空比{duty}%，延时{delay}")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit(f"设置{axis.upper()}轴方波扫频参数失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
                
        except Exception as e:
            self.log_message.emit(f"发送{axis.upper()}轴方波扫频参数命令出错：{str(e)}")
    
    def send_selftest_command(self):
        """发送网口自检命令"""
        command_value = MEMS_START_CMD if self.selftest_combo.currentText() == "使能" else MEMS_STOP_CMD
        action = self.selftest_combo.currentText()
        
        success = self.send_command_with_log(ProtocolCommands.SELFTEST_CONTROL, command_value, 1)
        if success:
            self.log_message.emit(f"已{action}网口自检")
    
    def read_mems_phase(self):
        """读取MEMS驱动信号相位信息"""
        try:
            command = build_read_command(ProtocolCommands.READ_MEMS_PHASE)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    self.log_message.emit("已发送读取MEMS相位命令，等待应答...")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit("发送读取MEMS相位命令失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
        except Exception as e:
            self.log_message.emit(f"读取MEMS相位出错：{str(e)}")
    
    def read_ddr3_status(self):
        """读取DDR3初始化状态"""
        try:
            command = build_read_command(ProtocolCommands.READ_DDR3_STATUS)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    self.log_message.emit("已发送读取DDR3状态命令，等待应答...")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit("发送读取DDR3状态命令失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
        except Exception as e:
            self.log_message.emit(f"读取DDR3状态出错：{str(e)}")
    
    def send_compensation_command(self):
        """发送硬件补偿命令"""
        try:
            x_comp = self.x_compensation_input.value()
            y_comp = self.y_compensation_input.value()
            
            command = build_compensation_command(x_comp, y_comp)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    self.log_message.emit(f"已设置硬件补偿：X={x_comp}，Y={y_comp}")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit("设置硬件补偿失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
                
        except Exception as e:
            self.log_message.emit(f"发送硬件补偿命令出错：{str(e)}")
    
    def send_watchdog_enable_command(self):
        """发送看门狗使能命令"""
        command_value = MEMS_START_CMD if self.watchdog_combo.currentText() == "使能" else MEMS_STOP_CMD
        action = self.watchdog_combo.currentText()
        
        success = self.send_command_with_log(ProtocolCommands.WATCHDOG_CONTROL, command_value, 1)
        if success:
            self.log_message.emit(f"已{action}看门狗")
    
    def send_feed_dog_command(self):
        """发送喂狗命令"""
        try:
            command = build_simple_command(ProtocolCommands.FEED_DOG)
            
            if self.udp_sender:
                success, bytes_sent = self.udp_sender.send_command(command)
                if success:
                    self.log_message.emit("已发送喂狗命令")
                    self.command_sent.emit(command.hex().upper())
                else:
                    self.log_message.emit("发送喂狗命令失败")
            else:
                self.log_message.emit("错误：UDP发送器未设置")
        except Exception as e:
            self.log_message.emit(f"发送喂狗命令出错：{str(e)}")