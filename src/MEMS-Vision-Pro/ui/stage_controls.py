"""
位移台控制界面模块
提供位移台控制的图形界面
"""

import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QComboBox, QGroupBox, QDoubleSpinBox, QSpinBox,
    QMessageBox, QFileDialog, QApplication
)
from PyQt5.QtCore import pyqtSignal, QTimer
import numpy as np

class StageControlWidget(QWidget):
    """位移台控制界面组件"""
    
    # 信号定义
    position_changed = pyqtSignal(float)  # 位置变化信号
    status_message = pyqtSignal(str)      # 状态消息信号
    error_message = pyqtSignal(str)       # 错误消息信号
    capture_image_request = pyqtSignal()  # 请求捕获图像信号
    
    def __init__(self, parent=None):
        """
        初始化位移台控制组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        self.stage_controller = None
        self.setup_ui()
        
    def set_stage_controller(self, controller):
        """设置位移台控制器"""
        self.stage_controller = controller
        if self.stage_controller:
            # 设置回调函数
            self.stage_controller.set_callbacks(
                position_callback=self.on_position_update,
                status_callback=self.on_status_update,
                error_callback=self.on_error_update
            )
            # 设置图像捕获回调
            self.stage_controller.set_image_capture_callback(self.capture_current_image)
            # 刷新串口列表
            self.refresh_ports()
            
    def on_capture_image_request(self):
        """处理图像捕获请求"""
        # 这里应该由主窗口来实现具体的图像捕获逻辑
        pass
        
    def setup_ui(self):
        """设置界面布局"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # 串口设置区域
        port_group = self.create_port_settings_group()
        main_layout.addWidget(port_group)
        
        # 位置显示区域
        position_group = self.create_position_display_group()
        main_layout.addWidget(position_group)
        
        # 控制按钮区域
        control_group = self.create_control_buttons_group()
        main_layout.addWidget(control_group)
        
        # 步进控制区域
        step_group = self.create_step_control_group()
        main_layout.addWidget(step_group)
        
        # 参数设置区域
        param_group = self.create_parameter_settings_group()
        main_layout.addWidget(param_group)
        
        # 图像拍摄控制区域
        image_group = self.create_image_control_group()
        main_layout.addWidget(image_group)
        
        # 添加弹性空间
        main_layout.addStretch()
        
        self.setLayout(main_layout)
        
    def create_port_settings_group(self):
        """创建串口设置组"""
        group = QGroupBox("串口设置")
        
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # 串口选择
        layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        layout.addWidget(self.port_combo)
        
        # 波特率
        layout.addWidget(QLabel("波特率:"))
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
        self.baudrate_combo.setCurrentText('115200')
        self.baudrate_combo.setMinimumWidth(80)
        layout.addWidget(self.baudrate_combo)
        
        # 连接按钮
        self.connect_button = QPushButton("连接")
        self.connect_button.clicked.connect(self.toggle_connection)
        self.connect_button.setMinimumWidth(60)
        layout.addWidget(self.connect_button)
        
        # 刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh_ports)
        refresh_button.setMinimumWidth(60)
        layout.addWidget(refresh_button)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
        
    def create_position_display_group(self):
        """创建位置显示组"""
        group = QGroupBox("位置信息")
        
        layout = QHBoxLayout()
        layout.setSpacing(15)
        
        # 当前位置
        layout.addWidget(QLabel("当前位置:"))
        self.position_label = QLabel("0.000")
        self.position_label.setMinimumWidth(80)
        self.position_label.setStyleSheet("font-weight: bold; color: blue;")
        layout.addWidget(self.position_label)
        layout.addWidget(QLabel("mm"))
        
        # 软件零点
        layout.addWidget(QLabel("软件零点:"))
        self.zero_label = QLabel("0.000")
        self.zero_label.setMinimumWidth(80)
        layout.addWidget(self.zero_label)
        layout.addWidget(QLabel("mm"))
        
        # 限位信息
        layout.addWidget(QLabel("限位:"))
        self.limit_label = QLabel("-10.0 ~ 10.0")
        self.limit_label.setMinimumWidth(100)
        layout.addWidget(self.limit_label)
        layout.addWidget(QLabel("mm"))
        
        layout.addStretch()
        group.setLayout(layout)
        return group
        
    def create_control_buttons_group(self):
        """创建控制按钮组"""
        group = QGroupBox("基本控制")
        
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # 回到零点
        zero_button = QPushButton("回到零点")
        zero_button.clicked.connect(self.go_to_zero)
        layout.addWidget(zero_button)
        
        # 设当前为零点
        set_zero_button = QPushButton("设当前为零点")
        set_zero_button.clicked.connect(self.set_zero)
        layout.addWidget(set_zero_button)
        
        # 机械归零
        mech_home_button = QPushButton("机械归零")
        mech_home_button.clicked.connect(self.mechanical_home)
        layout.addWidget(mech_home_button)
        
        # 停止
        stop_button = QPushButton("停止")
        stop_button.clicked.connect(self.stop_motion)
        layout.addWidget(stop_button)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
        
    def create_step_control_group(self):
        """创建步进控制组"""
        group = QGroupBox("步进控制")
        
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # 目标位置
        layout.addWidget(QLabel("目标位置:"))
        self.target_position = QDoubleSpinBox()
        self.target_position.setRange(-20.0, 20.0)
        self.target_position.setDecimals(3)
        self.target_position.setSingleStep(0.001)
        self.target_position.setMinimumWidth(80)
        layout.addWidget(self.target_position)
        
        move_button = QPushButton("移动")
        move_button.clicked.connect(self.move_to_target)
        layout.addWidget(move_button)
        
        # 步进值
        layout.addWidget(QLabel("步进:"))
        self.step_size = QDoubleSpinBox()
        self.step_size.setRange(0.001, 1.0)
        self.step_size.setDecimals(6)
        self.step_size.setSingleStep(0.001)
        self.step_size.setValue(0.001)  # 默认1微米
        self.step_size.setMinimumWidth(80)
        layout.addWidget(self.step_size)
        layout.addWidget(QLabel("mm"))
        
        # 步进按钮
        up_button = QPushButton("↑")
        up_button.clicked.connect(lambda: self.move_step(1))
        up_button.setMaximumWidth(30)
        layout.addWidget(up_button)
        
        down_button = QPushButton("↓")
        down_button.clicked.connect(lambda: self.move_step(-1))
        down_button.setMaximumWidth(30)
        layout.addWidget(down_button)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
        
    def create_parameter_settings_group(self):
        """创建参数设置组"""
        group = QGroupBox("参数设置")
        
        layout = QHBoxLayout()
        layout.setSpacing(15)
        
        # 速度设置
        layout.addWidget(QLabel("速度:"))
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 3000)
        self.speed_spin.setValue(1000)
        self.speed_spin.setMinimumWidth(70)
        layout.addWidget(self.speed_spin)
        layout.addWidget(QLabel("pps"))
        set_speed_button = QPushButton("设置")
        set_speed_button.clicked.connect(self.set_speed)
        layout.addWidget(set_speed_button)
        
        # 限位设置
        layout.addWidget(QLabel("最小限位:"))
        self.min_limit_spin = QDoubleSpinBox()
        self.min_limit_spin.setRange(-50.0, 0.0)
        self.min_limit_spin.setDecimals(1)
        self.min_limit_spin.setValue(-10.0)
        self.min_limit_spin.setMinimumWidth(70)
        layout.addWidget(self.min_limit_spin)
        
        layout.addWidget(QLabel("最大限位:"))
        self.max_limit_spin = QDoubleSpinBox()
        self.max_limit_spin.setRange(0.0, 50.0)
        self.max_limit_spin.setDecimals(1)
        self.max_limit_spin.setValue(10.0)
        self.max_limit_spin.setMinimumWidth(70)
        layout.addWidget(self.max_limit_spin)
        
        set_limit_button = QPushButton("设置限位")
        set_limit_button.clicked.connect(self.set_limits)
        layout.addWidget(set_limit_button)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
        
    def create_image_control_group(self):
        """创建图像控制组"""
        group = QGroupBox("图像拍摄控制")
        
        layout = QVBoxLayout()
        
        # 第一行：原有控件
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)
        
        # 每步拍摄图像数
        row1_layout.addWidget(QLabel("每步拍摄:"))
        self.images_per_step = QSpinBox()
        self.images_per_step.setRange(1, 100)
        self.images_per_step.setValue(1)
        self.images_per_step.setMinimumWidth(50)
        row1_layout.addWidget(self.images_per_step)
        row1_layout.addWidget(QLabel("张"))
        
        layout.addLayout(row1_layout)
        
        # 第二行：新增自动拍摄控件
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)
        
        # 自动拍摄范围设置
        row2_layout.addWidget(QLabel("自动拍摄:"))
        self.auto_capture_start = QDoubleSpinBox()
        self.auto_capture_start.setRange(-1000.0, 1000.0)
        self.auto_capture_start.setDecimals(3)
        self.auto_capture_start.setSingleStep(0.1)
        self.auto_capture_start.setValue(0.0)
        self.auto_capture_start.setMinimumWidth(80)
        row2_layout.addWidget(self.auto_capture_start)
        row2_layout.addWidget(QLabel("到"))
        
        self.auto_capture_end = QDoubleSpinBox()
        self.auto_capture_end.setRange(-1000.0, 1000.0)
        self.auto_capture_end.setDecimals(3)
        self.auto_capture_end.setSingleStep(0.1)
        self.auto_capture_end.setValue(100.0)
        self.auto_capture_end.setMinimumWidth(80)
        row2_layout.addWidget(self.auto_capture_end)
        row2_layout.addWidget(QLabel("微米"))
        
        # 步进值设置（微米）
        row2_layout.addWidget(QLabel("步进:"))
        self.auto_step_size = QDoubleSpinBox()
        self.auto_step_size.setRange(0.001, 1000.0)
        self.auto_step_size.setDecimals(3)
        self.auto_step_size.setSingleStep(0.1)
        self.auto_step_size.setValue(0.5)
        self.auto_step_size.setMinimumWidth(80)
        row2_layout.addWidget(self.auto_step_size)
        row2_layout.addWidget(QLabel("微米"))
        
        # 添加停止拍摄按钮
        self.stop_capture_button = QPushButton("停止拍摄")
        self.stop_capture_button.clicked.connect(self.stop_capture)
        self.stop_capture_button.setEnabled(False)
        row2_layout.addWidget(self.stop_capture_button)
        
        # 自动拍摄按钮
        self.auto_capture_button = QPushButton("自动拍摄")
        self.auto_capture_button.clicked.connect(self.auto_capture)
        row2_layout.addWidget(self.auto_capture_button)
        
        layout.addLayout(row2_layout)
        
        layout.addStretch()
        group.setLayout(layout)
        return group
        
    def refresh_ports(self):
        """刷新串口列表"""
        if self.stage_controller:
            ports = self.stage_controller.get_available_ports()
            self.port_combo.clear()
            self.port_combo.addItems(ports)
            
    def toggle_connection(self):
        """切换连接状态"""
        if not self.stage_controller:
            return
            
        if self.stage_controller.is_connected:
            self.stage_controller.disconnect()
            self.connect_button.setText("连接")
        else:
            port = self.port_combo.currentText()
            baudrate = int(self.baudrate_combo.currentText())
            if port:
                if self.stage_controller.connect(port, baudrate):
                    self.connect_button.setText("断开")
                    # 更新界面参数
                    self.update_ui_from_controller()
                else:
                    self.show_error("连接失败")
            else:
                self.show_error("请选择串口")
                
    def update_ui_from_controller(self):
        """从控制器更新界面参数"""
        if not self.stage_controller:
            return
            
        # 更新限位显示
        self.min_limit_spin.setValue(self.stage_controller.min_limit_z)
        self.max_limit_spin.setValue(self.stage_controller.max_limit_z)
        self.limit_label.setText(f"{self.stage_controller.min_limit_z:.1f} ~ {self.stage_controller.max_limit_z:.1f}")
        
        # 更新速度显示
        self.speed_spin.setValue(self.stage_controller.max_speed_z)
        
        # 更新步进值
        self.step_size.setValue(self.stage_controller.step_size)
        
        # 更新每步拍摄图像数
        self.images_per_step.setValue(self.stage_controller.images_per_step)
        
    def on_position_update(self, position):
        """位置更新回调"""
        # 更新当前位置显示
        self.position_label.setText(f"{position:.3f}")
        # 同时更新软件零点显示
        if self.stage_controller:
            self.zero_label.setText(f"{self.stage_controller.zero_z:.3f}")
            
    def on_status_update(self, message):
        """状态更新回调"""
        self.status_message.emit(message)
        
    def on_error_update(self, message):
        """错误更新回调"""
        self.error_message.emit(message)
        self.show_error(message)
        
    def show_error(self, message):
        """显示错误消息"""
        QMessageBox.critical(self, "错误", message)
        
    def go_to_zero(self):
        """回到零点"""
        if self.stage_controller:
            self.stage_controller.go_to_software_zero()
            
    def set_zero(self):
        """设当前为零点"""
        if self.stage_controller:
            self.stage_controller.zero_axis()
            
    def mechanical_home(self):
        """机械归零"""
        if self.stage_controller:
            self.stage_controller.mechanical_home_axis()
            
    def stop_motion(self):
        """停止运动"""
        if self.stage_controller:
            self.stage_controller.stop_axis()
            
    def move_to_target(self):
        """移动到目标位置"""
        if self.stage_controller:
            target = self.target_position.value()
            self.stage_controller.move_to_position(target)
            
    def move_step(self, direction):
        """步进移动"""
        if self.stage_controller:
            # 设置步进值
            if self.stage_controller:
                self.stage_controller.set_step_parameters(
                    self.step_size.value(),
                    self.images_per_step.value()
                )
            self.stage_controller.move_relative(direction)
            
    def set_speed(self):
        """设置速度"""
        if self.stage_controller:
            speed = self.speed_spin.value()
            self.stage_controller.set_speed(speed)
            
    def set_limits(self):
        """设置限位"""
        if self.stage_controller:
            min_val = self.min_limit_spin.value()
            max_val = self.max_limit_spin.value()
            if self.stage_controller.set_limit(min_val, max_val):
                self.limit_label.setText(f"{min_val:.1f} ~ {max_val:.1f}")
                
    def step_and_capture(self, direction):
        """步进并拍摄图像"""
        if not self.stage_controller:
            return
            
        # 设置步进参数
        self.stage_controller.set_step_parameters(
            self.step_size.value(),
            self.images_per_step.value()
        )
        
        # 执行步进和拍摄
        success = self.stage_controller.micro_step_and_capture(direction)
        if not success:
            self.error_message.emit("步进并拍摄失败")
            
    def auto_capture(self):
        """自动拍摄功能"""
        if not self.stage_controller:
            self.show_error("位移台控制器未初始化")
            return
            
        # 获取参数（微米）
        start_pos = self.auto_capture_start.value()
        end_pos = self.auto_capture_end.value()
        step_size = self.auto_step_size.value()
        images_per_step = self.images_per_step.value()
        
        # 设置参数（转换为毫米）
        self.stage_controller.set_step_parameters(step_size/1000.0, images_per_step)
        
        # 启用停止按钮，禁用自动拍摄按钮
        self.auto_capture_button.setEnabled(False)
        self.stop_capture_button.setEnabled(True)
        
        # 在新线程中执行自动拍摄，避免阻塞UI
        import threading
        self.capture_thread = threading.Thread(
            target=self._auto_capture_thread, 
            args=(start_pos/1000.0, end_pos/1000.0, step_size/1000.0),  # 转换为毫米
            daemon=True
        )
        self.capture_thread.start()
        
    def stop_capture(self):
        """停止拍摄"""
        if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
            # 设置停止标志
            if self.stage_controller:
                self.stage_controller.stop_capture = True
            self.status_message.emit("正在停止拍摄...")
            
    def _auto_capture_thread(self, start_pos_mm, end_pos_mm, step_size_mm):
        """自动拍摄线程函数"""
        try:
            # 重置停止标志
            if self.stage_controller:
                self.stage_controller.stop_capture = False
                
            # 执行自动拍摄序列
            if self.stage_controller:
                success = self.stage_controller.auto_capture_sequence(start_pos_mm, end_pos_mm, step_size_mm)
                if success:
                    # 拍摄完成后自动保存堆栈
                    self._auto_save_stack()
                    
        except Exception as e:
            pass
        finally:
            # 恢复按钮状态
            self._restore_buttons()
            
    def _restore_buttons(self):
        """恢复按钮状态"""
        self.auto_capture_button.setEnabled(True)
        self.stop_capture_button.setEnabled(False)
        
    def _auto_save_stack(self):
        """自动保存图像堆栈"""
        if not self.stage_controller:
            return
            
        stack_images = self.stage_controller.get_stack_images()
        if not stack_images:
            return
            
        # 生成文件名
        import time
        timestamp = int(time.time() * 1000)
        filename = f"auto_capture_stack_{timestamp}.tiff"
        
        # 保存堆栈
        try:
            from processing.data_saver import DataSaver
            saver = DataSaver()
            success = saver.save_stack_data(stack_images, filename)
            if success:
                self.status_message.emit(f"自动拍摄完成，图像堆栈已保存为: {filename} ({len(stack_images)}帧)")
        except Exception as e:
            pass
        
    def capture_current_image(self):
        """捕获当前图像用于位移台控制"""
        # 发射请求捕获图像信号
        self.capture_image_request.emit()
        # 注意：实际的图像数据需要由主窗口提供
        return None
        
    def closeEvent(self, a0):
        """窗口关闭事件"""
        if self.stage_controller:
            self.stage_controller.close()
        if a0:
            a0.accept()