import sys
import time
import socket
import math
import struct
import numba
import numpy as np
import cv2
from typing import Optional

from PyQt5.QtCore import (
    Qt, QThread, QObject, pyqtSignal, pyqtSlot, QMutex, QMutexLocker, QTimer
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QTextEdit,
    QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLineEdit, QFileDialog,
    QSlider
)
from queue import Queue, Empty, Full

########################
# 1) UDPReceiver
########################
# 全局队列和锁
packet_queue = Queue(maxsize=100000)  # 可以存储约70帧的数据
queue_mutex = QMutex()

class UDPReceiver(QThread):
    """只负责网络接收，将包放入全局队列"""
    packet_received = pyqtSignal(bytes)  # 用于更新计数器
    log_message = pyqtSignal(str)

    def __init__(self, target_ip, recv_port, parent=None):
        super().__init__(parent)
        self.target_ip = target_ip    # 目标IP（下位机IP）
        self.recv_port = recv_port    # 接收端口（8003）
        self._is_running = True
        self.save_data = False
        self.save_file = None
        self.sock = None  # 添加socket引用

    def start_saving(self, filename):
        """开始保存数据"""
        try:
            self.save_file = open(filename, 'wb')
            self.save_data = True
            self.log_message.emit(f"开始保存原始数据到: {filename}")
        except Exception as e:
            self.log_message.emit(f"创建保存文件失败: {e}")
            self.save_data = False

    def stop_saving(self):
        """停止保存数据"""
        if self.save_file:
            self.save_file.close()
            self.save_file = None
        self.save_data = False
        self.log_message.emit("停止保存原始数据")

    def run(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024 * 10)
            # 添加端口重用选项
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(('', self.recv_port))
            self.log_message.emit(f"UDP Receiver started on port {self.recv_port}")
        except Exception as e:
            self.log_message.emit(f"Failed to bind socket: {e}")
            return

        while self._is_running:
            try:
                data, _ = self.sock.recvfrom(65535)
                # 保存原始数据
                if self.save_data and self.save_file:
                    # 写入包长度和包数据
                    length = len(data)
                    self.save_file.write(length.to_bytes(4, 'big'))
                    self.save_file.write(data)
                    self.save_file.flush()

                # 将数据放入全局队列
                with QMutexLocker(queue_mutex):
                    try:
                        packet_queue.put(data, block=False)
                        self.packet_received.emit(data)
                    except Full:
                        self.log_message.emit("警告：队列已满，丢弃新包")
            except Exception as e:
                self.log_message.emit(f"Error receiving UDP packets: {e}")
                time.sleep(0.001)

        self.stop_saving()  # 确保关闭保存文件
        self.log_message.emit("UDP Receiver stopped.")

    def stop(self):
        self._is_running = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.sock.close()
            self.sock = None
        self.stop_saving()
        self.wait()


########################
# 2) FrameAssembler
########################
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
        super().__init__(parent)
        self.packets_per_frame = 1429
        self.frame_buffer_size = frame_buffer_size
        self.frame_buffer = {}
        self.process_interval = 0.02  # 减少到20ms
        self.frame_timeout = 0.5  # 帧超时时间（秒）
        self.last_process_time = time.time()
        self.complete_frames = []  # 存储完整帧
        self._is_running = True

    def run(self):
        self.log_message.emit("FrameAssembler thread started.")
        
        while self._is_running:
            try:
                # 监控队列大小
                with QMutexLocker(queue_mutex):
                    current_queue_size = packet_queue.qsize()
                    if current_queue_size > 5000:  # 如果队列过大，发出警告
                        self.log_message.emit(f"警告：队列积累过多，当前大小：{current_queue_size}")
                
                packets = []
                start_time = time.time()
                with QMutexLocker(queue_mutex):
                    while not packet_queue.empty() and len(packets) < self.packets_per_frame * 2:
                        data = packet_queue.get_nowait()
                        packets.append(data)   
                end_time = time.time()
                # print(f"获取数据时间: {end_time - start_time} 秒")       # 取包时间约0.001秒
                if packets:
                    self.process_packets(packets)
                    # 立即检查是否有完整帧
                    current_time = time.time()
                    if current_time - self.last_process_time >= self.process_interval:
                        self.process_frame_buffer()
                        self.last_process_time = current_time
                else:
                    time.sleep(0.0005)  # 减少等待时间
                    
            except Exception as e:
                self.log_message.emit(f"处理出错: {e}")
                time.sleep(0.0005)

    def process_packets(self, packets):
        """改进的数据包处理"""
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

    def process_frame_buffer(self):
        """改进的帧缓冲区处理"""
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
            elif current_time - timestamp > self.frame_timeout:
                # 超时的不完整帧
                frames_to_remove.append(frame_id)

        # 处理完整帧
        if complete_frames:
            self.frame_complete.emit(complete_frames[0])  # 优先处理最新的完整帧
            
        # 清理帧缓冲区
        for frame_id in frames_to_remove:
            del self.frame_buffer[frame_id]

        # 发送当前队列状态
        with QMutexLocker(queue_mutex):
            current_queue_size = packet_queue.qsize()
        self.queue_status.emit(current_queue_size)

    def stop(self):
        self._is_running = False
        self.wait()

@numba.njit(cache=True) # 使用 njit 以获得最佳性能，启用缓存
def _interpolate_columns_numba(image_data, nan_mask):
    """
    使用 Numba 优化的垂直插值函数。
    为每一列中的 NaN 值插值。
    
    Args:
        image_data (np.ndarray): 包含 NaN 值的图像数据
        nan_mask (np.ndarray): 布尔掩码，标记 NaN 位置
        
    Returns:
        np.ndarray: 插值后的图像
    """
    # 获取图像维度
    rows, cols = image_data.shape
    # 创建行索引数组
    row_indices = np.arange(rows)
    # 创建输出数组的副本
    result = image_data.copy()
    
    # 逐列处理
    for col in range(cols):
        # 获取当前列的掩码
        col_mask = nan_mask[:, col]
        
        # 检查列中是否既有 NaN 值又有有效值
        if np.any(col_mask) and not np.all(col_mask):
            # 获取有效点的位置和值
            valid_rows = row_indices[~col_mask]
            valid_values = image_data[valid_rows, col]
            
            # 获取 NaN 位置
            nan_rows = row_indices[col_mask]
            
            # 确保有足够的有效点进行插值
            if len(valid_rows) > 1 and len(nan_rows) > 0:
                # 一次性计算所有插值点
                interpolated_values = np.interp(nan_rows, valid_rows, valid_values)
                # 更新结果数组
                result[nan_rows, col] = interpolated_values
    
    return result

########################
# 3) ImageProcessor
########################
class ImageProcessor(QThread):
    """
    Worker thread for a single image processing run.
    """
    # 发射: (final_image, phasex_deg, phasey_deg)
    image_processed = pyqtSignal(np.ndarray, float, float)

    def __init__(self, packets, deltaphasex, deltaphasey, freqx, freqy, parent=None):
        super().__init__(parent)
        self.packets = packets
        self.deltaphasex = deltaphasex
        self.deltaphasey = deltaphasey
        self.freqx = freqx
        self.freqy = freqy
        self._is_running = True

    def run(self):
        if not self._is_running or not self.packets:
            return
        start_time = time.time()
        final_image, phasex_deg, phasey_deg = self.process_single_frame_one_freq(
            packets=self.packets,
            SampleRate=1e7,
            Freqx=self.freqx,
            Freqy=self.freqy,
            deltaphasex=self.deltaphasex,
            deltaphasey=self.deltaphasey
        )
        end_time = time.time()
        print(f"处理时间: {end_time - start_time} 秒")
        self.image_processed.emit(final_image, phasex_deg, phasey_deg)

    def stop(self):
        self._is_running = False
    
    def process_single_frame_one_freq(
        self,
        packets,
        SampleRate,
        Freqx,
        Freqy,
        deltaphasex,
        deltaphasey,
    ):
        """
        与原先逻辑相同: 解析packets并生成 final_image.
        这里保留原有相位计算，但不再遍历多种相位，也不在 UI 端调节。
        """
        # start_time = time.time()
        NumFrame = int(1e6)          # 每帧的采样点数
        ImageSize = 512              # 图像大小为 512 x 512
        Delta_t = 1.0 / SampleRate   # 每个采样点之间的时间间隔

        X_Amp = ImageSize / 2.0      # X 方向扫描振幅
        Y_Amp = ImageSize / 2.0      # Y 方向扫描振幅

        X_Freq = math.pi * Delta_t * 2 * Freqx  # 等价于 2π(SampleRate^-1)*Freqx
        Y_Freq = math.pi * Delta_t * 2 * Freqy
        PixelData = np.zeros((ImageSize, ImageSize), dtype=np.int64)

        first_packet = packets[0]

        # --- 相位计算部分，保持原样 ---
        phase_x_raw = struct.unpack('>I', first_packet[6:10])[0]
        phase_y_raw = struct.unpack('>I', first_packet[10:14])[0]

        # 假设 map_delta_phasex 和 map_delta_phasey 已经定义
        phasex_compensation=map_delta_phasex(phase_x_raw * 360.0 / 33554432.0)
        phasey_compensation=map_delta_phasey(phase_y_raw * 360.0 / 33554432.0)

        randn_phasex = np.random.randn() * 1
        randn_phasey = np.random.randn() * 1

        phasex_deg = (phase_x_raw * 360.0 / 33554432.0) + phasex_compensation + randn_phasex
        phasey_deg = (phase_y_raw * 360.0 / 33554432.0) + phasey_compensation + randn_phasey
        

        phasex = math.radians(round(phasex_deg * 1000) / 1000)
        phasey = math.radians(round(phasey_deg * 1000) / 1000)
        i_arr = np.arange(NumFrame, dtype=np.float64)  # [0, 1, 2, ..., 999999]

        
        

        # 计算扫描轨迹：X_vals, Y_vals
        X_vals = X_Amp * np.sin(X_Freq * i_arr + phasex) + 256.0
        Y_vals = Y_Amp * np.sin(Y_Freq * i_arr + phasey) + 256.0
        

        X_vals = np.floor(X_vals).astype(np.int32)
        Y_vals = np.floor(Y_vals).astype(np.int32)

        np.clip(X_vals, 0, ImageSize - 1, out=X_vals)
        np.clip(Y_vals, 0, ImageSize - 1, out=Y_vals)

        
        XY_linear_indices = X_vals * ImageSize + Y_vals

        PixelTimes_flat = np.bincount(
            XY_linear_indices,
            minlength=ImageSize * ImageSize
        )
        PixelTimes = PixelTimes_flat.reshape((ImageSize, ImageSize))

        PixelDataFlat = np.zeros(ImageSize * ImageSize, dtype=np.int64)
        
        # --- 优化：批量提取 Payload ---
        all_payload_bytes = []
        if packets:
            # 处理第一个数据包 (header 偏移不同)
            first_packet = packets[0]
            # 检查包长是否足够包含 packageNum
            if len(first_packet) >= 6:
                packageNum_first = (first_packet[4] << 8) + first_packet[5]
                flag_first = 14
                # 确保不超出数据包长度
                payload_end_first = min(flag_first + packageNum_first, len(first_packet))
                if payload_end_first > flag_first: # 确保有 payload
                    all_payload_bytes.append(first_packet[flag_first:payload_end_first])
            
            # 处理后续数据包
            for pkt in packets[1:]:
                # 检查包长是否足够包含 packageNum
                if len(pkt) >= 6:
                    packageNum_pkt = (pkt[4] << 8) + pkt[5]
                    flag_pkt = 6
                    # 确保不超出数据包长度
                    payload_end_pkt = min(flag_pkt + packageNum_pkt, len(pkt))
                    if payload_end_pkt > flag_pkt: # 确保有 payload
                        all_payload_bytes.append(pkt[flag_pkt:payload_end_pkt])
        
        # --- 优化：向量化字节解析 ---
        gray_values_arr = np.array([], dtype=np.int64) # 初始化空数组
        if all_payload_bytes:
            concatenated_bytes = b''.join(all_payload_bytes)
            
            if concatenated_bytes:
                # 确保字节长度是偶数
                if len(concatenated_bytes) % 2 != 0:
                    print("警告: 连接后的 payload 字节长度为奇数，将截断最后一个字节。")
                    concatenated_bytes = concatenated_bytes[:-1]
                    
                if concatenated_bytes: # 再次检查，可能截断后为空
                    # 使用 numpy.frombuffer 和 view 进行解析
                    concatenated_np_bytes = np.frombuffer(concatenated_bytes, dtype=np.uint8)
                    # >H 表示大端无符号16位整数
                    gray_values_arr = concatenated_np_bytes.view(dtype='>H').astype(np.int64)
        
        # --- 优化：使用 NumPy bincount 累加 ---
        total_data_points = len(gray_values_arr)
        num_indices_to_use = min(total_data_points, NumFrame)
        
        if num_indices_to_use > 0:
            # 生成需要使用的索引 (0 到 num_indices_to_use - 1)
            pixel_indices_arr = np.arange(num_indices_to_use, dtype=np.int64)
            
            # 获取对应的灰度值
            gray_values_to_use = gray_values_arr[:num_indices_to_use]
            
            # 使用这些索引从 XY_linear_indices 中查找到对应的图像平面线性索引
            final_pixel_linear_indices = XY_linear_indices[pixel_indices_arr]
            
            # 使用 np.bincount 加权累加灰度值
            accum = np.bincount(
                final_pixel_linear_indices,
                weights=gray_values_to_use, # 使用灰度值作为权重
                minlength=ImageSize * ImageSize
            ).astype(np.int64)
            
            # 将累加结果赋值给 PixelDataFlat
            PixelDataFlat = accum

        PixelData = PixelDataFlat.reshape((ImageSize, ImageSize))

        
        with np.errstate(divide='ignore', invalid='ignore'):
            final_image = PixelData / PixelTimes
        
        # --- 高效向量化垂直插值 ---
        start_interp_time = time.time() # 开始计时
        # 创建一个掩码，标记 NaN 值
        nan_mask = np.isnan(final_image)
        
        # 使用 Numba JIT 编译的函数进行插值
        interpolated_image = _interpolate_columns_numba(final_image, nan_mask)
        
        # 将剩余的NaN填充为0
        interpolated_image = np.nan_to_num(interpolated_image, nan=0.0)

        end_interp_time = time.time() # 结束计时
        interpolation_duration = end_interp_time - start_interp_time
        print(f"插值耗时: {interpolation_duration:.6f} 秒") # 打印插值时间

        return interpolated_image, phasex_deg, phasey_deg
    

    def save_frame_to_bin(self):
        """保存初始化时的packets为bin文件"""
        timestamp = int(time.time() * 1000)  # 获取当前时间戳（毫秒）
        filename = f"frame_{timestamp}.bin"
        try:
            with open(filename, 'wb') as f:
                for packet in self.packets:
                    f.write(packet)
            print(f"帧已保存为: {filename}")
        except Exception as e:
            print(f"保存帧失败: {e}")

########################
# 新增 UDPSender 类
########################
class UDPSender:
    """UDP发送类，用于发送控制指令到下位机"""
    def __init__(self, target_ip: str, target_port: int):
        self.target_ip = target_ip
        self.target_port = target_port

    def send_command(self, command: bytes) -> tuple[bool, int]:
        """
        发送命令到下位机
        返回: (是否成功, 发送的字节数)
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 绑定到本地8003端口发送
            sock.bind(('', 8003))
            bytes_sent = sock.sendto(command, (self.target_ip, self.target_port))
            sock.close()
            return True, bytes_sent
        except Exception as e:
            return False, 0

########################
# 4) MainWindow
########################
def convert_to_8bit_cv2(final_image):
    """
    将图像归一化到0-255并转为8位
    """
    normalized_image = cv2.normalize(final_image, None, 0, 255, cv2.NORM_MINMAX)
    return np.uint8(normalized_image)

def binary_threshold_by_mode(final_image):
    """
    对最常见非零像素做阈值二值化
    """
    unique, counts = np.unique(final_image[final_image > 0], return_counts=True)
    if len(unique) == 0:
        most_frequent_value = 0
    else:
        most_frequent_value = unique[np.argmax(counts)]
    binary_image = np.where(final_image > most_frequent_value, 255, 0)
    return np.uint8(binary_image)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UDP + FrameAssembler + ImageProcessor Demo")
        self.resize(900, 600)

        # UI
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.image_label = QLabel("等待图像")
        self.image_label.setFixedSize(512, 512)
        self.image_label.setStyleSheet("background-color: black;")

        # 添加字节计数显示
        self.bytes_label = QLabel("已接收: 0 字节")
        self.bytes_label.setStyleSheet("font-size: 14px; color: blue;")
        self.total_bytes = 0

        # 添加队列状态显示标签
        self.queue_label = QLabel("队列状态: 0 包")
        self.queue_label.setStyleSheet("font-size: 14px; color: green;")

        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 只保留接收控制按钮
        self.start_receiver_button = QPushButton("启动接收")
        self.stop_receiver_button = QPushButton("停止接收")
        self.start_receiver_button.clicked.connect(self.start_receiver)
        self.stop_receiver_button.clicked.connect(self.stop_receiver)
        self.stop_receiver_button.setEnabled(False)

        # 添加复位计数按钮
        self.reset_button = QPushButton("复位计数")
        self.reset_button.clicked.connect(self.reset_counter)

        # 添加保存数据按钮
        self.save_button = QPushButton("开始保存原始数据")
        self.save_button.setCheckable(True)  # 可切换的按钮
        self.save_button.clicked.connect(self.toggle_save_data)
        self.save_button.setEnabled(False)  # 初始时禁用
        
        # 添加保存帧按钮
        self.save_frame_button = QPushButton("保存帧")
        self.save_frame_button.setCheckable(True)  # 可切换的按钮
        self.save_frame_button.clicked.connect(self.toggle_save_frame)
        self.save_frame_button.setEnabled(False)  # 初始时禁用
        
        button_layout.addWidget(self.start_receiver_button)
        button_layout.addWidget(self.stop_receiver_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.save_frame_button)

        # 添加IP和端口设置
        settings_layout = QHBoxLayout()
        
        # IP输入框
        self.ip_label = QLabel("IP:")
        self.ip_input = QLineEdit("192.168.1.91")
        self.ip_input.setFixedWidth(120)
        
        settings_layout.addWidget(self.ip_label)
        settings_layout.addWidget(self.ip_input)
        settings_layout.addStretch()

        # 添加相位和频率设置
        phase_freq_layout = QHBoxLayout()
        
        # X相位设置
        self.phase_x_label = QLabel("X相位:")
        self.phase_x_input = QLineEdit("0.0")
        self.phase_x_input.setFixedWidth(60)
        
        # Y相位设置
        self.phase_y_label = QLabel("Y相位:")
        self.phase_y_input = QLineEdit("0.0")
        self.phase_y_input.setFixedWidth(60)
        
        # X频率设置
        self.freq_x_label = QLabel("X频率:")
        self.freq_x_input = QLineEdit("11390")
        self.freq_x_input.setFixedWidth(60)
        
        # Y频率设置
        self.freq_y_label = QLabel("Y频率:")
        self.freq_y_input = QLineEdit("3790")
        self.freq_y_input.setFixedWidth(60)
        
        # 在phase_freq_layout中添加"应用参数"按钮
        self.apply_params_button = QPushButton("应用参数")
        self.apply_params_button.clicked.connect(self.apply_parameters)
        self.apply_params_button.setEnabled(False)  # 初始时禁用
        
        phase_freq_layout.addWidget(self.phase_x_label)
        phase_freq_layout.addWidget(self.phase_x_input)
        phase_freq_layout.addWidget(self.phase_y_label)
        phase_freq_layout.addWidget(self.phase_y_input)
        phase_freq_layout.addWidget(self.freq_x_label)
        phase_freq_layout.addWidget(self.freq_x_input)
        phase_freq_layout.addWidget(self.freq_y_label)
        phase_freq_layout.addWidget(self.freq_y_input)
        phase_freq_layout.addWidget(self.apply_params_button)
        phase_freq_layout.addStretch()

        # 添加指令输入区域
        command_layout = QHBoxLayout()
        
        self.command_label = QLabel("指令(hex):")
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("例如: AA 01 02 03")
        self.command_input.setFixedWidth(200)
        
        self.send_command_button = QPushButton("发送指令")
        self.send_command_button.clicked.connect(self.send_command)
        self.send_command_button.setEnabled(False)
        
        command_layout.addWidget(self.command_label)
        command_layout.addWidget(self.command_input)
        command_layout.addWidget(self.send_command_button)
        command_layout.addStretch()

        # 添加多帧处理设置
        self.frame_buffer_size_input = QLineEdit("10")
        self.frame_buffer_size_input.setFixedWidth(60)
        settings_layout.addWidget(QLabel("帧缓存大小:"))
        settings_layout.addWidget(self.frame_buffer_size_input)
        
        # 添加多帧融合开关
        self.enable_frame_fusion = QPushButton("启用多帧融合")
        self.enable_frame_fusion.setCheckable(True)
        settings_layout.addWidget(self.enable_frame_fusion)

        # 添加帧率显示标签
        self.fps_label = QLabel("重建帧率: 0 FPS")
        self.fps_label.setStyleSheet("font-size: 14px; color: green;")
        settings_layout.addWidget(self.fps_label)

        # 创建UDP发送器
        self.udp_sender = UDPSender(self.ip_input.text().strip(), 8003)
        # 初始启用发送按钮
        self.send_command_button.setEnabled(True)
        
        # IP地址改变时更新发送器
        self.ip_input.textChanged.connect(self.update_sender_ip)

        # 添加图像调节控件
        self.image_controls_layout = QVBoxLayout()
        
        # 最大值滑动条
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("最大值:"))
        self.max_slider = QSlider(Qt.Horizontal)
        self.max_slider.setRange(0, 65535)
        self.max_slider.setValue(65535)
        self.max_slider.valueChanged.connect(self.schedule_update)
        max_layout.addWidget(self.max_slider)
        self.max_value_label = QLabel("65535")
        max_layout.addWidget(self.max_value_label)
        self.image_controls_layout.addLayout(max_layout)
        
        # 最小值滑动条
        min_layout = QHBoxLayout()
        min_layout.addWidget(QLabel("最小值:"))
        self.min_slider = QSlider(Qt.Horizontal)
        self.min_slider.setRange(0, 65535)
        self.min_slider.setValue(0)
        self.min_slider.valueChanged.connect(self.schedule_update)
        min_layout.addWidget(self.min_slider)
        self.min_value_label = QLabel("0")
        min_layout.addWidget(self.min_value_label)
        self.image_controls_layout.addLayout(min_layout)
        
        # 对比度滑动条
        contrast_layout = QHBoxLayout()
        contrast_layout.addWidget(QLabel("对比度:"))
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, 200)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.schedule_update)
        contrast_layout.addWidget(self.contrast_slider)
        self.contrast_value_label = QLabel("1.0")
        contrast_layout.addWidget(self.contrast_value_label)
        self.image_controls_layout.addLayout(contrast_layout)
        
        # 亮度滑动条
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(QLabel("亮度:"))
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.schedule_update)
        brightness_layout.addWidget(self.brightness_slider)
        self.brightness_value_label = QLabel("0")
        brightness_layout.addWidget(self.brightness_value_label)
        self.image_controls_layout.addLayout(brightness_layout)

        # 添加自动调整按钮
        auto_adjust_layout = QHBoxLayout()
        self.auto_adjust_button = QPushButton("自动调整显示范围")
        self.auto_adjust_button.clicked.connect(self.auto_adjust_display_range)
        auto_adjust_layout.addWidget(self.auto_adjust_button)
        auto_adjust_layout.addStretch()
        self.image_controls_layout.addLayout(auto_adjust_layout)

        # 主布局
        layout = QVBoxLayout()
        layout.addLayout(settings_layout)      # IP和端口设置
        layout.addLayout(phase_freq_layout)    # 相位和频率设置
        layout.addLayout(command_layout)       # 指令输入区域
        layout.addLayout(self.image_controls_layout)
        layout.addWidget(self.image_label)
        layout.addWidget(self.bytes_label)
        layout.addWidget(self.queue_label)
        layout.addWidget(self.log_text)
        layout.addLayout(button_layout)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # 初始化对象引用
        self.udp_receiver = None
        self.assembler = None
        self.processors = []

        # 保存原始16bit图像数据
        self.current_16bit_image = None

        # 添加防抖动定时器
        self.display_timer = QTimer()
        self.display_timer.setSingleShot(True)  # 单次触发
        self.display_timer.timeout.connect(self.update_image_display)
        
        # 修改滑动条信号连接
        self.max_slider.valueChanged.connect(self.schedule_update)
        self.min_slider.valueChanged.connect(self.schedule_update)
        self.contrast_slider.valueChanged.connect(self.schedule_update)
        self.brightness_slider.valueChanged.connect(self.schedule_update)
        
        # 更新标签的定时器
        self.label_timer = QTimer()
        self.label_timer.setSingleShot(True)
        self.label_timer.timeout.connect(self.update_value_labels)

        # 添加全局状态变量
        self.should_save_frame = False

        # 初始化帧率计算相关变量
        self.frame_times = []
        self.fps_update_timer = QTimer()
        self.fps_update_timer.timeout.connect(self.update_fps)
        self.fps_update_timer.start(1000)  # 每秒更新一次帧率

        # 延迟预编译Numba函数，避免阻塞界面显示
        # 使用QTimer.singleShot在界面显示后100毫秒再开始预编译
        QTimer.singleShot(10, self.warm_up_numba_functions)


    def update_bytes_counter(self, data):
        """更新接收字节计数"""
        self.total_bytes += len(data)
        self.bytes_label.setText(f"已接收: {self.total_bytes:,} 字节")

    def reset_counter(self):
        """复位字节计数器"""
        self.total_bytes = 0
        self.bytes_label.setText("已接收: 0 字节")
        self.log_text.append("计数器已复位")

    def start_receiver(self):
        """启动UDP接收"""
        try:
            # 如果已经有接收器在运行，先停止它
            if self.udp_receiver:
                self.stop_receiver()
                time.sleep(0.1)  # 等待端口完全释放
                
            target_ip = self.ip_input.text().strip()
            
            # 创建新的接收器
            self.udp_receiver = UDPReceiver(target_ip, 8003)
            self.udp_receiver.log_message.connect(self.log_text.append)
            self.udp_receiver.packet_received.connect(self.update_bytes_counter)
            self.udp_receiver.start()

            # 创建帧组装器时传入缓存大小
            buffer_size = int(self.frame_buffer_size_input.text())
            self.assembler = FrameAssembler(frame_buffer_size=buffer_size)
            self.assembler.log_message.connect(self.log_text.append)
            self.assembler.frame_complete.connect(self.on_frame_complete)
            self.assembler.frames_complete.connect(self.on_frames_complete)  # 新增多帧处理信号连接
            self.assembler.queue_status.connect(self.update_queue_status)
            self.assembler.start()

            self.start_receiver_button.setEnabled(False)
            self.stop_receiver_button.setEnabled(True)
            self.save_button.setEnabled(True)
            self.save_frame_button.setEnabled(True)  # 启用保存帧按钮
            
            self.log_text.append(f"UDP接收器已启动 (监听端口=8003)")
            
        except Exception as e:
            self.log_text.append(f"启动接收器失败：{str(e)}")

    def stop_receiver(self):
        """停止UDP接收"""
        if self.udp_receiver:
            self.udp_receiver.stop()
            self.udp_receiver.wait()  # 等待线程完全停止
            self.udp_receiver = None
            
        if self.assembler:
            self.assembler.stop()
            self.assembler.wait()  # 等待线程完全停止
            self.assembler = None
            
        # 清空全局队列
        with QMutexLocker(queue_mutex):
            while not packet_queue.empty():
                try:
                    packet_queue.get_nowait()
                except Empty:
                    break
                    
        # 等待所有处理器完成
        for processor in self.processors:
            if processor.isRunning():
                processor.stop()
                processor.wait()
        self.processors.clear()
        
        self.start_receiver_button.setEnabled(True)
        self.stop_receiver_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.save_frame_button.setEnabled(False)  # 禁用保存帧按钮
        
        if self.save_button.isChecked():
            self.save_button.click()  # 停止保存
            
        self.log_text.append("UDP接收器已停止")

    @pyqtSlot(list)
    def on_frame_complete(self, packets_list):
        """处理完整帧"""
        if not packets_list:  # 添加数据检查
            return
            
        # self.log_text.append(f"收到1帧，包数={len(packets_list)}，开始处理...")

        # 检查是否需要保存帧
        if self.should_save_frame and packets_list:  # 确保有数据时才保存
            self.save_packets_to_bin(packets_list)

        try:
            # 使用当前的参数值
            params = getattr(self, '_current_params', {
                'deltaphasex': float(self.phase_x_input.text()),
                'deltaphasey': float(self.phase_y_input.text()),
                'freqx': float(self.freq_x_input.text()),
                'freqy': float(self.freq_y_input.text())
            })
            
            # 创建新的处理器，传入当前设置的参数
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
        except Exception as e:
            self.log_text.append(f"处理出错：{str(e)}")

    def cleanup_processor(self, processor):
        """清理完成的处理器"""
        if processor in self.processors:
            self.processors.remove(processor)
            processor.deleteLater()

    @pyqtSlot(np.ndarray, float, float)
    def on_image_processed(self, final_image, phasex_deg, phasey_deg):
        """显示处理后的图像"""
        # 记录当前帧的时间戳
        self.frame_times.append(time.time())
        
        # 保存16bit原始数据
        self.current_16bit_image = final_image
        
        # 使用当前显示设置更新图像
        self.update_image_display()
        
        self.log_text.append(f"图像处理完成。相位: X={phasex_deg:.1f}°, Y={phasey_deg:.1f}°")

    def closeEvent(self, event):
        """窗口关闭时清理"""
        self.fps_update_timer.stop()  # 停止帧率更新定时器
        self.stop_receiver()
        super().closeEvent(event)

    def update_queue_status(self, queue_size):
        """更新队列状态显示"""
        self.queue_label.setText(f"队列状态: {queue_size:,} 包")

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

    def apply_parameters(self):
        """应用新的相位和频率参数"""
        try:
            # 获取新的参数值
            deltaphasex = float(self.phase_x_input.text())
            deltaphasey = float(self.phase_y_input.text())
            freqx = float(self.freq_x_input.text())
            freqy = float(self.freq_y_input.text())
            
            # 记录新的参数值
            self._current_params = {
                'deltaphasex': deltaphasex,
                'deltaphasey': deltaphasey,
                'freqx': freqx,
                'freqy': freqy
            }
            
            self.log_text.append(f"已更新参数：\n"
                               f"X相位={deltaphasex}°, Y相位={deltaphasey}°\n"
                               f"X频率={freqx}, Y频率={freqy}")
                               
        except ValueError:
            self.log_text.append("错误：请输入有效的数字")
        except Exception as e:
            self.log_text.append(f"更新参数失败：{str(e)}")

    def send_command(self):
        """发送控制指令到下位机"""
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
                
            # 转换为字节数组并发送
            command = bytes.fromhex(hex_str)
            success, bytes_sent = self.udp_sender.send_command(command)
            
            if success:
                self.log_text.append(f"已发送指令：{command.hex(' ').upper()} ({bytes_sent} 字节)")
            else:
                self.log_text.append("发送指令失败")
                
        except ValueError:
            self.log_text.append("错误：无效的十六进制格式")
        except Exception as e:
            self.log_text.append(f"发送指令出错：{str(e)}")

    def update_sender_ip(self):
        """当IP输入框内容改变时更新UDP发送器"""
        target_ip = self.ip_input.text().strip()
        if target_ip:  # 如果IP不为空
            self.udp_sender = UDPSender(target_ip, 8003)
            self.send_command_button.setEnabled(True)
        else:
            self.send_command_button.setEnabled(False)

    def schedule_update(self):
        """计划更新显示"""
        # 立即更新数值标签
        self.label_timer.start(10)  # 10ms后更新标签
        # 计划更新图像显示
        self.display_timer.start(50)  # 50ms后更新图像

    def update_value_labels(self):
        """更新数值标签"""
        self.max_value_label.setText(str(self.max_slider.value()))
        self.min_value_label.setText(str(self.min_slider.value()))
        self.contrast_value_label.setText(f"{self.contrast_slider.value()/100:.1f}")
        self.brightness_value_label.setText(str(self.brightness_slider.value()))

    def update_image_display(self):
        """更新图像显示"""
        if self.current_16bit_image is None:
            return
            
        # 获取当前设置
        max_val = self.max_slider.value()
        min_val = self.min_slider.value()
        contrast = self.contrast_slider.value() / 100.0
        brightness = self.brightness_slider.value()
        
        try:
            # 应用设置到图像
            # 1. 首先应用最大最小值范围
            img_adjusted = np.clip(self.current_16bit_image, min_val, max_val)
            img_adjusted = ((img_adjusted - min_val) / (max_val - min_val) * 65535).astype(np.uint16)
            
            # 2. 应用对比度
            img_adjusted = img_adjusted.astype(np.float32)
            img_adjusted = img_adjusted * contrast
            
            # 3. 应用亮度
            img_adjusted = img_adjusted + (brightness * 65535 / 100)
            
            # 4. 裁剪到有效范围
            img_adjusted = np.clip(img_adjusted, 0, 65535)
            
            # 5. 转换为8位显示
            img_8bit = (img_adjusted / 65535 * 255).astype(np.uint8)
            
            # 显示图像
            h, w = img_8bit.shape
            qimg = QImage(img_8bit.data, w, h, w, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.KeepAspectRatio
            )
            self.image_label.setPixmap(pixmap)
            
        except Exception as e:
            self.log_text.append(f"更新图像显示出错：{str(e)}")

    def auto_adjust_display_range(self):
        """自动调整图像显示范围"""
        if self.current_16bit_image is None:
            return
            
        try:
            # 计算图像的实际范围
            valid_pixels = self.current_16bit_image[self.current_16bit_image > 0]  # 排除0值
            if len(valid_pixels) == 0:
                return
                
            # 获取有效像素的最小值和最大值
            min_val = np.percentile(valid_pixels, 1)  # 使用1%分位数作为最小值
            max_val = np.percentile(valid_pixels, 99)  # 使用99%分位数作为最大值
            
            # 设置滑动条的值
            self.min_slider.setValue(int(min_val))
            self.max_slider.setValue(int(max_val))
            
            # 更新显示
            self.log_text.append(f"自动调整范围：最小值={int(min_val)}，最大值={int(max_val)}")
            
        except Exception as e:
            self.log_text.append(f"自动调整显示范围出错：{str(e)}")

    def toggle_save_frame(self):
        """切换保存帧状态"""
        self.should_save_frame = self.save_frame_button.isChecked()
        if self.should_save_frame:
            self.log_text.append("保存帧功能已激活")
        else:
            self.log_text.append("保存帧功能已停用")

    def save_packets_to_bin(self, packets):
        """保存传入的packets为bin文件"""
        if not packets:  # 添加数据检查
            self.log_text.append("警告：没有数据包可保存")
            return

        timestamp = int(time.time() * 1000)  # 获取当前时间戳（毫秒）
        filename = f"frame_{timestamp}.bin"
        
        try:
            # 检查是否有有效数据
            valid_packets = [p for p in packets if p and len(p) > 0]
            if not valid_packets:
                self.log_text.append("警告：所有数据包都为空")
                return
                
            with open(filename, 'wb') as f:
                for packet in valid_packets:
                    f.write(packet)
            self.log_text.append(f"帧已保存为: {filename}")
        except Exception as e:
            self.log_text.append(f"保存帧失败: {e}")

    @pyqtSlot(list)
    def on_frames_complete(self, frames_list):
        """处理多个完整帧"""
        if not self.enable_frame_fusion.isChecked():
            # 如果未启用多帧融合，只处理最新的一帧
            self.on_frame_complete(frames_list[-1])
            return

        self.log_text.append(f"收到 {len(frames_list)} 帧数据，开始融合处理...")

        try:
            # 在这里实现多帧融合逻辑
            # 示例：简单的帧平均
            all_images = []
            for packets in frames_list:
                params = getattr(self, '_current_params', {
                    'deltaphasex': float(self.phase_x_input.text()),
                    'deltaphasey': float(self.phase_y_input.text()),
                    'freqx': float(self.freq_x_input.text()),
                    'freqy': float(self.freq_y_input.text())
                })
                
                processor = ImageProcessor(
                    packets,
                    params['deltaphasex'],
                    params['deltaphasey'],
                    params['freqx'],
                    params['freqy']
                )
                
                # 同步处理每一帧
                final_image, phasex_deg, phasey_deg = processor.process_single_frame_one_freq(
                    packets,
                    SampleRate=1e7,
                    Freqx=params['freqx'],
                    Freqy=params['freqy'],
                    deltaphasex=params['deltaphasex'],
                    deltaphasey=params['deltaphasey']
                )
                all_images.append(final_image)

            # 执行帧融合（这里使用简单平均作为示例）
            if all_images:
                fused_image = np.mean(all_images, axis=0)
                self.on_image_processed(fused_image, phasex_deg, phasey_deg)
                self.log_text.append(f"完成 {len(all_images)} 帧融合")

        except Exception as e:
            self.log_text.append(f"多帧处理出错：{str(e)}")

    def update_fps(self):
        """更新帧率显示"""
        # 清理超过1秒的时间戳
        current_time = time.time()
        self.frame_times = [t for t in self.frame_times if current_time - t <= 1.0]
        
        # 计算帧率
        fps = len(self.frame_times)
        self.fps_label.setText(f"重建帧率: {fps} FPS")

    def warm_up_numba_functions(self):
        """预编译Numba函数，避免首次运行时的JIT编译延迟"""
        self.log_text.append("正在预编译优化函数，请稍候...")
        QApplication.processEvents()  # 刷新UI，显示提示消息
        
        try:      
            #预编译 _interpolate_columns_numba 函数
            self.log_text.append("  - 编译插值函数 (_interpolate_columns_numba)...")
            QApplication.processEvents()  # 编译前刷新UI
            
            start_time = time.time()
            dummy_image_size = 512  # 与代码中使用的图像大小一致
            dummy_image = np.random.rand(dummy_image_size, dummy_image_size).astype(np.float32)
            # 确保图像中有NaN值以触发插值逻辑
            dummy_image[0:100, 0:100] = np.nan
            dummy_nan_mask = np.isnan(dummy_image)
            
            # 调用函数触发编译
            _interpolate_columns_numba(dummy_image, dummy_nan_mask)
            
            elapsed_time = time.time() - start_time
            self.log_text.append(f"    完成! (耗时: {elapsed_time:.2f}秒)")
            QApplication.processEvents()  # 编译后刷新UI
            self.log_text.append("程序现在将以正常速度运行")
        except Exception as e:
            self.log_text.append(f"预编译过程中出错: {e}")
        
        QApplication.processEvents()  # 确保最终消息显示

########################
# main
########################
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

def map_delta_phasex(original_phase):
    """
    将原始相位映射到补偿相位
    
    参数:
    original_phase: 原始相位值 (0-360度)
    
    返回:
    mapped_phase: 映射后的补偿相位值
    """
    # 确保输入相位在0-360度范围内
    original_phase = original_phase % 360
    if original_phase < 180:
        full_phase = 185 - 0.5 * original_phase
    else:
        full_phase = 365 - 0.5 * original_phase
    # 对180取模得到最终补偿相位
    return full_phase % 360

def map_delta_phasey(original_phase):
    """
    将原始相位映射到补偿相位，
    驱动信号和轨迹信号之间存在一个二倍关系，无法确认使用哪一条映射关系
    参数:
    original_phase: 原始相位值 (0-360度)
    
    返回:
    mapped_phase: 映射后的补偿相位值
    """
    original_phase = original_phase % 360
    
    # 计算完整的补偿相位
    if original_phase < 180:
        full_phase = 215 - 0.5 * original_phase
    else:
        full_phase = 395 - 0.5 * original_phase
    return full_phase % 360


if __name__ == "__main__":
    main()
