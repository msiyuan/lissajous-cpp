"""
协议控制界面模块
包含MEMS控制、扫频设置、系统控制等功能界面
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QSpinBox, QComboBox, QLineEdit, QTabWidget, QScrollArea
)
from PyQt5.QtCore import pyqtSignal, Qt

from config.default_params import DEFAULT_MEMS_PARAMS, DEFAULT_ACQ_PARAMS, DEFAULT_SYSTEM_PARAMS
from network.udp_sender import UDPSender
from network.protocol_commands import (
    build_register_command, ProtocolCommands, REGISTER_ADDRESSES, REGISTER_DEFAULTS
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
        """创建寄存器控制区域（新协议）"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 创建滚动区域以容纳所有寄存器控件
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # 为每个寄存器创建输入框和发送按钮
        self.register_inputs = {}
        
        # 按功能分组显示寄存器
        # 1. 控制寄存器
        control_group = QGroupBox("控制寄存器")
        control_layout = QGridLayout()
        control_layout.setHorizontalSpacing(15)
        control_layout.setVerticalSpacing(10)
        self.add_register_control(control_layout, 'live', 0, 0, 1)
        self.add_register_control(control_layout, 'exit', 0, 3, 1)
        control_group.setLayout(control_layout)
        scroll_layout.addWidget(control_group)
        
        # 2. 帧参数寄存器
        frame_group = QGroupBox("帧参数寄存器")
        frame_layout = QGridLayout()
        frame_layout.setHorizontalSpacing(15)
        frame_layout.setVerticalSpacing(10)
        self.add_register_control(frame_layout, 'fp_all_point', 0, 0, 4)
        self.add_register_control(frame_layout, 'fp_valid_point', 0, 3, 4)
        self.add_register_control(frame_layout, 'sample_num', 1, 0, 2)
        self.add_register_control(frame_layout, 'acq_delay', 1, 3, 4)
        frame_group.setLayout(frame_layout)
        scroll_layout.addWidget(frame_group)
        
        # 3. X轴扫频寄存器
        x_sweep_group = QGroupBox("X轴扫频寄存器")
        x_sweep_layout = QGridLayout()
        x_sweep_layout.setHorizontalSpacing(15)
        x_sweep_layout.setVerticalSpacing(10)
        self.add_register_control(x_sweep_layout, 'x_sweep_start_fre', 0, 0, 4)
        self.add_register_control(x_sweep_layout, 'x_sweep_end_fre', 0, 3, 4)
        self.add_register_control(x_sweep_layout, 'x_sweep_fre_step', 1, 0, 2)
        self.add_register_control(x_sweep_layout, 'x_sweep_init_phase', 1, 3, 2)
        self.add_register_control(x_sweep_layout, 'x_sweep_fre_keep_num', 2, 0, 2)
        self.add_register_control(x_sweep_layout, 'x_min', 2, 3, 2)
        self.add_register_control(x_sweep_layout, 'x_max', 2, 6, 2)
        x_sweep_group.setLayout(x_sweep_layout)
        scroll_layout.addWidget(x_sweep_group)
        
        # 4. X轴工作寄存器
        x_work_group = QGroupBox("X轴工作寄存器")
        x_work_layout = QGridLayout()
        x_work_layout.setHorizontalSpacing(15)
        x_work_layout.setVerticalSpacing(10)
        self.add_register_control(x_work_layout, 'x_work_fre', 0, 0, 4)
        self.add_register_control(x_work_layout, 'x_work_init_phase', 0, 3, 2)
        x_work_group.setLayout(x_work_layout)
        scroll_layout.addWidget(x_work_group)
        
        # 5. Y轴扫频寄存器
        y_sweep_group = QGroupBox("Y轴扫频寄存器")
        y_sweep_layout = QGridLayout()
        y_sweep_layout.setHorizontalSpacing(15)
        y_sweep_layout.setVerticalSpacing(10)
        self.add_register_control(y_sweep_layout, 'y_sweep_start_fre', 0, 0, 4)
        self.add_register_control(y_sweep_layout, 'y_sweep_end_fre', 0, 3, 4)
        self.add_register_control(y_sweep_layout, 'y_sweep_fre_step', 1, 0, 2)
        self.add_register_control(y_sweep_layout, 'y_sweep_init_phase', 1, 3, 2)
        self.add_register_control(y_sweep_layout, 'y_sweep_fre_keep_num', 2, 0, 2)
        self.add_register_control(y_sweep_layout, 'y_min', 2, 3, 2)
        self.add_register_control(y_sweep_layout, 'y_max', 2, 6, 2)
        y_sweep_group.setLayout(y_sweep_layout)
        scroll_layout.addWidget(y_sweep_group)
        
        # 6. Y轴工作寄存器
        y_work_group = QGroupBox("Y轴工作寄存器")
        y_work_layout = QGridLayout()
        y_work_layout.setHorizontalSpacing(15)
        y_work_layout.setVerticalSpacing(10)
        self.add_register_control(y_work_layout, 'y_work_fre', 0, 0, 4)
        self.add_register_control(y_work_layout, 'y_work_init_phase', 0, 3, 2)
        y_work_group.setLayout(y_work_layout)
        scroll_layout.addWidget(y_work_group)
        
        # 全局操作按钮
        global_layout = QHBoxLayout()
        send_all_btn = QPushButton("发送所有寄存器")
        send_all_btn.clicked.connect(self.send_all_registers)
        send_all_btn.setMinimumHeight(35)
        global_layout.addWidget(send_all_btn)
        
        reset_btn = QPushButton("重置为默认值")
        reset_btn.clicked.connect(self.reset_registers)
        reset_btn.setMinimumHeight(35)
        global_layout.addWidget(reset_btn)
        
        global_layout.addStretch()
        scroll_layout.addLayout(global_layout)
        
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(800)  # 设置最小高度
        
        layout.addWidget(scroll_area)
        widget.setLayout(layout)
        return widget
    
    def add_register_control(self, layout, register_name, row, col, data_length):
        """添加寄存器控制控件"""
        # 寄存器标签
        label = QLabel(f"{register_name}:")
        label.setMinimumWidth(120)  # 设置标签最小宽度
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)  # 右对齐
        layout.addWidget(label, row, col)
        
        # 输入框
        input_widget = QSpinBox()
        # 根据数据长度设置范围
        if data_length == 1:
            input_widget.setRange(0, 255)
        elif data_length == 2:
            input_widget.setRange(0, 65535)
        else:  # 4字节
            input_widget.setRange(-2147483648, 2147483647)
        
        input_widget.setMinimumWidth(120)  # 增加输入框宽度
        input_widget.setMaximumWidth(150)  # 设置最大宽度
        input_widget.setMinimumHeight(25)  # 设置最小高度
        setattr(self, f"{register_name}_input", input_widget)
        self.register_inputs[register_name] = input_widget
        layout.addWidget(input_widget, row, col + 1)
        
        # 发送按钮
        send_btn = QPushButton("发送")
        send_btn.clicked.connect(lambda _, reg=register_name, length=data_length: self.send_register_command(reg, length))
        send_btn.setMinimumWidth(60)  # 设置按钮最小宽度
        send_btn.setMinimumHeight(25)  # 设置按钮最小高度
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
            success, bytes_sent = self.udp_sender.send_command(command)
            
            if success:
                self.log_message.emit(f"设置寄存器 {register_name} (0x{address:X}) = {value} ({data_length}字节)")
                self.command_sent.emit(command.hex().upper())
            else:
                self.log_message.emit(f"设置寄存器 {register_name} 失败")
            
            return success
        except Exception as e:
            self.log_message.emit(f"设置寄存器 {register_name} 出错：{str(e)}")
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
