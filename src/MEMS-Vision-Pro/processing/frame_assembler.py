"""
帧组装器模块
负责从全局队列中获取数据包并组装成完整帧（只支持新协议）
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
        处理数据包，按帧ID分组（只处理新协议）
        
        Args:
            packets: 数据包列表
        """
        current_time = time.time()
        
        for data in packets:
            if len(data) < 6:
                continue
                
            # 检查是否为新协议的帧头包
            if len(data) >= 2 and struct.unpack('>H', data[0:2])[0] == FRAME_HEADER_MAGIC:
                # 新协议帧头包
                self._process_new_frame_header(data, current_time)
            # 检查是否为新协议的数据包
            elif len(data) >= 2 and struct.unpack('>H', data[0:2])[0] == PACKET_HEADER_MAGIC:
                # 新协议数据包
                self._process_new_data_packet(data, current_time)

    def _process_new_frame_header(self, data, current_time):
        """
        处理新协议的帧头包

        Args:
            data: 帧头包数据
            current_time: 当前时间戳
        """
        if len(data) < 17:  # 最小长度：包头(2) + framecnt(2) + samplepoint(4) + phasex(4) + phasey(4) + 1字节ADC数据
            return

        # 解析帧头包
        # 包结构: 0x2AFF(2) + FrameCnt(2) + SamplePoint(4) + PhaseX(4) + PhaseY(4) + ADCData...
        frame_cnt = struct.unpack('>H', data[2:4])[0]  # 帧计数 (2字节)
        sample_point = struct.unpack('>I', data[4:8])[0]  # 采样点数 (4字节)
        phase_x = struct.unpack('>I', data[8:12])[0]  # X轴相位 (4字节)
        phase_y = struct.unpack('>I', data[12:16])[0]  # Y轴相位 (4字节)

        # 限制 sample_point 的最大值，防止异常数据
        if sample_point > 2000000:  # 最大2M采样点
            sample_point = 1000000  # 使用默认值

        # 创建帧缓冲区条目
        if frame_cnt not in self.frame_buffer:
            self.frame_buffer[frame_cnt] = {
                'packets': [],  # 存储所有数据包（包括帧头包）
                'timestamp': current_time,
                'sample_point': sample_point,
                'phase_x': phase_x,
                'phase_y': phase_y,
                'packets_dict': {},  # 用于按包序号存储数据包
                'received_data_bytes': 0,  # 已接收的数据字节数
                'max_pack_cnt': 1  # 帧头包是第1个包
            }

        # 存储帧头包和第一块ADC数据
        self.frame_buffer[frame_cnt]['packets_dict'][1] = data  # 帧头包作为包1
        self.frame_buffer[frame_cnt]['packets'].append(data)
        # 计算帧头包中的ADC数据字节数（从字节16开始到包末尾）
        if len(data) > 16:
            adc_data_len = len(data) - 16
            self.frame_buffer[frame_cnt]['received_data_bytes'] += adc_data_len

    def _process_new_data_packet(self, data, current_time):
        """
        处理新协议的数据包

        Args:
            data: 数据包
            current_time: 当前时间戳
        """
        if len(data) < 6:
            return

        # 解析数据包
        pack_cnt = struct.unpack('>H', data[2:4])[0]  # 包计数

        # 查找应该关联的帧
        # 策略：查找最可能的帧（基于时间戳和包序号）
        target_frame_cnt = None
        best_timestamp = 0

        # 首先检查这个包是否已存在于某帧中（去重）
        for frame_cnt, frame_data in self.frame_buffer.items():
            if 'packets_dict' in frame_data and pack_cnt in frame_data['packets_dict']:
                # 这个包已经存在，跳过
                return

        # 查找最合适的帧：优先选择最近创建的帧
        # 因为包通常是按顺序到达的，新包很可能属于最新创建的帧
        for frame_cnt, frame_data in self.frame_buffer.items():
            # 只有当这个包的序号不小于当前帧的最大包序号时，才考虑关联
            # 这样可以避免将高序号的包错误关联到旧帧
            max_pack = frame_data.get('max_pack_cnt', 1)
            if pack_cnt >= max_pack and frame_data['timestamp'] > best_timestamp:
                best_timestamp = frame_data['timestamp']
                target_frame_cnt = frame_cnt
            elif pack_cnt < max_pack and frame_data['timestamp'] > best_timestamp:
                # 包序号小于当前帧最大包序号，可能是迟到的包
                # 如果时间戳很新，也考虑关联
                if current_time - frame_data['timestamp'] < 0.1:  # 100ms内的帧
                    best_timestamp = frame_data['timestamp']
                    target_frame_cnt = frame_cnt

        if target_frame_cnt is not None and target_frame_cnt in self.frame_buffer:
            # 将数据包添加到对应帧的缓冲区
            if pack_cnt not in self.frame_buffer[target_frame_cnt]['packets_dict']:
                self.frame_buffer[target_frame_cnt]['packets_dict'][pack_cnt] = data
                self.frame_buffer[target_frame_cnt]['packets'].append(data)

                # 更新最大包计数
                if pack_cnt > self.frame_buffer[target_frame_cnt]['max_pack_cnt']:
                    self.frame_buffer[target_frame_cnt]['max_pack_cnt'] = pack_cnt

                # 计算数据包中的ADC数据字节数
                adc_data_len = 0
                if pack_cnt == 1:
                    # 帧头包，ADC数据从字节16开始
                    if len(data) > 16:
                        adc_data_len = len(data) - 16
                else:
                    # 数据包，ADC数据从字节4开始
                    if len(data) > 4:
                        adc_data_len = len(data) - 4

                self.frame_buffer[target_frame_cnt]['received_data_bytes'] += adc_data_len

    def process_frame_buffer(self):
        """处理帧缓冲区"""
        current_time = time.time()
        complete_frames = []
        frames_to_remove = []

        # 使用时间戳检查帧
        for frame_id, frame_data in self.frame_buffer.items():
            packets = frame_data['packets']
            timestamp = frame_data['timestamp']

            # 检查是否为新协议帧（包含sample_point信息）
            if 'sample_point' in frame_data:
                # 新协议帧处理逻辑
                received_data_bytes = frame_data.get('received_data_bytes', 0)
                sample_point = frame_data['sample_point']
                expected_data_bytes = sample_point * 2  # 期望的ADC数据字节数
                max_pack_cnt = frame_data.get('max_pack_cnt', 0)

                # 检查是否接收到了足够的数据
                if self._is_frame_complete(frame_data):
                    # 完整帧 - 按包序号排序
                    sorted_packets = []
                    packets_dict = frame_data.get('packets_dict', {})
                    # 按照包序号排序
                    for pack_cnt in sorted(packets_dict.keys()):
                        sorted_packets.append(packets_dict[pack_cnt])

                    complete_frames.append(sorted_packets)
                    frames_to_remove.append(frame_id)
                    self.log_message.emit(f"新协议帧 {frame_id} 组装完成: 接收{received_data_bytes}字节数据 (需要{expected_data_bytes}字节)")
                elif current_time - timestamp > self.frame_timeout:
                    # 超时的不完整帧
                    frames_to_remove.append(frame_id)
                    self.log_message.emit(f"新协议帧 {frame_id} 超时丢弃: 仅收到 {received_data_bytes} 字节，需要 {expected_data_bytes} 字节")

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

    def is_running(self):
        """检查是否正在运行"""
        return self._is_running and self.isRunning()

    def _is_frame_complete(self, frame_data):
        """
        检查帧是否完整，根据新协议规范

        Args:
            frame_data: 帧数据字典

        Returns:
            bool: 帧是否完整
        """
        received_data_bytes = frame_data.get('received_data_bytes', 0)
        sample_point = frame_data.get('sample_point', 0)
        max_pack_cnt = frame_data.get('max_pack_cnt', 0)

        # 期望的总ADC数据字节数
        expected_data_bytes = sample_point * 2

        # 需要至少有一个包
        if max_pack_cnt < 1:
            return False

        # 简化检查：如果接收到的数据字节数达到期望值的95%以上，认为帧完整
        # 这样可以容忍一些小的计算误差或丢包
        return received_data_bytes >= expected_data_bytes * 0.95
