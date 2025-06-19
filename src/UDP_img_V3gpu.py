import sys
import time
import socket
import math
import numpy as np
import cupy as cp
import struct
import numba
import cv2
from typing import Optional
import cupyx.scipy.ndimage

from PyQt5.QtCore import (
    Qt, QThread, QObject, pyqtSignal, pyqtSlot, QMutex, QMutexLocker, QTimer
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QTextEdit,
    QPushButton, QVBoxLayout, QWidget, QHBoxLayout, QLineEdit, QFileDialog,
    QSlider, QComboBox, QSpinBox, QGroupBox, QGridLayout, QTabWidget, QCheckBox
)
from queue import Queue, Empty, Full


########################
# 1) UDPReceiver
########################
# 全局队列和锁
packet_queue = Queue(maxsize=10000)  # 可以存储约70帧的数据
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
                    while not packet_queue.empty() and len(packets) < self.packets_per_frame * 3:
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
                # 添加完整帧的打印信息
                self.log_message.emit(f"帧 {frame_id} 组装完成: {len(packets)} 包 (需要{self.packets_per_frame}包)")
            elif current_time - timestamp > self.frame_timeout:
                # 超时的不完整帧
                frames_to_remove.append(frame_id)
                # 添加不完整帧的打印信息
                self.log_message.emit(f"帧 {frame_id} 超时丢弃: 仅收到 {len(packets)} 包，缺少 {self.packets_per_frame - len(packets)} 包")

        # 处理完整帧
        if complete_frames:
            self.frame_complete.emit(complete_frames[0])  # 优先处理最新的完整帧
            
        # 清理帧缓冲区
        for frame_id in frames_to_remove:
            del self.frame_buffer[frame_id]

        # 发送当前队列状态和缓冲区状态
        with QMutexLocker(queue_mutex):
            current_queue_size = packet_queue.qsize()
        
        # # 添加当前缓冲区状态的打印信息
        # if len(self.frame_buffer) > 0:
        #     buffer_status = []
        #     for fid, fdata in self.frame_buffer.items():
        #         buffer_status.append(f"帧{fid}:{len(fdata['packets'])}包")
        #     self.log_message.emit(f"缓冲区状态: {', '.join(buffer_status)}")
    
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
        使用 CuPy 加速数据包解析和灰度累加过程。
        """
        # start_time = time.time()
        NumFrame = int(1e6)          # 每帧的采样点数
        ImageSize = 512              # 图像大小为 512 x 512
        Delta_t = 1.0 / SampleRate   # 每个采样点之间的时间间隔

        X_Amp = ImageSize / 2.0      # X 方向扫描振幅
        Y_Amp = ImageSize / 2.0      # Y 方向扫描振幅

        X_Freq = math.pi * Delta_t * 2 * Freqx  # 等价于 2π(SampleRate^-1)*Freqx
        Y_Freq = math.pi * Delta_t * 2 * Freqy
        # PixelData = cp.zeros((ImageSize, ImageSize), dtype=cp.int64) # 这个可以后面再 reshape

        first_packet = packets[0]

        # --- 相位计算部分，保持原样 ---
        # ... (这里省略了相位计算的代码，因为它不是要优化的部分) ...
        phase_x_raw = struct.unpack('>I', first_packet[6:10])[0]
        phase_y_raw = struct.unpack('>I', first_packet[10:14])[0]

        # 假设 map_delta_phasex 和 map_delta_phasey 已经定义
        phasex_compensation=map_delta_phasex(phase_x_raw * 360.0 / 33554432.0)
        phasey_compensation=map_delta_phasey(phase_y_raw * 360.0 / 33554432.0)
        # phasex_compensation=0
        # phasey_compensation=0

        # 注意：randn_phasex/y 应该在 CPU 上生成，CuPy 的 random.randn() 在 GPU 上生成
        # 如果 randn 部分需要保持原行为（在 CPU 上），使用 numpy.random.randn()
        # 如果希望在 GPU 上，则使用 cp.random.randn()。
        # 这里假设它们是独立随机数，CPU/GPU 生成影响不大，使用 cp 保持在 GPU 上操作
        # randn_phasex = cp.random.randn() * 1
        # randn_phasey = cp.random.randn() * 1

        randn_phasex = 0
        randn_phasey = 0

        phasex_deg = ((phase_x_raw * 360.0 / 33554432.0) + phasex_compensation + randn_phasex)%360.0
        phasey_deg = ((phase_y_raw * 360.0 / 33554432.0) + phasey_compensation + randn_phasey)%360.0

        phasex = cp.deg2rad(cp.round(phasex_deg * 1000) / 1000)
        phasey = cp.deg2rad(cp.round(phasey_deg * 1000) / 1000)
        # --- 相位计算部分结束 ---


        # --- 轨迹计算部分，保持原样 ---
        i_arr = cp.arange(NumFrame, dtype=cp.float64)  # [0, 1, 2, ..., 999999]

        # 计算扫描轨迹：X_vals, Y_vals
        X_vals = X_Amp * cp.sin(X_Freq * i_arr + phasex) + 256.0
        Y_vals = Y_Amp * cp.sin(Y_Freq * i_arr + phasey) + 256.0

        X_vals = cp.floor(X_vals).astype(cp.int32)
        Y_vals = cp.floor(Y_vals).astype(cp.int32)

        cp.clip(X_vals, 0, ImageSize - 1, out=X_vals)
        cp.clip(Y_vals, 0, ImageSize - 1, out=Y_vals)

        # 计算线性索引，这个已经在 CuPy 上了，很好
        XY_linear_indices = cp.add(cp.multiply(X_vals, ImageSize), Y_vals, dtype=cp.int32)
        # --- 轨迹计算部分结束 ---

        # PixelTimes 不需要在这里预先计算，可以在累加灰度后，根据 PixelData 的非零项来确定哪些像素被访问过
        # PixelTimes = cp.bincount(
        #     XY_linear_indices,
        #     minlength=ImageSize * ImageSize
        # ).reshape((ImageSize, ImageSize))
        # 注意：如果你确实需要知道每个像素被扫描到的次数（而不仅仅是最终灰度），那么 PixelTimes 的计算可以保留，但它应该基于 *所有* NumFrame 采样点，而不是只有有数据的那些点。

        # --- 优化后的数据包解析和灰度累加 ---
        # end_time_1 = time.time()
        # print(f"Phase and Trajectory Calculation: {end_time_1 - start_time} 秒")

        # 提取所有数据包的 payload 字节
        all_payload_bytes = []
        if packets:
            # 处理第一个数据包 (header 偏移不同)
            first_packet = packets[0]
            packageNum_first = (first_packet[4] << 8) + first_packet[5]
            flag_first = 14
            # 确保不超出数据包长度
            payload_end_first = min(flag_first + packageNum_first, len(first_packet))
            all_payload_bytes.append(first_packet[flag_first:payload_end_first])

            # 处理后续数据包
            for pkt in packets[1:]:
                packageNum_pkt = (pkt[4] << 8) + pkt[5]
                flag_pkt = 6
                # 确保不超出数据包长度
                payload_end_pkt = min(flag_pkt + packageNum_pkt, len(pkt))
                all_payload_bytes.append(pkt[flag_pkt:payload_end_pkt])

        # end_time_payload_extract = time.time()
        # print(f"1: {end_time_payload_extract - end_time_1} 秒")

        # 连接所有 payload 字节，并转换为 CuPy 的 uint16 数组
        # 使用 numpy 的 frombuffer 更方便处理字节，然后转到 cupy
        concatenated_bytes = b''.join(all_payload_bytes)

        gray_values_arr_gpu = None # 初始化为 None

        if concatenated_bytes:
            # 确保字节长度是偶数，因为每两个字节是一个 uint16
            if len(concatenated_bytes) % 2 != 0:
                 print("Warning: Concatenated payload bytes length is odd. Truncating last byte.")
                 concatenated_bytes = concatenated_bytes[:-1]

            # 使用 numpy.frombuffer 解释字节为 uint8 数组，然后 view 为大端模式的 uint16
            # 再转换为 int64 (与原始代码中 gray 的类型保持一致) 并转移到 GPU
            concatenated_np_bytes = np.frombuffer(concatenated_bytes, dtype=np.uint8)
            gray_values_arr_np = concatenated_np_bytes.view(dtype='>H').astype(np.int64) # >H 表示大端无符号16位整数
            gray_values_arr_gpu = cp.asarray(gray_values_arr_np)

        # end_time_bytes_to_gpu = time.time()
        # print(f"2: {end_time_bytes_to_gpu - end_time_payload_extract} 秒")

        # 获取提取到的有效灰度值数量
        total_data_points = len(gray_values_arr_gpu) if gray_values_arr_gpu is not None else 0

        # 生成与 gray_values_arr_gpu 对应的 pixel_index 数组 (从 0 开始递增)
        # 注意：这些 index 对应的是数据点在整个扫描轨迹中的顺序位置。
        # 我们只关心前 NumFrame 个数据点，因为 i_arr 也是 NumFrame 长度。
        # 如果提取到的数据点少于 NumFrame，就只用提取到的这些点。
        num_indices_to_use = min(total_data_points, NumFrame)

        PixelDataFlat = cp.zeros(ImageSize * ImageSize, dtype=cp.int64)

        if num_indices_to_use > 0:
            # 获取需要使用的 pixel_index (0 到 num_indices_to_use - 1)
            pixel_indices_arr_gpu = cp.arange(num_indices_to_use, dtype=cp.int64)

            # 获取对应的灰度值
            gray_values_to_use = gray_values_arr_gpu[:num_indices_to_use]

            # 使用这些 pixel_index 从 XY_linear_indices 中查找到对应的图像平面线性索引
            # 这里的 pixel_indices_arr_gpu 正是 i_arr 的一个前缀，所以可以直接用作索引
            final_pixel_linear_indices = XY_linear_indices[pixel_indices_arr_gpu]

            # 使用 cp.bincount 加权累加灰度值到对应的图像像素位置
            # minlength 保证输出数组大小正确
            accum = cp.bincount(
                final_pixel_linear_indices,
                weights=gray_values_to_use, # 使用灰度值作为权重进行累加
                minlength=ImageSize * ImageSize
            ).astype(cp.int64)

            # 将累加结果赋值给 PixelDataFlat
            PixelDataFlat = accum

        # end_time_accumulation = time.time()
        # print(f"3: {end_time_accumulation - end_time_bytes_to_gpu} 秒")

        # 计算每个像素被访问到的次数 (用于后续求平均)
        # 这里的 bincount 基于的是有数据的那些点，而不是所有 NumFrame 的点
        # 如果 PixelTimes 确实需要基于所有 NumFrame 点的扫描轨迹，则需要保留前面基于 i_arr 的 PixelTimes 计算
        # 如果 PixelTimes 只需要知道哪些点有数据，则可以如下计算：
        if num_indices_to_use > 0:
             PixelTimesFlat = cp.bincount(
                 final_pixel_linear_indices,
                 minlength=ImageSize * ImageSize
             ).astype(cp.int64)
        else:
             PixelTimesFlat = cp.zeros(ImageSize * ImageSize, dtype=cp.int64)


        PixelData = PixelDataFlat.reshape((ImageSize, ImageSize))
        PixelTimes = PixelTimesFlat.reshape((ImageSize, ImageSize)) # Reshape PixelTimes as well

        # --- 最后的除法计算，保持原样 (已经在 GPU 上) ---
        # end_time_data_reshaped = time.time()
        # print(f"4: {end_time_data_reshaped - end_time_accumulation} 秒")

        # 在GPU上完成除法运算
        non_zero_mask = PixelTimes != 0
        final_image_gpu = cp.zeros_like(PixelData, dtype=cp.float64)
        # 避免除以零，只对有访问次数的像素进行除法
        final_image_gpu[non_zero_mask] = PixelData[non_zero_mask].astype(cp.float64) / PixelTimes[non_zero_mask].astype(cp.float64)

        # 将结果传回 CPU
        final_image_raw = cp.asnumpy(final_image_gpu)
        final_image = np.where(np.isfinite(final_image_raw), final_image_raw, np.nan)
        # 将 PixelTimes 转回 CPU 以便使用
        PixelTimes_cpu = cp.asnumpy(PixelTimes)
        # 创建一个掩码，标记那些被扫描次数为 0 的像素点
        unscanned_mask = (PixelTimes_cpu == 0)
        # 将这些未被扫描到的像素点的值设置为 np.nan，以便后续插值
        final_image[unscanned_mask] = np.nan

        # --- 高效向量化垂直插值 ---
        start_interp_time = time.time() # 开始计时
        # 创建一个掩码，标记 NaN 值 (现在包含了之前标记的 0 值位置)
        nan_mask = np.isnan(final_image)
        
        # 使用 Numba JIT 编译的函数进行插值
        interpolated_image = _interpolate_columns_numba(final_image, nan_mask)
        
        # 将剩余的NaN填充为0 (例如整列都是 NaN 的情况)
        interpolated_image = np.nan_to_num(interpolated_image, nan=0.0)

        end_interp_time = time.time() # 结束计时
        interpolation_duration = end_interp_time - start_interp_time
        print(f"插值耗时: {interpolation_duration:.6f} 秒") # 打印插值时间
        # end_time_4 = time.time()
        # print(f"5: {end_time_4 - end_time_data_reshaped} 秒")

        return interpolated_image, cp.asnumpy(phasex_deg), cp.asnumpy(phasey_deg) # 将相位也转回 numpy/CPU
    
    
    # def process_single_frame_one_freq(
    #     self,
    #     packets,
    #     SampleRate,
    #     Freqx,
    #     Freqy,
    #     deltaphasex,
    #     deltaphasey,
    # ):
    #     """
    #     与原先逻辑相同: 解析packets并生成 final_image.
    #     这里保留原有相位计算，但不再遍历多种相位，也不在 UI 端调节。
    #     """
    #     start_time = time.time()
    #     NumFrame = int(1e6)         # 每帧的采样点数
    #     ImageSize = 512             # 图像大小为 512 x 512
    #     Delta_t = 1.0 / SampleRate  # 每个采样点之间的时间间隔

    #     X_Amp = ImageSize / 2.0     # X 方向扫描振幅
    #     Y_Amp = ImageSize / 2.0     # Y 方向扫描振幅

    #     X_Freq = math.pi * Delta_t * 2 * Freqx  # 等价于 2π(SampleRate^-1)*Freqx
    #     Y_Freq = math.pi * Delta_t * 2 * Freqy
    #     PixelData = cp.zeros((ImageSize, ImageSize), dtype=cp.int64)

    #     first_packet = packets[0]

    #     phase_x_raw = struct.unpack('>I', first_packet[6:10])[0]
    #     phase_y_raw = struct.unpack('>I', first_packet[10:14])[0]
        
    #     phasex_compensation=map_delta_phasex(phase_x_raw * 360.0 / 33554432.0)
    #     phasey_compensation=map_delta_phasey(phase_y_raw * 360.0 / 33554432.0)

    #     randn_phasex = cp.random.randn() * 1
    #     randn_phasey = cp.random.randn() * 1

    #     phasex_deg = (phase_x_raw * 360.0 / 33554432.0) + phasex_compensation + randn_phasex
    #     phasey_deg = (phase_y_raw * 360.0 / 33554432.0) + phasey_compensation + randn_phasey
        

    #     #phasex = math.radians(cp.round(phasex_deg * 1000) / 1000)
    #     #phasey = math.radians(cp.round(phasey_deg * 1000) / 1000)
        
    #     # 使用CuPy的数学函数
    #     phasex = cp.deg2rad(cp.round(phasex_deg * 1000) / 1000)
    #     phasey = cp.deg2rad(cp.round(phasey_deg * 1000) / 1000)

    #     i_arr = cp.arange(NumFrame, dtype=cp.float64)  # [0, 1, 2, ..., 999999]
        

    #     # 计算扫描轨迹：X_vals, Y_vals
    #     X_vals = X_Amp * cp.sin(X_Freq * i_arr + phasex) + 256.0
    #     Y_vals = Y_Amp * cp.sin(Y_Freq * i_arr + phasey) + 256.0
        

    #     X_vals = cp.floor(X_vals).astype(cp.int32)
    #     Y_vals = cp.floor(Y_vals).astype(cp.int32)

    #     cp.clip(X_vals, 0, ImageSize - 1, out=X_vals)
    #     cp.clip(Y_vals, 0, ImageSize - 1, out=Y_vals)

        
    #     #XY_linear_indices = X_vals * ImageSize + Y_vals
    #     # 使用CuPy的elementwise操作
    #     XY_linear_indices = cp.add(cp.multiply(X_vals, ImageSize), Y_vals, dtype=cp.int32)

    #     PixelTimes_flat = cp.bincount(
    #         XY_linear_indices,
    #         minlength=ImageSize * ImageSize
    #     )
    #     PixelTimes = PixelTimes_flat.reshape((ImageSize, ImageSize))

    #     PixelDataFlat = cp.zeros(ImageSize * ImageSize, dtype=cp.int64)
    #     TotalNumEachFrame = NumFrame * 2

    #     packageNum = (first_packet[4] << 8) + first_packet[5]

    #     i = 14   
    #     flag = 14

    #     pixel_indices_list = []
    #     gray_values_list = []

    #     while i < packageNum + 6 and (i + 1) < len(first_packet):
    #         val = (first_packet[i] << 8) + first_packet[i + 1]
    #         gray = val

    #         pixel_index = int(NumFrame - (TotalNumEachFrame - i + flag) / 2)
    #         if 0 <= pixel_index < NumFrame:
    #             pixel_indices_list.append(pixel_index)
    #             gray_values_list.append(gray)

    #         i += 2

    #     packageNum -= 8
    #     TotalNumEachFrame -= packageNum
    #     end_time_1 = time.time()
    #     print(f"1: {end_time_1 - start_time} 秒")

    #     # ---------------------
    #     # 第 6 步：解析后续数据包
    #     # ---------------------
    #     for pkt in packets[1:]:
    #         packageNum = (pkt[4] << 8) + pkt[5]
    #         i = 6
    #         flag = 6
    #         while i < packageNum + 6 and (i + 1) < len(pkt):
    #             val = (pkt[i] << 8) + pkt[i + 1]
    #             gray = val

    #             pixel_index = int(NumFrame - (TotalNumEachFrame - i + flag) / 2)
    #             if 0 <= pixel_index < NumFrame:
    #                 pixel_indices_list.append(pixel_index)
    #                 gray_values_list.append(gray)

    #             i += 2

    #         # 如果需要，和原始逻辑一样做一次修正
    #         if flag == 14:
    #             packageNum -= 8

    #         TotalNumEachFrame -= packageNum
    #         if TotalNumEachFrame < 5:
    #             break  # 数据已读取完成或余量很小

    #     end_time_2 = time.time()
    #     print(f"2: {end_time_2 - end_time_1} 秒")

    #     # ---------------------
    #     # 第 7 步：累加灰度值
    #     # ---------------------
    #     if len(pixel_indices_list) > 0:
    #         pixel_indices_arr = cp.array(pixel_indices_list, dtype=cp.int64)
    #         gray_values_arr = cp.array(gray_values_list, dtype=cp.int64)

        
    #         final_pixel_linear_indices = XY_linear_indices[pixel_indices_arr]

    #         accum = cp.bincount(
    #             final_pixel_linear_indices,
    #             weights=gray_values_arr,
    #             minlength=ImageSize * ImageSize
    #         ).astype(cp.int64)  # 显式转换为 int64 类型

    #         PixelDataFlat += accum

    #     PixelData = PixelDataFlat.reshape((ImageSize, ImageSize))
    #     end_time_3 = time.time()
    #     print(f"3: {end_time_3 - end_time_2} 秒")


    #     #with np.errstate(divide='ignore', invalid='ignore'):
    #     #    final_image = np.divide(cp.asnumpy(PixelData), cp.asnumpy(PixelTimes))
    #     #    final_image[~np.isfinite(final_image)] = 0
    #     #return final_image, phasex_deg, phasey_deg
    #      # 在GPU上完成除法运算
    #     # 使用CuPy的除法避免数据回传
    #     non_zero_mask = PixelTimes != 0
    #     final_image_gpu = cp.zeros_like(PixelData, dtype=cp.float64)
    #     final_image_gpu[non_zero_mask] = PixelData[non_zero_mask] / PixelTimes[non_zero_mask]
    #     final_image = cp.asnumpy(final_image_gpu)
    #     final_image[~np.isfinite(final_image)] = 0
    #     end_time_4 = time.time()
    #     print(f"4: {end_time_4 - end_time_3} 秒")
    #     return final_image, phasex_deg, phasey_deg

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
            # self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
    # 使用CuPy直接处理数据，避免使用OpenCV
    # 计算图像的最大值和最小值
    if isinstance(final_image, np.ndarray):
        # 如果输入是NumPy数组，先转换为CuPy
        final_image_gpu = cp.asarray(final_image)
    else:
        final_image_gpu = final_image
    
    min_val = cp.min(final_image_gpu)
    max_val = cp.max(final_image_gpu)
    
    # 如果最大值等于最小值，避免除零错误
    if max_val == min_val:
        return cp.zeros_like(final_image_gpu, dtype=cp.uint8)
    
    # 归一化到0-255
    normalized_image = ((final_image_gpu - min_val) / (max_val - min_val) * 255.0)
    
    # 转换为8位整数
    return cp.uint8(normalized_image)

def binary_threshold_by_mode(final_image):
    """
    对最常见非零像素做阈值二值化
    """
    # 确保使用GPU处理
    if isinstance(final_image, np.ndarray):
        # 如果输入是NumPy数组，先转换为CuPy
        final_image_gpu = cp.asarray(final_image)
    else:
        final_image_gpu = final_image
    
    # 只处理非零像素
    non_zero_mask = final_image_gpu > 0
    if cp.sum(non_zero_mask) == 0:
        return cp.zeros_like(final_image_gpu, dtype=cp.uint8)
    
    # 使用直方图找到最频繁值
    non_zero_values = final_image_gpu[non_zero_mask]
    
    # 如果值的范围较大，进行离散化处理以加速计算
    if cp.max(non_zero_values) - cp.min(non_zero_values) > 1000:
        # 将值映射到1000个bin
        bins = 1000
        hist = cp.histogram(non_zero_values, bins=bins)
        bin_idx = cp.argmax(hist[0])
        bin_edges = hist[1]
        most_frequent_value = (bin_edges[bin_idx] + bin_edges[bin_idx + 1]) / 2
    else:
        # 直接计算唯一值和计数
        unique, counts = cp.unique(non_zero_values, return_counts=True)
        if len(unique) == 0:
            most_frequent_value = 0
        else:
            most_frequent_value = unique[cp.argmax(counts)]
    
    # 使用阈值创建二值图像
    binary_image = cp.where(final_image_gpu > most_frequent_value, 255, 0)
    return cp.uint8(binary_image)

def pad_image(image, target_size):
    """
    将图像填充到指定大小（保持居中）
    """
    # 确保图像是在GPU上的CuPy数组
    if isinstance(image, np.ndarray):
        image_gpu = cp.asarray(image)
    else:
        image_gpu = image
    
    # 获取原始图像尺寸
    h, w = image_gpu.shape[:2]
    
    # 计算需要填充的尺寸
    pad_top = (target_size[0] - h) // 2
    pad_bottom = target_size[0] - h - pad_top
    pad_left = (target_size[1] - w) // 2
    pad_right = target_size[1] - w - pad_left
    
    # 使用CuPy的pad函数直接在GPU上执行填充
    if len(image_gpu.shape) == 2:
        # 灰度图像
        return cp.pad(image_gpu, ((pad_top, pad_bottom), (pad_left, pad_right)), mode='constant')
    else:
        # 彩色图像
        return cp.pad(image_gpu, ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)), mode='constant')

def extract_center_region(image, target_size):
    """
    从大图像中提取中心区域
    """
    # 确保图像是在GPU上的CuPy数组
    if isinstance(image, np.ndarray):
        image_gpu = cp.asarray(image)
    else:
        image_gpu = image
    
    # 获取原始图像尺寸
    h, w = image_gpu.shape[:2]
    
    # 计算中心区域的起始位置
    start_h = (h - target_size[0]) // 2
    start_w = (w - target_size[1]) // 2
    
    # 提取中心区域
    if len(image_gpu.shape) == 2:
        # 灰度图像
        return image_gpu[start_h:start_h+target_size[0], start_w:start_w+target_size[1]]
    else:
        # 彩色图像
        return image_gpu[start_h:start_h+target_size[0], start_w:start_w+target_size[1], :]

def resize_image(image, target_size):
    """
    调整图像大小，保持宽高比，并确保在GPU上处理
    """
    # 确保图像是在GPU上的CuPy数组
    if isinstance(image, np.ndarray):
        image_gpu = cp.asarray(image)
    else:
        image_gpu = image
    
    # 获取原始图像尺寸
    h, w = image_gpu.shape[:2]
    
    # 计算缩放比例
    scale = min(target_size[0] / h, target_size[1] / w)
    
    # 计算新尺寸
    new_h = int(h * scale)
    new_w = int(w * scale)
    
    # 使用cupyx.scipy.ndimage进行调整大小
    if len(image_gpu.shape) == 2:
        # 灰度图像
        resized = cupyx.scipy.ndimage.zoom(image_gpu, (new_h/h, new_w/w), order=1)
    else:
        # 彩色图像
        resized = cupyx.scipy.ndimage.zoom(image_gpu, (new_h/h, new_w/w, 1), order=1)
    
    return resized

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
        self.ip_input = QLineEdit("192.168.1.91") # 127.0.0.1
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

        # 创建协议命令控制区域
        self.protocol_control_widget = self.create_protocol_control_widget()

        # 创建左右分栏布局
        main_horizontal_layout = QHBoxLayout()
        
        # 左侧布局 - 原有功能区域
        left_layout = QVBoxLayout()
        left_layout.addLayout(settings_layout)      # IP和端口设置
        left_layout.addLayout(phase_freq_layout)    # 相位和频率设置
        left_layout.addLayout(command_layout)       # 指令输入区域
        left_layout.addLayout(self.image_controls_layout)  # 图像控制
        left_layout.addWidget(self.image_label)     # 图像显示
        left_layout.addWidget(self.bytes_label)     # 字节计数
        left_layout.addWidget(self.queue_label)     # 队列状态
        
        # 右侧布局 - 协议命令控制区域
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.protocol_control_widget)
        right_layout.addStretch()  # 添加弹性空间
        
        # 创建左右侧容器
        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        left_widget.setMinimumWidth(600)  # 设置最小宽度
        
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        right_widget.setMinimumWidth(1200)  # 增加右侧最小宽度
        right_widget.setMaximumWidth(1600)  # 增加右侧最大宽度
        
        # 添加到水平布局
        main_horizontal_layout.addWidget(left_widget, 1)  # 左侧占1份
        main_horizontal_layout.addWidget(right_widget, 1) # 右侧占1份

        # 主布局
        layout = QVBoxLayout()
        layout.addLayout(main_horizontal_layout)
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
        if self.should_save_frame and packets_list: # 确保有数据时才保存
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

    def create_protocol_control_widget(self):
        """创建协议命令控制区域的控件"""
        widget = QWidget()
        main_layout = QVBoxLayout()

        # 添加协议命令的说明标签
        title_label = QLabel("通讯协议命令控制")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2E8B57;")
        main_layout.addWidget(title_label)

        # 创建主要控制区域，使用QGridLayout实现两列布局
        control_layout = QGridLayout()
        
        # 1. MEMS驱动信号参数配置
        mems_group = self.create_mems_control_section()
        
        # 2. 图像采集与传输控制
        image_group = self.create_image_control_section()
        
        # 3. 系统控制
        system_group = self.create_system_control_section()
        
        # 4. 看门狗与诊断
        watchdog_group = self.create_watchdog_control_section()

        # 将控件添加到网格布局中
        # MEMS组占据左侧一整列 (第0列)，并跨越3行
        control_layout.addWidget(mems_group, 0, 0, 3, 1) # (row, col, rowSpan, colSpan)
        
        # 其他组垂直排列在右侧列 (第1列)
        control_layout.addWidget(image_group, 0, 1)
        control_layout.addWidget(system_group, 1, 1)
        control_layout.addWidget(watchdog_group, 2, 1)

        # 设置列的拉伸因子，让两列宽度大致相当，可以根据需要调整比例
        control_layout.setColumnStretch(0, 1)
        control_layout.setColumnStretch(1, 1)
        
        # 添加一个空的行拉伸，使得右侧的组在垂直方向上不会被拉伸得太开
        control_layout.setRowStretch(3, 1) 

        main_layout.addLayout(control_layout)
        widget.setLayout(main_layout)
        return widget

    def create_mems_control_section(self):
        """创建MEMS驱动信号参数配置区域"""
        group = QGroupBox("MEMS驱动信号参数配置")
        layout = QVBoxLayout()

        # 波形模式和双参数模式
        mode_layout = QHBoxLayout()
        
        # 波形模式切换按钮
        self.wave_mode_button = QPushButton("正弦波")
        self.wave_mode_button.setCheckable(True)
        self.wave_mode_button.setChecked(False)  # 默认正弦波
        self.wave_mode_button.clicked.connect(self.toggle_wave_mode)
        self.wave_mode_button.setMinimumWidth(80)
        self.wave_mode_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        mode_layout.addWidget(QLabel("波形模式:"))
        mode_layout.addWidget(self.wave_mode_button)
        
        # 双参数模式切换按钮
        self.dual_param_button = QPushButton("单组参数")
        self.dual_param_button.setCheckable(True)
        self.dual_param_button.setChecked(False)  # 默认单组
        self.dual_param_button.clicked.connect(self.toggle_dual_param_mode)
        self.dual_param_button.setMinimumWidth(100)
        self.dual_param_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        mode_layout.addWidget(QLabel("参数模式:"))
        mode_layout.addWidget(self.dual_param_button)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # 组0参数设置
        group0_box = QGroupBox("组0参数")
        group0_layout = QGridLayout()
        
        # 组0 X轴参数
        group0_layout.addWidget(QLabel("X轴增益:"), 0, 0)
        self.x0_gain_input = QSpinBox()
        self.x0_gain_input.setRange(0,  500)
        self.x0_gain_input.setValue(300)
        self.x0_gain_input.setMinimumWidth(120)
        group0_layout.addWidget(self.x0_gain_input, 0, 1)
        
        group0_layout.addWidget(QLabel("X轴频率:"), 0, 2)
        self.x0_freq_input = QSpinBox()
        self.x0_freq_input.setRange(0, 1000000)
        self.x0_freq_input.setValue(764369)
        self.x0_freq_input.setMinimumWidth(120)
        group0_layout.addWidget(self.x0_freq_input, 0, 3)
        
        group0_layout.addWidget(QLabel("X轴相位:"), 0, 4)
        self.x0_phase_input = QSpinBox()
        self.x0_phase_input.setRange(0, 3600)
        self.x0_phase_input.setValue(0)
        self.x0_phase_input.setMinimumWidth(120)
        group0_layout.addWidget(self.x0_phase_input, 0, 5)
        
        # 组0 Y轴参数
        group0_layout.addWidget(QLabel("Y轴增益:"), 1, 0)
        self.y0_gain_input = QSpinBox()
        self.y0_gain_input.setRange(0, 500)
        self.y0_gain_input.setValue(300)
        self.y0_gain_input.setMinimumWidth(120)
        group0_layout.addWidget(self.y0_gain_input, 1, 1)
        
        group0_layout.addWidget(QLabel("Y轴频率:"), 1, 2)
        self.y0_freq_input = QSpinBox()
        self.y0_freq_input.setRange(0, 1000000)
        self.y0_freq_input.setValue(254342)
        self.y0_freq_input.setMinimumWidth(120)
        group0_layout.addWidget(self.y0_freq_input, 1, 3)
        
        group0_layout.addWidget(QLabel("Y轴相位:"), 1, 4)
        self.y0_phase_input = QSpinBox()
        self.y0_phase_input.setRange(0, 3600)
        self.y0_phase_input.setValue(0)
        self.y0_phase_input.setMinimumWidth(120)
        group0_layout.addWidget(self.y0_phase_input, 1, 5)
        
        # 组0操作按钮
        group0_btn_layout = QHBoxLayout()
        send_group0_btn = QPushButton("发送组0参数")
        send_group0_btn.clicked.connect(self.send_group0_params)
        group0_btn_layout.addWidget(send_group0_btn)
        group0_btn_layout.addStretch()
        
        group0_layout.addLayout(group0_btn_layout, 2, 0, 1, 6)
        group0_box.setLayout(group0_layout)
        layout.addWidget(group0_box)

        # 组1参数设置
        group1_box = QGroupBox("组1参数")
        group1_layout = QGridLayout()
        
        # 组1 X轴参数
        group1_layout.addWidget(QLabel("X轴增益:"), 0, 0)
        self.x1_gain_input = QSpinBox()
        
        self.x1_gain_input.setRange(0, 500)
        self.x1_gain_input.setValue(0)
        self.x1_gain_input.setMinimumWidth(120)
        group1_layout.addWidget(self.x1_gain_input, 0, 1)
        
        group1_layout.addWidget(QLabel("X轴频率:"), 0, 2)
        self.x1_freq_input = QSpinBox()
        self.x1_freq_input.setRange(0, 1000000)
        self.x1_freq_input.setValue(764369)
        self.x1_freq_input.setMinimumWidth(120)
        group1_layout.addWidget(self.x1_freq_input, 0, 3)
        
        group1_layout.addWidget(QLabel("X轴相位:"), 0, 4)
        self.x1_phase_input = QSpinBox()
        self.x1_phase_input.setRange(0, 3600)
        self.x1_phase_input.setValue(0)
        self.x1_phase_input.setMinimumWidth(120)
        group1_layout.addWidget(self.x1_phase_input, 0, 5)
        
        # 组1 Y轴参数
        group1_layout.addWidget(QLabel("Y轴增益:"), 1, 0)
        self.y1_gain_input = QSpinBox()
        self.y1_gain_input.setRange(0, 500)
        self.y1_gain_input.setValue(0)
        self.y1_gain_input.setMinimumWidth(120)
        group1_layout.addWidget(self.y1_gain_input, 1, 1)
        
        group1_layout.addWidget(QLabel("Y轴频率:"), 1, 2)
        self.y1_freq_input = QSpinBox()
        self.y1_freq_input.setRange(0, 1000000)
        self.y1_freq_input.setValue(254342)
        self.y1_freq_input.setMinimumWidth(120)
        group1_layout.addWidget(self.y1_freq_input, 1, 3)
        
        group1_layout.addWidget(QLabel("Y轴相位:"), 1, 4)
        self.y1_phase_input = QSpinBox()
        self.y1_phase_input.setRange(0, 3600)
        self.y1_phase_input.setValue(0)
        self.y1_phase_input.setMinimumWidth(120)
        group1_layout.addWidget(self.y1_phase_input, 1, 5)
        
        # 组1操作按钮
        group1_btn_layout = QHBoxLayout()
        send_group1_btn = QPushButton("发送组1参数")
        send_group1_btn.clicked.connect(self.send_group1_params)
        group1_btn_layout.addWidget(send_group1_btn)
        group1_btn_layout.addStretch()
        
        group1_layout.addLayout(group1_btn_layout, 2, 0, 1, 6)
        group1_box.setLayout(group1_layout)
        layout.addWidget(group1_box)

        # 扫频参数设置
        sweep_box = QGroupBox("扫频参数设置")
        sweep_layout = QVBoxLayout()
        
        # 扫频基本控制
        sweep_basic_layout = QHBoxLayout()
        
        # 扫频重复次数
        sweep_basic_layout.addWidget(QLabel("重复次数:"))
        self.sweep_repeat_input = QSpinBox()
        self.sweep_repeat_input.setRange(1, 255)
        self.sweep_repeat_input.setValue(1)
        self.sweep_repeat_input.setMinimumWidth(80)
        sweep_basic_layout.addWidget(self.sweep_repeat_input)
        
        # 扫频波形类型设置按钮
        set_sweep_type_btn = QPushButton("设置扫频类型")
        set_sweep_type_btn.clicked.connect(self.send_sweep_type_command)
        sweep_basic_layout.addWidget(set_sweep_type_btn)
        
        # 扫频启停按钮
        self.sweep_control_button = QPushButton("开始扫频2")
        self.sweep_control_button.setCheckable(True)
        self.sweep_control_button.setChecked(False)
        self.sweep_control_button.clicked.connect(self.toggle_sweep_control)
        self.sweep_control_button.setStyleSheet("QPushButton:checked { background-color: #FF5722; color: white; }")
        sweep_basic_layout.addWidget(self.sweep_control_button)
        
        sweep_basic_layout.addStretch()
        sweep_layout.addLayout(sweep_basic_layout)
        
        # X轴扫频参数
        x_sweep_box = QGroupBox("X轴扫频参数")
        x_sweep_layout = QGridLayout()
        
        # X轴起始/终止频率
        x_sweep_layout.addWidget(QLabel("起始频率:"), 0, 0)
        self.x_sweep_start_freq_input = QSpinBox()
        self.x_sweep_start_freq_input.setRange(0, 25000)
        self.x_sweep_start_freq_input.setValue(23500)
        self.x_sweep_start_freq_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_sweep_start_freq_input, 0, 1)
        
        x_sweep_layout.addWidget(QLabel("终止频率:"), 0, 2)
        self.x_sweep_end_freq_input = QSpinBox()
        self.x_sweep_end_freq_input.setRange(0, 25000)
        self.x_sweep_end_freq_input.setValue(22780)
        self.x_sweep_end_freq_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_sweep_end_freq_input, 0, 3)
        
        # X轴正弦波扫频参数
        x_sweep_layout.addWidget(QLabel("步进(Hz):"), 1, 0)
        self.x_sine_step_input = QSpinBox()
        self.x_sine_step_input.setRange(1, 100)
        self.x_sine_step_input.setValue(2)
        self.x_sine_step_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_sine_step_input, 1, 1)
        
        x_sweep_layout.addWidget(QLabel("幅值:"), 1, 2)
        self.x_sine_amplitude_input = QSpinBox()
        self.x_sine_amplitude_input.setRange(0, 65535)
        self.x_sine_amplitude_input.setValue(4)
        self.x_sine_amplitude_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_sine_amplitude_input, 1, 3)
        
        x_sweep_layout.addWidget(QLabel("初相位:"), 2, 0)
        self.x_sine_phase_input = QSpinBox()
        self.x_sine_phase_input.setRange(0, 3600)
        self.x_sine_phase_input.setValue(0)
        self.x_sine_phase_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_sine_phase_input, 2, 1)
        
        x_sweep_layout.addWidget(QLabel("维持周期:"), 2, 2)
        self.x_sine_keep_input = QSpinBox()
        self.x_sine_keep_input.setRange(1, 65535)
        self.x_sine_keep_input.setValue(100)
        self.x_sine_keep_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_sine_keep_input, 2, 3)
        
        # X轴方波扫频参数
        x_sweep_layout.addWidget(QLabel("方波步进:"), 3, 0)
        self.x_square_step_input = QSpinBox()
        self.x_square_step_input.setRange(1, 65535)
        self.x_square_step_input.setValue(2)
        self.x_square_step_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_square_step_input, 3, 1)
        
        x_sweep_layout.addWidget(QLabel("占空比:"), 3, 2)
        self.x_square_duty_input = QSpinBox()
        self.x_square_duty_input.setRange(0, 100)
        self.x_square_duty_input.setValue(100)
        self.x_square_duty_input.setSuffix(" %")
        self.x_square_duty_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_square_duty_input, 3, 3)
        
        x_sweep_layout.addWidget(QLabel("相位延时:"), 4, 0)
        self.x_square_delay_input = QSpinBox()
        self.x_square_delay_input.setRange(0, 65535)
        self.x_square_delay_input.setValue(0)
        self.x_square_delay_input.setMinimumWidth(120)
        x_sweep_layout.addWidget(self.x_square_delay_input, 4, 1)
        
        # X轴扫频控制按钮
        x_sweep_btn_layout = QHBoxLayout()
        x_freq_btn = QPushButton("设置X轴频率范围")
        x_freq_btn.clicked.connect(self.send_x_sweep_freq_range)
        x_sweep_btn_layout.addWidget(x_freq_btn)
        
        x_sine_params_btn = QPushButton("设置X轴正弦波参数")
        x_sine_params_btn.clicked.connect(self.send_x_sine_sweep_params)
        x_sweep_btn_layout.addWidget(x_sine_params_btn)
        
        x_square_params_btn = QPushButton("设置X轴方波参数")
        x_square_params_btn.clicked.connect(self.send_x_square_sweep_params)
        x_sweep_btn_layout.addWidget(x_square_params_btn)
        
        x_sweep_layout.addLayout(x_sweep_btn_layout, 5, 0, 1, 4)
        x_sweep_box.setLayout(x_sweep_layout)
        sweep_layout.addWidget(x_sweep_box)
        
        # Y轴扫频参数
        y_sweep_box = QGroupBox("Y轴扫频参数")
        y_sweep_layout = QGridLayout()
        
        # Y轴起始/终止频率
        y_sweep_layout.addWidget(QLabel("起始频率:"), 0, 0)
        self.y_sweep_start_freq_input = QSpinBox()
        self.y_sweep_start_freq_input.setRange(0, 10000)
        self.y_sweep_start_freq_input.setValue(8500)
        self.y_sweep_start_freq_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_sweep_start_freq_input, 0, 1)
        
        y_sweep_layout.addWidget(QLabel("终止频率:"), 0, 2)
        self.y_sweep_end_freq_input = QSpinBox()
        self.y_sweep_end_freq_input.setRange(0, 10000)
        self.y_sweep_end_freq_input.setValue(7580)
        self.y_sweep_end_freq_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_sweep_end_freq_input, 0, 3)
        
        # Y轴正弦波扫频参数
        y_sweep_layout.addWidget(QLabel("步进(Hz):"), 1, 0)
        self.y_sine_step_input = QSpinBox()
        self.y_sine_step_input.setRange(1, 100)
        self.y_sine_step_input.setValue(2)
        self.y_sine_step_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_sine_step_input, 1, 1)
        
        y_sweep_layout.addWidget(QLabel("幅值:"), 1, 2)
        self.y_sine_amplitude_input = QSpinBox()
        self.y_sine_amplitude_input.setRange(0, 65535)
        self.y_sine_amplitude_input.setValue(4)
        self.y_sine_amplitude_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_sine_amplitude_input, 1, 3)
        
        y_sweep_layout.addWidget(QLabel("初相位:"), 2, 0)
        self.y_sine_phase_input = QSpinBox()
        self.y_sine_phase_input.setRange(0, 3600)
        self.y_sine_phase_input.setValue(0)
        self.y_sine_phase_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_sine_phase_input, 2, 1)
        
        y_sweep_layout.addWidget(QLabel("维持周期:"), 2, 2)
        self.y_sine_keep_input = QSpinBox()
        self.y_sine_keep_input.setRange(1, 65535)
        self.y_sine_keep_input.setValue(100)
        self.y_sine_keep_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_sine_keep_input, 2, 3)
        
        # Y轴方波扫频参数
        y_sweep_layout.addWidget(QLabel("方波步进:"), 3, 0)
        self.y_square_step_input = QSpinBox()
        self.y_square_step_input.setRange(1, 65535)
        self.y_square_step_input.setValue(1000)
        self.y_square_step_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_square_step_input, 3, 1)
        
        y_sweep_layout.addWidget(QLabel("占空比:"), 3, 2)
        self.y_square_duty_input = QSpinBox()
        self.y_square_duty_input.setRange(0, 100)
        self.y_square_duty_input.setValue(100)
        self.y_square_duty_input.setSuffix(" %")
        self.y_square_duty_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_square_duty_input, 3, 3)
        
        y_sweep_layout.addWidget(QLabel("相位延时:"), 4, 0)
        self.y_square_delay_input = QSpinBox()
        self.y_square_delay_input.setRange(0, 65535)
        self.y_square_delay_input.setValue(0)
        self.y_square_delay_input.setMinimumWidth(120)
        y_sweep_layout.addWidget(self.y_square_delay_input, 4, 1)
        
        # Y轴扫频控制按钮
        y_sweep_btn_layout = QHBoxLayout()
        y_freq_btn = QPushButton("设置Y轴频率范围")
        y_freq_btn.clicked.connect(self.send_y_sweep_freq_range)
        y_sweep_btn_layout.addWidget(y_freq_btn)
        
        y_sine_params_btn = QPushButton("设置Y轴正弦波参数")
        y_sine_params_btn.clicked.connect(self.send_y_sine_sweep_params)
        y_sweep_btn_layout.addWidget(y_sine_params_btn)
        
        y_square_params_btn = QPushButton("设置Y轴方波参数")
        y_square_params_btn.clicked.connect(self.send_y_square_sweep_params)
        y_sweep_btn_layout.addWidget(y_square_params_btn)
        
        y_sweep_layout.addLayout(y_sweep_btn_layout, 5, 0, 1, 4)
        y_sweep_box.setLayout(y_sweep_layout)
        sweep_layout.addWidget(y_sweep_box)
        
        sweep_box.setLayout(sweep_layout)
        layout.addWidget(sweep_box)

        # 全局操作
        global_layout = QHBoxLayout()
        all_params_btn = QPushButton("发送所有参数")
        all_params_btn.clicked.connect(self.send_all_mems_params)
        global_layout.addWidget(all_params_btn)
        
        reset_params_btn = QPushButton("重置为默认值")
        reset_params_btn.clicked.connect(self.reset_mems_params)
        global_layout.addWidget(reset_params_btn)
        global_layout.addStretch()
        
        layout.addLayout(global_layout)
        group.setLayout(layout)
        return group

    def create_image_control_section(self):
        """创建图像采集与传输控制区域"""
        group = QGroupBox("图像采集与传输控制")
        layout = QVBoxLayout()

        # 第一行：延时和MEMS控制
        row1_layout = QHBoxLayout()
        
        row1_layout.addWidget(QLabel("采集延时:"))
        self.acq_delay_input = QSpinBox()
        self.acq_delay_input.setRange(0, 1000000000)
        self.acq_delay_input.setValue(80000000)
        self.acq_delay_input.setMinimumWidth(120)
        row1_layout.addWidget(self.acq_delay_input)
        
        acq_delay_btn = QPushButton("设置")
        acq_delay_btn.setFixedWidth(60)
        acq_delay_btn.clicked.connect(lambda: self.send_mems_command(0x30, self.acq_delay_input.value(), 4))
        row1_layout.addWidget(acq_delay_btn)
        
        row1_layout.addWidget(QLabel("MEMS:"))
        self.mems_control_button = QPushButton("已停止1")
        self.mems_control_button.setCheckable(True)
        self.mems_control_button.setChecked(False)  # 默认停止
        self.mems_control_button.clicked.connect(self.toggle_mems_control)
        self.mems_control_button.setMinimumWidth(80)
        self.mems_control_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        row1_layout.addWidget(self.mems_control_button)
        
        row1_layout.addStretch()
        
        layout.addLayout(row1_layout)

        # 第二行：AD采样率和控制
        row2_layout = QHBoxLayout()
        
        row2_layout.addWidget(QLabel("AD采样率:"))
        self.ad_rate_input = QSpinBox()
        self.ad_rate_input.setRange(1, 255)
        self.ad_rate_input.setValue(12)
        self.ad_rate_input.setSuffix(" 分频")
        self.ad_rate_input.setMinimumWidth(120)
        row2_layout.addWidget(self.ad_rate_input)
        
        ad_rate_btn = QPushButton("设置")
        ad_rate_btn.setFixedWidth(60)
        ad_rate_btn.clicked.connect(lambda: self.send_mems_command(0x32, self.ad_rate_input.value(), 1))
        row2_layout.addWidget(ad_rate_btn)
        
        row2_layout.addWidget(QLabel("AD采集:"))
        self.ad_control_button = QPushButton("已停止3")
        self.ad_control_button.setCheckable(True)
        self.ad_control_button.setChecked(False)  # 默认停止
        self.ad_control_button.clicked.connect(self.toggle_ad_control)
        self.ad_control_button.setMinimumWidth(80)
        self.ad_control_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
        row2_layout.addWidget(self.ad_control_button)
        
        row2_layout.addStretch()
        
        layout.addLayout(row2_layout)

        # 第三行：网络传输参数
        row3_layout = QHBoxLayout()
        
        row3_layout.addWidget(QLabel("触发水平:"))
        self.trigger_level_input = QSpinBox()
        self.trigger_level_input.setRange(0, 65535)
        self.trigger_level_input.setValue(1400)
        self.trigger_level_input.setSuffix(" 字节")
        self.trigger_level_input.setMinimumWidth(120)
        row3_layout.addWidget(self.trigger_level_input)
        
        trigger_btn = QPushButton("设置")
        trigger_btn.setFixedWidth(60)
        trigger_btn.clicked.connect(lambda: self.send_mems_command(0x33, self.trigger_level_input.value(), 2))
        row3_layout.addWidget(trigger_btn)
        
        row3_layout.addWidget(QLabel("包间隔:"))
        self.packet_interval_input = QSpinBox()
        self.packet_interval_input.setRange(0, 65535)
        self.packet_interval_input.setValue(2500)
        self.packet_interval_input.setSuffix("clk")
        self.packet_interval_input.setMinimumWidth(120)
        row3_layout.addWidget(self.packet_interval_input)
        
        interval_btn = QPushButton("设置")
        interval_btn.setFixedWidth(60)
        interval_btn.clicked.connect(lambda: self.send_mems_command(0x36, self.packet_interval_input.value(), 2))
        row3_layout.addWidget(interval_btn)
        row3_layout.addStretch()
        
        layout.addLayout(row3_layout)
        
        # # 第四行：手动AD采样
        # row4_layout = QHBoxLayout()
        
        # row4_layout.addWidget(QLabel("手动AD采样:"))
        # self.manual_ad_samples_input = QSpinBox()
        # self.manual_ad_samples_input.setRange(1, 1000000)
        # self.manual_ad_samples_input.setValue(1000)
        # self.manual_ad_samples_input.setMinimumWidth(120)
        # row4_layout.addWidget(self.manual_ad_samples_input)
        
        # manual_ad_btn = QPushButton("开始采样")
        # manual_ad_btn.setFixedWidth(80)
        # manual_ad_btn.clicked.connect(self.start_manual_ad_sampling)
        # row4_layout.addWidget(manual_ad_btn)
        # row4_layout.addStretch()
        
        # layout.addLayout(row4_layout)
        
        group.setLayout(layout)
        return group

    def create_system_control_section(self):
        """创建系统控制区域"""
        group = QGroupBox("系统控制与状态监控")
        layout = QVBoxLayout()

        # 第一行：网口自检控制
        row1_layout = QHBoxLayout()
        
        row1_layout.addWidget(QLabel("网口自检:"))
        self.selftest_combo = QComboBox()
        self.selftest_combo.addItems(["使能", "禁止"])
        self.selftest_combo.setMinimumWidth(80)
        row1_layout.addWidget(self.selftest_combo)
        
        selftest_btn = QPushButton("设置")
        selftest_btn.setFixedWidth(60)
        selftest_btn.clicked.connect(self.send_selftest_command)
        row1_layout.addWidget(selftest_btn)
        
        row1_layout.addWidget(QLabel("自检包数:"))
        self.selftest_count_input = QSpinBox()
        self.selftest_count_input.setRange(0, 100000)
        self.selftest_count_input.setValue(10000)
        self.selftest_count_input.setMinimumWidth(120)
        row1_layout.addWidget(self.selftest_count_input)
        
        count_btn = QPushButton("设置")
        count_btn.setFixedWidth(60)
        count_btn.clicked.connect(lambda: self.send_mems_command(0x37, self.selftest_count_input.value(), 4))
        row1_layout.addWidget(count_btn)
        row1_layout.addStretch()
        
        layout.addLayout(row1_layout)

        # 第二行：状态监控
        row2_layout = QHBoxLayout()
        
        read_phase_btn = QPushButton("读取MEMS相位")
        read_phase_btn.clicked.connect(self.read_mems_phase)
        row2_layout.addWidget(read_phase_btn)
        
        read_ddr3_btn = QPushButton("读取DDR3状态")
        read_ddr3_btn.clicked.connect(self.read_ddr3_status)
        row2_layout.addWidget(read_ddr3_btn)
        
        row2_layout.addStretch()
        layout.addLayout(row2_layout)

        # 第三行：硬件补偿
        row3_layout = QHBoxLayout()
        
        row3_layout.addWidget(QLabel("X轴零偏:"))
        self.x_compensation_input = QSpinBox()
        self.x_compensation_input.setRange(-32768, 32767)
        self.x_compensation_input.setValue(350)
        self.x_compensation_input.setMinimumWidth(120)
        row3_layout.addWidget(self.x_compensation_input)
        
        row3_layout.addWidget(QLabel("Y轴零偏:"))
        self.y_compensation_input = QSpinBox()
        self.y_compensation_input.setRange(-32768, 32767)
        self.y_compensation_input.setValue(480)
        self.y_compensation_input.setMinimumWidth(120)
        row3_layout.addWidget(self.y_compensation_input)
        
        comp_btn = QPushButton("设置补偿")
        comp_btn.clicked.connect(self.send_compensation_command)
        row3_layout.addWidget(comp_btn)
        row3_layout.addStretch()
        
        layout.addLayout(row3_layout)
        
        group.setLayout(layout)
        return group

    def create_watchdog_control_section(self):
        """创建看门狗与诊断区域"""
        group = QGroupBox("看门狗控制")
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("看门狗:"))
        self.watchdog_combo = QComboBox()
        self.watchdog_combo.addItems(["使能", "禁止"])
        self.watchdog_combo.setMinimumWidth(80)
        layout.addWidget(self.watchdog_combo)
        
        wd_enable_btn = QPushButton("设置")
        wd_enable_btn.setFixedWidth(60)
        wd_enable_btn.clicked.connect(self.send_watchdog_enable_command)
        layout.addWidget(wd_enable_btn)
        
        layout.addWidget(QLabel("超时时间:"))
        self.watchdog_timeout_input = QSpinBox()
        self.watchdog_timeout_input.setRange(1, 255)
        self.watchdog_timeout_input.setValue(20)
        self.watchdog_timeout_input.setSuffix(" 秒")
        self.watchdog_timeout_input.setMinimumWidth(120)
        layout.addWidget(self.watchdog_timeout_input)
        
        wd_timeout_btn = QPushButton("设置")
        wd_timeout_btn.setFixedWidth(60)
        wd_timeout_btn.clicked.connect(lambda: self.send_mems_command(0x44, self.watchdog_timeout_input.value(), 1))
        layout.addWidget(wd_timeout_btn)
        
        feed_dog_btn = QPushButton("喂狗")
        feed_dog_btn.clicked.connect(self.send_feed_dog_command)
        layout.addWidget(feed_dog_btn)
        
        layout.addStretch()
        group.setLayout(layout)
        return group

    def send_group0_params(self):
        """发送组0所有参数"""
        try:
            # 发送组0 X轴参数
            self.send_mems_command(0x20, self.x0_gain_input.value(), 2)  # X轴增益
            self.send_mems_command(0x21, self.x0_freq_input.value(), 4)  # X轴频率
            self.send_mems_command(0x22, self.x0_phase_input.value(), 2)  # X轴相位
            
            # 发送组0 Y轴参数
            self.send_mems_command(0x26, self.y0_gain_input.value(), 2)  # Y轴增益
            self.send_mems_command(0x27, self.y0_freq_input.value(), 4)  # Y轴频率
            self.send_mems_command(0x28, self.y0_phase_input.value(), 2)  # Y轴相位
            
            self.log_text.append("已发送组0所有参数")
        except Exception as e:
            self.log_text.append(f"发送组0参数出错：{str(e)}")

    def send_group1_params(self):
        """发送组1所有参数"""
        try:
            # 发送组1 X轴参数
            self.send_mems_command(0x23, self.x1_gain_input.value(), 2)  # X轴增益
            self.send_mems_command(0x24, self.x1_freq_input.value(), 4)  # X轴频率
            self.send_mems_command(0x25, self.x1_phase_input.value(), 2)  # X轴相位
            
            # 发送组1 Y轴参数
            self.send_mems_command(0x29, self.y1_gain_input.value(), 2)  # Y轴增益
            self.send_mems_command(0x2A, self.y1_freq_input.value(), 4)  # Y轴频率
            self.send_mems_command(0x2B, self.y1_phase_input.value(), 2)  # Y轴相位
            
            self.log_text.append("已发送组1所有参数")
        except Exception as e:
            self.log_text.append(f"发送组1参数出错：{str(e)}")

    def send_all_mems_params(self):
        """发送所有MEMS参数"""
        try:
            self.send_group0_params()
            self.send_group1_params()
            self.log_text.append("已发送所有MEMS参数")
        except Exception as e:
            self.log_text.append(f"发送所有MEMS参数出错：{str(e)}")

    def reset_mems_params(self):
        """重置MEMS参数为默认值"""
        try:
            # 重置组0参数
            self.x0_gain_input.setValue(300)
            self.x0_freq_input.setValue(764369)
            self.x0_phase_input.setValue(0)
            self.y0_gain_input.setValue(300)
            self.y0_freq_input.setValue(254342)
            self.y0_phase_input.setValue(0)
            
            # 重置组1参数
            self.x1_gain_input.setValue(0)
            self.x1_freq_input.setValue(764369)
            self.x1_phase_input.setValue(0)
            self.y1_gain_input.setValue(0)
            self.y1_freq_input.setValue(254342)
            self.y1_phase_input.setValue(0)
            
            # 重置扫频参数
            self.sweep_repeat_input.setValue(1)
            self.x_sweep_start_freq_input.setValue(23500)
            self.x_sweep_end_freq_input.setValue(22780)
            self.y_sweep_start_freq_input.setValue(8500)
            self.y_sweep_end_freq_input.setValue(7580)
            
            # 重置模式按钮
            self.wave_mode_button.setChecked(False)
            self.dual_param_button.setChecked(False)
            self.sweep_control_button.setChecked(False)
            self.toggle_wave_mode()
            self.toggle_dual_param_mode()
            
            self.log_text.append("已重置所有参数为默认值")
        except Exception as e:
            self.log_text.append(f"重置参数出错：{str(e)}")

    def send_mems_control_command(self):
        """发送MEMS启停控制命令"""
        if self.mems_control_combo.currentText() == "启动":
            command_value = 0x11
            action = "启动"
        else:
            command_value = 0x22
            action = "停止"
            
        success, bytes_sent = self.send_mems_command(0x31, command_value, 1)
        if success:
            self.log_text.append(f"已{action}MEMS驱动")

    def send_ad_control_command(self):
        """发送AD采集启停控制命令"""
        if self.ad_control_combo.currentText() == "启动":
            command_value = 0x11
            action = "启动"
        else:
            command_value = 0x22
            action = "停止"
            
        success, bytes_sent = self.send_mems_command(0x34, command_value, 1)
        if success:
            self.log_text.append(f"已{action}AD采集")
        else:
            self.log_text.append(f"{action}AD采集命令发送失败")

    # def start_manual_ad_sampling(self):
    #     """开始手动AD采样"""
    #     try:
    #         samples = self.manual_ad_samples_input.value()
    #         # 这里可以添加手动AD采样的具体实现
    #         self.log_text.append(f"开始手动AD采样：{samples} 样本")
    #     except Exception as e:
    #         self.log_text.append(f"手动AD采样出错：{str(e)}")

    def send_selftest_command(self):
        """发送网口自检命令"""
        if self.selftest_combo.currentText() == "使能":
            command_value = 0x11
            action = "使能"
        else:
            command_value = 0x22
            action = "禁止"
            
        success, bytes_sent = self.send_mems_command(0x35, command_value, 1)
        if success:
            self.log_text.append(f"已{action}网口自检")

    def read_mems_phase(self):
        """读取MEMS驱动信号相位信息"""
        try:
            command = bytes([0xAA, 0x40, 0x01, 0x11])
            success, bytes_sent = self.udp_sender.send_command(command)
            if success:
                self.log_text.append("已发送读取MEMS相位命令，等待应答...")
            else:
                self.log_text.append("发送读取MEMS相位命令失败")
        except Exception as e:
            self.log_text.append(f"读取MEMS相位出错：{str(e)}")

    def read_ddr3_status(self):
        """读取DDR3初始化状态"""
        try:
            command = bytes([0xAA, 0x48, 0x01, 0x11])
            success, bytes_sent = self.udp_sender.send_command(command)
            if success:
                self.log_text.append("已发送读取DDR3状态命令，等待应答...")
            else:
                self.log_text.append("发送读取DDR3状态命令失败")
        except Exception as e:
            self.log_text.append(f"读取DDR3状态出错：{str(e)}")

    def send_compensation_command(self):
        """发送硬件补偿命令"""
        try:
            x_comp = self.x_compensation_input.value()
            y_comp = self.y_compensation_input.value()
            
            # 处理负数（16位有符号整数）
            if x_comp < 0:
                x_comp = 65536 + x_comp
            if y_comp < 0:
                y_comp = 65536 + y_comp
                
            command = bytearray([0xAA, 0x47, 0x04])
            # X补偿值（2字节）
            command.extend([(x_comp >> 8) & 0xFF, x_comp & 0xFF])
            # Y补偿值（2字节）
            command.extend([(y_comp >> 8) & 0xFF, y_comp & 0xFF])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            if success:
                self.log_text.append(f"已设置硬件补偿：X={self.x_compensation_input.value()}，Y={self.y_compensation_input.value()}")
            else:
                self.log_text.append("设置硬件补偿失败")
                
        except Exception as e:
            self.log_text.append(f"发送硬件补偿命令出错：{str(e)}")

    def send_watchdog_enable_command(self):
        """发送看门狗使能命令"""
        if self.watchdog_combo.currentText() == "使能":
            command_value = 0x11
            action = "使能"
        else:
            command_value = 0x22
            action = "禁止"
            
        success, bytes_sent = self.send_mems_command(0x43, command_value, 1)
        if success:
            self.log_text.append(f"已{action}看门狗")

    def send_feed_dog_command(self):
        """发送喂狗命令"""
        try:
            command = bytes([0xAA, 0x45, 0x01, 0x11])
            success, bytes_sent = self.udp_sender.send_command(command)
            if success:
                self.log_text.append("已发送喂狗命令")
            else:
                self.log_text.append("发送喂狗命令失败")
        except Exception as e:
            self.log_text.append(f"发送喂狗命令出错：{str(e)}")

    def send_mems_command(self, cmd_code, value, data_length):
        """通用MEMS命令发送方法"""
        try:
            command = bytearray([0xAA, cmd_code, data_length])
            
            if data_length == 1:
                command.append(value & 0xFF)
            elif data_length == 2:
                command.extend([(value >> 8) & 0xFF, value & 0xFF])
            elif data_length == 4:
                command.extend([
                    (value >> 24) & 0xFF,
                    (value >> 16) & 0xFF,
                    (value >> 8) & 0xFF,
                    value & 0xFF
                ])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            self.log_text.append(f"发送命令0x{cmd_code:02X}，数据长度={data_length:02X}，值={value:02X}")
            return success, bytes_sent
            
        except Exception as e:
            self.log_text.append(f"发送命令0x{cmd_code:02X}出错：{str(e)}")
            return False, 0

    def toggle_wave_mode(self):
        """切换波形模式"""
        if self.wave_mode_button.isChecked():
            self.wave_mode_button.setText("方波")
            self.wave_mode_button.setStyleSheet("QPushButton:checked { background-color: #FF9800; color: white; }")
            
        else:
            self.wave_mode_button.setText("正弦波")
            self.wave_mode_button.setStyleSheet("QPushButton:checked { background-color: #4CAF50; color: white; }")
            

    def toggle_dual_param_mode(self):
        """切换双参数模式"""
        if self.dual_param_button.isChecked():
            self.dual_param_button.setText("双组交替")
            self.send_mems_command(0x38, 0x22, 1)  # 启用双组交替
        else:
            self.dual_param_button.setText("单组参数")
            self.send_mems_command(0x38, 0x11, 1)  # 使用单组

    def toggle_mems_control(self):
        """切换MEMS启停状态"""
        if self.mems_control_button.isChecked():
            self.mems_control_button.setText("已启动1")
            command = bytes([0xAA, 0x31, 0x01, 0x11])  # 启动MEMS
            action = "启动"
        else:
            self.mems_control_button.setText("已停止1")
            command = bytes([0xAA, 0x31, 0x01, 0x22])  # 停止MEMS
            action = "停止"
        
        success, bytes_sent = self.udp_sender.send_command(command)
        if success:
            self.log_text.append(f"已{action}MEMS驱动")
        else:
            self.log_text.append(f"{action}MEMS驱动命令发送失败")

    def toggle_ad_control(self):
        """切换AD采集启停状态"""
        if self.ad_control_button.isChecked():
            self.ad_control_button.setText("已启动3")
            command = bytes([0xAA, 0x34, 0x01, 0x11])  # 启动AD采集
            action = "启动"
        else:
            self.ad_control_button.setText("已停止3")
            command = bytes([0xAA, 0x34, 0x01, 0x22])  # 停止AD采集
            action = "停止"
        
        success, bytes_sent = self.udp_sender.send_command(command)
        if success:
            self.log_text.append(f"已{action}AD采集")
        else:
            self.log_text.append(f"{action}AD采集命令发送失败")

    def send_sweep_type_command(self):
        """发送扫频波形类型与重复次数设置"""
        try:
            wave_type = 0x22 if self.wave_mode_button.isChecked() else 0x01  # 方波=0x22, 正弦波=0x01
            repeat_count = self.sweep_repeat_input.value()
            
            command = bytes([0xAA, 0x50, 0x02, wave_type, repeat_count])
            
            success, bytes_sent = self.udp_sender.send_command(command)
            if success:
                wave_str = "方波" if wave_type == 0x22 else "正弦波"
                self.log_text.append(f"已设置扫频类型：{wave_str}，重复次数：{repeat_count}, 发送命令= {command.hex().upper()}")
            else:
                self.log_text.append("设置扫频类型失败")
                
        except Exception as e:
            self.log_text.append(f"发送扫频类型命令出错：{str(e)}")

    def toggle_sweep_control(self):
        """切换扫频启停状态"""
        if self.sweep_control_button.isChecked():
            self.sweep_control_button.setText("停止扫频2")
            command = bytes([0xAA, 0x51, 0x01, 0x11])  # 启动扫频
            action = "启动"
        else:
            self.sweep_control_button.setText("开始扫频2")
            command = bytes([0xAA, 0x51, 0x01, 0x22])  # 停止扫频
            action = "停止"
        
        success, bytes_sent = self.udp_sender.send_command(command)
        if success:
            self.log_text.append(f"已{action}扫频，发送命令= {command.hex().upper()}")
        else:
            self.log_text.append(f"{action}扫频命令发送失败")

    def send_x_sweep_freq_range(self):
        """设置X轴扫频起始/结束频率"""
        try:
            start_freq = self.x_sweep_start_freq_input.value()
            end_freq = self.x_sweep_end_freq_input.value()
            
            # 判断是正弦波还是方波
            if self.wave_mode_button.isChecked():  # 方波
                cmd_code = 0x54  # 方波扫频X轴起始/结束频率
            else:  # 正弦波
                cmd_code = 0x52  # 正弦波扫频X轴起始/结束频率
            
            command = bytearray([0xAA, cmd_code, 0x08])
            # 起始频率（4字节，大端格式）
            command.extend([
                (start_freq >> 24) & 0xFF,
                (start_freq >> 16) & 0xFF,
                (start_freq >> 8) & 0xFF,
                start_freq & 0xFF
            ])
            # 结束频率（4字节，大端格式）
            command.extend([
                (end_freq >> 24) & 0xFF,
                (end_freq >> 16) & 0xFF,
                (end_freq >> 8) & 0xFF,
                end_freq & 0xFF
            ])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            if success:
                wave_type = "方波" if self.wave_mode_button.isChecked() else "正弦波"
                self.log_text.append(f"已设置X轴{wave_type}扫频频率范围：{start_freq}Hz → {end_freq}Hz，发送命令= {command.hex().upper()}")
            else:
                self.log_text.append("设置X轴扫频频率范围失败")
                
        except Exception as e:
            self.log_text.append(f"发送X轴扫频频率范围命令出错：{str(e)}")

    def send_x_sine_sweep_params(self):
        """设置X轴正弦波扫频参数"""
        try:
            step = self.x_sine_step_input.value()
            amplitude = self.x_sine_amplitude_input.value()
            phase = self.x_sine_phase_input.value()
            keep_cycles = self.x_sine_keep_input.value()
            
            command = bytearray([0xAA, 0x53, 0x08])
            # 步进（2字节）
            command.extend([(step >> 8) & 0xFF, step & 0xFF])
            # 幅值（2字节）
            command.extend([(amplitude >> 8) & 0xFF, amplitude & 0xFF])
            # 初相位（2字节）
            command.extend([(phase >> 8) & 0xFF, phase & 0xFF])
            # 维持周期数（2字节）
            command.extend([(keep_cycles >> 8) & 0xFF, keep_cycles & 0xFF])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            if success:
                self.log_text.append(f"已设置X轴正弦波扫频参数：步进{step}Hz，幅值{amplitude}，相位{phase/10}°，维持{keep_cycles}周期，发送命令= {command.hex().upper()}")
            else:
                self.log_text.append("设置X轴正弦波扫频参数失败")
                
        except Exception as e:
            self.log_text.append(f"发送X轴正弦波扫频参数命令出错：{str(e)}")

    def send_x_square_sweep_params(self):
        """设置X轴方波扫频参数"""
        try:
            if not self.wave_mode_button.isChecked():  # 不是方波模式则不发送
                self.log_text.append("当前不是方波模式，无法设置方波参数")
                return
                
            step = self.x_square_step_input.value()
            duty = self.x_square_duty_input.value()
            delay = self.x_square_delay_input.value()
            
            command = bytearray([0xAA, 0x55, 0x06])
            # 步进（2字节）
            command.extend([(step >> 8) & 0xFF, step & 0xFF])
            # 占空比（2字节，需要转换为0-1000范围）
            duty_value = duty * 10  # 将百分比转换为千分比
            command.extend([(duty_value >> 8) & 0xFF, duty_value & 0xFF])
            # 相位延时（2字节）
            command.extend([(delay >> 8) & 0xFF, delay & 0xFF])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            if success:
                self.log_text.append(f"已设置X轴方波扫频参数：步进{step}Hz，占空比{duty}%，延时{delay}，发送命令= {command.hex().upper()}")
            else:
                self.log_text.append("设置X轴方波扫频参数失败")
                
        except Exception as e:
            self.log_text.append(f"发送X轴方波扫频参数命令出错：{str(e)}")

    def send_y_sweep_freq_range(self):
        """设置Y轴扫频起始/结束频率"""
        try:
            start_freq = self.y_sweep_start_freq_input.value()
            end_freq = self.y_sweep_end_freq_input.value()
            
            # 判断是正弦波还是方波
            if self.wave_mode_button.isChecked():  # 方波
                cmd_code = 0x58  # 方波扫频Y轴起始/结束频率
            else:  # 正弦波
                cmd_code = 0x56  # 正弦波扫频Y轴起始/结束频率
            
            command = bytearray([0xAA, cmd_code, 0x08])
            # 起始频率（4字节，大端格式）
            command.extend([
                (start_freq >> 24) & 0xFF,
                (start_freq >> 16) & 0xFF,
                (start_freq >> 8) & 0xFF,
                start_freq & 0xFF
            ])
            # 结束频率（4字节，大端格式）
            command.extend([
                (end_freq >> 24) & 0xFF,
                (end_freq >> 16) & 0xFF,
                (end_freq >> 8) & 0xFF,
                end_freq & 0xFF
            ])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            if success:
                wave_type = "方波" if self.wave_mode_button.isChecked() else "正弦波"
                self.log_text.append(f"已设置Y轴{wave_type}扫频频率范围：{start_freq}Hz → {end_freq}Hz，发送命令= {command.hex().upper()}")
            else:
                self.log_text.append("设置Y轴扫频频率范围失败")
                
        except Exception as e:
            self.log_text.append(f"发送Y轴扫频频率范围命令出错：{str(e)}")

    def send_y_sine_sweep_params(self):
        """设置Y轴正弦波扫频参数"""
        try:
            step = self.y_sine_step_input.value()
            amplitude = self.y_sine_amplitude_input.value()
            phase = self.y_sine_phase_input.value()
            keep_cycles = self.y_sine_keep_input.value()
            
            command = bytearray([0xAA, 0x57, 0x08])
            # 步进（2字节）
            command.extend([(step >> 8) & 0xFF, step & 0xFF])
            # 幅值（2字节）
            command.extend([(amplitude >> 8) & 0xFF, amplitude & 0xFF])
            # 初相位（2字节）
            command.extend([(phase >> 8) & 0xFF, phase & 0xFF])
            # 维持周期数（2字节）
            command.extend([(keep_cycles >> 8) & 0xFF, keep_cycles & 0xFF])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            if success:
                self.log_text.append(f"已设置Y轴正弦波扫频参数：步进{step}Hz，幅值{amplitude}，相位{phase/10}°，维持{keep_cycles}周期，发送命令= {command.hex().upper()}")
            else:
                self.log_text.append("设置Y轴正弦波扫频参数失败")
                
        except Exception as e:
            self.log_text.append(f"发送Y轴正弦波扫频参数命令出错：{str(e)}")

    def send_y_square_sweep_params(self):
        """设置Y轴方波扫频参数"""
        try:
            if not self.wave_mode_button.isChecked():  # 不是方波模式则不发送
                self.log_text.append("当前不是方波模式，无法设置方波参数")
                return
                
            step = self.y_square_step_input.value()
            duty = self.y_square_duty_input.value()
            delay = self.y_square_delay_input.value()
            
            command = bytearray([0xAA, 0x59, 0x06])
            # 步进（2字节）
            command.extend([(step >> 8) & 0xFF, step & 0xFF])
            # 占空比（2字节，需要转换为0-1000范围）
            duty_value = duty * 10  # 将百分比转换为千分比
            command.extend([(duty_value >> 8) & 0xFF, duty_value & 0xFF])
            # 相位延时（2字节）
            command.extend([(delay >> 8) & 0xFF, delay & 0xFF])
            
            success, bytes_sent = self.udp_sender.send_command(bytes(command))
            if success:
                self.log_text.append(f"已设置Y轴方波扫频参数：步进{step}Hz，占空比{duty}%，延时{delay}，发送命令= {command.hex().upper()}")
            else:
                self.log_text.append("设置Y轴方波扫频参数失败")
                
        except Exception as e:
            self.log_text.append(f"发送Y轴方波扫频参数命令出错：{str(e)}")

########################
# main
########################
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

# 添加全局变量来跟踪相位变化
_previous_x_phase = None
_previous_y_phase = None
_x_phase_increasing_flag = False
_y_phase_increasing_flag = False

def map_delta_phasex(original_phase):
    """
    将原始相位映射到补偿相位 - X方向
    
    参数:
    original_phase: 原始相位值 (0-360度)
    
    返回:
    mapped_phase: 补偿相位值 (6 或 186)
    """
    global _previous_x_phase, _x_phase_increasing_flag
    
    # 确保输入相位在0-360度范围内
    original_phase = original_phase % 360
    
    # 如果是第一次调用，初始化
    if _previous_x_phase is None:
        _previous_x_phase = original_phase
        return 6  # 默认返回6
    
    # 检测相位变化趋势
    current_trend_increasing = original_phase > _previous_x_phase
    
    # 只有当趋势发生变化时才切换flag
    if current_trend_increasing :
        _x_phase_increasing_flag = not _x_phase_increasing_flag

    
    # 根据当前的flag选择补偿值
    compensation = 186 if _x_phase_increasing_flag else 6
    
    # 更新前一次的相位值
    _previous_x_phase = original_phase
    
    # 调试输出
    trend = "上升" if current_trend_increasing else "下降"
    # print(f"X相位: {original_phase:.1f}° -> 趋势={trend} -> flag={_x_phase_increasing_flag} -> 补偿={compensation}")
    
    return compensation

def map_delta_phasey(original_phase):
    """
    将原始相位映射到补偿相位 - Y方向
    
    参数:
    original_phase: 原始相位值 (0-360度)
    
    返回:
    mapped_phase: 补偿相位值 (35 或 215)
    """
    global _previous_y_phase, _y_phase_increasing_flag
    
    # 确保输入相位在0-360度范围内
    original_phase = original_phase % 360
    
    # 如果是第一次调用，初始化
    if _previous_y_phase is None:
        _previous_y_phase = original_phase
        return 35  # 默认返回35
    
    # 检测相位变化趋势
    current_trend_increasing = original_phase > _previous_y_phase
    
    # 只有当趋势发生变化时才切换flag
    if current_trend_increasing :
        _y_phase_increasing_flag = not _y_phase_increasing_flag
   
    # 根据当前的flag选择补偿值
    compensation = 215 if _y_phase_increasing_flag else 35
    
    # 更新前一次的相位值
    _previous_y_phase = original_phase
    
    # 调试输出
    trend = "上升" if current_trend_increasing else "下降"
    # print(f"Y相位: {original_phase:.1f}° -> 趋势={trend} -> flag={_y_phase_increasing_flag} -> 补偿={compensation}")
    
    return compensation



if __name__ == "__main__":
    main()
