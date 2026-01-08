"""
协议控制界面模块
包含MEMS控制、扫频设置、系统控制等功能界面
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QSpinBox, QComboBox, QLineEdit, QTabWidget, QScrollArea
)
from PyQt5.QtCore import pyqtSignal, Qt

from config.default_params import (
    DEFAULT_MEMS_PARAMS, DEFAULT_ACQ_PARAMS, DEFAULT_SYSTEM_PARAMS,
    REGISTER_ADDRESSES, REGISTER_DEFAULTS
)
from network.udp_sender import UDPSender
from network.protocol_commands import build_register_command, ProtocolCommands
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

        # 使用标签页组织界面
        self.tab_widget = QTabWidget()
        
        # 1. 新协议寄存器设置
        register_tab = self.create_register_control_section()
        self.tab_widget.addTab(register_tab, "寄存器设置")
        
        # 2. 控制启停
        control_tab = self.create_control_start_stop_section()
        self.tab_widget.addTab(control_tab, "控制启停")

        main_layout.addWidget(self.tab_widget)
        
        # 添加弹性空间，避免控件拉伸过度
        main_layout.addStretch()
        
        self.setLayout(main_layout)
    
    def create_register_control_section(self):
        """创建寄存器控制区域（新协议）- 紧凑布局，无滚动"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # 为每个寄存器创建输入框和发送按钮
        self.register_inputs = {}

        # 使用GridLayout，每行2个寄存器，紧凑排列
        grid_layout = QGridLayout()
        grid_layout.setSpacing(5)
        grid_layout.setContentsMargins(5, 5, 5, 5)

        # 计算行和列
        registers = [
            ('live', 1), ('exit', 1),
            ('fp_all_point', 4), ('fp_valid_point', 4),
            ('sample_num', 2), ('acq_delay', 4),
            ('x_sweep_start_fre', 4), ('x_sweep_end_fre', 4),
            ('x_sweep_fre_step', 2), ('x_sweep_init_phase', 2),
            ('x_sweep_fre_keep_num', 2), ('x_min', 2),
            ('x_max', 2), ('x_work_fre', 4),
            ('x_work_init_phase', 2), ('y_sweep_start_fre', 4),
            ('y_sweep_end_fre', 4), ('y_sweep_fre_step', 2),
            ('y_sweep_init_phase', 2), ('y_sweep_fre_keep_num', 2),
            ('y_min', 2), ('y_max', 2),
            ('y_work_fre', 4), ('y_work_init_phase', 2),
        ]

        # 添加到网格，每行2个
        for i, (reg_name, data_len) in enumerate(registers):
            row = i // 2
            col = (i % 2) * 3  # 每个寄存器占3列
            self.add_register_control_compact(grid_layout, reg_name, row, col, data_len)

        layout.addLayout(grid_layout)

        # 全局操作按钮
        global_layout = QHBoxLayout()
        send_all_btn = QPushButton("发送所有寄存器")
        send_all_btn.clicked.connect(self.send_all_registers)
        send_all_btn.setMinimumHeight(30)
        send_all_btn.setMinimumWidth(100)
        global_layout.addWidget(send_all_btn)

        reset_btn = QPushButton("重置默认值")
        reset_btn.clicked.connect(self.reset_registers)
        reset_btn.setMinimumHeight(30)
        reset_btn.setMinimumWidth(100)
        global_layout.addWidget(reset_btn)

        global_layout.addStretch()
        layout.addLayout(global_layout)

        widget.setLayout(layout)
        return widget

    def add_register_control_compact(self, layout, register_name, row, col, data_length):
        """添加寄存器控制控件 - 紧凑布局"""
        # 寄存器标签
        label = QLabel(register_name)
        label.setMinimumWidth(80)
        label.setMaximumWidth(90)
        layout.addWidget(label, row, col)

        # 输入框
        input_widget = QSpinBox()
        if data_length == 1:
            input_widget.setRange(0, 255)
        elif data_length == 2:
            input_widget.setRange(0, 65535)
        else:
            input_widget.setRange(-2147483648, 2147483647)

        input_widget.setMinimumWidth(70)
        input_widget.setMaximumWidth(90)
        input_widget.setMinimumHeight(24)
        setattr(self, f"{register_name}_input", input_widget)
        self.register_inputs[register_name] = input_widget
        layout.addWidget(input_widget, row, col + 1)

        # 发送按钮
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(lambda _, reg=register_name, length=data_length: self.send_register_command(reg, length))
        send_btn.setMinimumWidth(45)
        send_btn.setMaximumWidth(55)
        send_btn.setMinimumHeight(24)
        layout.addWidget(send_btn, row, col + 2)
    
    def create_control_start_stop_section(self):
        """创建控制启停区域"""
        group = QGroupBox("控制启停")
        layout = QHBoxLayout()
        layout.setSpacing(10)  # 设置按钮间距
        
        # 开始成像按钮
        self.start_imaging_button = QPushButton("开始成像")
        self.start_imaging_button.clicked.connect(lambda: self.quick_set_register('live', 1))
        self.start_imaging_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.start_imaging_button.setMinimumWidth(80)
        layout.addWidget(self.start_imaging_button)

        # 结束成像按钮
        self.stop_imaging_button = QPushButton("结束成像")
        self.stop_imaging_button.clicked.connect(lambda: self.quick_set_register('exit', 1))
        self.stop_imaging_button.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.stop_imaging_button.setMinimumWidth(80)
        layout.addWidget(self.stop_imaging_button)

        layout.addStretch()
        group.setLayout(layout)
        return group
    
    def load_default_values(self):
        """加载默认值"""
        for register_name, default_value in REGISTER_DEFAULTS.items():
            if hasattr(self, f"{register_name}_input"):
                input_widget = getattr(self, f"{register_name}_input")
                input_widget.setValue(default_value)
    
    def set_udp_sender(self, udp_sender: UDPSender):
        """设置UDP发送器"""
        self.udp_sender = udp_sender

    def disable_controls(self):
        """禁用所有输入控件（接收状态时调用）"""
        # 禁用所有SpinBox控件
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, (QSpinBox, QComboBox, QLineEdit)):
                attr.setEnabled(False)

        # 禁用所有设置按钮，但保留控制启停按钮
        for widget in self.findChildren(QPushButton):
            widget.setEnabled(False)

    def enable_controls(self):
        """启用所有输入控件（停止接收时调用）"""
        # 启用所有SpinBox控件
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, (QSpinBox, QComboBox, QLineEdit)):
                attr.setEnabled(True)

        # 启用所有按钮
        for widget in self.findChildren(QPushButton):
            widget.setEnabled(True)
    
    def send_register_command(self, register_name: str, data_length: int):
        """发送寄存器设置命令（新协议）"""
        if not self.udp_sender:
            self.log_message.emit("错误：UDP发送器未设置")
            return False

        try:
            # 获取寄存器地址
            if register_name not in REGISTER_ADDRESSES:
                self.log_message.emit(f"未知寄存器: {register_name}")
                return False

            address = REGISTER_ADDRESSES[register_name]
            # 获取值
            input_widget = getattr(self, f"{register_name}_input")
            value = input_widget.value()

            # 构建命令
            command = build_register_command(address, value, data_length)

            # 格式化命令显示（每2字节一组）
            cmd_hex = ' '.join([command[i:i+2].hex().upper() for i in range(0, len(command), 2)])

            success, bytes_sent = self.udp_sender.send_command(command)

            if success:
                self.log_message.emit(f"[发送成功] {register_name} (0x{address:04X}) = {value} -> 目标端口: 0x{self.udp_sender.target_port:X}")
                self.log_message.emit(f"  命令: {cmd_hex} ({len(command)}字节)")
                self.command_sent.emit(command.hex().upper())
            else:
                self.log_message.emit(f"[发送失败] {register_name} - 请检查网络连接")

            return success
        except Exception as e:
            self.log_message.emit(f"[发送出错] {register_name}: {str(e)}")
            return False
    
    def quick_set_register(self, register_name: str, value: int):
        """快捷设置寄存器"""
        if register_name not in REGISTER_ADDRESSES:
            self.log_message.emit(f"未知寄存器: {register_name}")
            return False
            
        address = REGISTER_ADDRESSES[register_name]
        data_length = 1  # live和exit寄存器通常为1字节
        
        if not self.udp_sender:
            self.log_message.emit("错误：UDP发送器未设置")
            return False
        
        try:
            command = build_register_command(address, value, data_length)
            success, bytes_sent = self.udp_sender.send_command(command)
            
            if success:
                self.log_message.emit(f"快捷设置 {register_name} = {value}")
                self.command_sent.emit(command.hex().upper())
            else:
                self.log_message.emit(f"快捷设置 {register_name} 失败")
            
            return success
        except Exception as e:
            self.log_message.emit(f"快捷设置 {register_name} 出错：{str(e)}")
            return False
    
    def send_all_registers(self):
        """发送所有寄存器设置"""
        try:
            success_count = 0
            total_count = len(REGISTER_ADDRESSES)
            
            # 按特定顺序发送寄存器，确保依赖关系正确
            register_order = [
                'fp_all_point', 'fp_valid_point', 'sample_num', 'acq_delay',
                'x_sweep_start_fre', 'x_sweep_end_fre', 'x_sweep_fre_step', 
                'x_sweep_init_phase', 'x_sweep_fre_keep_num', 'x_min', 'x_max',
                'x_work_fre', 'x_work_init_phase',
                'y_sweep_start_fre', 'y_sweep_end_fre', 'y_sweep_fre_step',
                'y_sweep_init_phase', 'y_sweep_fre_keep_num', 'y_min', 'y_max',
                'y_work_fre', 'y_work_init_phase'
            ]
            
            for register_name in register_order:
                if register_name in REGISTER_ADDRESSES:
                    # 确定数据长度
                    data_length = 4  # 默认4字节
                    if register_name in ['sample_num', 'x_sweep_fre_step', 'x_sweep_init_phase',
                                       'x_sweep_fre_keep_num', 'x_min', 'x_max', 'x_work_init_phase',
                                       'y_sweep_fre_step', 'y_sweep_init_phase', 'y_sweep_fre_keep_num',
                                       'y_min', 'y_max', 'y_work_init_phase']:
                        data_length = 2
                    elif register_name in ['live', 'exit']:
                        data_length = 1
                    
                    if self.send_register_command(register_name, data_length):
                        success_count += 1
            
            self.log_message.emit(f"寄存器设置完成: {success_count}/{total_count} 成功")
        except Exception as e:
            self.log_message.emit(f"发送所有寄存器出错：{str(e)}")
    
    def reset_registers(self):
        """重置寄存器为默认值"""
        try:
            self.load_default_values()
            self.log_message.emit("已重置所有寄存器为默认值")
        except Exception as e:
            self.log_message.emit(f"重置寄存器出错：{str(e)}")
