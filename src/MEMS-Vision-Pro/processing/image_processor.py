"""
图像处理器模块
负责将数据包处理成图像
"""

import time
import math
import struct
import numpy as np
import cupy as cp
from PyQt5.QtCore import QThread, pyqtSignal

from config.constants import IMAGE_SIZE, NUM_FRAME, SAMPLE_RATE
from utils.phase_mapping import map_delta_phasex, map_delta_phasey
from utils.numba_functions import _interpolate_columns_numba

class ImageProcessor(QThread):
    """
    图像处理线程
    负责单个图像处理运行
    """
    # 发射: (final_image, phasex_deg, phasey_deg)
    image_processed = pyqtSignal(np.ndarray, float, float)

    def __init__(self, packets, deltaphasex, deltaphasey, freqx, freqy, parent=None):
        """
        初始化图像处理器
        
        Args:
            packets: 数据包列表
            deltaphasex: X方向相位调整
            deltaphasey: Y方向相位调整
            freqx: X方向频率
            freqy: Y方向频率
            parent: 父对象
        """
        super().__init__(parent)
        self.packets = packets
        self.deltaphasex = deltaphasex
        self.deltaphasey = deltaphasey
        self.freqx = freqx
        self.freqy = freqy
        self._is_running = True

    def run(self):
        """主运行函数"""
        if not self._is_running or not self.packets:
            return
            
        start_time = time.time()
        final_image, phasex_deg, phasey_deg = self.process_single_frame_one_freq(
            packets=self.packets,
            SampleRate=SAMPLE_RATE,
            Freqx=self.freqx,
            Freqy=self.freqy,
            deltaphasex=self.deltaphasex,
            deltaphasey=self.deltaphasey
        )
        end_time = time.time()
        print(f"处理时间: {end_time - start_time} 秒")
        self.image_processed.emit(final_image, phasex_deg, phasey_deg)

    def stop(self):
        """停止处理"""
        self._is_running = False
    
    def process_single_frame_one_freq(self, packets, SampleRate, Freqx, Freqy, deltaphasex, deltaphasey):
        """
        处理单帧数据生成图像
        
        Args:
            packets: 数据包列表
            SampleRate: 采样率
            Freqx: X方向频率
            Freqy: Y方向频率
            deltaphasex: X方向相位调整
            deltaphasey: Y方向相位调整
            
        Returns:
            tuple: (final_image, phasex_deg, phasey_deg)
        """
        # 初始化参数
        NumFrame = NUM_FRAME
        ImageSize = IMAGE_SIZE
        Delta_t = 1.0 / SampleRate

        X_Amp = ImageSize / 2.0
        Y_Amp = ImageSize / 2.0

        X_Freq = math.pi * Delta_t * 2 * Freqx
        Y_Freq = math.pi * Delta_t * 2 * Freqy

        first_packet = packets[0]

        # 相位计算部分
        phase_x_raw = struct.unpack('>I', first_packet[6:10])[0]
        phase_y_raw = struct.unpack('>I', first_packet[10:14])[0]

        # 使用相位映射函数
        phasex_compensation = map_delta_phasex(phase_x_raw * 360.0 / 33554432.0)
        phasey_compensation = map_delta_phasey(phase_y_raw * 360.0 / 33554432.0)

        randn_phasex = 0
        randn_phasey = 0

        phasex_deg = ((phase_x_raw * 360.0 / 33554432.0) + phasex_compensation + randn_phasex + deltaphasex) % 360.0
        phasey_deg = ((phase_y_raw * 360.0 / 33554432.0) + phasey_compensation + randn_phasey + deltaphasey) % 360.0

        phasex = cp.deg2rad(cp.round(phasex_deg * 1000) / 1000)
        phasey = cp.deg2rad(cp.round(phasey_deg * 1000) / 1000)

        # 轨迹计算部分
        i_arr = cp.arange(NumFrame, dtype=cp.float64)

        # 计算扫描轨迹：X_vals, Y_vals
        X_vals = X_Amp * cp.sin(X_Freq * i_arr + phasex) + 256.0
        Y_vals = Y_Amp * cp.sin(Y_Freq * i_arr + phasey) + 256.0

        X_vals = cp.floor(X_vals).astype(cp.int32)
        Y_vals = cp.floor(Y_vals).astype(cp.int32)

        cp.clip(X_vals, 0, ImageSize - 1, out=X_vals)
        cp.clip(Y_vals, 0, ImageSize - 1, out=Y_vals)

        # 计算线性索引
        XY_linear_indices = cp.add(cp.multiply(X_vals, ImageSize), Y_vals, dtype=cp.int32)

        # 优化后的数据包解析和灰度累加
        all_payload_bytes = self._extract_payload_bytes(packets)

        # 连接所有 payload 字节，并转换为 CuPy 的 uint16 数组
        concatenated_bytes = b''.join(all_payload_bytes)

        gray_values_arr_gpu = None

        if concatenated_bytes:
            gray_values_arr_gpu = self._process_payload_bytes(concatenated_bytes)

        # 获取提取到的有效灰度值数量
        total_data_points = len(gray_values_arr_gpu) if gray_values_arr_gpu is not None else 0

        # 生成与 gray_values_arr_gpu 对应的 pixel_index 数组
        num_indices_to_use = min(total_data_points, NumFrame)

        PixelDataFlat = cp.zeros(ImageSize * ImageSize, dtype=cp.int64)

        if num_indices_to_use > 0:
            PixelDataFlat, PixelTimesFlat = self._accumulate_pixel_data(
                gray_values_arr_gpu, XY_linear_indices, num_indices_to_use, ImageSize
            )
        else:
            PixelTimesFlat = cp.zeros(ImageSize * ImageSize, dtype=cp.int64)

        PixelData = PixelDataFlat.reshape((ImageSize, ImageSize))
        PixelTimes = PixelTimesFlat.reshape((ImageSize, ImageSize))

        # 最后的除法计算
        final_image = self._compute_final_image(PixelData, PixelTimes)

        return final_image, cp.asnumpy(phasex_deg), cp.asnumpy(phasey_deg)

    def _extract_payload_bytes(self, packets):
        """提取数据包的有效载荷字节"""
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

        return all_payload_bytes

    def _process_payload_bytes(self, concatenated_bytes):
        """处理连接的载荷字节"""
        # 确保字节长度是偶数，因为每两个字节是一个 uint16
        if len(concatenated_bytes) % 2 != 0:
            print("Warning: Concatenated payload bytes length is odd. Truncating last byte.")
            concatenated_bytes = concatenated_bytes[:-1]

        # 使用 numpy.frombuffer 解释字节为 uint8 数组，然后 view 为大端模式的 uint16
        concatenated_np_bytes = np.frombuffer(concatenated_bytes, dtype=np.uint8)
        gray_values_arr_np = concatenated_np_bytes.view(dtype='>H').astype(np.int64)
        gray_values_arr_gpu = cp.asarray(gray_values_arr_np)

        return gray_values_arr_gpu

    def _accumulate_pixel_data(self, gray_values_arr_gpu, XY_linear_indices, num_indices_to_use, ImageSize):
        """累加像素数据"""
        # 获取需要使用的 pixel_index
        pixel_indices_arr_gpu = cp.arange(num_indices_to_use, dtype=cp.int64)

        # 获取对应的灰度值
        gray_values_to_use = gray_values_arr_gpu[:num_indices_to_use]

        # 使用这些 pixel_index 从 XY_linear_indices 中查找到对应的图像平面线性索引
        final_pixel_linear_indices = XY_linear_indices[pixel_indices_arr_gpu]

        # 使用 cp.bincount 加权累加灰度值到对应的图像像素位置
        accum = cp.bincount(
            final_pixel_linear_indices,
            weights=gray_values_to_use,
            minlength=ImageSize * ImageSize
        ).astype(cp.int64)

        # 计算每个像素被访问到的次数
        PixelTimesFlat = cp.bincount(
            final_pixel_linear_indices,
            minlength=ImageSize * ImageSize
        ).astype(cp.int64)

        return accum, PixelTimesFlat

    def _compute_final_image(self, PixelData, PixelTimes):
        """计算最终图像"""
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

        # 高效向量化垂直插值
        start_interp_time = time.time()
        # 创建一个掩码，标记 NaN 值
        nan_mask = np.isnan(final_image)
        
        # 使用 Numba JIT 编译的函数进行插值
        interpolated_image = _interpolate_columns_numba(final_image, nan_mask)
        
        # 将剩余的NaN填充为0
        interpolated_image = np.nan_to_num(interpolated_image, nan=0.0)

        end_interp_time = time.time()
        interpolation_duration = end_interp_time - start_interp_time
        print(f"插值耗时: {interpolation_duration:.6f} 秒")

        return interpolated_image

    def save_frame_to_bin(self):
        """保存初始化时的packets为bin文件"""
        timestamp = int(time.time() * 1000)
        filename = f"frame_{timestamp}.bin"
        try:
            with open(filename, 'wb') as f:
                for packet in self.packets:
                    f.write(packet)
            print(f"帧已保存为: {filename}")
        except Exception as e:
            print(f"保存帧失败: {e}")