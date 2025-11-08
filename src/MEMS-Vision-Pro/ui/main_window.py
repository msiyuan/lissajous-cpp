"""
主窗口模块
简化版主窗口，专注于协调各个功能模块
"""

import time
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QTextEdit, QFileDialog, QApplication,
    QScrollArea, QSplitter, QTabWidget  # 添加QTabWidget
)
from PyQt5.QtCore import pyqtSlot, QTimer, Qt

from config.constants import WINDOW_WIDTH, WINDOW_HEIGHT, MIN_LEFT_WIDTH, MIN_RIGHT_WIDTH, MAX_RIGHT_WIDTH
from config.default_params import DEFAULT_NETWORK_PARAMS, DEFAULT_UI_PARAMS
from ui.protocol_controls import ProtocolControlWidget
from ui.image_controls import ImageControlWidget
from ui.stage_controls import StageControlWidget  # 添加这一行
from ui.status_widgets import StatusWidget, NetworkStatusWidget, ProcessingStatusWidget
from network.udp_receiver import UDPReceiver
from network.udp_sender import UDPSender
from processing.frame_assembler import FrameAssembler
from processing.image_processor import ImageProcessor
from processing.data_saver import DataSaver
from utils.global_queue import clear_queue
from utils.numba_functions import warm_up_interpolation_function
from utils.stage_controller import StageController  # 添加这一行


class MainWindow(QMainWindow):
    """主窗口类（简化版，专注于协调各模块）"""
    
    def __init__(self):
        """初始化主窗口"""
        super().__init__()
        self.setup_window()
        self.setup_components()
        self.setup_ui()
        self.setup_connections()
        self.setup_timers()
        
        # 延迟预编译Numba函数
        QTimer.singleShot(10, self.warm_up_numba_functions)
        
    def setup_window(self):
        """设置窗口基本属性"""
        self.setWindowTitle("MEMS-Vision-Pro - 新协议版本")
        self.resize(1600, 900)  # 增加窗口尺寸以适应新布局
        self.setMinimumSize(1400, 700)  # 设置最小尺寸
        
    def setup_components(self):
        """设置各个组件"""
        # 创建各个控制组件
        self.protocol_controls = ProtocolControlWidget()
        self.image_controls = ImageControlWidget()
        self.stage_controls = StageControlWidget()
        self.status_widget = StatusWidget()
        self.network_status = NetworkStatusWidget()
        self.processing_status = ProcessingStatusWidget()
        
        # 创建日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        
        # 初始化对象引用
        self.udp_receiver = None
        self.assembler = None
        self.processors = []
        self.data_saver = DataSaver()
        
        # 初始化位移台控制器
        self.stage_controller = StageController()
        self.stage_controls.set_stage_controller(self.stage_controller)
        
        # 应用状态
        self.should_save_frame = False
        self.should_save_stack = False  # 堆栈保存状态
        self.stack_images = []  # 存储堆栈图像
        self.stack_counter = 0  # 堆栈计数器
        self.max_stack_size = 1000  # 最大堆栈大小限制
        
        # 多帧融合相关
        self.frame_buffer = []  # 存储待融合的帧
        self.max_buffer_size = 10
        
    def setup_ui(self):
        """设置界面布局"""
        # 创建主分隔器
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setChildrenCollapsible(False)  # 防止面板被完全折叠
        main_splitter.setHandleWidth(8)  # 设置分隔器手柄宽度
        
        # 左侧区域 - 图像控制和网络设置
        left_widget = self.create_left_panel()
        
        # 创建标签页控件，包含位移台控制和协议命令控制
        self.control_tabs = QTabWidget()
        self.control_tabs.addTab(self.protocol_controls, "协议命令控制")
        self.control_tabs.addTab(self.stage_controls, "位移台控制")
        self.control_tabs.setMinimumWidth(400)  # 增加最小宽度
        self.control_tabs.setMaximumWidth(1600)  # 设置最大宽度
        
        # 添加到分隔器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(self.control_tabs)  # 添加标签页控件
        
        # 设置分隔器的拉伸因子
        main_splitter.setStretchFactor(0, 3)  # 左侧占3份
        main_splitter.setStretchFactor(1, 2)  # 右侧占2份
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)  # 增加间距
        main_layout.setContentsMargins(8, 8, 8, 8)  # 增加边距
        
        # 添加分隔器，占据大部分空间
        main_layout.addWidget(main_splitter, 1)  # 使用权重1，让其占据剩余空间
        
        # 控制按钮区域（固定高度）
        button_layout = self.create_control_buttons_layout()
        main_layout.addLayout(button_layout)
        
        # 日志区域 - 固定高度
        log_label = QLabel("系统日志:")
        log_label.setMaximumHeight(20)
        log_label.setMinimumHeight(20)
        log_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(log_label)
        
        # 日志文本区域 - 固定高度
        self.log_text.setMaximumHeight(100)
        self.log_text.setMinimumHeight(100)
        self.log_text.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        main_layout.addWidget(self.log_text)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
    
    def create_left_panel(self):
        """创建左侧面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)  # 增加间距
        left_layout.setContentsMargins(5, 5, 5, 5)  # 增加边距
        
        # 网络设置区域
        network_layout = self.create_network_settings_layout()
        left_layout.addLayout(network_layout)
        
        # 图像控制区域（添加滚动）
        image_scroll = QScrollArea()
        image_scroll.setWidgetResizable(True)
        image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        image_scroll.setWidget(self.image_controls)
        image_scroll.setMinimumHeight(300)  # 设置最小高度
        image_scroll.setStyleSheet("QScrollArea { border: 1px solid #ccc; }")
        left_layout.addWidget(image_scroll, 2)  # 添加拉伸因子，让图像控制区域占据更多空间
        
        # 状态显示区域
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)  # 增加状态控件间距
        status_layout.addWidget(self.status_widget)
        status_layout.addWidget(self.network_status)
        status_layout.addWidget(self.processing_status)
        left_layout.addLayout(status_layout)
        
        left_widget.setLayout(left_layout)
        left_widget.setMinimumWidth(700)  # 增加最小宽度
        left_widget.setMaximumWidth(1000)  # 设置最大宽度
        
        return left_widget
        
    def create_network_settings_layout(self):
        """创建网络设置布局"""
        # 使用水平布局，将所有设置放在一行
        layout = QHBoxLayout()
        layout.setSpacing(15)  # 增加控件间距
        layout.setContentsMargins(5, 5, 5, 5)  # 增加边距
        
        # IP设置
        layout.addWidget(QLabel("目标IP:"))
        self.ip_input = QLineEdit(DEFAULT_NETWORK_PARAMS['target_ip'])
        self.ip_input.setFixedWidth(130)  # 稍微增加宽度
        self.ip_input.setMinimumHeight(25)
        self.ip_input.textChanged.connect(self.update_sender_ip)
        layout.addWidget(self.ip_input)
        
        # 帧缓存设置
        layout.addWidget(QLabel("帧缓存:"))
        self.frame_buffer_size_input = QLineEdit(str(DEFAULT_UI_PARAMS['frame_buffer_size']))
        self.frame_buffer_size_input.setFixedWidth(60)  # 稍微增加宽度
        self.frame_buffer_size_input.setMinimumHeight(25)
        self.frame_buffer_size_input.textChanged.connect(self.on_frame_buffer_size_changed)
        layout.addWidget(self.frame_buffer_size_input)
        
        # 多帧融合开关
        self.enable_frame_fusion = QPushButton("多帧融合")
        self.enable_frame_fusion.setCheckable(True)
        self.enable_frame_fusion.setMinimumHeight(30)
        self.enable_frame_fusion.setMaximumWidth(120)
        self.enable_frame_fusion.clicked.connect(self.toggle_frame_fusion)
        layout.addWidget(self.enable_frame_fusion)
        
        # 添加状态指示
        self.fusion_status_label = QLabel("(关闭)")
        self.fusion_status_label.setStyleSheet("color: gray; font-size: 11px;")
        self.fusion_status_label.setMinimumHeight(30)
        layout.addWidget(self.fusion_status_label)
        
        # 添加弹性空间
        layout.addStretch()
        
        return layout
    
    def create_control_buttons_layout(self):
        """创建控制按钮布局"""
        layout = QHBoxLayout()
        layout.setSpacing(8)  # 增加按钮间距
        layout.setContentsMargins(5, 5, 5, 5)  # 增加边距
        
        # 接收控制按钮
        self.start_receiver_button = QPushButton("启动接收")
        self.stop_receiver_button = QPushButton("停止接收")
        self.start_receiver_button.clicked.connect(self.start_receiver)
        self.stop_receiver_button.clicked.connect(self.stop_receiver)
        self.stop_receiver_button.setEnabled(False)
        
        # 设置按钮样式和大小
        button_style = """
            QPushButton {
                padding: 8px 12px;
                font-weight: bold;
                border: 1px solid #aaa;
                border-radius: 4px;
            }
            QPushButton:enabled {
                background-color: #4CAF50;
                color: white;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        
        for btn in [self.start_receiver_button, self.stop_receiver_button]:
            btn.setStyleSheet(button_style)
            btn.setMinimumHeight(35)
            btn.setMinimumWidth(90)
        
        layout.addWidget(self.start_receiver_button)
        layout.addWidget(self.stop_receiver_button)
        
        # 复位计数按钮
        self.reset_button = QPushButton("复位")
        self.reset_button.clicked.connect(self.reset_counters)
        self.reset_button.setStyleSheet(button_style)
        self.reset_button.setMinimumHeight(35)
        self.reset_button.setMinimumWidth(70)
        layout.addWidget(self.reset_button)
        
        # 保存数据按钮
        self.save_button = QPushButton("保存数据")
        self.save_button.setCheckable(True)
        self.save_button.clicked.connect(self.toggle_save_data)
        self.save_button.setEnabled(False)
        self.save_button.setStyleSheet(button_style)
        self.save_button.setMinimumHeight(35)
        self.save_button.setMinimumWidth(90)
        layout.addWidget(self.save_button)
        
        # 保存帧按钮
        self.save_frame_button = QPushButton("保存帧")
        self.save_frame_button.setCheckable(True)
        self.save_frame_button.clicked.connect(self.toggle_save_frame)
        self.save_frame_button.setEnabled(False)
        self.save_frame_button.setStyleSheet(button_style)
        self.save_frame_button.setMinimumHeight(35)
        self.save_frame_button.setMinimumWidth(80)
        layout.addWidget(self.save_frame_button)
        
        # 保存图像按钮
        self.save_image_button = QPushButton("保存图像")
        self.save_image_button.clicked.connect(self.save_current_image)
        self.save_image_button.setEnabled(False)
        self.save_image_button.setStyleSheet(button_style)
        self.save_image_button.setMinimumHeight(35)
        self.save_image_button.setMinimumWidth(90)
        layout.addWidget(self.save_image_button)

        # 保存堆栈按钮
        self.save_stack_button = QPushButton("保存堆栈")
        self.save_stack_button.setCheckable(True)
        self.save_stack_button.clicked.connect(self.toggle_save_stack)
        self.save_stack_button.setEnabled(False)
        self.save_stack_button.setStyleSheet(button_style)
        self.save_stack_button.setMinimumHeight(35)
        self.save_stack_button.setMinimumWidth(90)
        layout.addWidget(self.save_stack_button)
        
        # 手动指令输入
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("手动指令(hex): AA 01 02 03")
        self.command_input.setFixedWidth(200)
        self.command_input.setMinimumHeight(35)
        layout.addWidget(self.command_input)
        
        self.send_command_button = QPushButton("发送")
        self.send_command_button.clicked.connect(self.send_manual_command)
        self.send_command_button.setStyleSheet(button_style)
        self.send_command_button.setMinimumHeight(35)
        self.send_command_button.setMinimumWidth(70)
        layout.addWidget(self.send_command_button)
        
        layout.addStretch()
        return layout
    
    def setup_connections(self):
        """设置信号连接"""
        # 协议控制组件信号连接
        self.protocol_controls.log_message.connect(self.log_text.append)
        self.protocol_controls.command_sent.connect(
            lambda cmd: self.log_text.append(f"发送命令: {cmd}")
        )
        
        # 添加位移台控制器位置更新信号连接
        if hasattr(self.stage_controls, 'position_changed'):
            self.stage_controls.position_changed.connect(self.on_stage_position_changed)
        
        # 图像控制组件信号连接
        self.image_controls.image_params_changed.connect(self.on_image_params_changed)
        self.image_controls.phase_correction_started.connect(self.on_phase_correction_started)
        
        # 位移台控制组件信号连接
        self.stage_controls.status_message.connect(self.log_text.append)
        self.stage_controls.error_message.connect(self.log_text.append)
        self.stage_controls.capture_image_request.connect(self.on_capture_image_request)
        
        # 初始创建UDP发送器
        self.update_sender_ip()
        
    def on_stage_position_changed(self, position):
        """处理位移台位置变化"""
        # 位置更新已经在stage_controls内部处理，这里可以添加额外的逻辑
        pass
    
    def on_capture_image_request(self):
        """处理位移台控制的图像捕获请求"""
        # 设置图像捕获回调
        if self.stage_controller:
            self.stage_controller.set_image_capture_callback(self.capture_current_image)
            
    def capture_current_image(self):
        """捕获当前图像用于位移台控制"""
        # 返回当前显示的图像数据
        image = self.image_controls.current_16bit_image
        # 如果没有图像数据，返回一个空数组而不是None
        if image is None:
            import numpy as np
            return np.array([])
        return image

    def setup_timers(self):
        """设置定时器"""
        pass
    
    def warm_up_numba_functions(self):
        """预编译Numba函数"""
        try:
            from utils.numba_functions import warm_up_interpolation_function
            warm_up_interpolation_function()
            self.log_text.append("Numba函数预编译完成")
        except Exception as e:
            self.log_text.append(f"Numba函数预编译失败: {e}")
    
    def reset_counters(self):
        """重置所有计数器"""
        # 重置状态控件中的计数器
        self.status_widget.reset_all_counters()
        self.processing_status.reset_processing_count()
        
        # 清空帧缓冲区
        if self.assembler:
            self.assembler.clear_buffer()
        
        # 清空多帧融合缓存
        self.frame_buffer.clear()
        
        # 清空堆栈
        self.stack_images.clear()
        self.stack_counter = 0
        
        self.log_text.append("所有计数器已重置")
    
    def toggle_save_data(self):
        """切换保存数据状态"""
        if self.save_button.isChecked():
            self.log_text.append("开始保存数据")
        else:
            self.log_text.append("停止保存数据")
    
    def toggle_save_frame(self):
        """切换保存帧状态"""
        self.should_save_frame = self.save_frame_button.isChecked()
        if self.should_save_frame:
            self.log_text.append("开始保存帧数据")
        else:
            self.log_text.append("停止保存帧数据")
    
    def save_current_image(self):
        """保存当前图像"""
        try:
            if self.image_controls.current_16bit_image is not None:
                success = self.image_controls.save_current_image()
                if success:
                    self.log_text.append("当前图像已保存")
                else:
                    self.log_text.append("保存图像失败")
            else:
                self.log_text.append("没有图像可保存")
        except Exception as e:
            self.log_text.append(f"保存图像时出错: {e}")
    
    def toggle_save_stack(self):
        """切换保存堆栈状态"""
        self.should_save_stack = self.save_stack_button.isChecked()
        if self.should_save_stack:
            self.log_text.append("开始保存堆栈数据")
        else:
            # 停止保存并保存当前堆栈
            if self.stack_images:
                timestamp = int(time.time() * 1000)
                filename = f"image_stack_{timestamp}.npy"
                success = self.data_saver.save_stack_data(self.stack_images, filename)
                if success:
                    self.log_text.append(f"堆栈数据已保存到: {filename}")
                else:
                    self.log_text.append("保存堆栈数据失败")
            self.stack_images.clear()
            self.stack_counter = 0
            self.log_text.append("停止保存堆栈数据")
    
    def send_manual_command(self):
        """发送手动指令"""
        try:
            command_str = self.command_input.text().strip()
            if not command_str:
                self.log_text.append("请输入指令")
                return
            
            # 解析十六进制指令
            hex_bytes = []
            for hex_str in command_str.split():
                if hex_str.startswith('0x'):
                    hex_str = hex_str[2:]
                hex_bytes.append(int(hex_str, 16))
            
            command = bytes(hex_bytes)
            
            # 发送指令
            if self.protocol_controls.udp_sender:
                success, bytes_sent = self.protocol_controls.udp_sender.send_command(command)
                if success:
                    self.log_text.append(f"手动指令已发送: {command_str}")
                    self.protocol_controls.command_sent.emit(command.hex().upper())
                else:
                    self.log_text.append("发送手动指令失败")
            else:
                self.log_text.append("UDP发送器未设置")
        except Exception as e:
            self.log_text.append(f"发送手动指令出错: {e}")
    
    def start_receiver(self):
        """启动UDP接收"""
        try:
            # 如果已经有接收器在运行，先停止它
            if self.udp_receiver:
                self.stop_receiver()
                time.sleep(0.1)
                
            target_ip = self.ip_input.text().strip()
            
            # 创建新的接收器
            self.udp_receiver = UDPReceiver(target_ip, 8003)
            self.udp_receiver.log_message.connect(self.log_text.append)
            self.udp_receiver.packet_received.connect(self.status_widget.update_bytes_counter)
            self.udp_receiver.start()

            # 创建帧组装器
            buffer_size = int(self.frame_buffer_size_input.text())
            self.assembler = FrameAssembler(frame_buffer_size=buffer_size)
            self.assembler.log_message.connect(self.log_text.append)
            self.assembler.frame_complete.connect(self.on_frame_complete)
            self.assembler.frames_complete.connect(self.on_frames_complete)
            self.assembler.queue_status.connect(self.status_widget.update_queue_status)
            self.assembler.start()

            # 更新界面状态
            self.start_receiver_button.setEnabled(False)
            self.stop_receiver_button.setEnabled(True)
            self.save_button.setEnabled(True)
            self.save_frame_button.setEnabled(True)
            self.save_image_button.setEnabled(True)  # 启用保存图像按钮
            self.save_stack_button.setEnabled(True)  # 启用保存堆栈按钮
            
            # 禁用协议控制界面的输入控件
            self.protocol_controls.disable_controls()

            # 更新网络状态
            self.network_status.update_connection_status(True)
            self.network_status.update_target_info(target_ip, 8003)
            
            self.log_text.append(f"UDP接收器已启动 (目标IP={target_ip}, 监听端口=8003)")
            
        except Exception as e:
            self.log_text.append(f"启动接收器失败：{str(e)}")

    def stop_receiver(self):
        """停止UDP接收"""
        if self.udp_receiver:
            self.udp_receiver.stop()
            self.udp_receiver.wait()
            self.udp_receiver = None
            
        if self.assembler:
            self.assembler.stop()
            self.assembler.wait()
            self.assembler = None
            
        # 清空全局队列
        clear_queue()
                
        # 等待所有处理器完成
        for processor in self.processors:
            if processor.isRunning():
                processor.stop()
                processor.wait()
        self.processors.clear()
        
        # 更新界面状态
        self.start_receiver_button.setEnabled(True)
        self.stop_receiver_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.save_frame_button.setEnabled(False)
        self.save_image_button.setEnabled(False)  # 禁用保存图像按钮
        self.save_stack_button.setEnabled(False)  # 禁用保存堆栈按钮
        # 如果正在保存堆栈，则停止并保存
        if self.should_save_stack:
            self.save_stack_button.click()  # 停止保存堆栈

        # 启用协议控制界面的输入控件
        self.protocol_controls.enable_controls()

        # 更新网络状态
        self.network_status.update_connection_status(False)
        
        # 清空多帧融合缓存
        self.frame_buffer.clear()
        
        if self.save_button.isChecked():
            self.save_button.click()  # 停止保存
            
        self.log_text.append("UDP接收器已停止")

    def validate_frame_buffer_size(self):
        """验证帧缓存大小"""
        try:
            value = int(self.frame_buffer_size_input.text())
            if 1 <= value <= 10:
                self.frame_buffer_size_input.setStyleSheet("")  # 恢复正常样式
                if self.enable_frame_fusion.isChecked():
                    self.fusion_status_label.setText(f"({value}帧平均)")
                return True
            else:
                self.frame_buffer_size_input.setStyleSheet("background-color: #ffcccc;")  # 红色背景
                if self.enable_frame_fusion.isChecked():
                    self.fusion_status_label.setText("(无效值)")
                return False
        except ValueError:
            self.frame_buffer_size_input.setStyleSheet("background-color: #ffcccc;")  # 红色背景
            if self.enable_frame_fusion.isChecked():
                self.fusion_status_label.setText("(无效值)")
            return False
            
    def on_frame_buffer_size_changed(self):
        """帧缓存大小变化处理"""
        self.validate_frame_buffer_size()
    
    def toggle_frame_fusion(self):
        """切换多帧融合状态"""
        if self.enable_frame_fusion.isChecked():
            if self.validate_frame_buffer_size():
                buffer_size = int(self.frame_buffer_size_input.text())
                self.fusion_status_label.setText(f"({buffer_size}帧平均)")
                self.fusion_status_label.setStyleSheet("color: green; font-size: 10px;")
                self.frame_buffer.clear()  # 清空缓存
                self.log_text.append(f"启用多帧融合：{buffer_size}帧平均")
            else:
                self.enable_frame_fusion.setChecked(False)
                self.fusion_status_label.setText("(关闭)")
                self.fusion_status_label.setStyleSheet("color: gray; font-size: 10px;")
                self.log_text.append("多帧融合启用失败：帧缓存值必须为1-10的整数")
        else:
            self.fusion_status_label.setText("(关闭)")
            self.fusion_status_label.setStyleSheet("color: gray; font-size: 10px;")
            self.frame_buffer.clear()  # 清空缓存
            self.log_text.append("多帧融合已关闭")

    @pyqtSlot(list)
    def on_frame_complete(self, packets_list):
        """处理完整帧"""
        if not packets_list:
            return
        
        # 检查是否启用多帧融合
        if self.enable_frame_fusion.isChecked():
            # 验证帧缓存大小
            if not self.validate_frame_buffer_size():
                self.log_text.append("多帧融合失败：帧缓存值无效，处理单帧")
                self._process_single_frame(packets_list)
                return
            
            # 多帧融合模式
            buffer_size = int(self.frame_buffer_size_input.text())
            self.frame_buffer.append(packets_list)
            
            # 如果缓存已满，进行融合处理
            if len(self.frame_buffer) >= buffer_size:
                self._process_fused_frames()
                self.frame_buffer.clear()  # 清空缓存
            else:
                # 缓存未满，等待更多帧
                self.log_text.append(f"多帧融合缓存：{len(self.frame_buffer)}/{buffer_size} 帧")
                return
        else:
            # 单帧模式
            self._process_single_frame(packets_list)
    
    def _process_single_frame(self, packets_list):
        """处理单个帧"""
        # 更新处理状态
        self.processing_status.update_processing_status("处理中")
        self.processing_status.increment_processing_count()
        self.status_widget.record_frame_time()

        # 检查是否需要保存帧
        if self.should_save_frame and packets_list:
            self.data_saver.save_packets_to_bin(packets_list)

        try:
            # 获取当前的处理参数
            params = self.image_controls.get_current_params()
            
            # 创建新的处理器
            processor = ImageProcessor(
                packets_list,
                params['deltaphasex'],
                params['deltaphasey'],
                params['freqx'],
                params['freqy']
            )
            processor.image_processed.connect(self.on_image_processed)
            processor.finished.connect(lambda: self.cleanup_processor(processor))
            self.processors.append(processor)
            processor.start()
            
        except ValueError as e:
            self.log_text.append("错误：相位或频率设置无效，请输入数字")
            self.processing_status.update_processing_status("错误")
        except Exception as e:
            self.log_text.append(f"处理出错：{str(e)}")
            self.processing_status.update_processing_status("错误")
    
    def _process_fused_frames(self):
        """处理融合帧"""
        if not self.frame_buffer:
            return
        
        buffer_size = len(self.frame_buffer)
        self.log_text.append(f"开始多帧融合处理：{buffer_size}帧平均")
        
        # 更新处理状态
        self.processing_status.update_processing_status("融合处理中")
        self.processing_status.increment_processing_count()
        self.status_widget.record_frame_time()
        
        try:
            # 获取当前的处理参数
            params = self.image_controls.get_current_params()
            
            # 处理每一帧并收集图像
            processed_images = []
            phasex_deg = 0.0
            phasey_deg = 0.0
            for i, packets_list in enumerate(self.frame_buffer):
                # 创建处理器
                processor = ImageProcessor(
                    packets_list,
                    params['deltaphasex'],
                    params['deltaphasey'],
                    params['freqx'],
                    params['freqy']
                )
                
                # 同步处理单帧
                final_image, phasex_deg, phasey_deg = processor.process_single_frame_one_freq(
                    packets_list,
                    SampleRate=1e7,
                    Freqx=params['freqx'],
                    Freqy=params['freqy'],
                    deltaphasex=params['deltaphasex'],
                    deltaphasey=params['deltaphasey']
                )
                processed_images.append(final_image)
                self.log_text.append(f"  帧 {i+1}/{buffer_size} 处理完成")
            
            # 执行多帧平均融合
            if processed_images:
                fused_image = np.mean(processed_images, axis=0)
                self.log_text.append(f"多帧融合完成：{buffer_size}帧平均")
                    
                # 直接更新图像显示
                self.image_controls.set_image(fused_image)
                # 如果需要保存堆栈，则添加到堆栈中
                self.add_image_to_stack(fused_image)
                self.log_text.append(f"融合图像显示完成。")
            
        except Exception as e:
            self.log_text.append(f"多帧融合处理出错：{str(e)}")
            self.processing_status.update_processing_status("错误")
        finally:
            # 更新处理状态为空闲
            self.update_processing_status_after_fusion()

    @pyqtSlot(list)
    def on_frames_complete(self, frames_list):
        """处理多个完整帧"""
        # 直接调用单帧处理逻辑，多帧融合在on_frame_complete中处理
        for frames in frames_list:
            self.on_frame_complete(frames)

    def cleanup_processor(self, processor):
        """清理完成的处理器"""
        if processor in self.processors:
            self.processors.remove(processor)
            processor.deleteLater()
        
        # 更新处理状态
        if len(self.processors) == 0:
            self.processing_status.update_processing_status("空闲")
    
    def update_processing_status_after_fusion(self):
        """更新多帧融合后的处理状态"""
        self.processing_status.update_processing_status("空闲")

    @pyqtSlot(np.ndarray, float, float)
    def on_image_processed(self, final_image, phasex_deg, phasey_deg):
        """处理图像处理结果"""
        # 设置图像到显示控件
        self.image_controls.set_image(final_image)

        # 如果需要保存堆栈，则添加到堆栈中
        self.add_image_to_stack(final_image)
        
        # self.log_text.append(f"图像处理完成。相位: X={phasex_deg:.1f}°, Y={phasey_deg:.1f}°")

    def on_image_params_changed(self, params):
        """处理图像参数变化"""
        self.log_text.append(f"参数已更新: X相位={params['deltaphasex']}°, Y相位={params['deltaphasey']}°, X频率={params['freqx']}, Y频率={params['freqy']}")

    def on_phase_correction_started(self):
        """处理相位校正开始信号"""
        self.log_text.append("开始相位校正扫描...")
        self.perform_phase_correction()
        
    def find_best_phases(self):
        """寻找最佳相位点"""
        try:
            import os
            import numpy as np
            
            # 读取分析结果
            base_path = "./phaseCorrect"
            x_csv_path = os.path.join(base_path, "x", "freq_metrics.csv")
            y_csv_path = os.path.join(base_path, "y", "freq_metrics.csv")
            
            if not os.path.exists(x_csv_path) or not os.path.exists(y_csv_path):
                self.log_text.append("频域分析结果文件不存在")
                return None, None
                
            # 读取X相位分析结果
            x_scores = []
            x_phases = []
            with open(x_csv_path, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:  # 跳过表头
                    for line in lines[1:]:
                        parts = line.strip().split(',')
                        if len(parts) >= 6:
                            filename = parts[0]
                            # 从文件名中提取相位值
                            if 'x_phase_' in filename:
                                phase_str = filename.split('x_phase_')[1].split('_deg')[0]
                                phase = float(phase_str)
                                x_phases.append(phase)
                                
                                # 计算综合评分（可以根据需要调整权重）
                                # SC_r 越大越好，centroid 越小越好，kurtosis 越大越好，anisotropy 越小越好
                                sc_r = float(parts[1])
                                centroid = float(parts[2])
                                kurtosis = float(parts[4])
                                anisotropy = float(parts[5])
                                
                                # 综合评分（简单加权）
                                score = sc_r - centroid/100 + kurtosis/100 - anisotropy*1000
                                x_scores.append(score)
            
            # 读取Y相位分析结果
            y_scores = []
            y_phases = []
            with open(y_csv_path, 'r') as f:
                lines = f.readlines()
                if len(lines) > 1:  # 跳过表头
                    for line in lines[1:]:
                        parts = line.strip().split(',')
                        if len(parts) >= 6:
                            filename = parts[0]
                            # 从文件名中提取相位值
                            if 'y_phase_' in filename:
                                phase_str = filename.split('y_phase_')[1].split('_deg')[0]
                                phase = float(phase_str)
                                y_phases.append(phase)
                                
                                # 计算综合评分
                                sc_r = float(parts[1])
                                centroid = float(parts[2])
                                kurtosis = float(parts[4])
                                anisotropy = float(parts[5])
                                
                                # 综合评分
                                score = sc_r - centroid/100 + kurtosis/100 - anisotropy*1000
                                y_scores.append(score)
            
            # 寻找最佳相位点
            best_x_phase = None
            best_y_phase = None
            
            if x_scores and x_phases:
                best_x_idx = np.argmax(x_scores)
                best_x_phase = x_phases[best_x_idx]
                self.log_text.append(f"X相位最佳点: {best_x_phase:.1f}° (评分: {x_scores[best_x_idx]:.4f})")
                
            if y_scores and y_phases:
                best_y_idx = np.argmax(y_scores)
                best_y_phase = y_phases[best_y_idx]
                self.log_text.append(f"Y相位最佳点: {best_y_phase:.1f}° (评分: {y_scores[best_y_idx]:.4f})")
                
            return best_x_phase, best_y_phase
            
        except Exception as e:
            self.log_text.append(f"寻找最佳相位点时出错: {e}")
            return None, None

    def safe_remove_directory(self, path):
        """
        安全地删除目录，处理文件被占用的情况
        
        Args:
            path: 要删除的目录路径
        """
        import os
        import shutil
        import time
        
        if not os.path.exists(path):
            return True
            
        # 尝试直接删除
        try:
            shutil.rmtree(path)
            return True
        except Exception as e:
            self.log_text.append(f"直接删除目录失败: {str(e)}")
        
        # 如果直接删除失败，尝试逐个删除文件
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            try:
                # 尝试删除所有文件和子目录
                failed_items = []
                for root, dirs, files in os.walk(path, topdown=False):
                    for name in files:
                        file_path = os.path.join(root, name)
                        try:
                            os.remove(file_path)
                        except Exception as file_e:
                            self.log_text.append(f"无法删除文件 {file_path}: {str(file_e)}")
                            failed_items.append(file_path)
                    
                    for name in dirs:
                        dir_path = os.path.join(root, name)
                        try:
                            os.rmdir(dir_path)
                        except Exception as dir_e:
                            self.log_text.append(f"无法删除目录 {dir_path}: {str(dir_e)}")
                            failed_items.append(dir_path)
                
                # 尝试删除根目录
                try:
                    os.rmdir(path)
                    self.log_text.append(f"成功清理目录 {path}")
                    return True
                except Exception as root_e:
                    if not failed_items:
                        self.log_text.append(f"成功删除所有文件，但无法删除根目录 {path}: {str(root_e)}")
                        return True
                    else:
                        self.log_text.append(f"无法删除根目录 {path}: {str(root_e)}")
                
                # 如果有失败的项目，增加重试次数
                if failed_items:
                    retry_count += 1
                    self.log_text.append(f"清理目录时遇到问题，{len(failed_items)} 个项目无法删除 (尝试 {retry_count}/{max_retries})")
                    if retry_count < max_retries:
                        # 等待一段时间再重试
                        time.sleep(0.5)
                else:
                    return True  # 成功删除所有内容
                    
            except Exception as e:
                retry_count += 1
                self.log_text.append(f"清理目录时遇到问题 (尝试 {retry_count}/{max_retries}): {str(e)}")
                if retry_count < max_retries:
                    # 等待一段时间再重试
                    time.sleep(0.5)
        
        # 如果所有方法都失败了，记录错误并返回False
        self.log_text.append(f"无法清理目录 {path}，请手动删除")
        return False

    def perform_phase_correction(self):
        """执行相位校正扫描"""
        try:
            import os
            import numpy as np
            from processing.data_saver import DataSaver
            
            # 重置相位映射状态，确保每次校正都是从干净状态开始
            try:
                from utils.phase_mapping import reset_phase_mapping
                reset_phase_mapping()
                self.log_text.append("已重置相位映射状态")
            except Exception as e:
                self.log_text.append(f"重置相位映射状态时出错: {e}")
            
            # 创建保存目录，先清空已存在的内容
            base_path = "./phaseCorrect"
            if os.path.exists(base_path):
                self.log_text.append("正在清理phaseCorrect文件夹...")
                if not self.safe_remove_directory(base_path):
                    self.log_text.append("警告：无法完全清理phaseCorrect文件夹，可能会遇到文件访问问题")
            
            x_path = os.path.join(base_path, "x")
            y_path = os.path.join(base_path, "y")
            
            os.makedirs(x_path, exist_ok=True)
            os.makedirs(y_path, exist_ok=True)
            
            # 获取当前相位值
            current_params = self.image_controls.get_current_params()
            current_x_phase = current_params.get('deltaphasex', 0.0)
            current_y_phase = current_params.get('deltaphasey', 0.0)
            
            self.log_text.append(f"当前相位值: X={current_x_phase}°, Y={current_y_phase}°")
            
            # 获取当前频率值
            freq_x = current_params.get('freqx', 1.0)
            freq_y = current_params.get('freqy', 1.0)
            
            # X相位扫描范围：从-5°到+5°，步长0.5°
            x_phases = np.arange(current_x_phase - 20.0, current_x_phase + 20.1, 0.1)
            # Y相位扫描范围：从-5°到+5°，步长0.5°
            y_phases = np.arange(current_y_phase - 20.0, current_y_phase + 20.1, 0.1)
            
            # 保存原始参数
            original_x_phase = self.image_controls.phase_x_input.text()
            original_y_phase = self.image_controls.phase_y_input.text()
            
            # 扫描X相位
            self.log_text.append("扫描X相位...")
            for i, phase in enumerate(x_phases):
                # 处理+0.0和-0.0的问题
                if abs(phase) < 1e-10:  # 如果相位接近0
                    phase = 0.0  # 统一设置为0.0
                
                # 设置参数
                self.image_controls.phase_x_input.setText(f"{phase:.1f}")
                self.image_controls.phase_y_input.setText(f"{current_y_phase:.1f}")
                
                # 应用参数
                self.image_controls.apply_parameters()
                
                # 等待参数生效，确保图像处理使用的是新参数
                QApplication.processEvents()
                import time
                time.sleep(0.2)  # 增加等待时间到200ms确保参数生效
                
                # 再次处理事件队列
                QApplication.processEvents()
                time.sleep(0.1)  # 额外等待100ms确保图像处理完成
                
                # 等待直到图像更新完成
                wait_count = 0
                max_wait = 30  # 最多等待1.5秒 (30 * 50ms)
                while wait_count < max_wait:
                    QApplication.processEvents()
                    time.sleep(0.05)
                    # 检查图像是否已经更新（通过检查参数是否匹配）
                    current_display_params = self.image_controls.get_current_params()
                    if abs(current_display_params.get('deltaphasex', 0) - phase) < 0.01:
                        break
                    wait_count += 1
                
                # 如果等待超时，记录警告
                if wait_count >= max_wait:
                    self.log_text.append(f"警告：等待X相位{phase:.1f}°图像更新超时")
                
                # 生成文件名（phase已经是绝对值，不需要再加current_x_phase）
                filename = f"x_phase_{phase:+.1f}_deg.tiff"
                filepath = os.path.join(x_path, filename)
                
                # 保存图像
                if self.image_controls.current_16bit_image is not None:
                    saver = DataSaver()
                    success = saver.save_image_data(self.image_controls.current_16bit_image, filepath, 'tiff')
                    if success:
                        self.log_text.append(f"保存X相位图像: {filename}")
                    else:
                        self.log_text.append(f"保存X相位图像失败: {filename}")
                else:
                    self.log_text.append(f"没有图像可保存: {filename}")
            
            # 扫描Y相位
            self.log_text.append("扫描Y相位...")
            for i, phase in enumerate(y_phases):
                # 处理+0.0和-0.0的问题
                if abs(phase) < 1e-10:  # 如果相位接近0
                    phase = 0.0  # 统一设置为0.0
                    
                # 设置参数
                self.image_controls.phase_x_input.setText(f"{current_x_phase:.1f}")
                self.image_controls.phase_y_input.setText(f"{phase:.1f}")
                
                # 应用参数
                self.image_controls.apply_parameters()
                
                # 等待参数生效，确保图像处理使用的是新参数
                QApplication.processEvents()
                import time
                time.sleep(0.2)  # 增加等待时间到200ms确保参数生效
                
                # 再次处理事件队列
                QApplication.processEvents()
                time.sleep(0.1)  # 额外等待100ms确保图像处理完成
                
                # 等待直到图像更新完成
                wait_count = 0
                max_wait = 30  # 最多等待1.5秒 (30 * 50ms)
                while wait_count < max_wait:
                    QApplication.processEvents()
                    time.sleep(0.05)
                    # 检查图像是否已经更新（通过检查参数是否匹配）
                    current_display_params = self.image_controls.get_current_params()
                    if abs(current_display_params.get('deltaphasey', 0) - phase) < 0.01:
                        break
                    wait_count += 1
                
                # 如果等待超时，记录警告
                if wait_count >= max_wait:
                    self.log_text.append(f"警告：等待Y相位{phase:.1f}°图像更新超时")
                
                # 生成文件名（phase已经是绝对值，不需要再加current_y_phase）
                filename = f"y_phase_{phase:+.1f}_deg.tiff"
                filepath = os.path.join(y_path, filename)
                
                # 保存图像
                if self.image_controls.current_16bit_image is not None:
                    saver = DataSaver()
                    success = saver.save_image_data(self.image_controls.current_16bit_image, filepath, 'tiff')
                    if success:
                        self.log_text.append(f"保存Y相位图像: {filename}")
                    else:
                        self.log_text.append(f"保存Y相位图像失败: {filename}")
                else:
                    self.log_text.append(f"没有图像可保存: {filename}")
            
            # 恢复原始参数
            self.image_controls.phase_x_input.setText(original_x_phase)
            self.image_controls.phase_y_input.setText(original_y_phase)
            self.image_controls.apply_parameters()
            
            self.log_text.append("相位校正扫描完成")
            
            # 分析频域特征并设置最佳相位点
            self.analyze_and_set_best_phases()
            
        except Exception as e:
            self.log_text.append(f"相位校正过程中出错: {e}")
            
    def analyze_and_set_best_phases(self):
        """分析频域特征并设置最佳相位点"""
        try:
            self.log_text.append("开始分析相位校正结果并寻找最佳相位点...")
            
            # 分析频域特征
            from utils.phase_correction_analyzer import analyze_phase_correction_results
            analyze_phase_correction_results()
            
            # 寻找最佳相位点
            best_x_phase, best_y_phase = self.find_best_phases()
            
            if best_x_phase is not None and best_y_phase is not None:
                # 设置最佳相位点
                self.image_controls.phase_x_input.setText(f"{best_x_phase:.1f}")
                self.image_controls.phase_y_input.setText(f"{best_y_phase:.1f}")
                self.image_controls.apply_parameters()
                self.log_text.append(f"已自动设置最佳相位点: X={best_x_phase:.1f}°, Y={best_y_phase:.1f}°")
            else:
                self.log_text.append("未能找到最佳相位点，使用原始相位值")
                
            self.log_text.append("频域特征分析完成，结果已保存到phaseCorrect文件夹下的x和y子文件夹中")
        except Exception as e:
            self.log_text.append(f"分析相位校正结果时出错: {e}")
            
    def update_sender_ip(self):
        """更新UDP发送器IP地址"""
        target_ip = self.ip_input.text().strip()
        # 更新协议控制组件中的UDP发送器
        if hasattr(self.protocol_controls, 'set_udp_sender'):
            self.protocol_controls.set_udp_sender(UDPSender(target_ip))
    
    def add_image_to_stack(self, image):
        """添加图像到堆栈"""
        if self.should_save_stack and image is not None:
            self.stack_images.append(image.copy())
            self.stack_counter += 1
            
            # 限制堆栈大小
            if len(self.stack_images) > self.max_stack_size:
                self.stack_images.pop(0)  # 移除最旧的图像
            
            # 更新堆栈状态显示
            self.processing_status.update_buffer_status(len(self.stack_images))
