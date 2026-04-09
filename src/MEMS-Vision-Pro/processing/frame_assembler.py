"""
帧组装器模块
负责从全局队列中获取数据包并组装成完整帧（只支持新协议）
以0x2AFF帧头标志位作为帧的分界，不基于字节数判断
"""

import os
import time
import struct
from PyQt5.QtCore import QThread, pyqtSignal
from utils.global_queue import get_multiple_packets, get_queue_size
from config.constants import FRAME_TIMEOUT, PROCESS_INTERVAL, INCOMPLETE_FRAME_DIR, FRAME_HEADER_MAGIC, PACKET_HEADER_MAGIC

class FrameAssembler(QThread):
    """
    独立线程处理队列中的包:
    1. 遇到0x2AFF帧头标志位时，开始新帧
    2. 遇到下一个0x2AFF时，当前帧结束，交给图像处理
    3. 不管中间丢失了多少包，实际有多少数据就处理多少
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
        self.frame_buffer_size = frame_buffer_size
        self.frame_buffer = {}
        self.current_frame = None  # 当前正在组装的帧
        self.current_frame_id = None
        self.process_interval = PROCESS_INTERVAL
        self.frame_timeout = FRAME_TIMEOUT
        self.last_process_time = time.time()
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
        max_packets = 2000 * 3  # 基于新协议的最大包数
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
        处理数据包，以0x2AFF帧头标志位作为帧的分界

        Args:
            packets: 数据包列表
        """
        current_time = time.time()

        for data in packets:
            if len(data) < 2:
                continue

            # 检查是否为新协议的帧头包 (0x2AFF)
            if struct.unpack('>H', data[0:2])[0] == FRAME_HEADER_MAGIC:
                # 新帧头到来：先完成上一帧，再开始新帧
                self._finalize_current_frame(current_time)
                self._start_new_frame(data, current_time)

            # 检查是否为新协议的数据包 (0x2CFF)
            elif struct.unpack('>H', data[0:2])[0] == PACKET_HEADER_MAGIC:
                # 数据包，添加到当前帧
                self._add_packet_to_current_frame(data)

    def _start_new_frame(self, data, current_time):
        """
        开始新帧

        Args:
            data: 帧头包数据
            current_time: 当前时间戳
        """
        if len(data) < 17:  # 最小长度检查
            return

        # 解析帧头包
        # 包结构: 0x2AFF(2) + FrameCnt(2) + SamplePoint(4) + PhaseX(4) + PhaseY(4) + ADCData...
        frame_cnt = struct.unpack('>H', data[2:4])[0]  # 帧计数 (2字节)
        sample_point = struct.unpack('<I', data[4:8])[0]  # 采样点数 (4字节)
        phase_x = struct.unpack('<I', data[8:12])[0]  # X轴相位 (4字节)
        phase_y = struct.unpack('<I', data[12:16])[0]  # Y轴相位 (4字节)

        # 限制 sample_point 的最大值，防止异常数据
        if sample_point > 2000000:
            sample_point = 1000000

        # 初始化当前帧
        self.current_frame_id = frame_cnt
        self.current_frame = {
            'packets': [],           # 所有数据包（按到达顺序）
            'timestamp': current_time,
            'sample_point': sample_point,
            'phase_x': phase_x,
            'phase_y': phase_y,
            'received_data_bytes': 0,
        }

        # 添加帧头包
        self.current_frame['packets'].append(data)
        # 计算帧头包中的ADC数据字节数（从字节16开始到包末尾）
        if len(data) > 16:
            adc_data_len = len(data) - 16
            self.current_frame['received_data_bytes'] += adc_data_len

    def _add_packet_to_current_frame(self, data):
        """
        添加数据包到当前帧

        Args:
            data: 数据包
        """
        if self.current_frame is None:
            # 没有当前帧，忽略这个包
            return

        if len(data) < 4:
            return

        # 添加包
        self.current_frame['packets'].append(data)

        # 计算数据包中的ADC数据字节数（从字节4开始）
        if len(data) > 4:
            adc_data_len = len(data) - 4
            self.current_frame['received_data_bytes'] += adc_data_len

    def _finalize_current_frame(self, current_time):
        """
        完成当前帧，将其放入缓冲区等待处理

        Args:
            current_time: 当前时间戳
        """
        if self.current_frame is None:
            return

        frame_id = self.current_frame_id

        # 将当前帧放入缓冲区
        self.frame_buffer[frame_id] = self.current_frame

        # 清空当前帧
        self.current_frame = None
        self.current_frame_id = None

    def process_frame_buffer(self):
        """处理帧缓冲区，发送完整的帧给图像处理"""
        current_time = time.time()
        frames_to_send = []
        frames_to_remove = []

        for frame_id, frame_data in self.frame_buffer.items():
            timestamp = frame_data['timestamp']
            received_data_bytes = frame_data.get('received_data_bytes', 0)
            sample_point = frame_data.get('sample_point', 0)
            expected_data_bytes = sample_point * 2

            # 立即发送所有已完成的帧（遇到新帧头就认为上一帧完成）
            frames_to_send.append((frame_id, frame_data))
            frames_to_remove.append(frame_id)

            # 记录日志
            completion_rate = (received_data_bytes / expected_data_bytes * 100) if expected_data_bytes > 0 else 0
            self.log_message.emit(f"帧 {frame_id} 完成: 接收{received_data_bytes}字节 ({completion_rate:.1f}%)")

        # 发送所有帧
        for frame_id, frame_data in frames_to_send:
            # 发送原始包列表和帧元数据
            self.frame_complete.emit(frame_data['packets'])

        # 清理已发送的帧
        for frame_id in frames_to_remove:
            del self.frame_buffer[frame_id]

        # 检查超时的当前帧（如果很久没有收到新帧头，强制完成当前帧）
        if self.current_frame is not None:
            age = current_time - self.current_frame['timestamp']
            if age > self.frame_timeout:
                received_data_bytes = self.current_frame.get('received_data_bytes', 0)
                sample_point = self.current_frame.get('sample_point', 0)
                expected_data_bytes = sample_point * 2
                completion_rate = (received_data_bytes / expected_data_bytes * 100) if expected_data_bytes > 0 else 0

                self.log_message.emit(f"帧 {self.current_frame_id} 超时完成: 接收{received_data_bytes}字节 ({completion_rate:.1f}%)")

                # 发送超时帧
                self.frame_complete.emit(self.current_frame['packets'])

                # 清空当前帧
                self.current_frame = None
                self.current_frame_id = None

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
        self.current_frame = None
        self.current_frame_id = None
        self.log_message.emit("帧缓冲区已清空")

    def is_running(self):
        """检查是否正在运行"""
        return self._is_running and self.isRunning()
