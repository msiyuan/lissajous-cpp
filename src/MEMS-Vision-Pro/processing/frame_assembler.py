"""
帧组装器模块
负责从全局队列中获取数据包并组装成完整帧
"""

import os
import time
from PyQt5.QtCore import QThread, pyqtSignal
from utils.global_queue import get_multiple_packets, get_queue_size
from config.constants import PACKETS_PER_FRAME, FRAME_TIMEOUT, PROCESS_INTERVAL, INCOMPLETE_FRAME_DIR

class FrameAssembler(QThread):
    """
    独立线程处理队列中的包:
    1. 维护一个帧缓冲区，存储最近的N帧
    2. 通过帧号和包号重组完整帧
    3. 当累积足够的完整帧后进行处理
    """
    frame_complete = pyqtSignal(list)  # 发送单帧
    frames_complete = pyqtSignal(list)  # 发送多帧数据
    log_message = pyqtSignal(str)
    queue_status = pyqtSignal(int)

    def __init__(self, parent=None, frame_buffer_size=10):
        """
        初始化帧组装器
        
        Args:
            parent: 父对象
            frame_buffer_size: 帧缓冲区大小
        """
        super().__init__(parent)
        self.packets_per_frame = PACKETS_PER_FRAME
        self.frame_buffer_size = frame_buffer_size
        self.frame_buffer = {}
        self.process_interval = PROCESS_INTERVAL
        self.frame_timeout = FRAME_TIMEOUT
        self.last_process_time = time.time()
        self.complete_frames = []  # 存储完整帧
        self._is_running = True
        self.incomplete_frame_dir = INCOMPLETE_FRAME_DIR
        
        # 创建不完整帧保存目录
        if not os.path.exists(self.incomplete_frame_dir):
            os.makedirs(self.incomplete_frame_dir)

    def run(self):
        """主运行循环"""
        self.log_message.emit("FrameAssembler thread started.")
        
        while self._is_running:
            try:
                self._process_queue_packets()
                time.sleep(0.0005)  # 减少等待时间
            except Exception as e:
                self.log_message.emit(f"处理出错: {e}")
                time.sleep(0.0005)

    def _process_queue_packets(self):
        """处理队列中的数据包"""
        # 监控队列大小
        current_queue_size = get_queue_size()
        if current_queue_size > 5000:  # 如果队列过大，发出警告
            self.log_message.emit(f"警告：队列积累过多，当前大小：{current_queue_size}")
        
        # 批量获取数据包
        max_packets = self.packets_per_frame * 3
        packets = get_multiple_packets(max_packets)
        
        if packets:
            self.process_packets(packets)
            # 立即检查是否有完整帧
            current_time = time.time()
            if current_time - self.last_process_time >= self.process_interval:
                self.process_frame_buffer()
                self.last_process_time = current_time

    def process_packets(self, packets):
        """
        处理数据包，按帧ID分组
        
        Args:
            packets: 数据包列表
        """
        current_time = time.time()
        
        for data in packets:
            if len(data) < 6:
                continue
                
            frame_id = data[2]
            
            if frame_id not in self.frame_buffer:
                self.frame_buffer[frame_id] = {
                    'packets': [],
                    'timestamp': current_time
                }
            self.frame_buffer[frame_id]['packets'].append(data)

    def save_incomplete_frame(self, frame_id, packets):
        """
        保存不完整的帧
        
        Args:
            frame_id: 帧ID
            packets: 数据包列表
        """
        if not packets:
            return

        timestamp = int(time.time() * 1000)
        filename = os.path.join(self.incomplete_frame_dir, f"incomplete_frame_{frame_id}_{timestamp}.bin")
        
        try:
            with open(filename, 'wb') as f:
                for packet in packets:
                    f.write(packet)
            self.log_message.emit(f"不完整帧 {frame_id} 已保存到: {filename}")
        except Exception as e:
            self.log_message.emit(f"保存不完整帧 {frame_id} 失败: {e}")

    def process_frame_buffer(self):
        """处理帧缓冲区"""
        current_time = time.time()
        complete_frames = []
        frames_to_remove = []

        # 使用时间戳检查帧
        for frame_id, frame_data in self.frame_buffer.items():
            packets = frame_data['packets']
            timestamp = frame_data['timestamp']
            
            if len(packets) >= self.packets_per_frame:
                # 完整帧
                complete_frames.append(packets)
                frames_to_remove.append(frame_id)
                # 添加完整帧的打印信息
                # self.log_message.emit(f"帧 {frame_id} 组装完成: {len(packets)} 包 (需要{self.packets_per_frame}包)")
            elif current_time - timestamp > self.frame_timeout:
                # 超时的不完整帧
                # self.save_incomplete_frame(frame_id, packets)
                frames_to_remove.append(frame_id)
                # 添加不完整帧的打印信息
                self.log_message.emit(f"帧 {frame_id} 超时丢弃: 仅收到 {len(packets)} 包，缺少 {self.packets_per_frame - len(packets)} 包")

        # 处理完整帧
        if complete_frames:
            self.frame_complete.emit(complete_frames[0])  # 优先处理最新的完整帧
            
        # 清理帧缓冲区
        for frame_id in frames_to_remove:
            del self.frame_buffer[frame_id]

        # 发送当前队列状态
        current_queue_size = get_queue_size()
        self.queue_status.emit(current_queue_size)

    def stop(self):
        """停止帧组装器"""
        self._is_running = False
        self.wait()

    def get_buffer_status(self):
        """
        获取当前缓冲区状态
        
        Returns:
            dict: 包含缓冲区状态信息的字典
        """
        buffer_status = {}
        for frame_id, frame_data in self.frame_buffer.items():
            buffer_status[frame_id] = {
                'packet_count': len(frame_data['packets']),
                'age': time.time() - frame_data['timestamp']
            }
        return buffer_status

    def clear_buffer(self):
        """清空帧缓冲区"""
        self.frame_buffer.clear()
        self.log_message.emit("帧缓冲区已清空")

    def set_packets_per_frame(self, packets_per_frame):
        """
        设置每帧包数
        
        Args:
            packets_per_frame: 每帧的数据包数量
        """
        self.packets_per_frame = packets_per_frame
        self.log_message.emit(f"每帧包数已设置为: {packets_per_frame}")

    def is_running(self):
        """检查是否正在运行"""
        return self._is_running and self.isRunning()