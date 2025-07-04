"""
主窗口模块
简化版主窗口，专注于协调各个功能模块
"""

import time
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QTextEdit, QFileDialog, QApplication,
    QScrollArea, QSplitter
)
from PyQt5.QtCore import pyqtSlot, QTimer, Qt

from config.constants import WINDOW_WIDTH, WINDOW_HEIGHT, MIN_LEFT_WIDTH, MIN_RIGHT_WIDTH, MAX_RIGHT_WIDTH
from config.default_params import DEFAULT_NETWORK_PARAMS, DEFAULT_UI_PARAMS
from ui.protocol_controls import ProtocolControlWidget
from ui.image_controls import ImageControlWidget
from ui.status_widgets import StatusWidget, NetworkStatusWidget, ProcessingStatusWidget
from network.udp_receiver import UDPReceiver
from network.udp_sender import UDPSender
from processing.frame_assembler import FrameAssembler
from processing.image_processor import ImageProcessor
from processing.data_saver import DataSaver
from utils.global_queue import clear_queue
from utils.numba_functions import warm_up_interpolation_function

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
        
        # 初始化对象引用
        self.udp_receiver = None
        self.assembler = None
        self.processors = []
        self.data_saver = DataSaver()
        
        # 应用状态
        self.should_save_frame = False
        
        # 多帧融合相关
        self.frame_buffer = []  # 存储待融合的帧
        self.max_buffer_size = 10
        
        # 延迟预编译Numba函数
        QTimer.singleShot(10, self.warm_up_numba_functions)
        
    def setup_window(self):
        """设置窗口基本属性"""
        self.setWindowTitle("UDP + FrameAssembler + ImageProcessor Demo - 模块化版本")
        self.resize(1400, 800)  # 增加窗口宽度以适应新布局
        self.setMinimumSize(1200, 600)  # 设置最小尺寸
        
    def setup_components(self):
        """设置各个组件"""
        # 创建各个控制组件
        self.protocol_controls = ProtocolControlWidget()
        self.image_controls = ImageControlWidget()
        self.status_widget = StatusWidget()
        self.network_status = NetworkStatusWidget()
        self.processing_status = ProcessingStatusWidget()
        
        # 创建日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        
    def setup_ui(self):
        """设置界面布局"""
        # 创建主分隔器
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧区域 - 图像控制和网络设置
        left_widget = self.create_left_panel()
        
        # 右侧区域 - 协议命令控制（添加滚动）
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setWidget(self.protocol_controls)
        right_scroll.setMinimumWidth(MIN_RIGHT_WIDTH)
        
        # 添加到分隔器
        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_scroll)
        
        # 设置分隔器比例
        main_splitter.setSizes([600, 800])
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(5)
        
        # 添加分隔器
        main_layout.addWidget(main_splitter, 1)  # 占主要空间
        
        # 控制按钮区域
        button_layout = self.create_control_buttons_layout()
        main_layout.addLayout(button_layout)
        
        # 日志区域
        log_label = QLabel("系统日志:")
        log_label.setMaximumHeight(20)
        main_layout.addWidget(log_label)
        main_layout.addWidget(self.log_text)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
    
    def create_left_panel(self):
        """创建左侧面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5)
        
        # 网络设置区域
        network_layout = self.create_network_settings_layout()
        left_layout.addLayout(network_layout)
        
        # 图像控制区域（添加滚动）
        image_scroll = QScrollArea()
        image_scroll.setWidgetResizable(True)
        image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        image_scroll.setWidget(self.image_controls)
        image_scroll.setMaximumHeight(600)  # 限制最大高度
        left_layout.addWidget(image_scroll)
        
        # 状态显示区域
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_widget)
        status_layout.addWidget(self.network_status)
        status_layout.addWidget(self.processing_status)
        left_layout.addLayout(status_layout)
        
        left_widget.setLayout(left_layout)
        left_widget.setMinimumWidth(MIN_LEFT_WIDTH)
        left_widget.setMaximumWidth(700)  # 限制最大宽度
        
        return left_widget
        
    def create_network_settings_layout(self):
        """创建网络设置布局"""
        # 使用水平布局，将所有设置放在一行
        layout = QHBoxLayout()
        layout.setSpacing(10)
        
        # IP设置
        layout.addWidget(QLabel("目标IP:"))
        self.ip_input = QLineEdit(DEFAULT_NETWORK_PARAMS['target_ip'])
        self.ip_input.setFixedWidth(120)
        self.ip_input.textChanged.connect(self.update_sender_ip)
        layout.addWidget(self.ip_input)
        
        # 帧缓存设置
        layout.addWidget(QLabel("帧缓存:"))
        self.frame_buffer_size_input = QLineEdit(str(DEFAULT_UI_PARAMS['frame_buffer_size']))
        self.frame_buffer_size_input.setFixedWidth(50)
        self.frame_buffer_size_input.textChanged.connect(self.validate_frame_buffer_size)
        layout.addWidget(self.frame_buffer_size_input)
        
        # 多帧融合开关
        self.enable_frame_fusion = QPushButton("多帧融合")
        self.enable_frame_fusion.setCheckable(True)
        self.enable_frame_fusion.setMaximumHeight(30)
        self.enable_frame_fusion.setMaximumWidth(100)
        self.enable_frame_fusion.clicked.connect(self.toggle_frame_fusion)
        layout.addWidget(self.enable_frame_fusion)
        
        # 添加状态指示
        self.fusion_status_label = QLabel("(关闭)")
        self.fusion_status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.fusion_status_label)
        
        # 添加弹性空间
        layout.addStretch()
        
        return layout
    
    def create_control_buttons_layout(self):
        """创建控制按钮布局"""
        layout = QHBoxLayout()
        layout.setSpacing(5)
        
        # 接收控制按钮
        self.start_receiver_button = QPushButton("启动接收")
        self.stop_receiver_button = QPushButton("停止接收")
        self.start_receiver_button.clicked.connect(self.start_receiver)
        self.stop_receiver_button.clicked.connect(self.stop_receiver)
        self.stop_receiver_button.setEnabled(False)
        
        # 设置按钮大小
        for btn in [self.start_receiver_button, self.stop_receiver_button]:
            btn.setMaximumHeight(35)
            btn.setMaximumWidth(80)
        
        layout.addWidget(self.start_receiver_button)
        layout.addWidget(self.stop_receiver_button)
        
        # 复位计数按钮
        self.reset_button = QPushButton("复位")
        self.reset_button.clicked.connect(self.reset_counters)
        self.reset_button.setMaximumHeight(35)
        self.reset_button.setMaximumWidth(60)
        layout.addWidget(self.reset_button)
        
        # 保存数据按钮
        self.save_button = QPushButton("保存数据")
        self.save_button.setCheckable(True)
        self.save_button.clicked.connect(self.toggle_save_data)
        self.save_button.setEnabled(False)
        self.save_button.setMaximumHeight(35)
        self.save_button.setMaximumWidth(80)
        layout.addWidget(self.save_button)
        
        # 保存帧按钮
        self.save_frame_button = QPushButton("保存帧")
        self.save_frame_button.setCheckable(True)
        self.save_frame_button.clicked.connect(self.toggle_save_frame)
        self.save_frame_button.setEnabled(False)
        self.save_frame_button.setMaximumHeight(35)
        self.save_frame_button.setMaximumWidth(70)
        layout.addWidget(self.save_frame_button)
        
        # 手动指令输入
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("手动指令(hex): AA 01 02 03")
        self.command_input.setFixedWidth(180)
        self.command_input.setMaximumHeight(35)
        layout.addWidget(self.command_input)
        
        self.send_command_button = QPushButton("发送")
        self.send_command_button.clicked.connect(self.send_manual_command)
        self.send_command_button.setMaximumHeight(35)
        self.send_command_button.setMaximumWidth(60)
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
        
        # 图像控制组件信号连接
        self.image_controls.image_params_changed.connect(self.on_image_params_changed)
        
        # 初始创建UDP发送器
        self.update_sender_ip()
        
    def setup_timers(self):
        """设置定时器"""
        pass
    
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
                self.log_text.append(f"融合图像显示完成。最终相位: X={phasex_deg:.1f}°, Y={phasey_deg:.1f}°")
            
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
        
        self.log_text.append(f"图像处理完成。相位: X={phasex_deg:.1f}°, Y={phasey_deg:.1f}°")

    def on_image_params_changed(self, params):
        """处理图像参数变化"""
        self.log_text.append(f"参数已更新: X相位={params['deltaphasex']}°, Y相位={params['deltaphasey']}°, X频率={params['freqx']}, Y频率={params['freqy']}")

    def update_sender_ip(self):
        """更新UDP发送器IP地址"""
        target_ip = self.ip_input.text().strip()
        if target_ip:
            udp_sender = UDPSender(target_ip, 8003)
            self.protocol_controls.set_udp_sender(udp_sender)
            self.send_command_button.setEnabled(True)
        else:
            self.send_command_button.setEnabled(False)

    def reset_counters(self):
        """复位所有计数器"""
        self.status_widget.reset_all_counters()
        self.processing_status.reset_processing_count()
        self.log_text.append("所有计数器已复位")

    def toggle_save_data(self):
        """切换数据保存状态"""
        if not self.udp_receiver:
            self.save_button.setChecked(False)
            return

        if self.save_button.isChecked():
            # 选择保存文件
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "选择保存位置",
                "",
                "二进制数据文件 (*.bin);;所有文件 (*.*)"
            )
            
            if filename:
                if not filename.endswith('.bin'):
                    filename += '.bin'
                self.udp_receiver.start_saving(filename)
                self.save_button.setText("停止保存")
            else:
                self.save_button.setChecked(False)
        else:
            self.udp_receiver.stop_saving()
            self.save_button.setText("开始保存原始数据")

    def toggle_save_frame(self):
        """切换保存帧状态"""
        self.should_save_frame = self.save_frame_button.isChecked()
        if self.should_save_frame:
            self.log_text.append("保存帧功能已激活")
        else:
            self.log_text.append("保存帧功能已停用")

    def send_manual_command(self):
        """发送手动输入的命令"""
        try:
            hex_str = self.command_input.text().strip()
            hex_str = hex_str.replace(" ", "")
            
            # 验证十六进制字符串
            if not all(c in '0123456789ABCDEFabcdef' for c in hex_str):
                self.log_text.append("错误：请输入有效的十六进制字符串")
                return
                
            if len(hex_str) % 2 != 0:
                self.log_text.append("错误：十六进制字符串长度必须为偶数")
                return
                
            # 获取UDP发送器
            udp_sender = self.protocol_controls.udp_sender
            if not udp_sender:
                self.log_text.append("错误：UDP发送器未设置")
                return
                
            # 转换为字节数组并发送
            command = bytes.fromhex(hex_str)
            success, bytes_sent = udp_sender.send_command(command)
            
            if success:
                self.log_text.append(f"已发送手动指令：{command.hex(' ').upper()} ({bytes_sent} 字节)")
            else:
                self.log_text.append("发送手动指令失败")
                
        except ValueError:
            self.log_text.append("错误：无效的十六进制格式")
        except Exception as e:
            self.log_text.append(f"发送手动指令出错：{str(e)}")

    def warm_up_numba_functions(self):
        """预编译Numba函数"""
        self.log_text.append("正在预编译优化函数，请稍候...")
        QApplication.processEvents()
        
        try:
            self.log_text.append("  - 编译插值函数...")
            QApplication.processEvents()
            
            elapsed_time = warm_up_interpolation_function()
            self.log_text.append(f"    完成! (耗时: {elapsed_time:.2f}秒)")
            QApplication.processEvents()
            self.log_text.append("程序现在将以正常速度运行")
        except Exception as e:
            self.log_text.append(f"预编译过程中出错: {e}")
        
        QApplication.processEvents()

    def closeEvent(self, event):
        """窗口关闭时的清理工作"""
        # 停止所有定时器
        if hasattr(self.status_widget, 'stop_timers'):
            self.status_widget.stop_timers()
        
        # 停止接收器
        self.stop_receiver()
        
        # 停止数据保存
        if hasattr(self.data_saver, 'stop_saving'):
            self.data_saver.stop_saving()
        
        super().closeEvent(event)