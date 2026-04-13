"""
状态显示组件模块
包含字节计数、队列状态、帧率显示等状态信息组件
"""

import time
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import QTimer, pyqtSignal

class StatusWidget(QWidget):
    """状态信息显示组件"""
    
    def __init__(self, parent=None):
        """
        初始化状态显示组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        self.total_bytes = 0
        self.frame_times = []
        self.setup_ui()
        self.setup_timers()
    
    def setup_ui(self):
        """设置界面布局"""
        layout = QVBoxLayout()
        
        # 字节计数显示
        self.bytes_label = QLabel("已接收: 0 字节")
        self.bytes_label.setStyleSheet("font-size: 14px; color: blue;")
        layout.addWidget(self.bytes_label)
        
        # 队列状态显示
        self.queue_label = QLabel("队列状态: 0 包")
        self.queue_label.setStyleSheet("font-size: 14px; color: green;")
        layout.addWidget(self.queue_label)
        
        # 帧率显示
        self.fps_label = QLabel("重建帧率: 0 FPS")
        self.fps_label.setStyleSheet("font-size: 14px; color: green;")
        layout.addWidget(self.fps_label)
        
        self.setLayout(layout)
    
    def setup_timers(self):
        """设置定时器"""
        # 帧率更新定时器
        self.fps_update_timer = QTimer()
        self.fps_update_timer.timeout.connect(self.update_fps)
        self.fps_update_timer.start(1000)  # 每秒更新一次帧率
    
    def update_bytes_counter(self, data: bytes):
        """
        更新接收字节计数
        
        Args:
            data: 接收到的数据包
        """
        self.total_bytes += len(data)
        self.bytes_label.setText(f"已接收: {self.total_bytes:,} 字节")
    
    def reset_bytes_counter(self):
        """重置字节计数器"""
        self.total_bytes = 0
        self.bytes_label.setText("已接收: 0 字节")
    
    def update_queue_status(self, queue_size: int):
        """
        更新队列状态显示
        
        Args:
            queue_size: 当前队列大小
        """
        self.queue_label.setText(f"队列状态: {queue_size:,} 包")
        
        # 根据队列大小设置颜色
        if queue_size > 8000:
            color = "red"
        elif queue_size > 5000:
            color = "orange"
        else:
            color = "green"
        
        self.queue_label.setStyleSheet(f"font-size: 14px; color: {color};")
    
    def record_frame_time(self):
        """记录帧处理时间戳"""
        self.frame_times.append(time.time())
    
    def update_fps(self):
        """更新帧率显示"""
        # 清理超过1秒的时间戳
        current_time = time.time()
        self.frame_times = [t for t in self.frame_times if current_time - t <= 1.0]
        
        # 计算帧率
        fps = len(self.frame_times)
        self.fps_label.setText(f"重建帧率: {fps} FPS")
        
        # 根据帧率设置颜色
        if fps > 10:
            color = "green"
        elif fps > 5:
            color = "orange"
        else:
            color = "red"
        
        self.fps_label.setStyleSheet(f"font-size: 14px; color: {color};")
    
    def get_statistics(self) -> dict:
        """
        获取当前统计信息
        
        Returns:
            dict: 包含各种统计信息的字典
        """
        current_time = time.time()
        recent_frames = [t for t in self.frame_times if current_time - t <= 1.0]
        
        return {
            'total_bytes': self.total_bytes,
            'current_fps': len(recent_frames),
            'total_frames': len(self.frame_times)
        }
    
    def reset_all_counters(self):
        """重置所有计数器"""
        self.total_bytes = 0
        self.frame_times.clear()
        self.bytes_label.setText("已接收: 0 字节")
        self.fps_label.setText("重建帧率: 0 FPS")
    
    def stop_timers(self):
        """停止所有定时器"""
        if hasattr(self, 'fps_update_timer'):
            self.fps_update_timer.stop()

class NetworkStatusWidget(QWidget):
    """网络状态显示组件"""

    def __init__(self, parent=None):
        """
        初始化网络状态组件

        Args:
            parent: 父组件
        """
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """设置界面布局"""
        layout = QVBoxLayout()

        # 连接状态
        self.connection_label = QLabel("连接状态: 未连接")
        self.connection_label.setStyleSheet("font-size: 14px; color: red;")
        layout.addWidget(self.connection_label)

        # IP地址显示
        self.ip_label = QLabel("目标IP: 未设置")
        self.ip_label.setStyleSheet("font-size: 12px; color: gray;")
        layout.addWidget(self.ip_label)

        # 控制端口显示
        self.control_port_label = QLabel("控制端口: 未设置")
        self.control_port_label.setStyleSheet("font-size: 12px; color: gray;")
        layout.addWidget(self.control_port_label)

        # 数据端口显示
        self.data_port_label = QLabel("数据端口: 未设置")
        self.data_port_label.setStyleSheet("font-size: 12px; color: gray;")
        layout.addWidget(self.data_port_label)

        self.setLayout(layout)

    def update_connection_status(self, connected: bool):
        """
        更新连接状态

        Args:
            connected: 是否已连接
        """
        if connected:
            self.connection_label.setText("连接状态: 已连接")
            self.connection_label.setStyleSheet("font-size: 14px; color: green;")
        else:
            self.connection_label.setText("连接状态: 未连接")
            self.connection_label.setStyleSheet("font-size: 14px; color: red;")

    def update_target_info(self, ip: str, data_port: int, control_port: int = 0x8004):
        """
        更新目标信息

        Args:
            ip: 目标IP地址
            data_port: 数据接收端口 (8003)
            control_port: 控制命令端口 (0x8004)
        """
        self.ip_label.setText(f"目标IP: {ip}")
        self.control_port_label.setText(f"控制端口: {control_port} (0x{control_port:X})")
        self.data_port_label.setText(f"数据端口: {data_port}")

class ProcessingStatusWidget(QWidget):
    """处理状态显示组件"""
    
    def __init__(self, parent=None):
        """
        初始化处理状态组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        self.processing_count = 0
        self.setup_ui()
    
    def setup_ui(self):
        """设置界面布局"""
        layout = QVBoxLayout()
        
        # 处理状态
        self.processing_label = QLabel("处理状态: 空闲")
        self.processing_label.setStyleSheet("font-size: 14px; color: gray;")
        layout.addWidget(self.processing_label)
        
        # 处理计数
        self.count_label = QLabel("已处理: 0 帧")
        self.count_label.setStyleSheet("font-size: 12px; color: blue;")
        layout.addWidget(self.count_label)
        
        # 缓冲区状态
        self.buffer_label = QLabel("缓冲区: 0 帧")
        self.buffer_label.setStyleSheet("font-size: 12px; color: green;")
        layout.addWidget(self.buffer_label)
        
        self.setLayout(layout)
    
    def update_processing_status(self, status: str):
        """
        更新处理状态
        
        Args:
            status: 状态字符串 ("空闲", "处理中", "错误")
        """
        self.processing_label.setText(f"处理状态: {status}")
        
        if status == "处理中":
            color = "orange"
        elif status == "错误":
            color = "red"
        else:
            color = "gray"
        
        self.processing_label.setStyleSheet(f"font-size: 14px; color: {color};")
    
    def increment_processing_count(self):
        """增加处理计数"""
        self.processing_count += 1
        self.count_label.setText(f"已处理: {self.processing_count} 帧")
    
    def update_buffer_status(self, buffer_count: int):
        """
        更新缓冲区状态
        
        Args:
            buffer_count: 缓冲区中的帧数
        """
        self.buffer_label.setText(f"缓冲区: {buffer_count} 帧")
        
        # 根据缓冲区状态设置颜色
        if buffer_count > 5:
            color = "red"
        elif buffer_count > 2:
            color = "orange"
        else:
            color = "green"
        
        self.buffer_label.setStyleSheet(f"font-size: 12px; color: {color};")
    
    def reset_processing_count(self):
        """重置处理计数"""
        self.processing_count = 0
        self.count_label.setText("已处理: 0 帧")